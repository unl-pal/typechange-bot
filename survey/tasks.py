#!/usr/bin/env python
# coding: utf-8

from typechangesapp.celery import app

from celery.utils.log import get_task_logger
celery_logger = get_task_logger(__name__)

from django.db.models import Q
from .models import Committer, Commit, Project

from django.conf import settings
from django.utils import timezone
from django.template import loader

from github import Github, Auth
import re

auth = Auth.Token(settings.GITHUB_AUTH)
g = Github(auth=auth)

consent_command = re.compile(f'{settings.GITHUB_NAME}\\sconsent', re.IGNORECASE)
optout_command = re.compile(f'{settings.GITHUB_NAME}\\soptout', re.IGNORECASE)

@app.task(ignore_result = True)
def process_push_data(owner, repo, commits):
    project = Project.objects.get(Q(owner=owner) & Q(name=repo))

    for commit_data in commits:
        commit = Commit(project=project,
                        hash=commit_data['id'],
                        message=commit_data['message'],
                        diff = '\n'.join(commit_data['modified']))
        process_commit.delay_on_commit(commit.pk)
        commit.save()

@app.task()
def process_commit(commit_pk):
    commit = Commit.objects.get(id=commit_pk)
    hash = commit.hash
    gh_commit = g.get_repo(f'{commit.project.owner}/{commit.project.name}') \
        .get_commit(sha=hash)

    commit_is_relevant = True     # TODO: Check if commit is relevant
    if commit_is_relevant:
        try:
            author = Committer.objects.get(username=gh_commit.author.login)
        except Committer.DoesNotExist:
            author = Committer(username=gh_commit.author.login)
            process_new_committer.delay(author.pk, commit_pk)
            author.save()

        try:
            committer = Committer.objects.get(username=gh_commit.committer.login)
        except Committer.DoesNotExist:
            committer = Committer(username=gh_commit.committer.login)
            committer.save()
            process_new_committer.delay(committer.pk, commit_pk)

    else:
        commit.is_relevant = False
        commit.save()

@app.task()
def process_new_committer(committer_pk, commit_pk):
    committer = Committer.objects.get(id=committer_pk)
    commit = Commit.objects.get(id=commit_pk)
    gh_commit = g.get_repo(f'{commit.project.owner}/{commit.project.name}') \
        .get_commit(sha=commit.hash)

    template = loader.get_template('informed-consent-message.md')
    message = template.render({'USER': f'@{committer.username}'})
    gh_commit.create_comment(message)


@app.task()
def process_comment(comment_user, comment_body, comment_payload):
    # TODO: Check if we're on a commit we're interested in...
    commit_id = comment_payload['commit_id']
    if Commit.objects.filter(hash=commit_id).count() == 1:
        commenter_new = False
        try:
            committer = Committer.objects.get(Q(username=comment_user))
        except Committer.DoesNotExist:
            committer = Committer(username = comment_user)
            committer.save()
            commenter_new = True

        if consent_command.search(comment_body):
            committer.consent_timestamp = timezone.now()
            if committer.opt_out and committer.opt_out < committer.consent_timestamp:
                committer.opt_out = None
            committer.save()
            commenter_new = False

        if optout_command.search(comment_body):
            committer.opt_out = timezone.now()
            committer.save()
            commenter_new = False
