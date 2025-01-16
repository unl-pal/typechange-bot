#!/usr/bin/env python
# coding: utf-8

from typechangesapp.celery import app

from celery.utils.log import get_task_logger
celery_logger = get_task_logger(__name__)

from django.db.models import Q
from django.db.utils import IntegrityError
from .models import Committer, Commit, Project, ProjectCommitter, Response
from .utils import *

from django.conf import settings
from django.utils import timezone
from django.template import loader

from git import Repo
from pathlib import Path

import re

consent_command = re.compile(f'@{settings.GITHUB_APP_NAME}\\sconsent', re.IGNORECASE)
optout_command = re.compile(f'@{settings.GITHUB_APP_NAME}\\soptout', re.IGNORECASE)

import socket
current_host = socket.gethostname()

@app.task()
def clone_repo(project_id):
    project = Project.objects.get(id=project_id)
    local_path = project.path
    local_path.parent.mkdir(exist_ok=True, parents=True)
    repo = Repo.clone_from(str(project), local_path)
    project.repository_host = current_host
    project.typechecker_files = get_typechecker_config(repo, project.primary_language)
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
def install_repo(owner: str, repo: str, installation_id: str):
    try:
        project = Project.objects.get(Q(owner=owner) & Q(name=repo))
        project.installation_id = installation_id
    except Project.DoesNotExist:
        project = Project(owner=owner, name=name, installation_id=installation_id)

    project.remove_date = None

    project.primary_language = project.gh.language
    if project.primary_language in ['TypeScript', 'Python']:
        project.track_changes = True

    project.save()

    if project.track_changes:
        if project.repository_host is None:
            clone_repo.delay(project.id)
        else:
            fetch_project.apply_async([project.id], queue=project.repository_host)

@app.task(ignore_result = True)
def fetch_project(project_id):
    project = Project.objects.get(id=project_id)
    repo = Repo(project.path)
    repo.remote().fetch()

@app.task(ignore_result = True)
def process_push_data(owner, repo, commits):
    project = Project.objects.get(Q(owner=owner) & Q(name=repo))

    if project.track_changes:
        fetch_project.apply_async([project.id], queue=project.repository_host)
        for commit_data in commits:
            try:
                commit = Commit(project=project,
                                hash=commit_data['id'],
                                message=commit_data['message'],
                                diff = '\n'.join(commit_data['modified']))
                commit.save()
            except IntegrityError:
                commit = Commit.objects.get(Q(project=project) & Q(hash=commit_data['id']))
                pass
            process_commit.apply_async([commit.pk], queue=project.repository_host)

@app.task(bind = True, autoretry_for=(ValueError,), retry_backoff=2, max_retries=5)
def process_commit(self, commit_pk: int):
    commit = Commit.objects.get(id=commit_pk)
    project = commit.project

    # TODO: Handle 24 hour thing

    commit_is_relevant = check_commit_is_relevant(Repo(project.path), commit)
    if commit_is_relevant is not None:

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
            # TODO Process new project link...

        if project.committers.filter(username=commit.gh.committer.login).count() == 0:
            try:
                committer = Committer.objects.get(commit.gh.committer.login)
            except Committer.DoesNotExist:
                committer = Committer(username=commit.gh.committer.login)
                committer.save()

            new_committer = True
            projects.committers.add(author, through_defaults={'initial_commit': commit})
            project.save()
            process_new_committer.delay(author.pk, commit_pk)
            # TODO Process new project link...


        commit.is_relevant = True
        commit.author = ProjectCommitter.objects.get(Q(project = commit.project) & Q(committer__username=commit.gh.author.login))
        commit.committer = ProjectCommitter.objects.get(Q(project = commit.project) & Q(committer__username=commit.gh.committer.login))
        commit.save()

        # TODO Process relevant changes
        if not new_author and not new_committer:
            file, line, is_added = commit_is_relevant[0]
            survey_template = loader.get_template('survey.md')
            if is_added:
                commit.gh.create_comment(survey_template.render({'USER': f'@{commit.gh.author.login}', 'ADDED': 'added'}), line = line, path = file)
            else:
                commit.gh.create_comment(survey_template.render({'USER': f'@{commit.gh.author.login}', 'ADDED': 'removed'}), line = line, path = file)

    else:
        commit.is_relevant = False
        commit.save()

@app.task()
def process_new_link(committer_pk: int, project_pk: int):
    pass

@app.task()
def process_new_committer(committer_pk, commit_pk):
    committer = Committer.objects.get(id=committer_pk)
    commit = Commit.objects.get(id=commit_pk)

    template = loader.get_template('informed-consent-message.md')
    message = template.render({'USER': f'@{committer.username}'})
    commit.gh.create_comment(message)


@app.task()
def process_comment(comment_user, comment_body, comment_payload):
    if comment_user.lower() == f'{settings.GITHUB_APP_NAME}[bot]'.lower():
        return
    # TODO: Check if we're on a commit we're interested in...
    commit_id = comment_payload['commit_id']
    if Commit.objects.filter(hash=commit_id).count() == 1:
        commit = Commit.objects.get(hash=commit_id)
        commenter_new = False
        try:
            committer = Committer.objects.get(Q(username=comment_user))
        except Committer.DoesNotExist:
            committer = Committer(username = comment_user)
            committer.save()
            commenter_new = True

        if committer.consent_timestamp:

            if consent_command.search(comment_body):
                committer.consent_timestamp = timezone.now()
                if committer.opt_out and committer.opt_out < committer.consent_timestamp:
                    committer.opt_out = None
                    committer.save()
                    commenter_new = False

                if committer.initial_survey_response is None:
                    template = loader.get_template('initial-survey.md')
                    commit.gh.create_comment(template.render({'USER': f'@{committer.username}'}))

            elif optout_command.search(comment_body):
                committer.opt_out = timezone.now()
                committer.save()
                commenter_new = False
                template = loader.get_template('acknowledgment-optout.md')
                commit.create_comment(template.render())

            elif commit.is_relevant:
                project_committer = ProjectCommitter.objects.get(Q(committer = committer) & Q(project = commit.project))
                response = Response(commit=commit, committer=project_committer, survey_response=comment_body)
                response.save()
