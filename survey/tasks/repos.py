#!/usr/bin/env python
# coding: utf-8

from .common import app, current_node
from django.conf import settings
from django.db.models import Q

from survey.models import Project, DeletedRepository
from git import Repo

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

    project.primary_language = project.gh.language
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
    project.typechecker_files = get_typechecker_configuration(repo, project.primary_language)
    project.save()

@app.task(ignore_result = True)
def fetch_project(project_id: int):
    project = Project.objects.get(id=project_id)
    try:
        repo = Repo(project.path)
    except:
        project.path.parent.mkdir(exist_ok=True, parents=True)
        repo = Repo.clone_from(project.clone_url, project.path)
    repo.remote().fetch()

@app.task()
def rename_repo(old_owner, old_name, new_owner, new_name):
    project = Project.objects.get(Q(owner=old_owner), Q(name=old_name))
    # TODO: Delete old repo?  Move old repo?
    project.owner = new_owner
    project.name = new_name
    project.save()
    project.path.parent.mkdir(exist_ok=True, parents=True)
    Repo.clone_from(project.clone_url, project.path)

@app.task()
def delete_repo(deleted_pk):
    repo = DeletedRepository.objects.get(id=deleted_pk)
    path = settings.DATA_DIR / repo.owner / repo.name
    for root, dirs, files in path.walk(top_down=False):
        for name in files:
            (root / name).unlink()
        for name in dirs:
            (root / name).rmdir()
    repo.delete()
