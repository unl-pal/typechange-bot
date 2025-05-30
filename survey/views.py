from django.shortcuts import render

from django.db.models import Q
from .models import Project, Commit, Response, Committer, FAQ
from .tasks import process_push_data, process_new_committer, process_comment, process_installation, process_installation_repositories, process_repository

import json

from django.conf import settings
from django.db.transaction import non_atomic_requests
from django.http import HttpResponse, HttpResponseForbidden
from django.views.decorators.csrf import csrf_exempt
from django.views.decorators.http import require_POST
from django.utils import timezone
from django.template import loader

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
            try:
                proj = Project.objects.get(owner=repo_owner, name=repo_name)
                process_push_data.apply_async([repo_owner, repo_name, payload['commits']], queue=proj.host_node.hostname)
            except Project.DoesNotExist:
                return HttpResponse()
        case "commit_comment":
            process_comment.delay(payload['comment']['user']['login'], payload['comment']['body'], payload['repository']['owner']['login'], payload['repository']['name'], payload['comment'])
        case "repository":
            process_repository.delay(payload)
        case _:
            return HttpResponse()

    return HttpResponse()


def projects_list(request):
    return render(request, 'registered-projects.html', {'projects': Project.objects.all()})

def consent_document(request):
    return render(request, 'consent.html', {})

def index(request):
    questions = FAQ.objects.order_by('-weight')[:]
    template = loader.get_template("index.html")
    return HttpResponse(template.render({'questions': questions}, request))
