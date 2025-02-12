#!/usr/bin/env python
# coding: utf-8

from typechangesapp.celery import app

from celery.utils.log import get_task_logger
celery_logger = get_task_logger(__name__)
from celery.result import ResultSet

from django.db.models import Q
from django.utils import timezone
from datetime import timedelta

from .models import Node, Commit

import socket
current_host = socket.gethostname()

try:
    current_node = Node.objects.get(hostname=current_host)
except Node.DoesNotExist:
    current_node = Node(hostname = current_host)
    current_node.save()

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
