#!/usr/bin/env python
# coding: utf-8

from django.core.management.base import BaseCommand, CommandError
from django.template import loader
from survey.models import Response, ChangeReason

import openai
import pandas as pd

class Command(BaseCommand):
    help = 'Run LLM to code responses.'

    survey_type = None
    api_key = None
    change_reasons = None

    def add_arguments(self, parser):
        parser.add_argument('--survey-type',
                            type=str,
                            required=True,
                            choices=['always', 'never', 'change'])
        parser.add_argument('--api-key',
                            type=str,
                            required=True)
        parser.add_argument('--debug',
                            action='store_true',
                            default=False)

        parser.add_argument('out_file')

    def query_open_ai(self, prompt):
        openai.api_key = self.api_key
        client = openai.OpenAI()
        response = client.chat.completions.create(
            model="gpt-4o-2024-05-13",
            temperature=1,
            max_tokens=1024,
            top_p=1,
            frequency_penalty=0,
            presence_penalty=0,
            messages=[
                {
                    "role": "user",
                    "content": str(prompt)
                }
            ]
        )

        codes = response.choices[0].message.content.split(',')
        return codes

    def make_prompt(self, response):
        template = loader.get_template('prompt-template.md')
        return template.render({ 'RESPONSE': response,
                                 'TYPE': ('always include' if self.survey_type == 'always' else ('never include' if self.survey_type == 'never' else 'change')),
                                 'TYPEING': ('always including' if self.survey_type == 'always' else ('never including' if self.survey_type == 'never' else 'changing')),
                                 'codes': self.change_reasons })

    def handle(self, *arguments,
               survey_type=None,
               api_key=None,
               debug=False,
               out_file=None,
               **options):
        openai.api_key = api_key
        self.api_key = api_key
        self.survey_type = survey_type

        if survey_type == 'always':
            self.change_reasons = ChangeReason.objects.get(id=11).get_children()
        elif survey_type == 'never':
            self.change_reasons = ChangeReason.objects.get(id=12).get_children()
        else:
            self.change_reasons = ChangeReason.objects.get(id=13).get_children()

        output = []
        for response in Response.objects.all():
            prompt_in = None
            if survey_type != 'change' and not response.is_initial_survey:
                continue
            if survey_type == 'always':
                prompt_in = response.always_include
            elif survey_type == 'never':
                prompt_in = response.never_include
            else:
                prompt_in = response.response
            if prompt_in is None:
                continue
            prompt = self.make_prompt(prompt_in)
            if debug:
                print(prompt)
                break
            codes = self.query_open_ai()
            output.append({'id': response.id,
                           'type': survey_type,
                           'codes': codes})

        df = pd.DataFrame(output)
        print(df.head())
        df.to_csv(out_file, index=False)
