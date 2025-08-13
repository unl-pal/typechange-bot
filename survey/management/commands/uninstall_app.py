#!/usr/bin/env python
# coding: utf-8

from django.core.management.base import BaseCommand, CommandError
from github import Github, GithubIntegration, Auth
from django.conf import settings
from django.utils import timezone

from survey.models import Project
import requests

class Command(BaseCommand):
    help = "Uninstall Application from installed repos"

    def add_arguments(self, parser):
        parser.add_argument('--dry-run', action='store_true', default=False)

        parser.add_argument('--limit', type=int, default=None)

        parser.add_argument('--app-id', type=str, default=settings.GITHUB_APP_ID)
        parser.add_argument('--app-key', type=str, default=settings.GITHUB_APP_KEY)

    def handle(self, *arguments,
               dry_run=False,
               app_id=None,
               app_key=None,
               limit=None,
               **options):

        application_auth = Auth.AppAuth(app_id, app_key)
        integration = GithubIntegration(auth=application_auth)

        for installation in integration.get_installations():
            projects = []
            for repo in installation.get_repos():
                print(f'Processing {repo.full_name}')
                owner, name = repo.full_name.split('/')
                try:
                    project = Project.objects.get(owner=owner, name=name)
                    project.installation_id = None
                    project.remove_date = timezone.now()
                    projects.append(project)
                except Project.DoesNotExist:
                    continue

            if not dry_run:
                response = requests.delete(f'https://api.github.com/app/installations/{installation.id}',
                                           headers={'Accept': 'application/vnd.github+json',
                                                    'X-GitHub-Api-Version': '2022-11-28',
                                                    'Authorization': f'Bearer {application_auth.create_jwt()}'})

                if response.ok:
                    for project in projects:
                        project.save()
                    response.close()

