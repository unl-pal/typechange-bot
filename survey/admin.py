from django.contrib import admin

from treebeard.admin import TreeAdmin
from treebeard.forms import movenodeform_factory

from .models import Committer, Project, Commit, Response, ProjectCommitter, ChangeReason, FAQ, Node, InitialResponseCode

# Register your models here.

class ProjectInline(admin.StackedInline):
    model = Project
    extra = 0
    can_delete = False
    show_change_link = True

    def has_add_permision(self, obj):
        return False

@admin.register(Node)
class NodeAdmin(admin.ModelAdmin):
    readonly_fields = ['hostname', 'count_projects_on']

    inlines = [ProjectInline]

    list_display = ['hostname', 'count_projects_on']

@admin.register(FAQ)
class FAQAdmin(admin.ModelAdmin):
    fields = ['weight', 'question', 'answer']

    list_display = ['weight', 'question', 'answer']
    list_display_links = ['question']

    search_fields = ['question', 'answer']

@admin.register(ProjectCommitter)
class ProjectCommitterAdmin(admin.ModelAdmin):
    readonly_fields = ['project', 'committer', 'initial_commit', 'maintainer_survey_response']
    fields = readonly_fields + ['response_tags']

    list_display = ['project_owner', 'project_name', 'committer']
    list_display_links = ['committer']

    @admin.display(description='Owner')
    def project_owner(self, obj):
        return obj.project.owner

    @admin.display(description='Project')
    def project_name(self, obj):
        return obj.project.name


@admin.register(Committer)
class CommitterAdmin(admin.ModelAdmin):
    readonly_fields = ['username', 'initial_contact_date', 'last_contact_date', 'consent_timestamp', 'opt_out', 'projects', 'initial_survey_response', 'should_contact']
    fields = readonly_fields + ['tags']

    list_display = ['username', 'last_contact_date', 'should_contact']

@admin.register(Project)
class ProjectAdmin(admin.ModelAdmin):
    fields = ['add_date', 'remove_date', 'host_node', 'primary_language', 'track_changes', 'typechecker_files', 'committers']
    readonly_fields = fields

    list_display = ['owner', 'name', 'primary_language', 'host_node', 'track_changes']
    list_display_links = ['owner', 'name']


@admin.register(Commit)
class CommitAdmin(admin.ModelAdmin):
    fields = ['project', 'hash', 'message', 'diff', 'is_relevant']
    readonly_fields = fields

    list_display = ["project_owner", "project_name", 'hash', 'is_relevant']
    list_display_links = list_display[:3]

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

    list_display = ['project_owner', 'project_name', 'commit', 'committer']
    list_display_links = list_display[:3]

    @admin.display(description='Owner')
    def project_owner(self, obj):
        return obj.commit.project.owner

    @admin.display(description='Project')
    def project_name(self, obj):
        return obj.commit.project.name

@admin.register(ChangeReason)
class ChangeReasonAdmin(TreeAdmin):
    form = movenodeform_factory(ChangeReason)

@admin.register(InitialResponseCode)
class InitialResponseCodeAdmin(TreeAdmin):
    form = movenodeform_factory(InitialResponseCode)
