from django.shortcuts import render

from django.db.models import Q
from .models import Project, Commit, Response, Committer
from .tasks import process_push_data, process_new_committer

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
            repo_owner = payload['repository']['owner']['name']
            repo_name = payload['repository']['name']
            process_push_data(repo_owner, repo_name, payload['commits'])
        case "commit_comment":
            process_comment(payload)
        case _:
            pass

    return HttpResponse()

@atomic
def process_comment(payload):
    comment_data = payload['comment']
    commit_id = comment_data['commit_id']
    commit = Commit.objects.get(Q(hash=commit_id))
    committer_id = comment_data['user']['login']
    try:
        committer = Committer.objects.get(Q(username=committer_id))
        response = Response(commit=commit,
                            committer=committer,
                            survey_response = comment_data['body'])
        response.save()
    except Committer.DoesNotExist:
        committer = Committer(username = committer_id)
        committer.save()
        process_new_committer.delay(committer.pk)


@atomic
def process_push(payload):
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
