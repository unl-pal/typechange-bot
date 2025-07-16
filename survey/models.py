from django.db import models
from django.conf import settings
from github import Github, Auth
import github
from treebeard.ns_tree import NS_Node
from markdownx.models import MarkdownxField

from django.utils import timezone
from datetime import timedelta

from typing import Optional

from pathlib import Path

application_auth = Auth.AppAuth(settings.GITHUB_APP_ID, settings.GITHUB_APP_KEY)

from socket import gethostname
CURRENT_HOST = gethostname()

# Create your models here.

class Node(models.Model):
    hostname = models.CharField('Host Name', max_length=200, editable=False, null=False)
    last_active = models.DateTimeField(auto_now_add=True)
    enabled = models.BooleanField(default=True, null=False)
    use_datadir_subdirs = models.BooleanField(default=False, null=False)

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
        DELETED = ('DE', "Deleted")

    node = models.ForeignKey(Node, on_delete=models.CASCADE, editable=False)
    owner = models.CharField(max_length=200, editable=False)
    name = models.CharField(max_length=200, editable=False)
    subdir = models.CharField(max_length=200, editable=False, null=True)

    reason = models.CharField(max_length=2,
                              choices=DeletionReason.choices,
                              default=DeletionReason.REBALANCE)

    deleted_on = models.DateTimeField(auto_now_add=True, editable=False)

    class Meta:
        verbose_name_plural = 'Deleted Repositories'

class ChangeReason(NS_Node):
    name = models.CharField(max_length=32, null=False, blank=False)
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
        verbose_name = "Maintainer Response Code"

class Committer(models.Model):
    username = models.CharField(max_length=200)
    name = models.CharField(max_length=200, null=True, editable=False)
    email_address = models.EmailField(null=True)
    has_been_emailed = models.BooleanField(default=False, null=False)
    initial_contact_date = models.DateTimeField('first contact', auto_now_add=True, editable=False)
    last_contact_date = models.DateTimeField("last contact", auto_now=True, editable=False)
    consent_timestamp = models.DateTimeField("consent date", null=True, editable=False)
    consent_project_commit = models.TextField("consent location", null=True, blank=True, editable=True)
    initial_contact_location = models.TextField("Location of initial contact", null=True, blank=True, editable=False)
    opt_out = models.DateTimeField("opt-out date", null=True, blank=True, editable=False)
    removal = models.DateTimeField("removal date", null=True, blank=True, editable=False)
    projects = models.ManyToManyField('Project', through='ProjectCommitter')
    initial_survey_response = models.TextField('initial survey response', null=True, blank=True, editable=False)
    tags = models.ManyToManyField(InitialReason)

    @property
    def name_or_username(self) -> str:
        if self.name is None:
            return self.username
        return self.name

    @property
    def formatted_email_address(self) -> Optional[str]:
        if self.email_address:
            return f'"{self.name_or_username}" <{self.email_address}>'

    @property
    def consented(self) -> bool:
        return self.consent_timestamp is not None

    @property
    def should_contact(self) -> bool:
        if self.opt_out is not None or self.removal is not None:
            return False

        if self.initial_contact_location is None:
            return True

        return self.consent_timestamp is not None and self.last_contact_date < (timezone.now() - timedelta(hours=24))

    def __str__(self):
        return f'{self.username}'

