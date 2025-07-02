from django.contrib import admin
from django.urls import reverse
from django.utils.html import format_html

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
    list_filter = ['node', 'reason', 'deleted_on']

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

    search_fields = ['project__owner', 'project__name', 'committer__username', 'maintainer_survey_response']
    list_display = ['committer', 'disp_project', 'is_maintainer']
    list_display_links = ['committer']
    list_filter = ['is_maintainer']

    @admin.display(description='Project')
    def disp_project(self, obj):
        return str(obj.project)

class HasConsentedFilter(admin.SimpleListFilter):
    title = "consented?"
    parameter_name='has_consented'

    def lookups(self, request, model_admin):
        return(('yes', 'Yes'),
               ('no', 'No'))

    def queryset(self, request, query_set):
        if self.value() == 'yes':
            return query_set.filter(consent_timestamp__isnull=False)
        elif self.value() == 'no':
            return query_set.filter(consent_timestamp__isnull=True)

@admin.register(Committer)
class CommitterAdmin(admin.ModelAdmin):
    readonly_fields = ['username', 'initial_contact_date', 'last_contact_date', 'consented', 'consent_timestamp', 'consent_project_commit', 'opt_out', 'projects', 'initial_survey_response', 'should_contact']
    fields = readonly_fields + ['tags']

    search_fields = ['username', 'project__name', 'project__owner']
    list_display = ['username', 'consented', 'last_contact_date', 'should_contact']
    list_filter = [HasConsentedFilter, 'last_contact_date']

    @admin.display(boolean=True,
                   description="Contactable?")
    def should_contact(self, obj):
        return obj.should_contact

    @admin.display(boolean=True,
                   description="Consented?")
    def consented(self, obj):
        return obj.consented

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

class IsInstalledFilter(admin.SimpleListFilter):
    title = "installed?"
    parameter_name='is_installed'

    def lookups(self, request, model_admin):
        return(('yes', 'Yes'),
               ('no', 'No'))

    def queryset(self, request, query_set):
        if self.value() == 'yes':
            return query_set.filter(installation_id__isnull=False)
        elif self.value() == 'no':
            return query_set.filter(installation_id__isnull=True)

@admin.register(Project)
class ProjectAdmin(admin.ModelAdmin):
    fields = ['gh_url', 'add_date', 'remove_date', 'host_node', 'language', 'track_changes', 'typechecker_files', 'has_language_files', 'has_typechecker_configuration', 'annotations_detected']
    readonly_fields = fields

    inlines = [ProjectCommitterInline]

    search_fields = ['owner', 'name']
    list_display = ['owner', 'name', 'language', 'host_node', 'is_installed', 'track_changes', 'has_language_files', 'has_typechecker_configuration', 'annotations_detected']
    list_display_links = ['owner', 'name']
    list_filter = ['track_changes', IsInstalledFilter, 'has_language_files', 'has_typechecker_configuration', 'annotations_detected', 'language', 'host_node']

    actions = ['delete_repos', 'force_fetch']

    @admin.display(description="GitHub URL")
    def gh_url(self, obj):
        return format_html("<a target='_blank' href='{url}'>{url}</a>", url=obj.clone_url)

    @admin.display(boolean=True,
                   description="Installed?")
    def is_installed(self, obj):
        return obj.is_installed

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
                                        subdir=proj.data_subdir,
                                        owner=proj.owner,
                                        name=proj.name,
                                        reason=DeletedRepository.DeletionReason.MANUAL)
            del_rec.save()
            proj.host_node = None
            proj.data_subdir = None
            proj.save()

    @admin.action(description="Fetch Selected Projects")
    def force_fetch(self, request, queryset):
        for proj in queryset.all():
            if proj.host_node is not None:
                fetch_project.apply_async([proj.pk], queue=proj.host_node.hostname)
            else:
                fetch_project.apply_async([proj.pk])

@admin.register(Commit)
class CommitAdmin(admin.ModelAdmin):
    fields = ['gh_url', 'project', 'hash', 'message', 'diff', 'is_relevant', 'relevance_type', 'relevant_change_file', 'relevant_change_line', 'author', 'committer']
    readonly_fields = fields

    inlines = [ResponseInline]

    search_fields = ['project__owner', 'project__name', 'committer__username', 'author__username']
    list_display = ["project_owner", "project_name", 'hash', 'is_relevant', 'relevance_type']
    list_display_links = list_display[:3]

    list_filter = ['is_relevant', 'relevance_type']

    @admin.display(description="GitHub URL")
    def gh_url(self, obj):
        return format_html("<a target='_blank' href='{url}'>{url}</a>", url=obj.public_url)

    @admin.display(description='Owner')
    def project_owner(self, obj):
        return obj.project.owner

    @admin.display(description='Project')
    def project_name(self, obj):
        return obj.project.name

class IsInitialSurveyFilter(admin.SimpleListFilter):
    title = "Initial Survey?"
    parameter_name='is_initial_survey'

    def lookups(self, request, model_admin):
        return(('yes', 'Yes'),
               ('no', 'No'))

    def queryset(self, request, query_set):
        if self.value() == 'no':
            return query_set.exclude(survey_response__icontains='### When declaring')
        elif self.value() == 'yes':
            return query_set.filter(survey_response__icontains='### When declaring')

@admin.register(Response)
class ResponseAdmin(admin.ModelAdmin):
    readonly_fields = ['commit', 'committer', 'survey_response']
    fields = readonly_fields + ['tags']

    search_fields = ['commit__project__owner', 'commit__project__name', 'committer__committer__username', 'survey_response']
    list_display = ['project_owner', 'project_name', 'link_to_commit', 'link_to_committer']
    list_display_links = list_display[:3]

    list_filter = [IsInitialSurveyFilter]

    @admin.display(description='Owner')
    def project_owner(self, obj):
        return obj.commit.project.owner

    @admin.display(description='Project')
    def project_name(self, obj):
        return obj.commit.project.name

    @admin.display(description='Commit')
    def link_to_commit(self, obj):
        link = reverse("admin:survey_commit_change", args=[obj.commit.id])
        return format_html('<a href="{}">{}</a>', link, obj.commit)

    @admin.display(description='Committer')
    def link_to_committer(self, obj):
        link = reverse("admin:survey_projectcommitter_change", args=[obj.committer.id])
        return format_html('<a href="{}">{}</a>', link, obj.committer)

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
