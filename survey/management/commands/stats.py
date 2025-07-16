#!/usr/bin/env python
# coding: utf-8

from django.core.management.base import BaseCommand, CommandError
from django.db.models import Count, Q

from survey.models import Project, Committer, Commit, Response, MetricsCommit

import pandas as pd
from scipy.stats import pearsonr

class Command(BaseCommand):
    help = "Show statistics about typechangebot installations."

    def add_arguments(self, parser):
        pass

    def handle(self, *arguments, **options):

        num_installed_projects = Project.objects.filter(installation_id__isnull=False).count()
        print(f'Number of installed projects: {num_installed_projects}')


        num_initial_responses = len([response for response in Response.objects.all() if response.is_initial_survey])
        print(f'Number of initial survey responses: {num_initial_responses}')

        num_non_initial_responses = len([response for response in Response.objects.all() if not response.is_initial_survey])
        print(f'Number of on-change survey response: {num_non_initial_responses}')

        responding_committers = set()
        for resp in Response.objects.all():
            responding_committers.add(resp.committer)
        print(f'Number of responding committers: {len(responding_committers)}')

        df_commit_data = pd.DataFrame([{ 'project': str(cmt.project),
                                         'hash': str(cmt.hash),
                                         'author': str(cmt.author),
                                         'relevance_type': str(cmt.relevance_type) }
                                       for cmt in MetricsCommit.objects.all()])

        print('Number of relevant changes:')

        df_num_changes = df_commit_data.groupby(['project', 'relevance_type'], as_index=False) \
                                       .count()[['project', 'relevance_type', 'hash']] \
                                       .rename(columns={'hash': 'count'})

        print(df_num_changes.groupby('relevance_type')['count'].describe())

        df_num_commits = pd.DataFrame([{ 'project': str(prj),
                                         'num_commits': prj.num_commits,
                                         'num_committers': prj.num_committers }
                                       for prj in Project.objects.filter(num_commits__isnull=False, num_committers__isnull=False)])

        df_freq = df_num_changes.merge(df_num_commits) \
                                .drop(columns=['num_committers']) \
                                .assign(pct_commits = lambda df: 100 * df['count'] / df['num_commits'])

        print('PCT of commits making change:')
        print(df_freq.groupby('relevance_type')['pct_commits'].describe())

        print('Total pct of type-annotation-modifying commits:')
        df_freq_pool = df_freq.drop(columns=['num_commits', 'relevance_type']) \
                              .groupby('project', as_index=False) \
                              .sum()

        print(df_freq_pool.pct_commits.describe())

        print('Number of commiters making changes/project:')
        df_committers = df_commit_data.groupby('project', as_index=False).author.value_counts()
        df_count_committers = df_committers.groupby('project', as_index=False).author.count()

        print(df_count_committers.describe())

        df_prop_committers = df_count_committers.merge(df_num_commits) \
            .drop(columns=['num_commits']) \
            .assign(pct_commiters_involved = lambda df: 100 * df.author / df.num_committers)

        print('Percent of committers making changes:')
        print(df_prop_committers.pct_committers_involved.describe())

        print('Correlation between number of committers and pct involved in making type annotation changes:')
        print(pearsonr(df_prop_committers.pct_committers, df_prop_comitters.num_committers))

