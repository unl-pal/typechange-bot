from django.db import models
from django.conf import settings
from github import Github, Auth
from treebeard.ns_tree import NS_Node

from django.utils import timezone
from datetime import timedelta

application_auth = Auth.AppAuth(settings.GITHUB_APP_ID, settings.GITHUB_APP_KEY)

from socket import gethostname
CURRENT_HOST = gethostname()

# Create your models here.

class ChangeReason(NS_Node):
    name = models.CharField(max_length=20, null=False, blank=False)
    description = models.TextField(null=True, blank=True)

    def __str__(self):
        if self.get_parent() is None:
            return self.name
        return f"{self.get_parent()} → {self.name}"

    pass

class Committer(models.Model):
    username = models.CharField(max_length=200)
    initial_contact_date = models.DateTimeField("initial contact date", auto_now_add=True, editable=False)
    last_contact_date = models.DateTimeField("date of last contact", auto_now=True, editable=False)
    consent_timestamp = models.DateTimeField("date of consent", null=True, editable=False)
    opt_out = models.DateTimeField("date of opt-out", null=True, blank=True, editable=False)
    removal = models.DateTimeField("date of removal request & processing", null=True, blank=True, editable=False)
    projects = models.ManyToManyField('Project', through='ProjectCommitter')
    initial_survey_response = models.TextField('response to initial survey', null=True, blank=True, editable=False)

    @property
    def should_contact(self) -> bool:
        if self.opt_out is not None or self.removal is not None:
            return False
        # TODO: Change back to 24 hours
        return self.consent_timestamp is not None and self.last_contact_date < (timezone.now() - timedelta(minutes=5))

    def __str__(self):
        return f'https://github.com/{self.username}'

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
    repository_host = models.CharField('repository host', max_length=200, editable=False, null=True)

    _repo = None

    def __str__(self):
        return f'https://github.com/{self.owner}/{self.name}'

    @property
    def gh(self):
        if self._repo is not None:
            return self._repo
        gh_ = Github(auth=Auth.AppInstallationAuth(application_auth, self.installation_id))
        self._repo = gh_.get_repo(f'{self.owner}/{self.name}')
        return self._repo

    @property
    def path(self):
        return settings.DATA_DIR / self.owner / self.name

    @property
    def is_on_current_node(self):
        return self.repository_host == CURRENT_HOST

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
    response_tags = models.ManyToManyField(ChangeReason)

    def __str__(self):
        return f'{self.committer.username} contributes to {self.project.owner}/{self.project.name}'

    class Meta:
        constraints = [
            models.UniqueConstraint(fields=['project', 'committer'], name='unique_project_committer')
        ]

class Commit(models.Model):
    project = models.ForeignKey(Project, on_delete=models.CASCADE, editable=False)
    hash = models.CharField(max_length=40, editable=False)
    message = models.TextField(blank=True, editable=False)
    diff = models.TextField(blank=True, editable=False)
    is_relevant = models.BooleanField(default=True)
    author = models.ForeignKey(ProjectCommitter, on_delete=models.CASCADE, editable=False, null=True, related_name='author')
    committer = models.ForeignKey(ProjectCommitter, on_delete=models.CASCADE, editable=False, null=True, related_name='pusher')

    _commit = None

    class Meta:
        constraints = [
            models.UniqueConstraint(fields=['project', 'hash'], name='unique_commit_hash_in_project')
        ]

    def __str__(self):
        return f'{self.project}/commit/{self.hash}'

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
    question = models.TextField()
    answer = models.TextField()
    weight = models.IntegerField()

    def __str__(self):
        return f'FAQ: {self.question}'
