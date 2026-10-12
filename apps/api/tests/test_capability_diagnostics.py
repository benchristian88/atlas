"""Vendor-neutral bounded diagnostics survive both untrusted-runtime adapters."""
import asyncio
from copy import deepcopy
from pathlib import Path
import secrets
import sys

import pytest
from app.services import integration_runtime as api

ROOT=Path(__file__).resolve().parents[3]
sys.path.insert(0,str(ROOT/'apps/runtime/ansible'))
from atlas_runtime import probe

VALUE=[{'capability':'inventory.records','state':'permission_limited','privilege':'Inventory.Audit','path_category':'inventory'}]


def test_generic_probe_diagnostics_are_additive_validated_and_forwarded(monkeypatch):
    result={'success':True,'category':'connected','source_version':'1.0','capability_diagnostics':VALUE}
    assert probe.safe_result(result)['capability_diagnostics']==VALUE
    async def response(*args): return result
    monkeypatch.setattr(api,'control_request',response)
    forwarded=asyncio.run(api.LocalIntegrationRuntime().test_connection({}, {}, {}, 'test-only'))
    assert forwarded['capability_diagnostics']==VALUE
    assert 'capability_diagnostics' not in probe.safe_result({key:value for key,value in result.items() if key!='capability_diagnostics'})


@pytest.mark.parametrize('attack',['text','blob','path','unknown','state','category','bound','length','secret'])
def test_both_diagnostic_boundaries_reject_arbitrary_source_data_and_credentials(attack):
    marker=secrets.token_hex(16)
    value=deepcopy(VALUE)
    if attack=='text': value='raw source text'
    elif attack=='blob': value[0]['state']={'payload':'hidden'}
    elif attack=='path': value[0]['capability']='/sensitive/source/path'
    elif attack=='unknown': value[0]['raw']='payload'
    elif attack=='state': value[0]['state']='unsupported'
    elif attack=='category': value[0]['path_category']='source-specific-category'
    elif attack=='bound': value*=17
    elif attack=='length': value[0]['privilege']='a'*65
    else: value[0]['capability']='prefix'+marker
    assert api.safe_capability_diagnostics(value,[marker])==[]
    assert probe.safe_capability_diagnostics(value,[marker])==[]
