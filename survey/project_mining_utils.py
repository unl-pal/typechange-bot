#!/usr/bin/env python
# coding: utf-8

from datetime import datetime
from dateutil.relativedelta import relativedelta
import github
import pandas as pd

from django.conf import settings

from typing import Optional

def get_git_hub(token: str = settings.GITHUB_API_KEY):
    global g
    g = github.Github(auth=github.Auth.Token(token))
    return g

g: Optional[github.Github] = None
get_git_hub()

def get_repo(owner: str, project_name: str, gh: Optional[github.Github] = None) -> github.Repository.Repository:
    if gh is None:
        global g
        gh = g

    return gh.get_repo(f'{owner}/{project_name}')


def collect_repo_maintainers(repo: github.Repository.Repository, gh: Optional[github.Github] = None):
    if gh is None:
        global g
        gh = g

    stats = repo.get_stats_contributors()

    login = []
    people = []
    totals = []

    for s in stats:
        weeks = [week for week in s.weeks if week.w >= (datetime.now(week.w.tzinfo) + relativedelta(months=-6))]
        total = sum([week.c for week in weeks])

        if total > 0:
            login.append(s.author.login)
            people.append(s.author)
            totals.append(total)

    df = pd.DataFrame(zip(login, people, totals), columns=['login', 'stats', 'contributions'])
    df = df[~df['login'].str.contains('\\[bot\\]')]
    # print(df)

    cutoff = df['contributions'].mean() + 1.5 * df['contributions'].std()
    # print(cutoff)

    def get_email(login):
        user = gh.get_user(login)
        if user and user.email:
            return (user.email, user.name)

    df2 = df[df['contributions'] >= cutoff] \
        .assign(email_and_name = lambda df: df.login.apply(get_email)) \
        .dropna(axis=0) \
        .assign(email = lambda df: df.email_and_name.apply(lambda x: x[0]),
                name = lambda df: df.email_and_name.apply(lambda x: x[1]),
                project = lambda df: repo.full_name) \
        .reset_index() \
        [['login', 'name', 'email', 'contributions', 'project']]


    return df2

