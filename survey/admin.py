from django.contrib import admin

from .models import Committer, Project, Commit, Response

# Register your models here.

admin.site.register(Committer)
admin.site.register(Project)
admin.site.register(Commit)
admin.site.register(Response)
