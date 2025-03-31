#!/usr/bin/env python
# coding: utf-8

from typechangesapp.celery import app

from celery.utils.log import get_task_logger
celery_logger = get_task_logger(__name__)

from survey.models import Node

import socket
current_host = socket.gethostname()

try:
    current_node = Node.objects.get(hostname=current_host)
except Node.DoesNotExist:
    current_node = Node(hostname = current_host)
    current_node.save()

current_node.enabled = True
current_node.save()


__all__ = [
    'app',
    'current_host',
    'celery_logger',
    'current_node'
]
