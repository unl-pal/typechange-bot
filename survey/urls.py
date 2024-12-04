#!/usr/bin/env python
# coding: utf-8

from django.urls import path

from . import views

urlpatterns = [
    path("webhook", views.github_webhook, name="webhook"),
    path("", views.index, name='home'),
    path("informed-consent", views.consent_document)
]
