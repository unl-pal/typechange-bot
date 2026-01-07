#!/usr/bin/env python
# coding: utf-8

from typing import List, Optional, Tuple

import git
from git import Repo

import re
from enum import StrEnum, auto

from .models import Project
from .ast_diff import AstDiff

import whatthepatch

python_file_check = re.compile(r'\.pyi?$', re.IGNORECASE)
typescript_file_check = re.compile(r'\.ts$', re.IGNORECASE)

insert_re = re.compile(r'^insert-(tree|node)', re.IGNORECASE)
update_re = re.compile(r'^update-(tree|node)', re.IGNORECASE)

position_re = re.compile(r'\[(\d+),(\d+)\]', re.IGNORECASE)

tree_re = re.compile(r'^(typed_parameter|type_annotation|type|union_type|help)', re.IGNORECASE)


def file_is_relevant(name: str, language: str) -> bool:
    match language:
        case Project.ProjectLanguage.PYTHON:
            return python_file_check.search(name) is not None
        case Project.ProjectLanguage.TYPESCRIPT:
            return typescript_file_check.search(name) is not None
        case _:
            return False


class ChangeType(StrEnum):
    ADDED = auto()
    REMOVED = auto()
    CHANGED = auto()

def check_commit_is_relevant(repo: Repo, commit: str, language: str) -> Optional[List[Tuple[str, int, ChangeType]]]:
    git_commit = repo.rev_parse(commit)

    # Check if it's a merge: merges aren't interesting, but their children may already have been...
    if len(git_commit.parents) > 1:
        return None

    # List of changed files is in the stats field of a commit
    changes = git_commit.stats.files
    possibly_relevant_files = []
    for file, change_data in changes.items():
        if file_is_relevant(str(file), language):
            possibly_relevant_files.append(file)

    if len(possibly_relevant_files) > 0:
        changes = []
        diffs = git_commit.diff(git_commit.parents[0], paths=possibly_relevant_files)
        for diff in diffs:
            gh_diff = None
            patch_str = ""
            patch = None
            # TODO: get the patch
            for gh_diff_obj in []:
                if gh_diff_obj.filename == diff.b_path:
                    gh_diff = gh_diff_obj
                    patch_str = gh_diff.patch
                    patch = list(whatthepatch.parse_patch(patch_str))[0]
                    break
            try:
                astdiff = AstDiff.from_diff(git_commit, diff, language.lower())
                relevant_changes = is_diff_relevant(astdiff)
                if relevant_changes:
                    for file, line, is_added in relevant_changes:
                        diff_index = 0
                        for i, change in enumerate(patch.changes):
                            if is_added:
                                if change.new == line:
                                    diff_index = patch_str.count('\n', 0, patch_str.find(change.line))
                                    break
                            else:
                                if change.old == line:
                                    change_rem_line = astdiff.a_data.split('\n')[line - 1]
                                    diff_index = patch_str.count('\n', 0, patch_str.find(change_rem_line))
                                    break
                        changes.append((file, diff_index, is_added))
                    # changes.extend(relevant_changes)
            except:
                continue
        if len(changes) == 0:
            return None
        return changes

    return None

def locate_type_tree(diff: AstDiff, start: int, end: int) -> bool:

    for match in diff.matches:
        if tree_re.match(match['src']):
            #print('matched', match)
            position_start, position_end = list(map(int, position_re.search(match['src']).groups()))
            if position_start <= start and end <= position_end:
                return True

    return False

def is_diff_relevant(diff: AstDiff) -> Optional[List[Tuple[str, int, ChangeType]]]:
    relevant_changes = []
    for action in diff.actions:
        added = True if insert_re.search(action['action']) else False
        updated = True if update_re.search(action['action']) else False
        change_type = (ChangeType.ADDED if added else (ChangeType.CHANGED if updated else ChangeType.REMOVED))

        position_string = action['parent' if not (added or updated) else 'tree']
        position_start, position_end = list(map(int, position_re.search(position_string).groups()))

        linenum = -1
        if added or updated:
            linenum = diff.a_data.count('\n', 0, position_start) + 1
        else:
            linenum = diff.b_data.count('\n', 0, position_start) + 1

        is_relevant = False

        if tree_re.match(action['tree']):
            is_relevant = True

        if locate_type_tree(diff, position_start, position_end):
            is_relevant = True

        if is_relevant:
            relevant_changes.append((diff.b_name, linenum, change_type))

    if len(relevant_changes) > 0:
        return relevant_changes
    else:
        return None
