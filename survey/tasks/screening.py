#!/usr/bin/env python
# coding: utf-8

from .common import current_node, app

from survey.models import Project
from django.utils import timezone

from survey.utils import get_typechecker_configuration, has_annotations, has_language_file
from git import Repo
from tempfile import TemporaryDirectory
from pathlib import Path

@app.task()
def prescreen_project(project_id: int) -> None:
    project: Project = Project.objects.get(id=project_id)

    project.has_language_files = False
    project.has_typechecker_configuration = False
    project.typechecker_files = None
    project.annotations_detected = False

    with TemporaryDirectory() as temp_dir:
        git_repo = Repo.clone_from(project.clone_url, temp_dir,
                                   multi_options=[ "--depth 1",
                                                   "--shallow-submodules",
                                                   "--no-remote-submodules" ])

        project.has_language_files = has_language_file(git_repo, project.language)

        if project.has_language_files:
            typechecker_config = get_typechecker_configuration(git_repo, project.language)
            if typechecker_config is not None:
                project.typechecker_files = typechecker_config
                project.has_typechecker_configuration = True

            project.annotations_detected = has_annotations(git_repo, project.language)


    project.track_changes = project.has_language_files and (project.has_typechecker_configuration or project.annotations_detected)

    project.save()
