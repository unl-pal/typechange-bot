#!/usr/bin/env python
# coding: utf-8

from .common import app, current_node
from .repos import fetch_project

from django.db import transaction

from django.db.models import Q
from django.db.utils import IntegrityError
from survey.models import Committer, Commit, Project, ProjectCommitter, Response, Node
from survey.utils import *
from survey.project_mining_utils import collect_repo_maintainers

from django.conf import settings
from django.utils import timezone
from django.template import loader

from datetime import timedelta

from git import Repo
from pathlib import Path

import re

consent_command: re.Pattern = re.compile(f'@{settings.GITHUB_APP_NAME}(\\[bot\\])?\\sconsent', re.IGNORECASE)
optout_command = re.compile(f'@{settings.GITHUB_APP_NAME}(\\[bot\\])?\\soptout', re.IGNORECASE)
remove_command = re.compile(f'@{settings.GITHUB_APP_NAME}(\\[bot\\])?\\sremove', re.IGNORECASE)

@app.task(ignore_result = True)
def process_push_data(owner, repo, commits):
    project = Project.objects.get(Q(owner=owner) & Q(name=repo))

    if project.track_changes:
        fetch_project.apply_async([project.id], queue=project.host_node.hostname)
        for commit_data in commits:
            try:
                commit = Commit(project=project,
                                hash=commit_data['id'],
                                message=commit_data['message'],
                                diff = '\n'.join(commit_data['modified']))
                commit.save()
            except IntegrityError:
                commit = Commit.objects.get(Q(project=project) & Q(hash=commit_data['id']))

            process_commit.apply_async([commit.pk], queue=project.host_node.hostname)

@app.task(bind = True, autoretry_for=(ValueError,), retry_backoff=2, max_retries=5)
def process_commit(self, commit_pk: int):
    commit = Commit.objects.get(id=commit_pk)
    project = commit.project

    commit_is_relevant = check_commit_is_relevant(Repo(project.path), commit)
    if commit_is_relevant is None:
        commit.is_relevant = False
        commit.save()
        return

    new_author = False
    new_committer = False

    maintainers_list = None

    if project.committers.filter(username=commit.gh.author.login).count() == 0:
        try:
            author = Committer.objects.get(username=commit.gh.author.login)
        except Committer.DoesNotExist:
            author = Committer(username=commit.gh.author.login)
            author.save()

        if maintainers_list == None:
            maintainers_list = collect_repo_maintainers(project.gh, project.gh_app)['login'].to_list()

        is_maintainer = commit.gh.author.login in maintainers_list

        new_author = True
        project.committers.add(author, through_defaults={'initial_commit': commit, 'is_maintainer': is_maintainer})
        project.save()
        process_new_committer.delay(author.pk, commit_pk)
        process_new_link.delay(author.pk, project.pk)

    if project.committers.filter(username=commit.gh.committer.login).count() == 0:
        try:
            committer = Committer.objects.get(commit.gh.committer.login)
        except Committer.DoesNotExist:
            committer = Committer(username=commit.gh.committer.login)
            committer.save()

        if maintainers_list == None:
            maintainers_list = collect_repo_maintainers(project.gh, project.gh_app)['login'].to_list()

        is_maintainer = commit.gh.committer.login in maintainers_list

        new_committer = True
        project.committers.add(committer, through_defaults={'initial_commit': commit})
        project.save()
        process_new_committer.delay(committer.pk, commit_pk)
        process_new_link.delay(committer.pk, project.pk)

    commit.is_relevant = True
    commit.author = ProjectCommitter.objects.get(Q(project = commit.project) & Q(committer__username=commit.gh.author.login))
    commit.committer = ProjectCommitter.objects.get(Q(project = commit.project) & Q(committer__username=commit.gh.committer.login))
    commit.save()

    with transaction.atomic():
        notify_who = []

        if not new_author and Committer.objects.get(username=commit.gh.author.login).should_contact:
            notify_who.append(commit.gh.author.login)

        if not new_committer and commit.gh.committer.login != commit.gh.author.login and Committer.objects.get(username=commit.gh.committer.login).should_contact:
            notify_who.append(commit.gh.committer.login)

        if len(notify_who) > 0:
            file, line, change_type = commit_is_relevant[0]
            survey_template = loader.get_template('survey.md')
            template_data = {
                'BOT_NAME': settings.GITHUB_APP_NAME,
                'USER': ', '.join(list(f'@{login}' for login in notify_who[::-1])),
                'ADDED': change_type.value
            }
            commit.gh.create_comment(survey_template.render(template_data), position = line, path = file)
            for username in notify_who:
                user = Committer.objects.get(username=username)
                user.last_contact_date = timezone.now()
                user.save()


