from django.db import models
from django.conf import settings
from github import Github, Auth
import github
from treebeard.ns_tree import NS_Node
from markdownx.models import MarkdownxField

from django.utils import timezone
from datetime import timedelta

from pathlib import Path

application_auth = Auth.AppAuth(settings.GITHUB_APP_ID, settings.GITHUB_APP_KEY)

from socket import gethostname
CURRENT_HOST = gethostname()

# Create your models here.

class Node(models.Model):
    hostname = models.CharField('Host Name', max_length=200, editable=False, null=False)
    last_active = models.DateTimeField(auto_now_add=True)
    enabled = models.BooleanField(default=True, null=False)

    def __str__(self):
        return self.hostname

    @property
    def count_projects_on(self):
        return self.project_set.count()

    class Meta:
        constraints = [
            models.UniqueConstraint(fields=['hostname'], name='unique_node_names')
        ]
        ordering = ('hostname', )
        verbose_name = "Worker Node"

class DeletedRepository(models.Model):
    class DeletionReason(models.TextChoices):
        REBALANCE = ('RB', "Rebalance")
        RENAME = ('RN', "Rename")
        UNUSED = ('UN', "Unused")
        IRRELEVANT = ('IR', "Irrelevant")
        MANUAL = ('MN', "Manual")

    node = models.ForeignKey(Node, on_delete=models.CASCADE, editable=False)
    owner = models.CharField(max_length=200, editable=False)
    name = models.CharField(max_length=200, editable=False)

    reason = models.CharField(max_length=2,
                              choices=DeletionReason.choices,
                              default=DeletionReason.REBALANCE)

    deleted_on = models.DateTimeField(auto_now_add=True, editable=False)

    class Meta:
        verbose_name_plural = 'Deleted Repositories'

class ChangeReason(NS_Node):
    name = models.CharField(max_length=20, null=False, blank=False)
    description = models.TextField(null=True, blank=True)

    def __str__(self):
        if self.get_parent() is None:
            return self.name
        return f"{self.get_parent()} → {self.name}"

    class Meta:
        verbose_name = "Reason for Change"

class InitialReason(NS_Node):
    name = models.CharField(max_length=20, null=False, blank=False)
    description = models.TextField(null=True, blank=True)

    def __str__(self):
        if self.get_parent() is None:
            return self.name
        return f"{self.get_parent()} → {self.name}"

    class Meta:
        verbose_name = "Initial Response Code"

class MaintainerReason(NS_Node):
    name = models.CharField(max_length=20, null=False, blank=False)
    description = models.TextField(null=True, blank=True)

    def __str__(self):
        if self.get_parent() is None:
            return self.name
        return f"{self.get_parent()} → {self.name}"

    class Meta:
        verbose_name = "Maintainer Response Codes"


class Committer(models.Model):
    username = models.CharField(max_length=200)
    email_address = models.EmailField(null=True)
    initial_contact_date = models.DateTimeField("initial contact date", auto_now_add=True, editable=False)
    last_contact_date = models.DateTimeField("date of last contact", auto_now=True, editable=False)
    consent_timestamp = models.DateTimeField("date of consent", null=True, editable=False)
    consent_project_commit = models.TextField("location of consent", null=True, blank=True, editable=True)
    opt_out = models.DateTimeField("date of opt-out", null=True, blank=True, editable=False)
    removal = models.DateTimeField("date of removal request & processing", null=True, blank=True, editable=False)
    projects = models.ManyToManyField('Project', through='ProjectCommitter')
    initial_survey_response = models.TextField('response to initial survey', null=True, blank=True, editable=False)
    tags = models.ManyToManyField(InitialReason)

    @property
    def should_contact(self) -> bool:
        if self.opt_out is not None or self.removal is not None:
            return False
        # TODO: Change back to 24 hours
        return self.consent_timestamp is not None and self.last_contact_date < (timezone.now() - timedelta(minutes=5))

    def __str__(self):
        return f'{self.username}'

