#!/usr/bin/env python
# coding: utf-8

from .common import current_node, app

from survey.models import Project, ProjectCommitter, DeletedRepository
from django.utils import timezone
from django.db.models import Q

from .repos import install_repo, rename_repo
from .screening import prescreen_project

__all__ = [
    'process_installation',
    'process_installation_repositories',
    'process_repository'
]

@app.task()
def process_installation(payload):
    repositories = payload['repositories']

    match payload['action']:
        case 'created':
            installation_id = payload['installation']['id']
            for repo in repositories:
                owner, name = repo['full_name'].split('/')
                install_repo.delay(owner, name, installation_id)
        case 'deleted':
            for repo in repositories:
                owner, name = repo['full_name'].split('/')
                if Project.objects.filter(owner=owner, name=name).count() > 0:
                    for project in Project.objects.filter(owner=owner, name=name):
                        deleted_repo = DeletedRepository(node = project.host_node,
                                                         owner = project.owner,
                                                         name = project.name,
                                                         reason = DeletedRepository.DeletionReason.DELETED)
                        if project.data_subdir is not None:
                            deleted_repo.subdir = project.data_subdir
                        deleted_repo.save()

                        project.installation_id = None
                        project.data_subdir = None
                        project.remove_date = timezone.now()
                        project.track_changes = False
                        project.save()

        case 'suspend':
            for repo in repositories:
                owner, name = repo['full_name'].split('/')
                try:
                    proj = Project.objects.get(owner=owner, name=name)
                    proj.track_changes = False
                    proj.save()
                except Project.DoesNotExist:
                    continue
            pass
        case 'unsuspend':
            for repo in repositories:
                owner, name = repo['full_name'].split('/')
                try:
                    proj = Project.objects.get(owner=owner, name=name)
                    prescreen_project.delay(proj.id)
                except Project.DoesNotExist:
                    continue

@app.task()
def process_installation_repositories(payload):
    match payload['action']:
        case 'added':
            installation_id = payload['installation']['id']
            for repo in payload['repositories_added']:
                owner, name = repo['name'].split('/')
                install_repo.delay(owner, repo, installation_id)
        case 'removed':
            for repo in payload['repositories_removed']:
                owner, name = repo['name'].split('/')
                if Project.objects.filter(owner=owner, name=name).count() > 0:
                    for project in Project.objects.filter(owner=owner, name=name):
                        deleted_repo = DeletedRepository(node = project.host_node,
                                                         owner = project.owner,
                                                         name = project.name,
                                                         reason = DeletedRepository.DeletionReason.DELETED)
                        if project.data_subdir is not None:
                            deleted_repo.subdir = project.data_subdir
                        deleted_repo.save()

                        project.installation_id = None
                        project.data_subdir = None
                        project.remove_date = timezone.now()
                        project.track_changes = False
                        project.save()


@app.task()
def process_repository(payload):
    match payload['action']:
        case "archived" | "deleted":
            owner, name = payload['repository']['full_name'].split('/')
            try:
                repo = Project.objects.get(Q(owner=owner) & Q(name=name))
            except:
                return
            repo.track_changes = False
            repo.save()
        case "renamed":
            old_name = payload['changes']['repository']['name']['from']
            owner, new_name = payload['repository']['full_name'].split('/')
            project = Project.objects.get(Q(owner=owner), Q(name=old_name))
            rename_repo.apply_async([owner, old_name, owner, new_name], queue=project.host_node.hostname)
