# Generated by Django 4.2.16 on 2025-02-12 15:41

from django.db import migrations

def repository_host_to_node(apps, schema_editor):
    Node = apps.get_model("survey", "Node")
    Project = apps.get_model("survey", "Project")
    for project in Project.objects.all():
        try:
            node = Node.objects.get(hostname = Project.repository_host)
        except:
            node = Node(hostname = project.repository_host)
            node.save()
        project.host_node = node
        project.save()

class Migration(migrations.Migration):

    dependencies = [
        ('survey', '0026_node_alter_faq_weight_node_unique_node_names_and_more'),
    ]

    operations = [
        migrations.RunPython(repository_host_to_node)
    ]
