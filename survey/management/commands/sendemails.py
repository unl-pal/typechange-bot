#!/usr/bin/env python
# coding: utf-8

from django.core.management.base import BaseCommand, CommandError
from django.conf import settings

from survey.tasks import send_maintainer_email
from survey.models import Committer, Project, ProjectCommitter

import time


class Command(BaseCommand):
    help = "Send Emails to Maintainers"

    burst_size = 1

    pause_hours = 0
    pause_minutes = 3
    pause_seconds = 0

    pause_total_seconds = 0

    def add_arguments(self, parser):
        parser.add_argument('--burst-size',
                            help='How many emails to send at once.',
                            type=int,
                            default=1)

        parser.add_argument('--pause-hours',
                            help='Pause N hours between each burst',
                            default=0,
                            type=int,
                            metavar='N')
        parser.add_argument('--pause-minutes',
                            help='Pause N minutes between each burst',
                            default=3,
                            type=int,
                            metavar='N')
        parser.add_argument('--pause-seconds',
                            help='Pause N seconds between each burst',
                            default=0,
                            type=int,
                            metavar='N')

        parser.add_argument('--dry-run',
                            default=False,
                            action='store_true',
                            help='When passed, do not send emails, just show the first burst.')

        pass

    def handle(self, *args,
               burst_size=1,
               dry_run=False,
               pause_hours=0, pause_minutes=3, pause_seconds=0,
               **options):

        self.burst_size = burst_size
        self.pause_hours = pause_hours
        self.pause_minutes = pause_minutes
        self.pause_seconds = pause_seconds

        self.pause_total_seconds = self.pause_seconds + 60 * (self.pause_minutes + 60 * self.pause_hours)

        while Committer.objects.filter(email_address__isnull=False, has_been_emailed=False).count() > 0:
            for committer in Committer.objects.filter(email_address__isnull=False, has_been_emailed=False)[:self.burst_size]:
                print(f'Sending to committer {committer}')
                if not dry_run:
                    send_maintainer_email.delay(committer.id)

            if dry_run:
                break

            print(f'Pausing {self.pause_hours:02d}:{self.pause_minutes:02d}:{self.pause_seconds:02d}')
            time.sleep(self.pause_total_seconds)
