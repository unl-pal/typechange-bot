#!/usr/bin/env python
# coding: utf-8

import os

from celery import Celery

# Set the default Django settings module for the 'celery' program.
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'typechangesapp.settings')

app = Celery('proj',
             task_cls='celery.contrib.django.task.DjangoTask',
             beat_scheduler='django_celery_beat.schedulers:DatabaseScheduler')

# Using a string here means the worker doesn't have to serialize
# the configuration object to child processes.
# - namespace='CELERY' means all celery-related configuration keys
#   should have a `CELERY_` prefix.
app.config_from_object('django.conf:settings', namespace='CELERY')

# Load task modules from all registered Django apps.
app.autodiscover_tasks()
app.autodiscover_tasks(related_name='periodic_tasks')


@app.task(bind=True, ignore_result=True)
def debug_task(self):
    print(f'Request: {self.request!r}')
