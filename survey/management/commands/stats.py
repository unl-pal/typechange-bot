#!/usr/bin/env python
# coding: utf-8

from django.core.management.base import BaseCommand, CommandError
from django.db.models import Count, Q

from survey.models import Project, Committer, Commit, Response, MetricsCommit

import pandas as pd
from scipy.stats import pearsonr


import matplotlib.pyplot as plt
import seaborn as sns

plt.rcParams['pdf.fonttype'] = 42
plt.rcParams['ps.fonttype'] = 42

sns.set_theme(context='paper',
        style='whitegrid',
        palette='colorblind',
        font_scale=1.2)

plt.rcParams['figure.figsize'] = [7.0, 4.0]
plt.rcParams['figure.dpi'] = 600.0
plt.rcParams['font.size'] = 24
plt.rcParams['legend.loc'] = 'upper right'

def save_table(df, filename):
    if isinstance(df, pd.Series):
        df = df.to_frame()
    styler = df.style \
               .format(None, precision=2) \
               .map_index(lambda x: 'textbf:--rwrap;', axis='columns') \
               .hide(names=True, axis='columns') \
               .map_index(lambda x: 'textbf:--rwrap;', axis='index') \
               .hide(names=True, axis='index') \
               .format_index(None, escape='latex', axis='columns') \
               .format_index(None, escape='latex', axis='rows') \
               .set_table_styles([
                   {'selector': 'toprule', 'props': ':toprule;'},
                   {'selector': 'bottomrule', 'props': ':bottomrule;'}],
                  overwrite=False)
    with open(filename, 'w+') as fh:
        fh.write(styler.to_latex())


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

        print()
        print('Number of relevant changes:')

        df_num_changes = df_commit_data.groupby(['project', 'relevance_type'], as_index=False) \
                                       .count()[['project', 'relevance_type', 'hash']] \
                                       .rename(columns={'hash': 'count'})
        num_changes = df_num_changes.groupby('relevance_type')['count'].describe()
        print(num_changes)
        save_table(num_changes, 'number_relevant_changes.tex')


        df_num_commits = pd.DataFrame([{ 'project': str(prj),
                                         'num_commits': prj.num_commits,
                                         'num_committers': prj.num_committers }
                                       for prj in Project.objects.filter(num_commits__isnull=False, num_committers__isnull=False)])

        df_freq = df_num_changes.merge(df_num_commits) \
                                .drop(columns=['num_committers']) \
                                .assign(pct_commits = lambda df: 100 * df['count'] / df['num_commits'])

        df_freq_pool = df_freq.drop(columns=['num_commits', 'relevance_type']) \
                      .groupby('project', as_index=False) \
                      .sum()

        pct_overall = df_freq_pool.pct_commits.describe()


        print()
        print('pct of commits making change:')
        pct_making_change = df_freq.groupby('relevance_type')['pct_commits'].describe()
        pct_making_change.loc['Tot.'] = pct_overall
        pct_making_change = pct_making_change.convert_dtypes()
        print(pct_making_change)
        save_table(pct_making_change, 'pct_commits_making_change_type.tex')

        print()
        print('Total pct of type-annotation-modifying commits:')

        print(pct_overall)
        save_table(pct_overall, 'pct_commits_making_change.tex')

        df_committers = df_commit_data.groupby('project', as_index=False).author.value_counts()
        df_count_committers = df_committers.groupby('project', as_index=False).author.count()

        df_prop_committers = df_count_committers.merge(df_num_commits) \
            .drop(columns=['num_commits']) \
            .assign(pct_committers_involved = lambda df: 100 * df.author / df.num_committers)

        print()
        print('Percent of committers making changes:')
        pct_committers_involved = df_prop_committers[['num_committers', 'pct_committers_involved']].describe()
        print(pct_committers_involved)
        pct_committers_involved = pct_committers_involved.rename(columns={'num_committers': '# Committers',
                                                                          'pct_committers_involved': '% Committers'})
        save_table(pct_committers_involved, 'pct_committers.tex')

        print()
        print('Correlation between number of committers and pct involved in making type annotation changes:')
        print(pearsonr(df_prop_committers.pct_committers_involved, df_prop_committers.num_committers))
        fig, ax = plt.subplots(constrained_layout=True)
        sns.regplot(data=df_prop_committers, x='pct_committers_involved', y='num_committers', ax=ax)
        ax.set_ylabel('# Committers')
        ax.set_xlabel('% Commiters Changing Annotations')
        fig.savefig('correlation.pdf')
