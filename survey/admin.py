from django.contrib import admin

from treebeard.admin import TreeAdmin
from treebeard.forms import movenodeform_factory

from .models import Committer, Project, Commit, Response, ProjectCommitter, ChangeReason, FAQ, Node

# Register your models here.

admin.site.register(Node)

@admin.register(FAQ)
class FAQAdmin(admin.ModelAdmin):
    fields = ['weight', 'question', 'answer']

    list_display = ['question', 'weight']
    search_fields = ['question', 'answer']

@admin.register(ProjectCommitter)
class ProjectCommitterAdmin(admin.ModelAdmin):
    readonly_fields = ['project', 'committer', 'initial_commit', 'maintainer_survey_response']
    fields = readonly_fields + ['response_tags']

    list_display = ['committer', 'project_owner', 'project_name']

    @admin.display(description='Owner')
    def project_owner(self, obj):
        return obj.project.owner

    @admin.display(description='Project')
    def project_name(self, obj):
        return obj.project.name


@admin.register(Committer)
class CommitterAdmin(admin.ModelAdmin):
    fields = ['username', 'initial_contact_date', 'last_contact_date', 'consent_timestamp', 'opt_out', 'projects', 'initial_survey_response', 'should_contact']
    readonly_fields = fields

    list_display = ['username', 'last_contact_date', 'should_contact']

@admin.register(Project)
class ProjectAdmin(admin.ModelAdmin):
    fields = ['add_date', 'remove_date', 'host_node', 'primary_language', 'track_changes', 'typechecker_files', 'committers']
    readonly_fields = fields

    list_display = ['owner', 'name', 'primary_language', 'host_node', 'track_changes']

@admin.register(Commit)
class CommitAdmin(admin.ModelAdmin):
    fields = ['project', 'hash', 'message', 'diff', 'is_relevant']
    readonly_fields = fields

    list_display = ['hash', 'is_relevant', "project_owner", "project_name"]

    @admin.display(description='Owner')
    def project_owner(self, obj):
        return obj.project.owner

    @admin.display(description='Project')
    def project_name(self, obj):
        return obj.project.name

@admin.register(Response)
class ResponseAdmin(admin.ModelAdmin):
    readonly_fields = ['commit', 'committer', 'survey_response']
    fields = readonly_fields + ['tags']

    list_display = ['commit', 'committer', 'project_owner', 'project_name']

    @admin.display(description='Owner')
    def project_owner(self, obj):
        return obj.commit.project.owner

    @admin.display(description='Project')
    def project_name(self, obj):
        return obj.commit.project.name


@admin.register(ChangeReason)
class CodeAdmin(TreeAdmin):
    form = movenodeform_factory(ChangeReason)
