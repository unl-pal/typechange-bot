from django.db import models

# Create your models here.

class Committer(models.Model):
    username = models.CharField(max_length=200)
    initial_contact_date = models.DateTimeField("initial contact date", auto_now_add=True, editable=False)
    last_contact_date = models.DateTimeField("date of last contact", auto_now=True, editable=False)
    consent_timestamp = models.DateTimeField("date of consent", null=True, editable=False)
    opt_out = models.DateTimeField("date of opt-out", null=True, blank=True, editable=False)
    initial_survey_response = models.TextField('response to initial survey', null=True, blank=True, editable=False)

    def __str__(self):
        return f'https://github.com/{self.username}'

class Project(models.Model):
    owner = models.CharField('project owner', max_length=200, editable=False)
    name = models.CharField('project name', max_length=200, editable=False)
    installation_id = models.IntegerField('installation ID', editable=False)
    add_date = models.DateTimeField('project add date', auto_now_add=True, editable=False)
    remove_date = models.DateTimeField('project remove date', blank=True, null=True, editable=False)

    def __str__(self):
        return f'https://github.com/{self.owner}/{self.name}'

    class Meta:
        constraints = [
            models.UniqueConstraint(fields=['owner', 'name'], name="unique_project_name")
        ]

class Commit(models.Model):
    project = models.ForeignKey(Project, on_delete=models.CASCADE, editable=False)
    hash = models.CharField(max_length=40, editable=False)
    message = models.TextField(blank=True, editable=False)
    diff = models.TextField(blank=True, editable=False)
    is_relevant = models.BooleanField(default=True)

    def __str__(self):
        return f'{self.project}/commit/{self.hash}'

class Response(models.Model):
    commit = models.ForeignKey(Commit, on_delete=models.CASCADE, editable=False)
    committer = models.ForeignKey(Committer, on_delete=models.CASCADE, editable=False)
    survey_response = models.TextField(editable=False)

    def __str__(self):
        return f'Response of {self.committer} on {self.commit}'
