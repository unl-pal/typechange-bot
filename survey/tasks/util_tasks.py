#!/usr/bin/env python
# coding: utf-8

from .common import app, current_node

from django.core.mail import EmailMessage

@app.task()
def send_email(subject, message, **kwargs):
    email = EmailMessage(subject, message, **kwargs)
    email.send()
