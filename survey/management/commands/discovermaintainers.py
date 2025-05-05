#!/usr/bin/env python
# coding: utf-8

from typing import List, Tuple

import pandas as pd

from django.core.management.base import BaseCommand, CommandError
from django.db.models import Count
from django.conf import settings

from github import Github, RateLimitExceededException, UnknownObjectException
from survey.models import Project, Committer, ProjectCommitter

from datetime import datetime
from dateutil.relativedelta import relativedelta
import pytz
import time

class Command(BaseCommand):
    help = "Discover GitHub Project Maintainers"

    token = None

    default_backoff = 15
    ex_backoff = default_backoff

    gh = None

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

        if backoff_in is not None:
            print(f'Hit rate limit: sleeping for {self.last_wait_length} seconds (in {backoff_in}).')
        else:
            print(f'Hit rate limit: sleeping for {self.last_wait_length} seconds.')
        time.sleep(self.last_wait_length)
        self.last_wait_finished = datetime.now()

    def collect_maintainers(self, repo):
        stats = None
        try:
            stats = repo.get_stats_contributors()
            login = []
            people = []
            totals = []

            for s in stats:
                weeks = [ week for week in s.weeks if week.w >= self.START_DATE ]
                total = sum([ week.c for week in weeks ])

                if total > 0:
                    if s.author is not None:
                        login.append(s.author.login)
                        people.append(s.author)
                        totals.append(total)

            df = pd.DataFrame(zip(login, people, totals), columns = ['login', 'stats', 'contributions'])
            df = df[~df['login'].str.contains('\\[bot\\]')]
            cutoff = df['contributions'].mean() + 1.5 * df['contributions'].std()

            maintainer_logins = df[df['contributions'] >= cutoff]['login'].to_list()

            if len(maintainer_logins) > 0:
                return maintainer_logins
            else:
                return df.sort_values('contributions', ascending=False)['login'].to_list()[:2]

        except RateLimitExceededException:
            self.enforce_rate_limits('collect_maintainers')
            return self.collect_maintainers(repo)
        except TypeError:
            return []

    def get_email(self, login):
        try:
            user = self.gh.get_user(login)
            if user and user.email:
                return (user.email, user.name)
            else:
                return (None, None)
        except RateLimitExceededException:
            self.enforce_rate_limits('get_email')
            return self.get_email(login)

    def add_arguments(self, parser):
        parser.add_argument('--token',
                            help='Token used for GitHub API Access (will be taken from GITHUB_API_KEY if set)',
                            default=settings.GITHUB_API_KEY,
                            type=str)

    def handle(self, *args,
               token=None,
               **options):

        if token is None:
            raise CommandError('A GitHub API key must be provided with either GITHUB_API_KEY or --token.', returncode=2)

        self.token = token

        self.gh = Github(self.token, per_page=1)

        prc = Project.objects.all().annotate(maintainer_count=Count('committers'))

        for project in prc.filter(maintainer_count=0):
            print(f'Processing {project}')
            try:
                gh_proj = self.gh.get_repo(str(project))
                for maintainer in self.collect_maintainers(gh_proj):
                    print(f'Processing maintainer {maintainer}')
                    try:
                        committer = Committer.objects.get(username=maintainer)
                    except Committer.DoesNotExist:
                        email, name = self.get_email(maintainer)
                        committer = Committer(username = maintainer,
                                              name=name,
                                              email_address=email)
                        committer.save()
                    project_committer = ProjectCommitter(project=project, committer=committer, is_maintainer=True)
                    project_committer.save()
            except UnknownObjectException:
                project.delete()
                print('Project deleted on GitHub.')
            except KeyboardInterrupt as ex:
                raise ex
            except:
                pass
            self.enforce_rate_limits()
