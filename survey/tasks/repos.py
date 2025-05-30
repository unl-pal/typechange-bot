#!/usr/bin/env python
# coding: utf-8

from .common import app, current_node
from django.conf import settings
from django.db.models import Q

from survey.models import Project, DeletedRepository
from survey.utils import get_typechecker_configuration, has_annotations, has_language_file
from git import Repo, GitCommandError
import os
import shutil

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

    if project.gh.fork or project.gh.private:
        project.track_changes = False
        project.save()
        return

    try:
        language = project.gh.language
    except:
        languages = project.gh.get_languages()
        language = max(languages, key=languages.get)

    if language in ['TypeScript', 'Python', 'PHP', 'R', 'Ruby']:
        project.track_changes = True
        project.language = Project.ProjectLanguage.from_github_name(language)

    project.save()

    if project.track_changes:
        if project.host_node is None:
            clone_repo.delay(project.id)
        else:
            fetch_project.apply_async([project.id], queue=project.host_node.hostname)

@app.task()
def clone_repo(project_id):
    project = Project.objects.get(id=project_id)

    if project.gh.fork:
        project.track_changes = False
        project.save()
        return

    if project.gh.private:
        project.track_changes = False
        project.save()
        return

    if current_node.use_datadir_subdirs:
        locations = { p: shutil.disk_usage(p.readlink()).free for p in settings.DATA_DIR.iterdir() if p.is_symlink() }
        subdir = max(locations, key=locations.get).parts[-1]
        project.data_subdir = subdir
    local_path = project.path
    if not local_path.exists():
        try:
            local_path.parent.mkdir(exist_ok=True, parents=True)
            repo = Repo.clone_from(project.clone_url, local_path)
        except GitCommandError:
            project.track_changes = False
            project.save()
            return
    else:
        repo = Repo(local_path)

    project.host_node = current_node
    project.save()

    if project.typechecker_files is None:
        project.typechecker_files = get_typechecker_configuration(repo, project.language)
    project.has_language_files = has_language_file(repo, project.language)
    project.annotations_detected = has_annotations(repo, project.language)

    project.track_changes = project.has_language_files and ((project.has_typechecker_configuration is not None) or project.annotations_detected)

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
    parent = path.parent
    path.rmdir()
    if len(list(parent.iterdir())) == 0:
        parent.rmdir()
    repo.delete()