class Project(models.Model):
    owner = models.CharField('project owner', max_length=200, editable=False)
    name = models.CharField('project name', max_length=200, editable=False)
    installation_id = models.IntegerField('installation ID', editable=False, null=True)
    primary_language = models.CharField('primary programming language', max_length=30, editable=False, null=True)
    track_changes = models.BooleanField('are we tracking this project\'s changes?', null=False, editable=False, default=False)
    typechecker_files = models.TextField('list of typechecker configuration files detected', null=True, editable=False)
    add_date = models.DateTimeField('project add date', auto_now_add=True, editable=False)
    remove_date = models.DateTimeField('project remove date', blank=True, null=True, editable=False)
    committers = models.ManyToManyField(Committer, through='ProjectCommitter')
    host_node = models.ForeignKey(Node, on_delete=models.CASCADE, editable=False, null=True)

    _repo = None
    _gh_app = None

    def __str__(self):
        return f'{self.owner}/{self.name}'

    @property
    def clone_url(self):
        return f'https://github.com/{self.owner}/{self.name}'

    @property
    def gh_app(self) -> github.Github:
        if self._gh_app is not None:
            return self._gh_app
        self._gh_app = Github(auth=Auth.AppInstallationAuth(application_auth, self.installation_id))
        return self._gh_app

    @property
    def gh(self) -> github.Repository.Repository:
        if self._repo is not None:
            return self._repo
        self._repo = self.gh_app.get_repo(f'{self.owner}/{self.name}')
        return self._repo

    @property
    def path(self) -> Path:
        return settings.DATA_DIR / self.owner / self.name

    @property
    def is_on_current_node(self) -> bool:
        return self.host_node.hostname == CURRENT_HOST

    class Meta:
        constraints = [
            models.UniqueConstraint(fields=['owner', 'name'], name="unique_project_name")
        ]

class ProjectCommitter(models.Model):
    project = models.ForeignKey(Project, on_delete=models.CASCADE, editable=False)
    committer = models.ForeignKey(Committer, on_delete=models.CASCADE, editable=False)
    is_maintainer = models.BooleanField(null=True)
    has_been_emailed = models.BooleanField(default=False, null=False)
    maintainer_survey_response = models.TextField('response to maintainer survey', null=True, blank=True, editable=False)
    initial_commit = models.ForeignKey('Commit', on_delete=models.CASCADE, editable=False, null=True)
    tags = models.ManyToManyField (MaintainerReason)

    def __str__(self):
        return f'{self.committer}'

    class Meta:
        constraints = [
            models.UniqueConstraint(fields=['project', 'committer'], name='unique_project_committer')
        ]
        verbose_name = "Project Committer"

class Commit(models.Model):
    class RelevanceType(models.TextChoices):
        IRRELEVANT = ('IR', "Irrelevant")
        ADDED = ('AD', 'Added')
        REMOVED = ('RM', 'Removed')
        CHANGED = ('CH', 'Changed')

    project = models.ForeignKey(Project, on_delete=models.CASCADE, editable=False)
    hash = models.CharField(max_length=40, editable=False)
    message = models.TextField(blank=True, editable=False)
    diff = models.TextField(blank=True, editable=False)
    is_relevant = models.BooleanField(default=True)
    relevance_type = models.CharField(max_length=2,
                                      choices=RelevanceType.choices,
                                      default=RelevanceType.IRRELEVANT)

    created_at = models.DateTimeField(auto_now_add=True, editable=False)
    author = models.ForeignKey(ProjectCommitter, on_delete=models.SET_NULL, editable=False, null=True, related_name='author')
    committer = models.ForeignKey(ProjectCommitter, on_delete=models.SET_NULL, editable=False, null=True, related_name='pusher')

    _commit = None

    class Meta:
        constraints = [
            models.UniqueConstraint(fields=['project', 'hash'], name='unique_commit_hash_in_project')
        ]

    def __str__(self):
        return f'{self.hash}'

    @property
    def public_url(self):
        return f'{self.project.clone_url}/commit/{self.hash}'

    @property
    def gh(self):
        if self._commit is not None:
            return self._commit
        self._commit = self.project.gh.get_commit(sha=self.hash)
        return self._commit

class Response(models.Model):
    commit = models.ForeignKey(Commit, on_delete=models.CASCADE, editable=False)
    committer = models.ForeignKey(ProjectCommitter, on_delete=models.CASCADE, editable=False)
    committer_commits_at_time = models.IntegerField(null=True, editable=False)
    survey_response = models.TextField(editable=False)
    tags = models.ManyToManyField(ChangeReason)

    def __str__(self):
        return f'Response of {self.committer} on {self.commit}'

class FAQ(models.Model):
    question = MarkdownxField('Frequently Asked Question')
    answer = MarkdownxField()
    weight = models.IntegerField()

    class Meta:
        ordering = ('-weight', )
        verbose_name = "FAQ"

    def __str__(self):
        return f'FAQ: {self.question}'
