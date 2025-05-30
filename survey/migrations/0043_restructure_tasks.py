# Generated by Django 4.2.16 on 2025-02-12 20:52

from django.db import migrations

def update_task_names(apps, schema_editor):
    PeriodicTask = apps.get_model('django_celery_beat', 'PeriodicTask')
    for task in PeriodicTask.objects.all():
        task.task = task.task.replace('survey.periodic_tasks', 'survey.tasks.periodic')
        task.save()

class Migration(migrations.Migration):

    dependencies = [
        ('survey', '0042_install_health_check'),
    ]

    operations = [
        migrations.RunPython(update_task_names)
    ]
