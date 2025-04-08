#!/usr/bin/env python
# coding: utf-8

from .common import app, current_node
from django.conf import settings
from django.db.models import Q

from survey.models import Project, DeletedRepository
from survey.utils import get_typechecker_configuration
from git import Repo
import os

__all__ = [
    'install_repo',
    'clone_repo',
    'fetch_project',
    'rename_repo',
    'delete_repo'
]

@app.task()
def install_repo(owner: str, repo: str, installation_id: str):
    try:
        project = Project.objects.get(Q(owner=owner) & Q(name=repo))
        project.installation_id = installation_id
    except Project.DoesNotExist:
        project = Project(owner=owner, name=repo, installation_id=installation_id)

    project.remove_date = None

    project.save()

    # TODO: Uncomment when live
    # if project.gh.fork:
    #     project.track_changes = False
    #     project.save()
    #     return

    try:
        project.primary_language = project.gh.language
    except:
        languages = project.gh.get_languages()
        project.primary_language = max(languages, key=languages.get)

    if project.primary_language in ['TypeScript', 'Python', 'PHP', 'R']:
        project.track_changes = True

    project.save()

    if project.track_changes:
        if project.host_node is None:
            clone_repo.delay(project.id)
        else:
            fetch_project.apply_async([project.id], queue=project.host_node.hostname)

@app.task()
def clone_repo(project_id):
    project = Project.objects.get(id=project_id)
    local_path = project.path
    local_path.parent.mkdir(exist_ok=True, parents=True)
    repo = Repo.clone_from(project.clone_url, local_path)
    project.host_node = current_node
    if project.typechecker_files is None:
        project.typechecker_files = get_typechecker_configuration(repo, project.primary_language)
    project.save()

@app.task(ignore_result = True)
def fetch_project(project_id: int):
    project = Project.objects.get(id=project_id)
    try:
        repo = Repo(project.path)
        repo.remote().fetch()
    except:
        clone_repo(project_id)


@app.task()
def rename_repo(old_owner, old_name, new_owner, new_name):
    project = Project.objects.get(Q(owner=old_owner), Q(name=old_name))
    old_path = project.path
    project.owner = new_owner
    project.name = new_name
    project.save()
    old_path.rename(project.path)

@app.task()
def delete_repo(deleted_pk):
    repo = DeletedRepository.objects.get(id=deleted_pk)
    if repo.subdir is not None:
        path = settings.DATA_DIR / repo.subdir / repo.owner / repo.name
    else:
        path = settings.DATA_DIR / repo.owner / repo.name
    if path.exists():
        for root, dirs, files in os.walk(path, topdown=False):
            for name in files:
                os.remove(os.path.join(root, name))
            for name in dirs:
                os.rmdir(os.path.join(root, name))
    repo.delete()
