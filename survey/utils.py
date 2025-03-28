#!/usr/bin/env python
# coding: utf-8

import tomllib, json
import re
from typing import List, Optional, Tuple
import git
from git import Repo
from .models import Commit, Project
from django.db.models import Q
from .ast_diff import AstDiff
import whatthepatch

python_file_check = re.compile(r'\.pyi?$', re.IGNORECASE)
typescript_file_check = re.compile(r'\.ts$', re.IGNORECASE)
php_file_check = re.compile(r'\.php$', re.IGNORECASE)

insert_re = re.compile(r'^insert-(tree|node)', re.IGNORECASE)

tree_re = re.compile(r'^(typed_parameter|type_annotation|type|union_type|help)', re.IGNORECASE)

def get_typechecker_configuration(repo, language: str, commit_like: str='HEAD'):
    typecheckers = []
    if language == 'Python':
        for object in repo.rev_parse(commit_like).tree.traverse():
            if object.type == 'blob':
                if object.name in ['mypy.ini',
                            '.mypy.ini',
                            '.pyre_configuration',
                            'pytype.toml',
                            'pyrightconfig.json']:
                    typecheckers.append(object.path)

                elif object.name == 'pyproject.toml':
                    data = tomllib.loads(object.data_stream.read().decode())
                    if 'tool' in data.keys():
                        for tool in ['mypy', 'pytype', 'pyright']:
                            if tool in data['tool'].keys():
                                typecheckers.append(f'{object.path}[tool.{tool}]')
    elif language == 'TypeScript':
        for object in repo.rev_parse(commit_like).tree.traverse():
            if object.type == 'blob':
                if re.search(r'[tj]sconfig.json$', object.name):
                    data = json.loads(object.data_stream.read().decode)
                    if 'compilerOptions' in data.keys():
                        for typecheck_option in ["allowUnreachableCode",
                                                 "allowUnusedLabels",
                                                 "alwaysStrict",
                                                 "exactOptionalPropertyTypes",
                                                 "noFallthroughCasesInSwitch",
                                                 "noImplicitAny",
                                                 "noImplicitOverride",
                                                 "noImplicitReturns",
                                                 "noImplicitThis",
                                                 "noPropertyAccessFromIndexSignature",
                                                 "noUncheckedIndexedAccess",
                                                 "noUnusedLocals",
                                                 "noUnusedParameters",
                                                 "strict",
                                                 "strictBindCallApply",
                                                 "strictBuiltinIteratorReturn",
                                                 "strictFunctionTypes",
                                                 "strictNullChecks",
                                                 "strictPropertyInitialization",
                                                 "useUnknownInCatchVariables"]:
                            if typecheck_option in data['compilerOptions'].keys():
                                typecheckers.append(f'{object.path}[compilerOptions][{typecheck_option}]')
    elif language == "Ruby":
        pass
    elif language == "R":
        pass
    elif language == "PHP":
        pass

    if len(typecheckers) > 0:
        return '\n'.join(typecheckers)
    return None

def file_is_relevant(name: str, language: str) -> bool:
    if language == 'Python':
        return python_file_check.search(name) is not None
    elif language == 'TypeScript':
        return typescript_file_check.search(name) is not None
    return False

def check_commit_is_relevant(repo: Repo, commit: Commit) -> Optional[List[Tuple[str, int, bool]]]:
    language = commit.project.primary_language
    git_commit = repo.rev_parse(commit.hash)

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
            for gh_diff_obj in commit.gh.files:
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

def is_diff_relevant(diff: AstDiff) -> Optional[List[Tuple[str, int, bool]]]:
    relevant_changes = []
    for action in diff.actions:
        added = True if insert_re.search(action['action']) else False
        if tree_re.match(action['tree']):
            linenum = -1
            if added:
                position = int(action['parent'][action['parent'].find('[') + 1:action['parent'].find(',')])
                linenum = diff.a_data.count('\n', 0, position) + 1
            else:
                position = int(action['tree'][action['tree'].find('[') + 1:action['tree'].find(',')])
                linenum = diff.b_data.count('\n', 0, position) + 1
            relevant_changes.append((diff.b_name, linenum, added))
    if len(relevant_changes) > 0:
        return relevant_changes
    else:
        return None

def get_comment_gh(commit_id, owner, name):
    try:
        commit = Commit.objects.get(hash=commit_id)
        return commit.gh
    except Commit.DoesNotExist:
        repo = Project.objects.get(Q(owner=owner) & Q(name=name))
        return repo.gh.get_commit(sha=commit_id)
    except Project.DoesNotExist:
        return None
