#!/usr/bin/env python
# coding: utf-8

from typechangesapp.celery import app

from celery.utils.log import get_task_logger
celery_logger = get_task_logger(__name__)

from django.db import transaction

from django.db.models import Q
from django.db.utils import IntegrityError
from .models import Committer, Commit, Project, ProjectCommitter, Response, Node
from .utils import *

from django.conf import settings
from django.utils import timezone
from django.template import loader

from git import Repo
from pathlib import Path

import re

consent_command: re.Pattern = re.compile(f'@{settings.GITHUB_APP_NAME}(\\[bot\\])?\\sconsent', re.IGNORECASE)
optout_command = re.compile(f'@{settings.GITHUB_APP_NAME}(\\[bot\\])?\\soptout', re.IGNORECASE)
remove_command = re.compile(f'@{settings.GITHUB_APP_NAME}(\\[bot\\])?\\sremove', re.IGNORECASE)

import socket
current_host = socket.gethostname()

try:
    current_node = Node.objects.get(hostname=current_host)
except Node.DoesNotExist:
    current_node = Node(hostname = current_host)
    current_node.save()

@app.task()
def clone_repo(project_id):
    project = Project.objects.get(id=project_id)
    local_path = project.path
    local_path.parent.mkdir(exist_ok=True, parents=True)
    repo = Repo.clone_from(project.clone_url, local_path)
    project.host_node = current_node
    project.typechecker_files = get_typechecker_configuration(repo, project.primary_language)
    project.save()

@app.task()
def process_installation(payload):
    repositories = payload['repositories']

    match payload['action']:
        case 'created':
            installation_id = payload['installation']['id']
            for repo in repositories:
                owner, name = repo['full_name'].split('/')
                install_repo.delay(owner, repo, installation_id)
        case 'deleted':
            for repo in repositories:
                owner, name = repo['full_name'].split('/')
                if Project.objects.filter(owner=owner, name=name).count() > 0:
                    for project in Project.objects.filter(owner=owner, name=name):
                        project.installation_id = None
                        project.remove_date = timezone.now()
                        project.track_changes = False
                        project.save()
        case 'suspend':
            # TODO: Handle Suspensions
            pass
        case 'unsuspend':
            # TODO: Handle Unsuspensions
            pass

@app.task()
def process_installation_repositories(payload):
    match payload['action']:
        case 'added':
            installation_id = payload['installation']['id']
            for repo in payload['repositories_added']:
                owner, name = repo['full_name'].split('/')
                install_repo.delay(owner, repo, installation_id)
        case 'removed':
            for repo in payload['repositories_removed']:
                owner, name = repo['full_name'].split('/')
                if Project.objects.filter(owner=owner, name=name).count() > 0:
                    for project in Project.objects.filter(owner=owner, name=name):
                        project.installation_id = None
                        project.remove_date = timezone.now()
                        project.track_changes = False
                        project.save()

@app.task()
def process_repository(payload):
    match payload['action']:
        case "archived" | "deleted":
            owner, name = payload['repository']['full_name'].split('/')
            try:
                repo = Project.objects.get(Q(owner=owner) & Q(name=name))
            except:
                return
            repo.track_changes = False
            repo.save()
        case "renamed":
            old_owner, old_name = payload['changes']['repository']['name']['frome'].split('/')
            new_owner, new_name = payload['repository']['full_name'].split('/')
            project = Project.objects.get(Q(owner=old_owner), Q(name=old_name))
            rename_repo.apply_async([old_owner, old_name, new_owner, new_name], queue=project.host_node.host_name)

@app.task()
def rename_repo(old_owner, old_name, new_owner, new_name):
    project = Project.objects.get(Q(owner=old_owner), Q(name=old_name))
    # TODO: Delete old repo?  Move old repo?
    project.owner = new_owner
    project.name = new_name
    project.save()
    project.path.parent.mkdir(exist_ok=True, parents=True)
    Repo.clone_from(project.clone_url, project.path)

@app.task()
def install_repo(owner: str, repo: str, installation_id: str):
    try:
        project = Project.objects.get(Q(owner=owner) & Q(name=repo))
        project.installation_id = installation_id
    except Project.DoesNotExist:
        project = Project(owner=owner, name=repo, installation_id=installation_id)

    project.remove_date = None

    project.primary_language = project.gh.language
    if project.primary_language in ['TypeScript', 'Python', 'PHP', 'R']:
        project.track_changes = True

    project.save()

    if project.track_changes:
        if project.host_node is None:
            clone_repo.delay(project.id)
        else:
            fetch_project.apply_async([project.id], queue=project.host_node.hostname)

@app.task(ignore_result = True)
def fetch_project(project_id: int):
    project = Project.objects.get(id=project_id)
    repo = Repo(project.path)
    repo.remote().fetch()

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

    if project.committers.filter(username=commit.gh.author.login).count() == 0:
        try:
            author = Committer.objects.get(username=commit.gh.author.login)
        except Committer.DoesNotExist:
            author = Committer(username=commit.gh.author.login)
            author.save()

        new_author = True
        project.committers.add(author, through_defaults={'initial_commit': commit})
        project.save()
        process_new_committer.delay(author.pk, commit_pk)
        process_new_link.delay(author.pk, project.pk)

    if project.committers.filter(username=commit.gh.committer.login).count() == 0:
        try:
            committer = Committer.objects.get(commit.gh.committer.login)
        except Committer.DoesNotExist:
            committer = Committer(username=commit.gh.committer.login)
            committer.save()

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

        if not new_author and Committer.objects.get(username=commit.gh.author.login).should_contact():
            notify_who.append(commit.gh.author.login)

        if not new_committer and commit.gh.committer.login != commit.gh.author.login and Committer.objects.get(username=commit.gh.committer.login).should_contact():
            notify_who.append(commit.gh.committer.login)

        if len(notify_who) > 0:
            file, line, is_added = commit_is_relevant[0]
            survey_template = loader.get_template('survey.md')
            template_data = {
                'USER': ', '.join(list(f'@{login}' for login in notify_who[::-1])),
                'ADDED': ('added' if is_added else 'removed')
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
        print(comment_body)
        committer.consent_timestamp = timezone.now()
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
        template = loader.get_template('acknowledgment.md')
        commit.gh.create_comment(template.render({'BOT_NAME': settings.GITHUB_APP_NAME}))