class Project(models.Model):
    class ProjectLanguage(models.TextChoices):
        PYTHON = ('PY', "Python")
        TYPESCRIPT = ('TS', "TypeScript")
        RUBY = ('RB', 'Ruby')
        PHP = ('PH', 'PHP')
        R_LANG = ('RL', "GNU R")

        @classmethod
        def from_github_name(cls, gh_name: str):
            lang = gh_name.lower()
            if lang == 'python':
                return cls.PYTHON
            elif lang == 'typescript':
                return cls.TYPESCRIPT
            elif lang == "Ruby":
                return cls.RUBY
            elif lang == "R":
                return cls.R_LANG
            elif lang == "PHP":
                return cls.PHP
            return cls.PYTHON


    owner = models.CharField('owner', max_length=200, editable=False)
    name = models.CharField('name', max_length=200, editable=False)
    installation_id = models.IntegerField('installation ID', editable=False, null=True)

    language = models.CharField('primary language',
                                max_length=2,
                                choices=ProjectLanguage.choices,
                                default=ProjectLanguage.PYTHON)
    track_changes = models.BooleanField('tracking?', null=False, editable=False, default=False)
    typechecker_files = models.TextField('typchecker files detected', null=True, editable=False)
    add_date = models.DateTimeField('add date', auto_now_add=True, editable=False)
    remove_date = models.DateTimeField('remove date', blank=True, null=True, editable=False)
    committers = models.ManyToManyField(Committer, through='ProjectCommitter')
    host_node = models.ForeignKey(Node, on_delete=models.CASCADE, editable=False, null=True)
    data_subdir = models.CharField('data subdirectory', max_length=200, editable=False, null=True)

    has_language_files = models.BooleanField('has files in the language?', editable=False, default=False)
    has_typechecker_configuration = models.BooleanField('has typechecker config?', editable=False, default=False)
    annotations_detected = models.BooleanField('annotations detected?', editable=False, default=False)
    metrics_collected = models.BooleanField('metrics collected?', editable=False, default=False)
    num_commits = models.IntegerField(editable=False, null=True)
    num_committers = models.IntegerField(editable=False, null=True)

    _repo = None
    _gh_app = None

    def __str__(self):
        return f'{self.owner}/{self.name}'

    @property
    def is_installed(self):
        return self.installation_id is not None

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
        if self.data_subdir is not None:
            return settings.DATA_DIR / self.data_subdir / self.owner / self.name
        else:
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
    is_relevant = models.BooleanField(default=False)
    relevance_type = models.CharField(max_length=2,
                                      choices=RelevanceType.choices,
                                      default=RelevanceType.IRRELEVANT)
    relevant_change_file = models.TextField(null=True, blank=True, editable=False)
    relevant_change_line = models.IntegerField(null=True, editable=False)

    created_at = models.DateTimeField(auto_now_add=True, editable=False)
    author = models.ForeignKey(ProjectCommitter, on_delete=models.SET_NULL, editable=False, null=True, related_name='author')
    committer = models.ForeignKey(ProjectCommitter, on_delete=models.SET_NULL, editable=False, null=True, related_name='pusher')

    json_data = models.JSONField(null=True, editable=False)

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
    tags = models.ManyToManyField(ChangeReason, related_name='responses')

    @property
    def survey_cleaned(self):
        return '\n'.join(line.rstrip() for line in self.survey_response.split('\n') if not line.startswith('>'))

    @property
    def is_initial_survey(self) -> bool:
        if self.survey_response.find('### When declaring') != -1:
            return True
        return False

    @property
    def factors(self):
        if self.is_initial_survey:
            response = self.survey_cleaned
            declaring_start = response.find("When declaring")
            if declaring_start != -1:
                response = self.survey_response[declaring_start:]
                nl = response.find('nl')
                response = response[nl:].strip()
                always_start = response.find('you always include')
                if always_start == -1:
                    return response
                response = response[:always_start].strip()
                end_nl = response.rfind('\n')
                response = response[:end_nl].strip()
                if len(response) == 0:
                    return None
                lines = response.split('\n')
                return list(line.strip() if line[0:2] != ' - ' else line[2:].strip() for line in lines)

    @property
    def always_include(self):
        if self.is_initial_survey:
            response = self.survey_cleaned
            always_start = response.find('where you always include')
            if always_start != -1:
                response = self.survey_response[always_start:]
                nl = response.find('\n')
                response = response[nl:].strip()
                never_start = response.find('where you never')
                if never_start == -1:
                    return response
                response = response[:never_start]
                end_nl = response.rfind('\n')
                response = response[:end_nl].strip()
                if len(response) == 0:
                    return None
                return response

    @property
    def never_include(self):
        if self.is_initial_survey:
            response = self.survey_cleaned
            never_start = response.find('where you never include')
            if never_start != -1:
                response = self.survey_response[never_start:]
                start = response.find('\n')
                response = response[start:].strip()
                if len(response) == 0:
                    return None
                return response

    @property
    def response(self) -> None | str:
        if not self.is_initial_survey:
            response = self.survey_cleaned
            add_remove_start = response.find('add/remove')
            if add_remove_start != -1:
                respose = response[add_remove_start:]
                start = response.find('\n')
                response = response[start:].strip()
                if len(response) == 0:
                    return
                return response

    def __str__(self):
        return f'Response of {self.committer} on {self.commit}'

class FAQ(models.Model):
    question = MarkdownxField('Frequently Asked Question')
    display = models.BooleanField(default=False)
    answer = MarkdownxField()
    weight = models.IntegerField()

    class Meta:
        ordering = ('-weight', )
        verbose_name = "FAQ"

    def __str__(self):
        return f'FAQ: {self.question}'


class MetricsCommit(models.Model):
    class RelevanceType(models.TextChoices):
        IRRELEVANT = ('IR', "Irrelevant")
        ADDED = ('AD', 'Added')
        REMOVED = ('RM', 'Removed')
        CHANGED = ('CH', 'Changed')

    project = models.ForeignKey(Project, on_delete=models.CASCADE, editable=False)
    hash = models.CharField(max_length=40, editable=False)
    relevance_type = models.CharField(max_length=2,
                                      choices=RelevanceType.choices,
                                      default=RelevanceType.IRRELEVANT)
    relevant_change_file = models.TextField(null=True, blank=True, editable=False)
    relevant_change_line = models.IntegerField(null=True, editable=False)

    created_at = models.DateTimeField(auto_now_add=True, editable=False)
    author = models.CharField(max_length=200, editable=False)
    committer = models.CharField(max_length=200, editable=False)

    _commit = None

    class Meta:
        constraints = [
            models.UniqueConstraint(fields=['project', 'hash'], name='unique_metricscommit_hash_in_project')
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
