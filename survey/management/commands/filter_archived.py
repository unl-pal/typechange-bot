#!/usr/bin/env python
# coding: utf-8

from django.core.management.base import BaseCommand, CommandError
from django.conf import settings

from survey.models import Project

from github import Github, RateLimitExceededException, UnknownObjectException

from datetime import datetime
from dateutil.relativedelta import relativedelta
import pytz
import time

class Command(BaseCommand):
    help = "Disable tracking for uninstalled, archived or mirrored projects"


    default_backoff = 15
    ex_backoff = default_backoff

    last_wait_finished = datetime.now()
    last_wait_length = -1
    def enforce_rate_limits(self, backoff_in = None):
        rate_limit_reset_time = datetime.fromtimestamp(self.gh.rate_limiting_resettime, tz=pytz.UTC).replace(tzinfo=pytz.UTC)
        time_until_reset = int((rate_limit_reset_time - datetime.now(pytz.UTC)).total_seconds())
        time_since_last_reset = ((datetime.now() - self.last_wait_finished).total_seconds() - 2*self.ex_backoff)
        if datetime.now(pytz.UTC) < datetime.fromtimestamp(self.gh.rate_limiting_resettime, tz=pytz.UTC):
            if backoff_in is not None:
                print(f"Ratelimit requested: not needed (in {backoff_in}).")
            else:
                print("Ratelimit requested: not needed.")
            return
        if time_since_last_reset <= self.last_wait_length:
            if self.ex_backoff > self.default_backoff:
                print("Using exponential backoff for rate-limiting.")
            self.last_wait_length = time_until_reset + self.ex_backoff
            self.ex_backoff *= 2
        else:
            if self.ex_backoff > self.default_backoff:
                self.ex_backoff = self.default_backoff
            self.last_wait_length = time_until_reset + self.default_backoff


    def add_arguments(self, parser):
        parser.add_argument('--token',
                    help='Token used for GitHub API Access (will be taken from GITHUB_API_KEY if set)',
                    default=settings.GITHUB_API_KEY,
                    type=str)

    def handle(self, *args,
               token=None, **options):

        self.gh = Github(token, per_page=1)

        for project in Project.objects.filter(track_changes=True, installation_id__isnull=True):
            print(f'Checking {project}...', end='')
            try:
                gh_proj = self.gh.get_repo(str(project))
                if gh_proj.archived or (gh_proj.mirror_url is not None):
                    project.track_changes = False
                    project.save()
                    print('Mirror or Archive, not tracking.')
                else:
                    print('Tracking status unchanged.')
            except UnknownObjectException:
                project.delete()
                print('Project deleted on GitHub.')
            except KeyboardInterrupt as ex:
                raise ex
            except:
                pass

            self.enforce_rate_limits()

