#!/usr/bin/env python
# coding: utf-8

from .common import current_node, app

from survey.models import Project
from django.utils import timezone

from survey.utils import get_typechecker_configuration, has_annotations
from git import Repo
from tempfile import TemporaryDirectory
from pathlib import Path

@app.task()
def prescreen_project(project_id: int) -> None:
    project: Project = Project.objects.get(id=project_id)

    with TemporaryDirectory() as temp_dir:
        git_repo = Repo.clone_from(project.clone_url, temp_dir,
                                   multi_options=[ "--depth 1",
                                                   "--shallow-submodules"
                                                   "--no-remote-submodules" ])
        typechecker_config = get_typechecker_configuration(temp_dir, project.language)
        if typechecker_config is not None:
            project.typechecker_files = typechecker_config
            project.has_typechecker_configuration = True

        if has_annotations(git_repo, project.language):
            project.annotations_detected = True

    project.track_changes = project.has_typechecker_configuration or project.annotations_detected

    project.save()
