#!/usr/bin/env python
# coding: utf-8

from django.core.management.base import BaseCommand, CommandError
from github import Github, GithubIntegration, Auth
from django.conf import settings
from django.utils import timezone

from survey.models import Project


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

        repos = Project.objects.filter(installation_id__isnull=False)
        if limit is not None:
            repos = repos[:limit]

        for repo in repos:
            print(repo)
            installation = integration.get_repo_installation(repo.owner, repo.name)
            if not dry_run:
                requester = installation._requester
                repo.installation_id = None
                repo.remove_date = timezone.now()
                repo.save()
                out = requester.requestJson('DELETE', f'/app/installations/{installation_id}')
                print(out)

        pass

