#!/usr/bin/env python
# coding: utf-8

from django.core.management.base import BaseCommand, CommandError
from celery.bin import worker

from typechangesapp import celery_app

class Command(BaseCommand):
    help = 'Run celery worker'

    def handle(self, *args, **options):
        celery_app.worker_main(argv=['worker', '--loglevel=INFO', '--beat'])
