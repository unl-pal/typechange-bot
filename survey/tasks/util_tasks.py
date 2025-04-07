#!/usr/bin/env python
# coding: utf-8

from .common import app, current_node
from survey.models import ProjectCommitter

from django.core.mail import EmailMessage, EmailMultiAlternatives
from django.template import loader
from django.conf import settings

@app.task()
def send_email(subject, message, **kwargs):
    email = EmailMessage(subject, message, **kwargs)
    email.send()

@app.task()
def send_maintainer_email(maintainer_id: int):
    maintainer = ProjectCommitter.objects.get(id=maintainer_id)
    if maintainer.is_maintainer and not maintainer.has_been_emailed and maintainer.email_address is not None:
        template_data = {
            'NAME': f'{maintainer.committer.username}',
            'PROJECT': f'{maintainer.project.owner}/{maintainer.project.name}'
        }
        html_template = loader.get_template('maintainer-request.html')
        message_html = html_template.render(template_data)
        text_template = loader.get_template('maintainer-request.txt')
        message_text = text_template.render(template_data)
        message = EmailMultiAlternatives(f'Research Opportunity: Can we monitor {maintainer.project.owner}/{maintainer.project.name}?',
                                         message_html,
                                         to=[maintainer.email_address],
                                         reply_to=[f'{settings.ADMIN_NAME} <{settings.ADMIN_EMAIL}>'])
        message.content_subtype = "html"
        message.attach_alternative(message_text, 'text/plain')
        message.send()
        maintainer.has_been_emailed = True
        maintainer.save()
