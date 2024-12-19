#!/usr/bin/env python
# coding: utf-8

from git import Diff
from tempfile import NamedTemporaryFile
from pathlib import Path
from typing import Union, Optional
import subprocess
from subprocess import CalledProcessError
import json

GUMTREE_PATH = 'gumtree'

class AstDiff:

    def __init__(self, pre_diff_version: Union[str, Path], post_diff_version: Union[str, Path]):
        diff_proc = subprocess.run([GUMTREE_PATH, 'textdiff', '-f', 'json', str(pre_diff_version), str(post_diff_version)],
                                   capture_output=True,
                                   check=True)
        if len(diff_proc.stdout.decode()) == 0:
            raise ValueError("AST Diff Generation Failed, no output.",
                             diff_proc.stderr.decode())
        self._diff_data_json = diff_proc.stdout.decode()
        self._diff_json = json.loads(self._diff_data_json)


    @classmethod
    def from_diff(cls, diff: Diff, suffix: Optional[str] = None):
        with NamedTemporaryFile(suffix=suffix) as pre_diff, \
             NamedTemporaryFile(suffix=suffix) as post_diff:
            pre_diff.write(diff.a_blob.data_stream.read())
            pre_diff.flush()
            post_diff.write(diff.b_blob.data_stream.read())
            post_diff.flush()
            obj = cls(pre_diff.name, post_diff.name)
        return obj
