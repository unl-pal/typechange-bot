#!/usr/bin/env python
# coding: utf-8

from .common import app, current_node

from celery.result import ResultSet

from django.db.models import Q
from django.utils import timezone
from datetime import timedelta

from .repos  import delete_repo

from survey.models import Node, Commit, DeletedRepository

__all__ = [
    'vacuum_irrelevant_commits',
    'node_health_check',
    'node_health_response',
    'clean_repos'
]

@app.task()
def vacuum_irrelevant_commits():
    time_created = timezone.now() - timedelta(hours=36)
    Commit.objects.filter(created_at__lt = time_created, is_relevant=False).delete()

@app.task()
def node_health_check():
    results = []
    for node in Node.objects.filter(enabled=True):
        results.append(node_health_response.apply_async([], queue=node.hostname))

    while not all(result.ready() for result in results):
        pass

    check_time = timezone.now() - timedelta(hours=2)
    for node in Node.objects.filter(enabled=True, last_active__lte=check_time):
        node.enabled = False
        node.save()

@app.task()
def node_health_response():
    current_node.last_active = timezone.now()
    current_node.save()
    return True

@app.task()
def clean_repos():
    week_ago = timezone.now() - timedelta(days=7)
    for repo in DeletedRepository.objects.filter(deleted_on__lt=week_ago):
        delete_repo.apply_async([repo.id], queue=repo.node.hostname)
