#!/usr/bin/env python
# coding: utf-8

from django.core.management.base import BaseCommand, CommandError
from django.db.models import Count, Q

from survey.models import Project, Committer, Commit

import pandas as pd

class Command(BaseCommand):
    help = "Show statistics about typechangebot installations."

    def add_arguments(self, parser):
        pass

    def handle(self, *arguments, **options):

        df = pd.DataFrame([
            {
                'project': str(prj),
                'num_committers': prj.committers.count(),
                'relevant_commits': prj.commit_set.exclude(relevance_type=Commit.RelevanceType.IRRELEVANT).count(),
                'irrelevant_commits': prj.commit_set.exclude(relevance_type=Commit.RelevanceType.IRRELEVANT).count()
            }
            for prj in Project.objects.filter(installation_id__isnull=False) ])


        print('Installed projects:')
        print(df.to_string(index=False))

        print('Numerical summary:')
        print(df[['num_committers', 'relevant_commits', 'irrelevant_commits']] \
              .describe() \
              .round(2) \
              .to_string())
