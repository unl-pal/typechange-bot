#!/usr/bin/env python
# coding: utf-8

from django.core.management.base import BaseCommand, CommandError

from survey.models import Response

import pandas as pd
import random

class Command(BaseCommand):
    help = "Get responses"

    def add_arguments(self, parser):
        parser.add_argument('--initial-survey', action='store_true', default=False)

        parser.add_argument('--n-random',
                            type=int,
                            default=None)

        parser.add_argument('out_file')
        pass

    def handle(self, *arguments,
               out_file=None,
               n_random=None,
               initial_survey=False,
               **options):

        responses = []

        for response in Response.objects.all():
            if response.is_initial_survey == initial_survey:
                responses.append(response)

        if n_random is not None:
            responses = random.sample(responses, n_random)

        response_items = []

        for response in responses:
            if initial_survey:
                response.items.append({'id': response.id,
                                       'factors': response.factors,
                                       'always': response.always_include,
                                       'never': response.never_include})
            else:
                response_items.append({'id': response.id,
                                       'survey': response.response})
            pass

        df = pd.DataFrame(response_items)
        print(df.head())
        df.to_csv(out_file, index=False)

