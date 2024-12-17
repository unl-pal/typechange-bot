#!/usr/bin/env python
# coding: utf-8

import tomllib

def get_typechecker_configuration(repo, language):
    typecheckers = []
    if language == 'Python':
        for object in repo.active_branch.tree.traverse():
            if object.type == 'blob':
                if name in ['mypy.ini',
                            '.mypy.ini',
                            '.pyre_configuration',
                            'pytype.toml',
                            'pyrightconfig.json']:
                    typecheckers += object.path

                elif name == 'pyproject.toml':
                    data = tomllib.loads(object.data_stream.read())
                    if 'tool' in data.keys():
                        for tool in ['mypy', 'pytype', 'pyright']:
                            if tool in data['tool'].keys():
                                typecheckers += f'{object.path}[tool.{tool}]'

        if len(typecheckers) > 0:
            return '\n'.join(typecheckers)
    elif language == 'TypeScript':
        pass

    return None
