#!/usr/bin/env python
# coding: utf-8

from typechangesapp.celery import app

from celery.utils.log import get_task_logger
celery_logger = get_task_logger(__name__)

from django.db.models import Q
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

