#!/usr/bin/env python
# coding: utf-8

from django.core.management.base import BaseCommand
from git import Repo
from git.objects.commit import Commit as git_commit
from socket import gethostname
from survey.models import Commit, MetricsCommit, Project, Node
from survey.tasks.commits import change_type_to_relevance_type
from survey.utils import check_commit_is_relevant


class Command(BaseCommand):
    help = "Count commits in projects."

    def handle(self, *args, **options):
        node = Node.objects.get(hostname=gethostname())
        for project in node.project_set.filter(track_changes=True, installation_id__isnull=False, num_commits__isnull=True):
            try:
                print(f'Counting commits in project {project}...')
                repo = Repo(project.path)
                count = int(repo.git.rev_list('--count', '--all'))
                project.num_commits = count
                project.save()
            except KeyboardInterrupt as ex:
                raise ex
            except:
                print(f'failed to open repository at {project.path}')
