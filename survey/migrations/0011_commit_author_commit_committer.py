# Generated by Django 4.2.16 on 2024-12-03 16:16

from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):

    dependencies = [
        ('survey', '0010_project_primary_language_project_track_changes_and_more'),
    ]

    operations = [
        migrations.AddField(
            model_name='commit',
            name='author',
            field=models.ForeignKey(editable=False, null=True, on_delete=django.db.models.deletion.CASCADE, related_name='author', to='survey.projectcommitter'),
        ),
        migrations.AddField(
            model_name='commit',
            name='committer',
            field=models.ForeignKey(editable=False, null=True, on_delete=django.db.models.deletion.CASCADE, related_name='pusher', to='survey.projectcommitter'),
        ),
    ]
