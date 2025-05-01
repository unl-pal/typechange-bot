#!/usr/bin/env python
# coding: utf-8

from .common import app, current_node
from survey.models import Committer

from django.core.mail import EmailMessage, EmailMultiAlternatives
from django.template import loader
from django.conf import settings

@app.task()
def send_email(subject, message, **kwargs):
    email = EmailMessage(subject, message, **kwargs)
    email.send()

@app.task()
def send_maintainer_email(committer_id: int):
    committer = Committer.objects.get(id=committer_id)
    maintained_tracked_projects = committer.projectcommitter_set.filter(is_maintainer=True, project__track_changes=True).count()
    if committer.email_address is not None and not committer.has_been_emailed:
        if maintained_tracked_projects > 0:
            template_data = { 'committer': committer }
            html_template = loader.get_template('maintainer-request.html')
            message_html = html_template.render(template_data)
            text_template = loader.get_template('maintainer-request.txt')
            message_text = text_template.render(template_data)
            message = EmailMultiAlternatives(f'Research Opportunity: Can we monitor your projects?',
                                             message_html,
                                             to=[committer.formatted_email_address],
                                             reply_to=[f'{settings.ADMIN_NAME} <{settings.ADMIN_EMAIL}>'])
            message.content_subtype = "html"
            message.attach_alternative(message_text, 'text/plain')
            message.send()
        committer.has_been_emailed = True
        committer.save()
