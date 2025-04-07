from django.core.management.base import BaseCommand

from survey.models import Node

class Command(BaseCommand):
    help = "List projects by node."

    def add_arguments(self, parser):
        parser.add_argument('--node',
                            type=str,
                            help="Node name to show repos for.")

    def handle(self, *args, **options):

        if options['node'] is not None:
            nodes = [Node.objects.get(host_name=options['node'])]
        else:
            nodes = list(Node.objects.all())

        for node in nodes:
            print(f" - {node.hostname} ({node.last_active}, {node.count_projects_on})")
            for project in node.project_set.all():
                print(f"    - {project}, {'Tracking' if project.track_changes else 'Not Tracking'}, {project.primary_language}")
