# Generated by Django 4.2.16 on 2025-05-15 17:51

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('survey', '0068_committer_initial_contact_location'),
    ]

    operations = [
        migrations.AlterField(
            model_name='commit',
            name='is_relevant',
            field=models.BooleanField(default=False),
        ),
    ]
