#!/usr/bin/env python
# coding: utf-8

from django.core.management.base import BaseCommand, CommandError
from django.conf import settings

from survey.tasks import send_maintainer_email
from survey.models import Committer, Project, ProjectCommitter, Node

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

        parser.add_argument('--queue',
                            help='Send mail via specific queue.',
                            choices=[ node.hostname for node in Node.objects.all()] )

        pass

    def handle(self, *args,
               burst_size=1,
               dry_run=False,
               pause_hours=0, pause_minutes=3, pause_seconds=0,
               queue=None,
               **options):

        self.burst_size = burst_size
        self.pause_hours = pause_hours
        self.pause_minutes = pause_minutes
        self.pause_seconds = pause_seconds

        self.pause_total_seconds = self.pause_seconds + 60 * (self.pause_minutes + 60 * self.pause_hours)

        remaining = Committer.objects.filter(email_address__isnull=False, has_been_emailed=False).count()

        while remaining > 0:
            for committer in Committer.objects.filter(email_address__isnull=False, has_been_emailed=False)[:self.burst_size]:
                print(f'Sending to committer {committer}')
                maintained_tracked_projects = committer.projectcommitter_set.filter(is_maintainer=True, project__track_changes=True).count()
                if not dry_run:
                    if maintained_tracked_projects == 0:
                        print(f"Committer {committer.username} has no trackable projects.")
                        committer.has_been_emailed = True
                        committer.save()
                        continue

                    if queue is not None:
                        send_maintainer_email.apply_async([committer.id], queue=queue)
                    else:
                        send_maintainer_email.delay(committer.id)

            if dry_run:
                break

            remaining = Committer.objects.filter(email_address__isnull=False, has_been_emailed=False).count()
            if remaining == 0:
                break

            print(f'Pausing {self.pause_hours:02d}:{self.pause_minutes:02d}:{self.pause_seconds:02d} ({remaining} remaining)')
            time.sleep(self.pause_total_seconds)
