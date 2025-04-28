#!/usr/bin/env python
# coding: utf-8

from django.core.management.base import BaseCommand, CommandError
from django.conf import settings

from survey.models import Project, Committer, ProjectCommitter

from github import Github, RateLimitExceededException


from datetime import datetime
from dateutil.relativedelta import relativedelta
import pytz
import time

class Command(BaseCommand):
    help = "Post-Filter Projects"

    language = None
    token = None
    min_stars = 2

    gh = None

    default_backoff = 15
    ex_backoff = default_backoff

    last_wait_finished = datetime.now()
    last_wait_length = -1
    def enforce_rate_limits(self, backoff_in = None):
        self.store_partition_data_file()
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


    def add_argument(self, parser):

        parser.add_argument('language',
                            help="Projects in language to post-filter",
                            choices = [ item[0] for item in Project.ProjectLanguage.choices ])
        parser.add_argument('--token',
                            help='Token used for GitHub API Access (will be taken from GITHUB_API_KEY if set)',
                            default=settings.GITHUB_API_KEY,
                            type=str)

        parseradd_argument('--min-stars',
                           help='Minimum stars',
                           type=int,
                           default=2)

        def handle(self, *args,
                   language=None, token=None, min_stars=None,
                   **options):

            if token is None:
                raise CommandError('A GitHub API key must be provided with either GITHUB_API_KEY or --token.', returncode=2)

            self.language = Project.ProjectLanguage(language)
            self.min_stars = min_stars
            self.token = token

            self.gh = Github(self.token, per_page=1)

            for project in Project.objects.filter(language=self.language):
                print(f'Checking {project}... ', end='')
                gh_proj = self.gh.get_project(str(project))
                if gh_proj.fork or (gh_proj.stargazers_count < self.min_stars):
                    project.track_changes = False
                    project.save()
                    print('Not tracking.')
                else:
                    print('Tracking status unchanged.')

                self.enforce_rate_limits()


    pass
