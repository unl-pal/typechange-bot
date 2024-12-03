from django.shortcuts import render

from django.db.models import Q
from .models import Project, Commit, Response, Committer
from .tasks import process_push_data, process_new_committer, process_comment, process_installation, process_installation_repositories

import json

from django.conf import settings
from django.db.transaction import non_atomic_requests
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
        case "installation":
            process_installation.delay(payload)
        case "installation_repositories":
            process_installation_repositories.delay(payload)
        case "push":
            repo_owner = payload['repository']['owner']['name']
            repo_name = payload['repository']['name']
            process_push_data.delay(repo_owner, repo_name, payload['commits'])
        case "commit_comment":
            process_comment.delay(payload['comment']['user']['login'], payload['comment']['body'], payload['comment'])
        case _:
            pass

    return HttpResponse()



def index(request):
    return HttpResponse("")
