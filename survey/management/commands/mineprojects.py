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

import git
from tempfile import TemporaryDirectory
from pathlib import Path

import json

class Command(BaseCommand):
    help = "Mine GitHub Projects"

    language = None
    tokens = []
    destination = []
    min_contributors = 1
    min_contributions = (7, 1)
    min_stars = 2
    check_annotations = False
    check_config = False

    # Search Options, Backoff, Rate Limit
    default_backoff = 15
    ex_backoff = default_backoff
    api_search_limit = 1000

    gh = None

    results = None
    page_num = 0

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


    def get_next_page(self):
        try:
            page = self.results.get_page(self.page_num)
            self.page_num += 1
            return page
        except RateLimitExceededException:
            self.wait_limit()
            return self.get_next_page()

    def check_contribution(self, id):
        try:
            repo = self.gh.get_repository(id)
            return repo.get_stats_participation().all[-self.min_contributions[1]:] >= self.min_contributions[0]
        except RateLimitExceededException:
            self.wait_limit()
            return self.check_contribution(id)

    def wait_limit(self):
        seconds = int(5 + (self.gh.rate_limiting_resettime.replace(tzinfo=pytz.UTC) - datetime.now(pytz.UTC)).total_seconds())
        print(f'Hit rate limit: sleeping for {seconds} seconds')
        time.sleep(seconds)

    def add_arguments(self, parser):

        parser.add_argument('language',
                            help='Programming language to search for.',
                            choices=[ item[0] for item in Project.ProjectLanguage.choices ])
        parser.add_argument('--token',
                            help='Token used for GitHub API Access.',
                            required=True,
                            type=str)

        parser.add_argument('--min-contributors',
                            help='Minimum number of contributors',
                            type=int,
                            default=1)
        parser.add_argument('--min-contributions',
                            help='Minimum contributions (commits in weeks)',
                            nargs=2,
                            metavar=('COMMITS', 'WEEKS'),
                            type=int,
                            default=[7, 1])
        parser.add_argument('--min-stars',
                            help='Minimum stars',
                            type=int,
                            default=2)
        parser.add_argument('--check-annotations',
                            help='Check for annotations in candidate projects.',
                            default=False,
                            action='store_true')
        parser.add_argument('--check-config',
                            help="Check for typechecker configuration.",
                            default=False,
                            action='store_true')

    def handle(self, *args, language=None, token=None, destination=None,
               min_contributors=None, min_contributions=None, min_stars=None,
               check_annotations=None, check_config=None,
               **options):
        self.language = language
        self.destination = destination
        self.token = token
        self.min_contributors = min_contributors
        self.min_contributions = min_contributions
        self.min_stars = min_stars
        self.check_annotations = check_annotations
        self.check_config = check_config

        for tok in self.tokens:
            self.sleep[tok] = -1

        self.rotate_tokens()

        self.gh = Github(self.token, per_page=100)

        self.results = self.gh.search_repositories(f'language:{self.language} stars:>={self.min_stars}',
                                                sort='updated',
                                                order='desc')

        while True:
            repos = self.get_next_page()
            for repo in repos:
                d = repo.raw_data

                id = str(d['id'])
                path = self.destination / id[0] / id[1] / id[2]
                filename = path / (id + '.json')
                bad_path = self.destination / 'bad' / id[0] / id[1] / id[2]
                bad_filename = bad_path / (id + '.json')

                if not filename.exists():
                    if not bad_filename.exists():

                        path.mkdir(parents=True, exist_ok=True)
                        with open(path, 'w') as fh:
                            fh.write(json.dumps(d, indent=2))
                        print(f'Good {filename}')

                        owner, name = repo.full_name.split('/')
                        proj = Project(language=self.language,
                                       owner=owner,
                                       name=name)
                        proj.save()
                        prescreen_projects.apply_async([proj.id])

                        df = self.collect_repo_maintainers(repo)
                        for i, row in df.iterrows():
                            try:
                                committer = Committer.objects.get(username=row['login'])
                            except Committer.DoesNotExist:
                                committer = Committer(username=row['login'],
                                                      name=row['name'],
                                                      email=row['email'])
                                committer.save()

                            proj_committer = ProjectCommitter(project=proj, committer=committer, is_maintainer=True)
                            proj_committer.save()

                    else:
                        print(f'Bad {filename}')

                else:
                    print(f'Skipped {filename}')
