#!/usr/bin/env python
# coding: utf-8

from typechangesapp.celery import app

from celery.utils.log import get_task_logger
celery_logger = get_task_logger(__name__)

from django.conf import settings
from django.utils import timezone

@app.task()
def process_commit(commit):
    pass

@app.task()
def process_new_committer(committer_pk):
    pass
