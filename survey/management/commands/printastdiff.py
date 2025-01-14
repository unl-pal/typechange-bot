#!/usr/bin/env python
# coding: utf-8

from django.core.management.base import BaseCommand, CommandError
from django.conf import settings

import json

from typing import Optional, Tuple, List

from survey.ast_diff import AstDiff
from pathlib import Path

class Command(BaseCommand):
    help = "Show AST Diff information."

    data_dir: Path = Path(settings.BASE_DIR) / 'test-data'

    def add_arguments(self, parser):
        parser.add_argument('--data-dir',
                            help='Path to language test data directory.',
                            default=self.data_dir,
                            type=Path)
        parser.add_argument('--language',
                            type=str)
        parser.add_argument('--test',
                            type=str)
        pass

    def generate_test_list(self, language: Optional[str], test: Optional[str]) -> List[Tuple[str, str]]:
        if language is not None and test is not None:
            if (self.data_dir / language / test).is_dir():
                return [(language, test)]
            return []
        elif language is not None:
            return list(map(lambda p: (language, p.parts[-1]), Path(self.data_dir / language).iterdir()))
        else:
            tests: List[Tuple[str, str]] = []
            for dir in self.data_dir.iterdir():
                for subdir in dir.iterdir():
                    tests.append((subdir.parts[-2], subdir.parts[-1]))
            return tests

    def handle(self, *args, **options):
        self.data_dir = options['data_dir']
        if options['test'] is not None and options['language'] is None:
            raise CommandError("To specify a test (--test), specify a language as well (--language).")

        for i, (lang, test) in enumerate(self.generate_test_list(options['language'], options['test'])):
            if i > 0:
                print('\f')
            print(f'# Language {lang}, location {test}')
            print()

            dir = self.data_dir / lang / test
            with_annot = dir / f'with.{lang}'
            without_annot = dir / f'without.{lang}'

            print(f'## With annotation at location:')
            print()
            print(f'```{lang}')
            with open(with_annot, 'r') as fh:
                print(fh.read())
            print(f'```')
            print()

            print(f'## Without annotation at location {test}:')
            print()
            print(f'```{lang}')
            with open(without_annot, 'r') as fh:
                print(fh.read())
            print(f'```')
            print()

            print(f"## Removing Annotation at location:")
            diff_remove = AstDiff(with_annot, without_annot, lang)
            print('```json')
            print(json.dumps(diff_remove.actions, indent=4))
            print('```')
            print()

            print(f"## Adding Annotation at location:")
            diff_add = AstDiff(without_annot, with_annot, lang)
            print('```json')
            print(json.dumps(diff_add.actions, indent=4))
            print('```')
            print()
