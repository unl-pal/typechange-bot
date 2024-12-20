#!/usr/bin/env python
# coding: utf-8

from git import Diff, Commit
from tempfile import NamedTemporaryFile
from pathlib import Path
from typing import Union, Optional
import subprocess
from subprocess import CalledProcessError
import json

GUMTREE_PATH = 'gumtree'

class AstDiff:

    def __init__(self, a_file: Union[str, Path], b_file: Union[str, Path]):
        self.a_name = str(a_file)
        self.b_name = str(b_file)
        diff_proc = subprocess.run([GUMTREE_PATH, 'textdiff', '-f', 'json', self.a_name, self.b_name],
                                   capture_output=True,
                                   check=True)
        if len(diff_proc.stdout.decode()) == 0:
            raise ValueError("AST Diff Generation Failed, no output.",
                             diff_proc.stderr.decode())
        self._diff_data_json = diff_proc.stdout.decode()
        self._diff_json = json.loads(self._diff_data_json)

    def __str__(self):
        return f'AstDiff(\'{self.a_name}\', \'{self.b_name}\')'

    @property
    def actions(self):
        if 'actions' in  self._diff_json.keys():
            return self._diff_json['actions']

    @classmethod
    def from_diff(cls, commit: Commit, diff: Diff, suffix: Optional[str] = None):
        with NamedTemporaryFile(suffix=suffix) as pre_diff, \
             NamedTemporaryFile(suffix=suffix) as post_diff:
            pre_diff.write(diff.a_blob.data_stream.read())
            pre_diff.flush()
            post_diff.write(diff.b_blob.data_stream.read())
            post_diff.flush()
            obj = cls(pre_diff.name, post_diff.name)
            obj.a_name = f'{diff.a_path}[{commit.parents[0].hexsha[0:6]}]'
            obj.b_name = f'{diff.b_path}[{commit.hexsha[0:6]}]'
        return obj
