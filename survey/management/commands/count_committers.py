#!/usr/bin/env python
# coding: utf-8

from django.core.management.base import BaseCommand
from survey.models import Project

class Command(BaseCommand):
    help = "Count committers in projects."

    def handle(self, *args, **options):
        for project in Project.objects.filter(track_changes=True, installation_id__isnull=False, num_committers__isnull=True):
            try:
                print(f'Counting commits in project {project}...')
                count = len({ s.author.login for s in project.gh.get_stats_contributors() if s.author is not None })
                project.num_committers = count
                project.save()
            except KeyboardInterrupt as ex:
                raise ex
            except:
                print(f'failed to count committers for {project}')
