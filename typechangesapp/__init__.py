#!/usr/bin/env python
# coding: utf-8

from .celery import app as celery_app

__all__ = ('celery_app',)
