#!/usr/bin/env python
# coding: utf-8

from django.core.management.base import BaseCommand, CommandError
from django.db.models import Count

from survey.models import Project, Committer, Commit

from django.utils import timezone
from datetime import timedelta

class Command(BaseCommand):
    help = "Clean up database, removing unneeded objects"

    dry_run = False
    confirm = True
    show_n = 30

    def add_arguments(self, parser):

        parser.add_argument('--no-dry-run',
                            default=True,
                            action='store_false',
                            help='When passed, do not make any database changes, only print proposed changes.')

        parser.add_argument('--vacuum-type',
                            default='all',
                            choices=['all', 'projects', 'committers', 'commits'],
                            help='What to vacuum.')

        parser.add_argument('--show-n',
                            default=30,
                            type=int,
                            help='How many of each object to show.')

        parser.add_argument('--no-confirm',
                            default=False,
                            action='store_true',
                            help='When passed (and not in dry-run mode), do not confirm deletion operations.')

    def confirm_vacuum(self, type):
        if self.confirm:
            result = None
            while result is None:
                result = input(f'Delete {type}? (y/n) ').lower().strip()
                if result[0] == 'y':
                    return True
                if result[0] == 'n':
                    return False
                result = None
        return True

    def vacuum_projects(self):
        vacuumable_projects = Project.objects.filter(installation_id__isnull=True, track_changes=False)
        print(f'There are {vacuumable_projects.count()} projects which are vacuumable')
        for proj in vacuumable_projects[:self.show_n]:
            print(f' - {proj}')
        if vacuumable_projects.count() > self.show_n:
            print('and more.')
        if not self.dry_run and self.confirm_vacuum('projects'):
            print('Deleting projects')
            vacuumable_projects.delete()

    def vacuum_committers(self):
        vacuumable_committers = Committer.objects \
            .filter(consent_timestamp__isnull = True) \
            .annotate(project_count = Count('projects')) \
            .filter(project_count=0)
        print(f'There are {vacuumable_committers.count()} committers which are vacuumable.')
        for committer in vacuumable_committers[:self.show_n]:
            print(f' - {committer}')
        if vacuumable_committers.count() > self.show_n:
            print('and more.')
        if not self.dry_run and self.confirm_vacuum('committers'):
            print('Deleting committers')
            vacuumable_committers.delete()

    def vacuum_commits(self):
        time_created = timezone.now() - timedelta(hours=36)
        vacuumable_commits = Commit.objects \
                                   .filter(created_at__lt=time_created,
                                           relevance_type=Commit.RelevanceType.IRRELEVANT)
        print(f'There are {vacuumable_commits.count()} commits which are vacuumable.')
        for commit in vacuumable_commits[:self.show_n]:
            print(f' - {commit} on {commit.project}')
        if vacuumable_commits.count() > self.show_n:
            print('and more.')
        if not self.dry_run and self.confirm_vacuum('commits'):
            print('Deleting commits')
            vacuumable_commits.delete()


    def handle(self, *args,
               vacuum_type='all',
               no_dry_run=True,
               no_confirm=False,
               show_n=30,
               **options):

        self.dry_run = no_dry_run
        self.confirm = not no_confirm
        self.show_n = show_n

        match vacuum_type:
            case 'all':
                self.vacuum_projects()
                self.vacuum_committers()
                self.vacuum_commits()
            case 'projects':
                self.vacuum_projects()
            case 'committers':
                self.vacuum_committers()
            case 'commits':
                self.vacuum_commits()

