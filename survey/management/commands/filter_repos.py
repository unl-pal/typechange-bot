from django.core.management.base import BaseCommand
from survey.models import Project

class Command(BaseCommand):

    def handle(self, *args, **options):
        projects = Project.objects.filter(
            host_node__hostname="cse-rdyer"
        )

        count = 0
        for project in projects:
            if not project.path.exists():
                continue
            if project.metrics_collected:
                continue

            count += 1
            print(
                project.id,
                project.owner,
                project.name,
                project.track_changes,
                project.metrics_collected,
                project.path
            )

        print("TOTAL:", count)
