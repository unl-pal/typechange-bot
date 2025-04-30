from django.contrib import admin

from treebeard.admin import TreeAdmin
from treebeard.forms import movenodeform_factory

from .models import Committer, Project, Commit, Response, ProjectCommitter, ChangeReason, FAQ, Node, InitialReason, MaintainerReason, DeletedRepository

from .tasks import delete_repo, fetch_project

# Register your models here.

@admin.register(DeletedRepository)
class DeletedRepoAdmin(admin.ModelAdmin):
    readonly_fields = ['node', 'owner', 'name', 'reason', 'deleted_on']

    list_display = readonly_fields
    list_display_links = ['owner', 'name', 'reason']
    list_filter = readonly_fields

    actions = ['delete_on_workers']

    def has_delete_permissions(self, request, obj=None):
        return False

    def get_actions(self, request):
        actions = super(DeletedRepoAdmin, self).get_actions(request)
        del actions['delete_selected']
        return actions

    @admin.action(description="Delete Repositories on Workers")
    def delete_on_workers(self, request, queryset):
        for repo in queryset.all():
            delete_repo.apply_async([repo.pk], queue=repo.node.hostname)

class ProjectInline(admin.StackedInline):
    model = Project
    extra = 0
    can_delete = False
    show_change_link = True

    def has_add_permission(self, request, obj):
        return False

@admin.register(Node)
class NodeAdmin(admin.ModelAdmin):
    readonly_fields = ['hostname', 'count_projects_on', 'last_active']
    fields = readonly_fields + ['enabled', 'use_datadir_subdirs']

    inlines = [ProjectInline]

    list_display = ['hostname', 'last_active', 'enabled', 'count_projects_on']
    list_filter = ['hostname', 'last_active', 'enabled']

@admin.register(FAQ)
class FAQAdmin(admin.ModelAdmin):
    fields = ['weight', 'display', 'question', 'answer']

    list_display = ['weight', 'display', 'question', 'answer']
    list_display_links = ['question']

    search_fields = ['question', 'answer']

class ResponseInline(admin.StackedInline):
    model = Response
    extra = 0
    can_delete = False
    show_change_link = True

    readonly_fields = ['committer', 'survey_response']
    fields = readonly_fields + ['tags']

    def has_add_permission(self, request, obj):
        return False


@admin.register(ProjectCommitter)
class ProjectCommitterAdmin(admin.ModelAdmin):
    readonly_fields = ['project', 'committer', 'initial_commit', 'is_maintainer', 'maintainer_survey_response']
    fields = readonly_fields + ['tags']

    inlines = [ResponseInline]

    list_display = ['committer', 'disp_project', 'is_maintainer']
    list_display_links = ['committer']
    list_filter = ['is_maintainer', 'committer__username']

    search = ['survey_response']

    @admin.display(description='Project')
    def disp_project(self, obj):
        return str(obj.project)

@admin.register(Committer)
class CommitterAdmin(admin.ModelAdmin):
    readonly_fields = ['username', 'initial_contact_date', 'last_contact_date', 'consent_timestamp', 'consent_project_commit', 'opt_out', 'projects', 'initial_survey_response', 'should_contact']
    fields = readonly_fields + ['tags']

    list_display = ['username', 'last_contact_date', 'should_contact']
    list_filter = ['last_contact_date']

    @admin.display(boolean=True,
                   description="Contactable?")
    def should_contact(self, obj):
        return obj.should_contact

class ProjectCommitterInline(admin.TabularInline):
    model = ProjectCommitter
    extra = 0
    can_delete = False
    show_change_link = True

    readonly_fields = ['committer', 'is_maintainer', 'should_contact']
    fields = readonly_fields

    @admin.display(boolean=True,
                   description="Contactable?")
    def should_contact(self, obj):
        return obj.committer.should_contact

    def has_add_permission(self, request, obj):
        return False

@admin.register(Project)
class ProjectAdmin(admin.ModelAdmin):
    fields = ['add_date', 'remove_date', 'host_node', 'language', 'track_changes', 'typechecker_files', 'has_language_files', 'has_typechecker_configuration', 'annotations_detected']
    readonly_fields = fields

    inlines = [ProjectCommitterInline]

    list_display = ['owner', 'name', 'language', 'host_node', 'track_changes', 'has_language_files', 'has_typechecker_configuration', 'annotations_detected']
    list_display_links = ['owner', 'name']
    list_filter = ['track_changes', 'has_language_files', 'has_typechecker_configuration', 'annotations_detected', 'language', 'host_node']

    actions = ['delete_repos', 'force_fetch']

    def has_delete_permissions(self, request, obj=None):
        return False

    def get_actions(self, request):
        actions = super(ProjectAdmin, self).get_actions(request)
        del actions['delete_selected']
        return actions

    @admin.action(description="Delete Selected Projects' Repositories")
    def delete_repos(self, request, queryset):
        for proj in queryset.all():
            del_rec = DeletedRepository(node=proj.host_node,
                                        owner=proj.owner,
                                        name=proj.name,
                                        reason=DeletedRepository.DeletionReason.MANUAL)
            del_rec.save()

    @admin.action(description="Fetch Selected Projects")
    def force_fetch(self, request, queryset):
        for proj in queryset.all():
            if proj.host_node is not None:
                fetch_project.apply_async([proj.pk], queue=proj.host_node.hostname)
            else:
                fetch_project.apply_async([proj.pk])

@admin.register(Commit)
class CommitAdmin(admin.ModelAdmin):
    fields = ['project', 'hash', 'message', 'diff', 'is_relevant', 'relevance_type']
    readonly_fields = fields

    inlines = [ResponseInline]

    list_display = ["project_owner", "project_name", 'hash', 'is_relevant', 'relevance_type']
    list_display_links = list_display[:3]

    list_filter = ['relevance_type']

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
    list_filter = ['committer']

    search = ['survey_response']

    @admin.display(description='Owner')
    def project_owner(self, obj):
        return obj.commit.project.owner

    @admin.display(description='Project')
    def project_name(self, obj):
        return obj.commit.project.name

@admin.register(ChangeReason)
class ChangeReasonAdmin(TreeAdmin):
    form = movenodeform_factory(ChangeReason)

    search_fields = ['description']

@admin.register(InitialReason)
class InitialReasonAdmin(TreeAdmin):
    form = movenodeform_factory(InitialReason)

    search_fields = ['description']

@admin.register(MaintainerReason)
class MaintainerReasonAdmin(TreeAdmin):
    form = movenodeform_factory(MaintainerReason)

    search_fields = ['description']
