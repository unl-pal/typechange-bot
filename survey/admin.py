from django.contrib import admin

from treebeard.admin import TreeAdmin
from treebeard.forms import movenodeform_factory

from .models import Committer, Project, Commit, Response, ProjectCommitter, ChangeReason, FAQ, Node

# Register your models here.

admin.site.register(FAQ)
admin.site.register(Node)

@admin.register(ProjectCommitter)
class ProjectCommitterAdmin(admin.ModelAdmin):
    readonly_fields = ['project', 'committer', 'initial_commit', 'maintainer_survey_response']
    fields = readonly_fields + ['response_tags']

@admin.register(Committer)
class CommitterAdmin(admin.ModelAdmin):
    fields = ['username', 'initial_contact_date', 'last_contact_date', 'consent_timestamp', 'opt_out', 'projects', 'initial_survey_response', 'should_contact']
    readonly_fields = fields

@admin.register(Project)
class ProjectAdmin(admin.ModelAdmin):
    fields = ['add_date', 'remove_date', 'host_node', 'primary_language', 'track_changes', 'typechecker_files', 'committers']
    readonly_fields = fields

@admin.register(Commit)
class CommitAdmin(admin.ModelAdmin):
    fields = ['project', 'hash', 'message', 'diff', 'is_relevant']
    readonly_fields = fields

@admin.register(Response)
class ResponseAdmin(admin.ModelAdmin):
    readonly_fields = ['commit', 'committer', 'survey_response']
    fields = readonly_fields + ['tags']

@admin.register(ChangeReason)
class CodeAdmin(TreeAdmin):
    form = movenodeform_factory(ChangeReason)
