#!/usr/bin/env python
# coding: utf-8

from django.core.management.base import BaseCommand
from git import Repo
from git.objects.commit import Commit as git_commit
from socket import gethostname
from survey.models import Commit, MetricsCommit, Project
from survey.tasks.commits import change_type_to_relevance_type
from survey.utils import check_commit_is_relevant


class Command(BaseCommand):
    help = "Collect metrics for projects in the survey"

    def handle(self, *args, **options):
        for project in Project.objects.filter(track_changes=True, installation_id__isnull=False, metrics_collected=False):
            if project.host_node and project.host_node.hostname == gethostname():
                self.collect_metrics(project)
                project.metrics_collected = True
                project.save()

    def collect_metrics(self, project):
        print(f'Collecting metrics for {project}...')
        try:
            repo = Repo(project.path)
            for commit in repo.iter_commits():
                self.process_commit(project, repo, commit)
        except KeyboardInterrupt as ex:
            raise ex
        except:
            print(f'Failed to open repository at {project.path}.')

    def process_commit(self, project: Project, repo: Repo, raw_commit: git_commit):
        commit = Commit(project=project,
                        hash=raw_commit.hexsha,
                        message="",
                        diff=repo.git.diff(raw_commit),)

        commit_is_relevant = check_commit_is_relevant(repo, commit)
        if commit_is_relevant is not None:
            metric = MetricsCommit()
            relevant_file, relevant_line, change_type = commit_is_relevant[0]
            metric.project = project
            metric.hash = commit.hash
            metric.relevance_type = change_type_to_relevance_type(change_type)
            metric.relevant_change_file = relevant_file
            metric.relevant_change_line = relevant_line
            metric.created_at = raw_commit.committed_datetime
            metric.author = commit.gh.author.login
            metric.committer = commit.gh.committer.login
            metric.save()
            print(f'  -> Processed commit {metric.hash} with relevance type {metric.relevance_type} in file {metric.relevant_change_file} at line {metric.relevant_change_line}.')
