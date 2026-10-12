"""Generic retained-source endpoint policy, with existing RBAC and scope checks."""
from copy import deepcopy
from dataclasses import replace
import os
import uuid

import pytest
from fastapi import HTTPException

from app.routes import integration_connections as routes
from app.services import aip_ingestion as aip
from tests.test_i3_discovery import db, configured, new_run
from tests.i3_fixtures import message
from tests.test_administration import request

pytestmark = pytest.mark.skipif(not os.getenv('ATLAS_TEST_DATABASE_URL'), reason='requires disposable PostgreSQL')


@pytest.mark.parametrize('history',[None,'failed','cancelled','complete','partial'])
def test_source_endpoints_are_locked_only_after_successful_discovery(db,configured,history):
    row,principal,*_=configured
    if history:
        run=new_run(db,configured)
        aip.accept_batch(db,run,message(run))
        aip.finalise(db,run,row,message(run,completion=history),failure=history in {'failed','cancelled'})
        run.dispatch_state='settled'; db.commit()
    original=deepcopy(row.config_json)
    config={**original,'endpoint':'https://another-source.example.test'}
    if history in {'complete','partial'}:
        with pytest.raises(HTTPException) as error:
            routes.update_integration(row.id,routes.ConnectionUpdate(config=config),request(),principal,db)
        assert error.value.status_code==409 and error.value.detail['code']=='source_identity_locked'
        assert 'new Integration' in error.value.detail['message']
        db.refresh(row); assert row.config_json==original
        # Cosmetic changes and the unchanged endpoint remain editable.
        result=routes.update_integration(row.id,routes.ConnectionUpdate(name='Renamed',config=original),request(),principal,db)
        assert result['name']=='Renamed'
    else:
        result=routes.update_integration(row.id,routes.ConnectionUpdate(config=config),request(),principal,db)
        assert result['config']['endpoint']==config['endpoint']


def test_source_identity_check_cannot_leak_cross_tenant_or_bypass_manage_rbac(db,configured):
    row,principal,*_=configured
    run=new_run(db,configured); aip.accept_batch(db,run,message(run))
    aip.finalise(db,run,row,message(run,completion='complete')); run.dispatch_state='settled'; db.commit()
    payload=routes.ConnectionUpdate(config={**row.config_json,'endpoint':'https://another-source.example.test'})
    for grants in [(replace(principal.grants[0],scope_type='site',customer_id=uuid.uuid4(),site_id=uuid.uuid4()),),
                   (replace(principal.grants[0],permissions=frozenset({'integrations.view'})),)]:
        forbidden=replace(principal,grants=grants)
        with pytest.raises(HTTPException) as error:
            routes.update_integration(row.id,payload,request(),forbidden,db)
        assert error.value.status_code==404 and error.value.detail=='Integration not found'
