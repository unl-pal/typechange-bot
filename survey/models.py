from django.db import models
from django.conf import settings
from github import Github, Auth

application_auth = Auth.AppAuth(settings.GITHUB_APP_ID, settings.GITHUB_APP_KEY)

# Create your models here.

class Committer(models.Model):
    username = models.CharField(max_length=200)
    initial_contact_date = models.DateTimeField("initial contact date", auto_now_add=True, editable=False)
    last_contact_date = models.DateTimeField("date of last contact", auto_now=True, editable=False)
    consent_timestamp = models.DateTimeField("date of consent", null=True, editable=False)
    opt_out = models.DateTimeField("date of opt-out", null=True, blank=True, editable=False)
    projects = models.ManyToManyField('Project', through='ProjectCommitter')

    def __str__(self):
        return f'https://github.com/{self.username}'

class Project(models.Model):
    owner = models.CharField('project owner', max_length=200, editable=False)
    name = models.CharField('project name', max_length=200, editable=False)
    installation_id = models.IntegerField('installation ID', editable=False, null=True)
    primary_language = models.CharField('primary programming language', max_length=30, editable=False, null=True)
    track_changes = models.BooleanField('are we tracking this project\'s changes?', null=False, editable=False, default=False)
    typechecker_files = models.CharField('list of typechecker configuration files detected', max_length=300, null=True, editable=False)
    add_date = models.DateTimeField('project add date', auto_now_add=True, editable=False)
    remove_date = models.DateTimeField('project remove date', blank=True, null=True, editable=False)
    committers = models.ManyToManyField(Committer, through='ProjectCommitter')

    _repo = None

    def __str__(self):
        return f'https://github.com/{self.owner}/{self.name}'

    @property
    def repo(self):
        if self._repo is not None:
            return self._repo
        gh = Github(auth=Auth.AppInstallationAuth(application_auth, self.installation_id))
        self._repo = gh.get_repo(f'{self.owner}/{self.name}')
        return self._repo

    class Meta:
        constraints = [
            models.UniqueConstraint(fields=['owner', 'name'], name="unique_project_name")
        ]

class ProjectCommitter(models.Model):
    project = models.ForeignKey(Project, on_delete=models.CASCADE, editable=False)
    committer = models.ForeignKey(Committer, on_delete=models.CASCADE, editable=False)
    initial_commit = models.ForeignKey('Commit', on_delete=models.CASCADE, editable=False, null=True)
    initial_survey_response = models.TextField('response to initial survey', null=True, blank=True, editable=False)

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
    def commit(self):
        if self._commit is not None:
            return self._commit
        self._commit = self.project.repo.get_commit(sha=self.hash)
        return self._commit

class Response(models.Model):
    commit = models.ForeignKey(Commit, on_delete=models.CASCADE, editable=False)
    committer = models.ForeignKey(ProjectCommitter, on_delete=models.CASCADE, editable=False)
    survey_response = models.TextField(editable=False)

    def __str__(self):
        return f'Response of {self.committer} on {self.commit}'
