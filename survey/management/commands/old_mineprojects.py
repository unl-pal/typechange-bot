#!/usr/bin/env python
# coding: utf-8

from django.core.management.base import BaseCommand, CommandError

from django.conf import settings

from survey.project_mining_utils import get_git_hub, g as github
from github import GithubException

import git
from tempfile import TemporaryDirectory
from pathlib import Path

import ast

class TypeAnnotationDetectionVisitor(ast.NodeVisitor):
    def visitFunctionDef(self, node):
        if node.returns is not None:
            return True

        for arg in (node.args.posonlyargs + node.args.args + node.args.kwonlyargs):
            if arg.annotation is not None:
                return True

        return super().generic_visit(node)

    def visitAnnAssign(self, node):
        return True

class Command(BaseCommand):
    help = "Mine GitHub projects."

    def has_typechecker_configuration(self, repository, language):
        if language == 'python':
            for filename in  ['mypy.ini', '.mypy.ini', '.pyre_configuration', '.pytype.toml', 'pyrightconfig.json']:
                try:
                    repository.get_contents(filename)
                    return True
                except:
                    continue
            return False
        if language == 'typescript':
            for filename in ['tsconfig.json', 'jsconfig.json']:
                try:
                    repository.get_contents(filename)
                    return True
                except:
                    continue
            return False
        # TODO Handle Ruby, R, PHP
        return False

    def has_annotations(self, repository, language):
        if language == 'typescript':
            return True
        if language == 'python':
            with TemporaryDirectory() as temp:
                git.Repo.clone_from(f'https://github.com/{repository.full_name}', temp)
                for filename in Path(temp).glob('**/*.py'):
                    try:
                        with open(filename, 'r') as fh:
                            tree = ast.parse(fh.read())
                        visitor = TypeAnnotationDetectionVisitor()
                        if visitor.visit(tree):
                            return True
                    except:
                        continue
            return False
        # TODO Handle Ruby, R, PHP
        return False

    def add_arguments(self, parser):
        parser.add_argument('--apikey',
                            help="GitHub API Key (override settings)",
                            type=str)
        parser.add_argument('language',
                            help='Language to search',
                            type=str)
        parser.add_argument('--min-stars',
                            help='Minimum stars',
                            type=int,
                            default=2)
        parser.add_argument('--min-contributors',
                            help='Minimum number of contributors',
                            type=int,
                            default=1)
        parser.add_argument('--min-contributions',
                            help='Minimum contributions (commits in weeks)',
                            nargs=2,
                            metavar=('COMMITS', 'WEEKS'),
                            type=int,
                            default=[7, 1])
        parser.add_argument('--check-annotations',
                            help='Check for annotations in candidate projects.',
                            default=False,
                            action='store_true')
        parser.add_argument('--check-config',
                            help="Check for typechecker configuration.",
                            default=False,
                            action='store_true')
        parser.add_argument('--outfile',
                            help="Data output file",
                            type=Path)

    def handle(self, *args, **options):
        if options['apikey'] is None:
            gh = github
        else:
            gh = get_git_hub(options['apikey'])

        fh = None
        if options['outfile']:
            if options['outfile'].exists():
                fh = open(options['outfile'], 'a', buffering=1)
            else:
                fh = open(options['outfile'], 'w', buffering=1)
                fh.write("repo,language,configured_typechecker,annotations_detected,stars\n")

        search_string = f'language:{options["language"].lower()}'

        print("repo,language,configured_typechecker,annotations_detected,stars")

        repos = gh.search_repositories(query=search_string, sort='stars', order='desc')
        for project in repos:
            if project.stargazers_count < options['min_stars']:
                continue

            meets_participation_requirement = sum(project.get_stats_participation().all[-options['min_contributions'][1]:]) >= options['min_contributions'][0]
            if not meets_participation_requirement:
                continue

            has_typechecker = self.has_typechecker_configuration(project, options["language"].lower()) if options['check_config'] else False
            has_annotations = self.has_annotations(project, options["language"].lower()) if options['check_annotations'] else False

            out_line = f'{project.full_name},{options["language"].lower()},{has_typechecker},{has_annotations},{project.stargazers_count}'
            print(out_line)
            if fh:
                fh.write(out_line + '\n')
