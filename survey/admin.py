from django.contrib import admin

from .models import Committer, Project, Commit, Response, ProjectCommitter

# Register your models here.

admin.site.register(ProjectCommitter)

@admin.register(Committer)
class CommitterAdmin(admin.ModelAdmin):
    fields = ['username', 'initial_contact_date', 'last_contact_date', 'consent_timestamp', 'opt_out', 'projects']
    readonly_fields = fields

@admin.register(Project)
class ProjectAdmin(admin.ModelAdmin):
    fields = ['add_date', 'remove_date', 'committers']
    readonly_fields = fields

@admin.register(Commit)
class CommitAdmin(admin.ModelAdmin):
    fields = ['project', 'hash', 'message', 'diff']
    readonly_fields = fields

@admin.register(Response)
class ResponseAdmin(admin.ModelAdmin):
    fields = ['commit', 'committer', 'survey_response']
    readonly_fields = ['commit', 'committer', 'survey_response']
