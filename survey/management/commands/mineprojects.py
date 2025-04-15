#!/usr/bin/env python
# coding: utf-8

from typing import List, Tuple

import pandas as pd

from django.core.management.base import BaseCommand, CommandError
from django.conf import settings

from github import Github, RateLimitExceededException
from survey.utils import get_typechecker_configuration, has_annotations
from survey.models import Project, Committer, ProjectCommitter
from survey.tasks import prescreen_project

from datetime import datetime
from dateutil.relativedelta import relativedelta
import pytz
import time

import git
from tempfile import TemporaryDirectory
from pathlib import Path

import json

class Command(BaseCommand):
    help = "Mine GitHub Projects"

    language = None
    token = None
    destination = None

    min_contributors = 1
    min_contributions = (7, 1)

    min_stars = 2

    START_DATE = (datetime.now() - relativedelta(months=7)).replace(tzinfo=pytz.UTC)
    END_DATE = datetime.now(pytz.UTC)

    start_values: List[datetime] = []
    period_counts: List[int] = []

    # Search Options, Backoff, Rate Limit
    default_backoff = 15
    ex_backoff = default_backoff

    gh = None

    results = None
    page_num = 0

    partition_data_file = None

    current_partition = 0

    def store_partition_data_file(self):
        if self.partition_data_file is not None:
            partition_data_dict = {
                'start_values': list( start_value.isoformat() for start_value in self.start_values ),
                'period_counts': self.period_counts,
                'start_date': self.START_DATE.isoformat(),
                'end_date': self.END_DATE.isoformat(),
                'partitions': list( partition.isoformat() for partition in self.partition ),
                'current_partition': self.current_partition
            }
            with open(self.partition_data_file, 'w+') as fh:
                print(f'Storing partition data file in {self.partition_data_file}')
                json.dump(partition_data_dict, fh, indent=4)

    def read_partition_data_file(self):
        if self.partition_data_file is not None and self.partition_data_file.exists():
            try:
                print(f'Attempting to read partition data from {self.partition_data_file}... ', end='')
                with open(self.partition_data_file, 'r') as fh:
                    partition_data_dict = json.load(fh)
                self.start_values = list(datetime.fromisoformat(date) for date in partition_data_dict['start_values'])
                self.period_counts = partition_data_dict['period_counts']
                self.end_values = partition_data_dict['start_values']
                self.START_DATE = datetime.fromisoformat(partition_data_dict['start_date'])
                self.END_DATE = datetime.fromisoformat(partition_data_dict['end_date'])
                self.partitions = list(datetime.fromisoformat(date) for date in partition_data_dict['partitions'])[partition_data_dict['current_partition']:]
                print('Done!')
                return True
            except:
                raise CommandError(f'JSON Partition File {self.partition_data_file} is invalid.')
        else:
            return False

    def probe_date_values(self):
        current = self.START_DATE
        last = None
        while last is None or last < self.END_DATE:
            self.start_values.append(current)
            self.period_counts.append(self.get_counts_for_category(current, desc=False))
            self.store_partition_data_file()

            last = current
            current = current + relativedelta(weeks=1)

    counts_memo: dict = {}
    def get_counts_for_category(self, min_val, max_val = None, desc = True):
        if isinstance(min_val, datetime):
            min_val = min_val.isoformat()
            if max_val is not None:
                max_val = max_val.isoformat()

        if (min_val, max_val) in self.counts_memo:
            return self.counts_memo[(min_val, max_val)]

        try:
            if max_val is not None and min_val != max_val:
                val = f'pushed:{min_val}..{max_val}'
            elif desc:
                val = f'pushed:>{min_val}'
            else:
                val = f'pushed:<{min_val}'

            # self.wait_limit()
            query = f'language:{self.language.label} {val}'
            print(f'{query!r} - ', end='')
            results = self.gh.search_repositories(query)
            results.get_page(0)

            self.counts_memo[(min_val, max_val)] = results.totalCount
            print(results.total_count)

            return results.totalCount
        except KeyboardInterrupt as ex:
            self.store_partition_data_file()
            raise ex
        except:
            self.wait_limit()
            return self.get_counts_for_category(min_val, max_val, desc)

    def collect_maintainers(self, repo):
        stats = None
        while True:
            try:
                stats = repo.get_stats_contributors()
                break
            except RateLimitExceededException:
                self.wait_limit()

        login = []
        people = []
        totals = []

        for s in stats:
            weeks = [ week for week in s.weeks if week.w >= (datetime.now(week.w.tzinfo) + relativedelta(months=-6)) ]
            total = sum([ week.c for week in weeks ])

            if total > 0:
                login.append(s.author.login)
                people.append(s.author)
                totals.append(total)
        df = pd.DataFrame(zip(login, people, totals), columns = ['login', 'stats', 'contributions'])
        df = df[~df['login'].str.contains('\\[bot\\]')]
        cutoff = df['contributions'].mean() + 1.5 * df['contributions'].std()

        def get_email(login):
            while True:
                try:
                    user = self.gh.get_user(login)
                    if user and user.email:
                        return (user.email, user.name)
                    else:
                        return None
                except RateLimitExceededException:
                    self.wait_limit()

        df2 = df[df['contributions'] >= cutoff] \
            .assign(email_and_name = lambda df: df.login.apply(get_email)) \
            .dropna(axis=0) \
            .assign(email = lambda df: df.email_and_name.apply(lambda x: x[0]),
                    name = lambda df: df.email_and_name.apply(lambda x: x[1]),
                    project = lambda df: repo.full_name) \
            .reset_index() \
            [['login', 'name', 'email']]

        return df2

    def check_contribution(self, id):
        try:
            repo = self.gh.get_repository(id)
            return repo.get_stats_participation().all[-(self.min_contributions[1] * 28):] >= self.min_contributions[0]
        except RateLimitExceededException:
            self.wait_limit()
            return self.check_contribution(id)

    def process_partition(self, start, end):
        try:
            if isinstance(start, datetime):
                start = start.isoformat()
                if end is not None:
                    end = end.isoformat()

            if end is not None and start != end:
                val = f'pushed:{start}..{end}'
            else:
                val = f'pushed:>={start}'

            results = self.gh.search_repositories(f'language:{self.language.label} {val}')
            results.get_page(0)

            self.wait_limit()

            for repo in results:
                self.process_repo(repo)

        except KeyboardInterrupt as ex:
            self.store_partition_data_file()
            raise ex
        except:
            self.wait_limit()
            return self.process_partition(start, end)


    part_memo: dict = {}
    def download_partition(self, start, end):
        if (start, end) in self.part_memo:
            return
        self.part_memo[(start, end)] = True

        if self.get_counts_for_category(start, end) <= 1000:
            print(f'Partition {start}..{end} has <= 1000 items')
            self.process_partition(start, end)
        elif start < end:
            if end - start == 1:
                self.download_partition(start, start)
                self.download_partition (end, end)
            else:
                if isinstance(start, datetime):
                    mid = datetime.fromtimestamp(start.timestamp() + (end.timestamp() - start.timestamp()) / 2, tz=pytz.UTC)
                else:
                    mid = start + (end - start) // 2

                self.download_partition(start, mid)
                self.download_partition(mid, end)

    def process_repo(self, repo):
        owner, name = repo.full_name.split('/')
        print(f'Processing: {repo.full_name}')
        try:
            proj = Project.objects.get(owner=owner, name=name)
            return
        except Project.DoesNotExist:
            proj = Project(language=self.language,
                           owner=owner,
                           name=name)
            proj.save()
            prescreen_project.apply_async([proj.id])

            maintainers = self.collect_repo_maintainers(repo)
            for i, maintainer in maintainers.iterrows():
                try:
                    committer = Committer.objects.get(username = maintainer['login'])
                except Committer.DoesNotExist:
                    committer = Committer(username = maintainer['login'],
                                          name = maintainer['name'],
                                          email = row['email'])
                    committer.save()

                project_committer = ProjectCommitter(project=proj, committer=committer, is_maintainer=True)
                proj_committer.save()


    last_wait_finished = datetime.now()
    last_wait_length = -1
    def wait_limit(self):
        self.store_partition_data_file()
        if ((datetime.now() - self.last_wait_finished).total_seconds() - 2*self.ex_backoff) <= self.last_wait_length:
            print("Using exponential backoff for rate-limiting.")
            rate_limit_reset = datetime.fromtimestamp(self.gh.rate_limiting_resettime, tz=pytz.UTC).replace(tzinfo=pytz.UTC)
            self.last_wait_length = int((rate_limit_reset - datetime.now(pytz.UTC)).total_seconds()) + self.ex_backoff
            self.ex_backoff *= 2
        else:
            self.ex_backoff = self.default_backoff
            rate_limit_reset = datetime.fromtimestamp(self.gh.rate_limiting_resettime, tz=pytz.UTC).replace(tzinfo=pytz.UTC)
            self.last_wait_length = int(self.default_backoff + (rate_limit_reset - datetime.now(pytz.UTC)).total_seconds())

        print(f'Hit rate limit: sleeping for {self.last_wait_length} seconds.')
        time.sleep(self.last_wait_length)
        self.last_wait_finished = datetime.now()

    def add_arguments(self, parser):

        parser.add_argument('language',
                            help='Programming language to search for.',
                            choices=[ item[0] for item in Project.ProjectLanguage.choices ])
        parser.add_argument('--token',
                            help='Token used for GitHub API Access (will be taken from GITHUB_API_KEY if set)',
                            default=settings.GITHUB_API_KEY,
                            type=str)

        parser.add_argument('--min-contributors',
                            help='Minimum number of contributors',
                            type=int,
                            default=1)
        parser.add_argument('--min-contributions',
                            help='Minimum contributions (commits in weeks)',
                            nargs=2,
                            metavar=('COMMITS', 'MONTHS'),
                            type=int,
                            default=[1, 6])
        parser.add_argument('--min-stars',
                            help='Minimum stars',
                            type=int,
                            default=2)

        parser.add_argument('--end-date',
                            action='store',
                            type=datetime.fromisoformat,
                            help='End date in ISO 8601 format (default is now)')
        parser.add_argument('--start-date',
                            action='store',
                            type=datetime.fromisoformat,
                            help='Start date in ISO 6801 format (default is 7 months prior to current date)')

        parser.add_argument('--probe-starts',
                            action='store',
                            default=[],
                            type=lambda s: [ datetime.fromisoformat(item) for item in s.split(',') ],
                            help='Initial probe start values to use for the probe (comma-separated ISO8601 formatted dates)')
        parser.add_argument('--probe-counts',
                            action='store',
                            default=[],
                            type=lambda s: [ int(item) for item in s.split(',') ],
                            help='Initial count values to use for the probe (comma-separated integers)')

        parser.add_argument('--partition',
                            action='store',
                            default=[],
                            type=lambda s: [ datetime.fromisoformat(item) for item in s.split(',') ],
                            help='Manually specify partition (comma-separated ISO8601 formatted dates)')

        parser.add_argument('--partition-data-file',
                            action='store',
                            type=Path,
                            help='Name of file to store partition data in.')

    def handle(self, *args, language=None, token=None, destination=None,
               min_contributors=None, min_contributions=None, min_stars=None,
               start_date=None, end_date=None,
               probe_starts=None, probe_counts=None, partition=None,
               partition_data_file=None,
               **options):

        if token is None:
            raise CommandError('A GitHub API key must be provided with either GITHUB_API_KEY or --token.', returncode=2)

        if partition_data_file is not None:
            self.partition_data_file = partition_data_file


        self.language = Project.ProjectLanguage(language)
        self.destination = destination
        self.token = token
        self.min_contributors = min_contributors
        self.min_contributions = min_contributions
        self.min_stars = min_stars

        self.gh = Github(self.token, per_page=1)

        if not self.read_partition_data_file():
            self.start_values = probe_starts
            self.period_counts = probe_counts
            self.partition = partition
            if start_date is not None:
                self.START_DATE = start_date

            if end_date is not None:
                self.END_DATE = end_date


        if len(self.start_values) == 0 or len(self.start_values) != len(self.period_counts):
            print("Probing date values.")
            self.probe_date_values()
            print(f'--probe-starts {",".join([start.isoformat() for start in self.start_values])}')
            print(f'--probe-counts {",".join([str(count) for count in self.period_counts])}')
            self.store_partition_data_file()

        if len(self.partition) == 0:
            print("Generating initial partitions list.")
            i = 0
            for j, val in enumerate(self.period_counts):
                i = j
                if val >= 800:
                    break

            self.start_values = self.start_values[i:]
            self.period_counts = self.period_counts[i:]

            self.partition.append(self.start_values[0])
            last_count = self.period_counts[0]

            for i, start_val in enumerate(self.start_values[1:]):
                span = self.period_counts[i + 1] - last_count
                counts = span // 1001
                previous_start = self.start_values[i - 1]
                for offset in range(0, counts):
                    self.partition.append(datetime.fromtimestamp(previous_start.timestamp() + offset * (start_val.timestamp() - previous_start.timestamp())/ counts, tz=pytz.UTC))
                self.partition.append(start_val)
                last_count = self.period_counts[i + 1]
            self.partition.append(self.END_DATE)
            self.store_partition_data_file()


        self.partition.sort()
        last_partition = self.START_DATE
        self.partition = [x for x in self.partition if x >= last_partition and x <= self.END_DATE]
        print(f'--partition {",".join([start.isoformat() for start in self.partition])}')
        self.store_partition_data_file()

        input("Press enter to continue...\n")

        self.gh.per_page = 100

        for i, current_partition in enumerate(self.partition):
            self.current_partition = i
            try:
                self.download_partition(last_partition, current_partition)
            except KeyboardInterrupt as ex:
                self.store_partition_data_file()
                raise ex
            last_partition = current_partition

