#!/usr/bin/env python
# coding: utf-8

from django.core.management.base import BaseCommand, CommandError
from django.template import loader
from django.conf import settings
from survey.models import Response, ChangeReason

import openai
import pandas as pd
import json

import re

class Command(BaseCommand):
    help = 'Run LLM to code responses.'

    survey_type = None
    api_key = None
    change_reasons = None

    schema = {
        "name": "string_list_code",
        "schema": {
            "type": "object",
            "properties": {
                "code": {
                    "type": "array",
                    "description": "A list of string elements called 'code'.",
                    "items": {
                        "type": "string"
                    }
                }
            },
            "required": [
                "code"
            ],
            "additionalProperties": False
        },
        "strict": True
    }

    change_names = set()

    def add_arguments(self, parser):
        parser.add_argument('--survey-type',
                            type=str,
                            required=True,
                            choices=['always', 'never', 'change'])
        parser.add_argument('--api-key',
                            type=str,
                            default=settings.OPENAI_API_KEY)
        parser.add_argument('--debug',
                            default=False,
                            action='store_true')

        parser.add_argument('out_file')

    def clean_codes(self, in_codes):
        original_codes = re.split('[ :,;\n]', in_codes)

        if len(self.change_names) == 0:
            for reason in self.change_reasons:
                self.change_names.add(reason.name.lower())

        codes = []
        non_codes = []

        for code in original_codes:
            code = re.sub('[^a-zA-Z]+', '', code)
            if len(code) <= 3:
                continue
            if code.lower() in self.change_names:
                codes.append(code)
            else:
                non_codes.append(code)

        return codes + ['**'] + non_codes

    def query_open_ai(self, prompt):
        client = openai.OpenAI(api_key=self.api_key)
        response = client.chat.completions.create(
            model="gpt-4.1-mini-2025-04-14",
            temperature=0.3,
            max_tokens=1024,
            top_p=0.5,
            frequency_penalty=0,
            presence_penalty=0,
            messages=[
                {
                    "role": "user",
                    "content": str(prompt)
                }
            ],
            response_format={
                "type": "json_schema",
                "json_schema": self.schema
            }
        )
        return json.loads(response.choices[0].message.content)['code']

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

            print(f'Coding {response}... ', end='')
            codes = self.query_open_ai(prompt)
            data_out = {'id': response.id,
                        'response': prompt_in,
                        'type': survey_type,
                        'codes': ';'.join(codes)}
            if survey_type == 'change':
                data_out['relevance_type'] = response.commit.relevance_type
            output.append(data_out)
            print('Done!')

        df = pd.DataFrame(output)
        print(df.head())
        df.to_csv(out_file, index=False)
