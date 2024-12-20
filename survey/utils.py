#!/usr/bin/env python
# coding: utf-8

import tomllib, json
import re
from typing import List, Optional, Tuple
import git
from git import Repo
from .models import Commit
from .ast_diff import AstDiff


python_file_check = re.compile(r'\.pyi?$', re.IGNORECASE)
typescript_file_check = re.compile(r'\.ts$', re.IGNORECASE)

def get_typechecker_configuration(repo, language, commit_like='HEAD'):
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

    if len(typecheckers) > 0:
        return '\n'.join(typecheckers)
    return None

def file_is_relevant(name, language):
    if language == 'Python':
        return python_file_check.search(name)
    elif language == 'TypeScript':
        return typescript_file_check.search(name)
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
        if file_is_relevant(file, language):
            possibly_relevant_files.append(file)

    if len(possibly_relevant_files) > 0:
        changes = [('', 1, True)]
        diffs = git_commit.diff(git_commit.parents[0], paths=possibly_relevant_files)
        for diff in diffs:
            try:
                astdiff = AstDiff.from_diff(git_commit, diff, suffix = {'Python': '.py', 'TypeScript': '.ts'}[language])
            except:
                continue
            # TODO Process tree diff for addition/removal of annotations
        if len(changes) == 0:
            return None
        return changes

    return None
