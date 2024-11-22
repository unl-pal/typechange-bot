#!/usr/bin/env python
# coding: utf-8

from typechangesapp.celery import app

from celery.utils.log import get_task_logger
celery_logger = get_task_logger(__name__)

from django.db.models import Q
from .models import Committer, Commit, Project

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
        process_commit.delay_on_commit(commit.pk)

@app.task()
def process_commit(commit_pk):
    pass

@app.task()
def process_new_committer(committer_pk):
    pass

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

        if re.search(r'@unlpalbotuseracct consent', comment_body, re.I):
            committer.consent_timestamp = timezone.now()
            if committer.opt_out and committer.opt_out < committer.consent_timestamp:
                committer.opt_out = None
            committer.save()
            commenter_new = False

        if re.search(r'@unlpalbotuseracct optout', comment_body, re.I):
            committer.opt_out = timezone.now()
            committer.save()
            commenter_new = False

        if commenter_new:
            # TODO: Delay this
            process_new_committer.delay(committer.pk, commit_id)