@app.task()
def process_new_link(committer_pk: int, project_pk: int):
    # TODO Write code to process new committer/project links
    pass

@app.task()
def process_new_committer(committer_pk: int, commit_pk: int):
    committer = Committer.objects.get(id=committer_pk)
    commit = Commit.objects.get(id=commit_pk)

    template = loader.get_template('informed-consent-message.md')
    message = template.render({'USER': f'@{committer.username}', 'BOT_NAME': settings.GITHUB_APP_NAME })
    commit.gh.create_comment(message)


@app.task()
def process_comment(comment_user: str, comment_body: str, repo_owner: str, repo_name: str, comment_payload: dict):
    if comment_user.lower() == f'{settings.GITHUB_APP_NAME}[bot]'.lower():
        return

    try:
        committer = Committer.objects.get(username = comment_user)
    except:
        return

    if remove_command.search(comment_body):
        with transaction.atomic():
            committer.opt_out = timezone.now()
            committer.removal = timezone.now()
            committer.initial_survey_response = None
            for project_committer in ProjectCommitter.objects.filter(Q(committer=committer)):
                Response.objects.filter(Q(committer=project_committer)).delete()
                project_committer.delete()
            committer.save()
        commit_gh = get_comment_gh(comment_payload['commit_id'], repo_owner, repo_name)
        template = loader.get_template('acknowledgment-removal.md')
        commit_gh.create_comment(template.render({'USER': f'@{comment_user}', 'BOT_NAME': settings.GITHUB_APP_NAME}))
        return

    if optout_command.search(comment_body):
        committer.opt_out = timezone.now()
        committer.save()
        commenter_new = False
        commit_gh = get_comment_gh(comment_payload['commit_id'], repo_owner, repo_name)
        template = loader.get_template('acknowledgment-optout.md')
        commit_gh.create_comment(template.render({'USER': f'@{comment_user}', 'BOT_NAME': settings.GITHUB_APP_NAME}))
        return

    commit_id = comment_payload['commit_id']
    commit = None
    try:
        commit = Commit.objects.get(hash=commit_id)
    except:
        return


    if not commit.is_relevant:
        return

    if consent_command.search(comment_body):
        committer.consent_timestamp = timezone.now()
        committer.consent_project_commit = f"{commit.project.owner}/{commit.project.repo}/{commit_id}"
        committer.opt_out = None
        committer.removal = None

        committer.save()
        commenter_new = False

        if committer.initial_survey_response is None:
            template = loader.get_template('initial-survey.md')
            commit.gh.create_comment(template.render({'USER': f'@{committer.username}', 'BOT_NAME': settings.GITHUB_APP_NAME}))

    elif committer.consent_timestamp is not None:
        project_committer = ProjectCommitter.objects.get(Q(committer = committer) & Q(project = commit.project))
        if project_committer.initial_commit == commit and committer.initial_survey_response is None and not project_committer.is_maintainer:
            committer.initial_survey_response = comment_body
            committer.save()
            process_commit.apply_async([commit.id], queue=project_committer.project.host_node.hostname)
        elif project_committer.initial_commit == commit and committer.initial_survey_response is None and project_committer.is_maintainer:
            committer.initial_survey_response = comment_body
            committer.save()
            project_committer.maintainer_survey_response = comment_body
            project_committer.save()
            process_commit.apply_async([commit.id], queue=project_committer.project.host_node.hostname)
        elif project_committer.is_maintainer and project_committer.initial_commit == commit:
            project_committer.maintainer_survey_response = comment_body
            project_committer.save()
            process_commit.apply_async([commit.id], queue=project_committer.project.host_node.hostname)
        elif Response.objects.filter(Q(commit=commit) & Q(committer=project_committer)).count() == 0:
            response = Response(commit=commit, committer=project_committer, survey_response=comment_body)
            response.save()
            committer.save()

        for comment in commit.gh.get_comments():
            if comment.id == comment_payload['id']:
                comment.create_reaction('+1')

        # template = loader.get_template('acknowledgment.md')
        # commit.gh.create_comment(template.render({'BOT_NAME': settings.GITHUB_APP_NAME}))
