# Generated by Django 4.2.16 on 2025-07-15 01:04

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('survey', '0073_project_metrics_collected_metricscommit_and_more'),
    ]

    operations = [
        migrations.AlterField(
            model_name='changereason',
            name='name',
            field=models.CharField(max_length=32),
        ),
    ]
