#!/usr/bin/env python
# coding: utf-8

from django.core.management.base import BaseCommand, CommandError

from survey.models import ChangeReason

import pandas as pd
from pathlib import Path

class Command(BaseCommand):
    help = "Import codes"

    def add_arguments(self, parser):
        parser.add_argument('--codebook',
                            required=True,
                            type=Path,
                            help='Path to codebook CSV')
        parser.add_argument('--code-column-name',
                            default='code',
                            help='Name of code column in codebook')
        parser.add_argument('--description-column-name',
                            default='description',
                            help='Name of description column in codebook')

        parser.add_argument('path',
                            nargs='*',
                            help='Path to import under')

    def handle(self, *arguments,
               codebook=None,
               code_column_name=None,
               description_column_name=None,
               path=None,
               **options):
        parent_node = None
        for i, stage in enumerate(path):
            if i == 0:
                for node in ChangeReason.get_root_nodes():
                    if node.name == stage:
                        parent_node = node
                        break
                else:
                    raise CommandError(f'Root node {stage} does not exist.')
                continue
            for node in parent_node.get_children():
                if node.name == stage:
                    parent_node = node
                    break
            else:
                raise CommandError(f'Node {stage!r} does not exist in {str(parent_node)!r}')
        print(parent_node)

        df = pd.read_csv(codebook)
        for i, row in df.iterrows():
            if row[description_column_name] is None:
                node = parent_node.add_child(name=row[code_column_name])
                print(node)
            else:
                node = parent_node.add_child(name=row[code_column_name], description=row[description_column_name])
                print(node)
