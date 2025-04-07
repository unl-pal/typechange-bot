from django.core.management.base import BaseCommand, CommandError

from survey.models import Project, Node, DeletedRepository
from survey.tasks import fetch_project

class Command(BaseCommand):
    help = "Move project(s) to a different node."

    def add_arguments(self, parser):
        parser.add_argument('--to',
                            type=str,
                            help='Node to move project(s) to.',
                            required=True)
        parser.add_argument('--from',
                            type=str,
                            help='Node to move project(s) off of.')
        parser.add_argument('--project',
                            type=str,
                            help='Project to move (by name).')
        parser.add_argument('--dry-run',
                            help='Perform a dry-run of the rebalance operation (print actions, but do not take them)',
                            default=False,
                            action='store_true')

    def handle(self, *args, **options):

        if (options['from'] is None and options['project'] is None) or (options['from'] is not None and options['project'] is not None):
            raise CommandError('You must provide exactly one of --from and --project.')

        projects = []

        if options['from'] is not None:
            node = Node.objects.get(hostname=options['from'])
            projects = node.project_set.all()
        else:
            owner, name = options['project'].split('/')
            projects = [Project.objects.get(owner=owner, name=name)]

        to_node = Node.objects.get(hostname=options['to'])

        for project in projects:
            deletion_record = DeletedRepository(node=project.host_node,
                                                owner=project.owner,
                                                name=project.name,
                                                reason=DeletedRepository.DeletionReason.MANUAL)
            if project.data_sub_directory is not None:
                deletion_record.subdir = project.data_sub_directory

            if not options['dry_run']:
                deletion_record.save()
                project.host_node = to_node
                project.data_sub_directory = None
                project.save()
                fetch_project.apply_async([project.id], queue=to_node.hostname)

