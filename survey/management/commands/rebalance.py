#!/usr/bin/env python
# coding: utf-8

from django.core.management.base import BaseCommand, CommandError

from pathlib import Path

import pandas as pd

from survey.models import Project, Node, DeletedRepository

from survey.tasks import clone_repo

class Command(BaseCommand):
    help = "Rebalance and move projects."

    def add_arguments(self, parser):
        parser.add_argument('--dry-run',
                            help='Perform a dry-run of the rebalance operation (print actions, but do not take them)',
                            default=False,
                            action='store_true')

        parser.add_argument('--data-file',
                            help='Path to CSV file describing a given state.  Needs host, project_count, and enabled columns.  Only possible with `--dry-run\'.',
                            type=Path)
    def calculate_balance_table(self, df):
        df = df.copy()

        nodes = df.enabled.sum()
        projects = df.project_count.sum()

        target = projects // nodes + (1 if (projects % nodes) != 0 else 0)

        df['move_count'] = df.project_count - target

        df.loc[~df.enabled, 'move_count'] = df.loc[~df.enabled, 'project_count']

        df['off_balance'] = df.move_count.div(target).mul(100).convert_dtypes()
        df = df.sort_values(['move_count', 'enabled', 'project_count'], ascending=[False, True, False])

        mean_misbalance = df.off_balance.mean()

        movable_projects = df.loc[df.move_count > 0].move_count.sum()
        available_slots = df.loc[df.move_count < 0].move_count.sum() * -1

        return df, nodes, projects, target, mean_misbalance, movable_projects, available_slots

    def handle(self, *args, **options):
        if options['dry_run'] and options['data_file']:
            state_table = pd.read_csv(options['data_file'])[['host', 'project_count', 'enabled']]
        else:
            node_data = []
            for node in Node.objects.all():
                node_data.append({'host': node.hostname, 'project_count': node.project_set.count(), 'enabled': node.enabled})
            state_table = pd.DataFrame(node_data)

        balance_table, nodes, projects, target, mean_off_balance, excess, available = self.calculate_balance_table(state_table)
        print('Current State:')
        print(balance_table.to_string(index=False))
        print()
        print(f'There are {nodes} nodes, with {projects} total projects.')
        print(f'Each node should have about {target} projects on it.')
        print()
        print(f'There are {excess} excess projects, and {available} available slots.')

        if excess == 0:
            print('Since no excess projects are available, no action will be taken.')
            return 0
        elif excess == available:
            print("Nodes should be balanced at the end.")
        else:
            print("Nodes will be nearly balanced.")

        if options['dry_run'] and options['data_file']:
            return 0

        print()

        movable_data = balance_table.loc[balance_table.move_count > 0]
        available_data = balance_table.loc[balance_table.move_count < 0].sort_values(by='move_count')

        movable_repositories = []

        for i, row in movable_data.iterrows():
            node = Node.objects.get(hostname=row.host)
            for prj in Project.objects.filter(host_node=node).order_by('add_date')[:row.move_count]:
                print(f'Collecting {prj} from {node}.')
                movable_repositories.append(prj)

        print()

        for i, row in available_data.iterrows():
            new_node = Node.objects.get(hostname=row.host)
            needed = -row.move_count
            remaining = min(needed, len(movable_repositories))
            projects_to_move = movable_repositories[:remaining]
            for prj in projects_to_move:
                deletion_record = DeletedRepository(node=prj.host_node, owner=prj.owner, name=prj.name, reason=DeletedRepository.DeletionReason.REBALANCE)
                if prj.data_subdir is not None:
                    deletion_record.subdir = prj.data_subdir
                print(f'Created deletion record for {prj} on {prj.host_node}.')
                if not options['dry_run']:
                    deletion_record.save()
                prj.host_node = new_node
                print(f'Changed {prj} node to {new_node}')
                if not options['dry_run']:
                    prj.data_subdir = None
                    prj.save()
                print(f'Fetching {prj} on {new_node}')
                if not options['dry_run']:
                    clone_repo.apply_async([prj.id], queue=new_node.hostname)
