from django.shortcuts import render

from .models import Project

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
            pass
        case "push":
            pass
        case "commit_comment":
            pass
        case _:
            pass

    return HttpResponse()

@atomic
def process_push(payload):
    print(payload['repository'])

    pass

@atomic
def process_installation(payload):
    if action == "added":
        for repo in payload['repositories_added']:
            owner, repo = repo['full_name'].split('/')
            if not repo['private']:
                if Project.objects.filter(owner=owner, repo=owner).count() == 0:
                    project = Project(owner=owner, repo=repo)
                    project.save()
    else:
        for repo in payload['repositories_removed']:
            # Find repository
            # Mark removed
            pass

def index(request):
    return HttpResponse("")
