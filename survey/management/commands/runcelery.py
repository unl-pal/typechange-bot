#!/usr/bin/env python
# coding: utf-8

from django.core.management.base import BaseCommand, CommandError
from celery.bin import worker
from socket import gethostname

from typechangesapp import celery_app

class Command(BaseCommand):
    help = 'Run celery worker'

    def handle(self, *args, **options):
        hostname = gethostname()
        queues = f'celery,{hostname}'
        celery_app.worker_main(argv=['worker', '--loglevel=INFO', '-Q', queues])
