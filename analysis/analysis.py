#!/usr/bin/env python
# coding: utf-8

import pandas as pd

import scipy.stats as stats
from itertools import combinations

for file in ['always', 'change', 'never']:
    df = pd.read_csv(f'analysis/{file}.csv') \
        .assign(official_codes = lambda df: df.codes.str.split(';'))

    df_codes = pd.DataFrame(df.official_codes.apply(lambda r: { code: True for code in r } if type(r) == list else {}).to_list()).fillna(False)
    codes_list = sorted(filter(lambda code: ' ' not in code, df_codes.columns.to_list()))

    df = pd.concat([df, df_codes], axis=1)

    stat = {}

    for a, b in combinations(codes_list, r=2):
        if a not in stat.keys():
            stat[a] = {a: 1}
        if b not in stat.keys():
            stat[b] = {b: 1}
        result = stats.spearmanr(df[a], df[b])
        stat[a][b] = result.statistic

    correlations = pd.DataFrame(stat)[codes_list].reindex(codes_list)
    if file != 'always':
        print('\f')
    print(file)
    print(correlations.round(3).to_string())

    styler = correlations.style \
                         .format(None, precision=3, thousands=',', escape='latex', na_rep='---') \
                         .map_index(lambda x: 'textbf:--rwrap;', axis='columns') \
                         .hide(names=True, axis='columns') \
                         .map_index(lambda x: 'textbf:--rwrap;', axis='index') \
                         .hide(names=True, axis='index') \
                         .format_index(None, escape='latex', axis='columns') \
                         .format_index(None, escape='latex', axis='rows') \
                         .set_table_styles([
                             {'selector': 'toprule', 'props': ':toprule;'},
                             {'selector': 'bottomrule', 'props': ':bottomrule;'}],
                                           overwrite=False)

    with open(f'{file}.tex', 'w+') as fh:
        fh.write(styler.to_latex())
