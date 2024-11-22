from django.db import models

# Create your models here.

class Committer(models.Model):
    username = models.CharField(max_length=200)
    initial_contact_date = models.DateTimeField("initial contact date", auto_now_add=True)
    last_contact_date = models.DateTimeField("date of last contact", auto_now=True)
    consent_timestamp = models.DateTimeField("date of consent", null=True)
    opt_out = models.DateTimeField("date of opt-out", null=True, blank=True)
    initial_survey_response = models.TextField('response to initial survey', null=True, blank=True)

    def __str__(self):
        return f'https://github.com/{self.username}'

class Project(models.Model):
    owner = models.CharField('project owner', max_length=200)
    name = models.CharField('project name', max_length=200)
    add_date = models.DateTimeField('project add date', auto_now_add=True)

    def __str__(self):
        return f'https://github.com/{self.owner}/{self.name}'

class Commit(models.Model):
    project = models.ForeignKey(Project, on_delete=models.CASCADE)
    hash = models.CharField(max_length=40)
    diff = models.TextField()

    def __str__(self):
        return f'{self.project}/commit/{self.hash}'

class Response(models.Model):
    commit = models.ForeignKey(Commit, on_delete=models.CASCADE)
    person = models.ForeignKey(Committer, on_delete=models.CASCADE)
    survey_response = models.TextField()

    def __str__(self):
        return f'Response of {self.person} on {self.commit}'
