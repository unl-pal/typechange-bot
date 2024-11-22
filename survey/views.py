from django.shortcuts import render

from django.db.models import Q
from .models import Project, Commit
from .tasks import process_commit

import json

from django.conf import settings
from django.db.transaction import atomic, non_atomic_requests
from django.http import HttpResponse, HttpResponseForbidden
from django.views.decorators.csrf import csrf_exempt
from django.views.decorators.http import require_POST
from django.utils import timezone


# Create your views here.

@csrf_exempt
@require_POST
@non_atomic_requests
def github_webhook(request):

    github_event = request.headers.get("X-GitHub-Event")
    payload = json.loads(request.body)

    match github_event:
        case "installation_repositories":
            process_installation(payload)
        case "push":
            process_push(payload)
            pass
        case "commit_comment":
            pass
        case _:
            pass

    return HttpResponse()

@atomic
def process_push(payload):
    print(payload['repository'])
    repo = payload['repository']['name']
    owner = payload['repository']['owner']['name']
    project = Project.objects.get(Q(owner=owner) & Q(name=repo))

    for commit_data in payload['commits']:
        commit = Commit(project=project,
                        hash=commit_data['id'],
                        message=commit_data['message'],
                        diff = '\n'.join(commit_data['modified']))
        commit.save()
        process_commit.delay(commit.pk)

@atomic
def process_installation(payload):
    # TODO
    if action == "added":
        for repo in payload['repositories_added']:
            owner, repo = repo['full_name'].split('/')
            if not repo['private']:
                if Project.objects.filter(owner=owner, repo=repo).count() == 0:
                    project = Project(owner=owner, repo=repo)
                    project.save()
    else:
        for repo in payload['repositories_removed']:
            # Find repository
            # Mark removed
            pass

def index(request):
    return HttpResponse("")
