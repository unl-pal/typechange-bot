#!/usr/bin/env python
# coding: utf-8

from typechangesapp.celery import app

from celery.utils.log import get_task_logger
celery_logger = get_task_logger(__name__)

from django.conf import settings
from django.utils import timezone

@app.task(ignore_result = True)
def process_push_data(owner, repo, commits):
    project = Project.objects.get(Q(owner=owner) & Q(name=repo))

    for commit_data in commits:
        commit = Commit(project=project,
                        hash=commit_data['id'],
                        message=commit_data['message'],
                        diff = '\n'.join(commit_data['modified']))
        commit.save()
        process_commit.delay(commit.pk)

@app.task()
def process_commit(commit_pk):
    pass

@app.task()
def process_new_committer(committer_pk):
    pass
