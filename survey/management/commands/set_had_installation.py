#!/usr/bin/env python
# coding: utf-8

from django.core.management.base import BaseCommand
from survey.models import Project

class Command(BaseCommand):
    help = "Set had_installation for installed projects."

    def handle(self, *args, **options):
        for project in Project.objects.filter(host_node__isnull=False):
            project.had_installation = True
            project.save()
