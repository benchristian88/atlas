# SPDX-License-Identifier: Apache-2.0
"""Pure complete ruleset identity/bypass validation. No administrative client."""
from .contract import REPOSITORY, positive_integer, require as check

EXPECTED = {
    'atlas-main': [], 'atlas-history-lock': [], 'atlas-bootstrap-lock': [],
    'atlas-catalogue-current': [{'actor_id': 5422372, 'actor_type': 'Integration', 'bypass_mode': 'always'}],
    'atlas-publication-tags': [{'actor_id': 5422372, 'actor_type': 'Integration', 'bypass_mode': 'always'}],
}

def validate_list(value):
    check(type(value) is list and len(value) == len(EXPECTED), 'authorization_rulesets')
    result = {}
    for row in value:
        check(type(row) is dict and row.get('name') in EXPECTED and row['name'] not in result
              and positive_integer(row.get('id')) and row['id'] not in result.values()
              and row.get('source_type') == 'Repository' and row.get('source') == REPOSITORY,
              'authorization_ruleset_identity')
        result[row['name']] = row['id']
    return result

def validate_detail(value, name, identity):
    check(type(value) is dict and type(value.get('id')) is int and value['id'] == identity
          and value.get('name') == name and value.get('source_type') == 'Repository'
          and value.get('source') == REPOSITORY and value.get('bypass_actors') == EXPECTED[name],
          'authorization_ruleset_bypass')
