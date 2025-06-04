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

consent_command: re.Pattern = re.compile(f'^\\s*@{settings.GITHUB_APP_NAME}(\\[bot\\])?\\sconsent', re.IGNORECASE)
optout_command = re.compile(f'^\\s*@{settings.GITHUB_APP_NAME}(\\[bot\\])?\\soptout', re.IGNORECASE)
remove_command = re.compile(f'^\\s*@{settings.GITHUB_APP_NAME}(\\[bot\\])?\\sremove', re.IGNORECASE)

@app.task(ignore_result = True)
def process_push_data(owner, repo, commits):
    project = Project.objects.get(Q(owner=owner) & Q(name=repo))

    if project.track_changes:
        fetch_project(project.id)
        for commit_data in commits:
            try:
                commit = Commit(project=project,
                                hash=commit_data['id'],
                                message=commit_data['message'],
                                diff = '\n'.join(commit_data['modified']))
                commit.save()
            except IntegrityError:
                commit = Commit.objects.get(Q(project=project) & Q(hash=commit_data['id']))
            except:
                continue

            try:
                process_commit(commit.pk)
            except:
                continue

def change_type_to_relevance_type(change_type: ChangeType):
    match change_type:
        case ChangeType.ADDED:
            return Commit.RelevanceType.ADDED
        case ChangeType.REMOVED:
            return Commit.RelevanceType.REMOVED
        case ChangeType.CHANGED:
            return Commit.RelevanceType.CHANGED
        case _:
            return Commit.RelevanceType.CHANGED

@app.task(bind=True, autoretry_for=(ValueError,), retry_backoff=2, max_retries=5)
def post_process_old_commit(self, commit_pk: int):
    commit = Commit.objects.get(id=commit_pk)
    project = commit.project

    if commit.is_relevant and commit.relevance_type == Commit.RelevanceType.IRRELEVANT:
        relevant_file, relevant_line, change_type = check_commit_is_relevant(Repo(project.path), commit)[0]
        commit.relevance_type = change_type_to_relevance_type(change_type)
        commit.relevant_change_file = relevant_file
        commit.relevant_change_line = relevant_line
        commit.save()

@app.task(bind = True, autoretry_for=(ValueError,), retry_backoff=2, max_retries=5)
def process_commit(self, commit_pk: int):
    commit = Commit.objects.get(id=commit_pk)
    project = commit.project

    commit_is_relevant = check_commit_is_relevant(Repo(project.path), commit)
    if commit_is_relevant is None:
        commit.is_relevant = False
        commit.save()
        return
    relevant_file, relevant_line, change_type = commit_is_relevant[0]
    commit.json_data = commit.gh.raw_data
    commit.relevance_type = change_type_to_relevance_type(change_type)
    commit.relevant_change_file = relevant_file
    commit.relevant_change_line = relevant_line
    commit.is_relevant = True
    commit.save()

    new_author = False
    new_committer = False

    maintainers_list = None

    for i, cmtr in enumerate([commit.gh.author, commit.gh.committer]):
        try:
            committer = Committer.objects.get(username=cmtr.login)
        except Committer.DoesNotExist:
            committer = Committer(username = cmtr.login,
                                  name = cmtr.name,
                                  email_address = cmtr.email)
            committer.save()

            if i == 0:
                new_author = True
            else:
                new_committer = True

        if project.committers.filter(username=cmtr.login).count == 0:
            if maintainers_list == None:
                maintainers_list = collect_repo_maintainers(project.gh, project.gh_app)['login'].to_list()
            project.committers.add(committer,
                                   through_defaults={'initial_commit': commit,
                                                     'is_maintainer': (True if cmtr.login in maintainers_list else False)})
            project.save()

        if committer.initial_contact_location is None:
            process_new_committer(committer.pk, commit_pk)

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
def process_new_committer(committer_pk: int, commit_pk: int):
    committer = Committer.objects.get(id=committer_pk)
    commit = Commit.objects.get(id=commit_pk)

    if committer.initial_contact_location is None:
        committer.initial_contact_location = commit.public_url
        committer.save()

    template = loader.get_template('informed-consent-message.md')
    message = template.render({'USER': f'@{committer.username}', 'BOT_NAME': settings.GITHUB_APP_NAME })
    commit.gh.create_comment(message)

def send_error(committer, commands_sent, commit, owner, name):
    commit_gh = get_comment_gh(commit, owner, name)
    template = loader.get_template('command-error.md')
    message = template.render({'USER': f'@{committer}',
                               'BOT_NAME': settings.GITHUB_APP_NAME,
                               'COMMANDS': ', '.join(f'@{settings.GITHUB_APP_NAME}[bot] {cmd}' for cmd in commands_sent)})
    commit_gh.create_comment(message)

@app.task()
def process_comment(comment_user: str, comment_body: str, repo_owner: str, repo_name: str, comment_payload: dict):
    if comment_user.lower() == f'{settings.GITHUB_APP_NAME}[bot]'.lower():
        return

    try:
        committer = Committer.objects.get(username = comment_user)
    except:
        return

    request_removal = remove_command.search(comment_body)
    request_optout = optout_command.search(comment_body)
    consented = consent_command.search(comment_body)

    if request_removal and request_optout and consented:
        send_error(comment_user, ['CONSENT', 'OPTOUT', 'REMOVE'], comment_payload['commit_id'], repo_owner, repo_name)
        return
    if request_removal and request_optout:
        send_error(comment_user, ['OPTOUT', 'REMOVE'], comment_payload['commit_id'], repo_owner, repo_name)
        return
    if request_removal and consented:
        send_error(comment_user, ['CONSENT', 'REMOVE'], comment_payload['commit_id'], repo_owner, repo_name)
        return
    if request_optout and consented:
        send_error(comment_user, ['CONSENT', 'OPTOUT'], comment_payload['commit_id'], repo_owner, repo_name)
        return


    if request_removal:
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

    if request_optout:
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

    if consented:
        committer.consent_timestamp = timezone.now()
        committer.consent_project_commit = f"{commit.project.owner}/{commit.project.name}/{commit_id}"
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

        # for comment in commit.gh.get_comments():
        #     if comment.id == comment_payload['id']:
        #         comment.create_reaction('+1')

        # template = loader.get_template('acknowledgment.md')
        # commit.gh.create_comment(template.render({'BOT_NAME': settings.GITHUB_APP_NAME}))
