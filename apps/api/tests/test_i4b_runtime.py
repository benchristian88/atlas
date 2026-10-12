"""Candidate code through real pinned Ansible/AIP/I3, with test-only source I/O."""
import asyncio
from copy import deepcopy
from http.server import BaseHTTPRequestHandler, HTTPServer
import io
import json
import os
from pathlib import Path
import secrets
import shutil
import subprocess
import sys
import tarfile
import threading
import time

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import select, func

from app.database import get_db
from app.main import app
from app.models import Asset, AssetType, RelationshipType, ConnectorMapping, EvidenceRecord, KnowledgeAssertion, KnowledgeChange, ReconciliationItem
from app.services import connector_lifecycle as lifecycle, discovery_orchestration as orchestration, aip_ingestion as aip
from app.services.connector_catalogue import CataloguePackage, catalogue
from app.services.connector_store import PackageStore
from app.services.connector_verification import BootstrapReleaseVerifier, OfficialBundleVerifier
from app.services.integration_runtime import LocalIntegrationRuntime
from app.services.integration_secrets import AtlasEncryptedSecretProvider
from app.services.reconciliation import accept_item
from tests.i3_fixtures import ROOT
from tests.test_i3_discovery import db, configured, new_run

FIXTURES=Path(__file__).parent/'fixtures/i4b'
pytestmark=[pytest.mark.skipif(not os.getenv('ATLAS_TEST_DATABASE_URL'),reason='requires disposable PostgreSQL'),
            pytest.mark.skipif(not os.getenv('ATLAS_TEST_RUNTIME_PYTHON'),reason='requires pinned I4A Ansible environment')]


def package():
    manifest=json.loads((FIXTURES/'manifest.json').read_text())
    digest=manifest['distribution']['bundle_digest']
    value=CataloguePackage(manifest['id'],manifest['version'],digest,manifest,'bootstrap',True,FIXTURES/'bundle.tar.gz')
    verifier=OfficialBundleVerifier(BootstrapReleaseVerifier(frozenset({(manifest['id'],manifest['version'],digest)}),'test-only-i4b'))
    return value,verifier


@pytest.fixture
def candidate(db,configured,tmp_path,monkeypatch):
    sys.path.insert(0,str(ROOT/'apps/runtime/ansible'))
    from atlas_runtime import jobs,collections,probe
    from atlas_runtime.server import Runtime,Server
    staged=tmp_path/'runtime'
    shutil.copytree(ROOT/'apps/runtime/ansible',staged,ignore=shutil.ignore_patterns('__pycache__','collections'))
    collections.install(ROOT/'vendor/collections',path=staged/'collections')
    environment={**os.environ,'PYTHONPATH':str(staged),'PYTHONDONTWRITEBYTECODE':'1'}
    code="import json; from pathlib import Path; from atlas_runtime.server import Runtime; print(json.dumps(Runtime('test-health-only',Path('/tmp/not-used'),'development').health()))"
    actual=json.loads(subprocess.check_output([os.environ['ATLAS_TEST_RUNTIME_PYTHON'],'-c',code],env=environment,text=True))
    assert actual['state']=='healthy'
    store=configured[2]
    bundle,verifier=package()
    for key in ['cluster','hypervisor_node','virtual_machine','container','storage_pool','network_device']:
        if db.scalar(select(AssetType).where(AssetType.key==key)) is None:
            db.add(AssetType(key=key,name=key,active=True))
    for key in ['member_of','runs_on','uses_storage','connected_to']:
        target='i4b_'+key
        db.add(RelationshipType(key=target,name=target,source_label=key,target_label=key,inverse_label=key,
            directional=True,active=True))
    db.flush()
    for key in ['member_of','runs_on','uses_storage','connected_to']:
        target='i4b_'+key
        db.add(ConnectorMapping(connector_id=bundle.connector_id,connector_version=bundle.version,
            kind='relationship',source_key='proxmox.'+key,target_key=target,relationship_type_key=target,ignored=False))
    db.flush()
    stored=store.install(bundle,verifier)
    health={**actual,'status':'healthy','capabilities':{**actual,'operations':['run_discovery','get_job','cancel_job'],'aip_versions':['1.0']}}
    lifecycle.activate(db,stored,health)
    row=configured[0]
    row.connector_id=row.plugin_id=stored.connector_id
    row.connector_version,row.connector_digest=stored.version,stored.bundle_digest[7:]
    row.config_schema_version='1.1'
    row.config_json={'endpoint':'https://source.example.test:8006','tls_policy':'verify'}
    row.selected_scopes=['inventory']
    AtlasEncryptedSecretProvider(db).replace(row,{'token_id':'fixture_'+secrets.token_hex(8)+'@pve!discovery','token_secret':secrets.token_urlsafe(32)})
    db.commit()
    control_secret=secrets.token_hex(48)
    runtime=Runtime(control_secret,store.root,'development')
    monkeypatch.setattr(runtime,'health',lambda:actual)
    monkeypatch.setattr(jobs.sys,'executable',os.environ['ATLAS_TEST_RUNTIME_PYTHON'])
    monkeypatch.setattr(jobs,'__file__',str(staged/'atlas_runtime/jobs.py'))
    monkeypatch.setattr(jobs,'execution_environment',lambda:{'ANSIBLE_COLLECTIONS_PATH':str(staged/'collections'),'ANSIBLE_COLLECTIONS_SCAN_SYS_PATH':'False'})
    monkeypatch.setattr(jobs,'workspace_root',lambda:tmp_path)
    monkeypatch.setattr(probe,'__file__',str(staged/'atlas_runtime/probe.py'))
    monkeypatch.setattr(probe,'execution_environment',jobs.execution_environment)
    monkeypatch.setattr(probe,'workspace_root',lambda:tmp_path)
    secret_file=tmp_path/'control.secret'; secret_file.write_text(control_secret); secret_file.chmod(0o600)
    monkeypatch.setenv('ATLAS_RUNTIME_CONTROL_SECRET_FILE',str(secret_file))
    monkeypatch.setenv('ATLAS_RUNTIME_URL','http://127.0.0.1:8091')
    client=LocalIntegrationRuntime()
    monkeypatch.setattr(orchestration,'runtime',client)
    app.dependency_overrides[get_db]=lambda:db
    callbacks=[]
    class Callback(BaseHTTPRequestHandler):
        def do_POST(self):
            body=self.rfile.read(int(self.headers['Content-Length']))
            response=TestClient(app).post(self.path,content=body,headers={'Authorization':self.headers['Authorization'],'Content-Type':'application/json'})
            callbacks.append((self.path,response.status_code,json.loads(body)))
            self.send_response(response.status_code); self.send_header('Content-Type','application/json'); self.end_headers(); self.wfile.write(response.content)
        def log_message(self,*args): pass
    control=Server(('127.0.0.1',8091),runtime)
    callback=HTTPServer(('127.0.0.1',8000),Callback)
    threads=[threading.Thread(target=server.serve_forever,daemon=True) for server in [control,callback]]
    for thread in threads: thread.start()
    try:
        assert asyncio.run(client.health())['status']=='healthy'
        yield configured,runtime,client,callbacks
    finally:
        runtime.jobs.shutdown()
        for server in [control,callback]: server.shutdown(); server.server_close()
        for thread in threads: thread.join(2)
        app.dependency_overrides.clear()


def execute(db,candidate,scenario):
    configured,runtime,client,callbacks=candidate
    row=configured[0]
    row.config_json={**row.config_json,'fixture_scenario':scenario}; db.commit()
    run=new_run(db,configured)
    asyncio.run(orchestration.dispatch(db,run.id))
    assert run.runtime_job_id and run.status=='running'
    deadline=time.monotonic()+30
    while time.monotonic()<deadline:
        state=asyncio.run(client.get_job(run.id,run.runtime_job_id))
        if state['state'] in {'succeeded','failed','cancelled'}: break
        time.sleep(.1)
    assert state['state'] in {'succeeded','failed','cancelled'},state
    db.expire_all(); asyncio.run(orchestration.reconcile(db,run.id))
    return run,state


@pytest.mark.parametrize('scenario,expected',[('complete','complete'),('permission_filtered','partial'),('empty_unproven','partial'),('offline','partial'),('source_failure','failed'),('limits','failed'),('malformed_aip','failed')])
def test_candidate_real_runner_and_aggregate_ingestion(db,candidate,tmp_path,scenario,expected):
    run,state=execute(db,candidate,scenario)
    assert run.completeness_status==expected,(state,run.summary,run.error_message)
    assert run.status==('completed' if expected in {'complete','partial'} else 'failed')
    assert run.dispatch_state=='settled' and not list(tmp_path.glob('job-*'))
    assert not db.scalar(select(KnowledgeChange.id).where(KnowledgeChange.discovery_run_id==run.id,KnowledgeChange.change_type=='no_longer_observed'))
    if expected in {'complete','partial'}:
        assert run.batch_count>=1 and run.observation_count>0
        assert db.scalar(select(EvidenceRecord.id).where(EvidenceRecord.discovery_run_id==run.id))
        assert db.scalar(select(KnowledgeAssertion.id).where(KnowledgeAssertion.discovery_run_id==run.id))
        assert all(code==200 for _,code,_ in candidate[3])
        assert db.scalar(select(func.count()).select_from(Asset).where(Asset.customer_id==run.customer_id))==0
        batch=next(body for path,code,body in candidate[3] if path.endswith('/batches'))
        before=db.scalar(select(func.count()).select_from(EvidenceRecord).where(EvidenceRecord.discovery_run_id==run.id))
        assert aip.accept_batch(db,run,deepcopy(batch))['replayed']
        assert db.scalar(select(func.count()).select_from(EvidenceRecord).where(EvidenceRecord.discovery_run_id==run.id))==before


def test_partial_candidate_cannot_create_absence_after_accepted_complete_baseline(db,candidate):
    complete,_=execute(db,candidate,'complete')
    items=list(db.scalars(select(ReconciliationItem).join(KnowledgeAssertion).where(KnowledgeAssertion.discovery_run_id==complete.id)))
    for item in items:
        if item.entity_type=='asset' and item.category=='newly_discovered' and item.candidate_external_id.startswith('guest/'):
            accept_item(db,item,candidate[0][1].user)
    db.commit()
    before=set(db.scalars(select(Asset.id).where(Asset.customer_id==complete.customer_id)))
    assert len(before)>0
    partial,_=execute(db,candidate,'empty_unproven')
    assert partial.completeness_status=='partial' and partial.summary.get('no_longer_observed_count',0)==0
    assert set(db.scalars(select(Asset.id).where(Asset.customer_id==complete.customer_id)))==before


def test_candidate_cancellation_kills_the_real_source_child_and_cleans_workspace(db,candidate,tmp_path):
    configured,runtime,client,callbacks=candidate
    configured[0].config_json={**configured[0].config_json,'fixture_scenario':'slow'}; db.commit()
    run=new_run(db,configured); asyncio.run(orchestration.dispatch(db,run.id))
    deadline=time.monotonic()+15
    while time.monotonic()<deadline and not list(tmp_path.glob('job-*/fixture.pid')): time.sleep(.1)
    paths=list(tmp_path.glob('job-*/fixture.pid')); assert paths
    pid=int(paths[0].read_text())
    orchestration.cancel_intent(run); db.commit()
    asyncio.run(client.cancel_job(run.id,run.runtime_job_id))
    deadline=time.monotonic()+10
    while time.monotonic()<deadline:
        status=asyncio.run(client.get_job(run.id,run.runtime_job_id))
        if status['state']=='cancelled': break
        time.sleep(.1)
    assert status['state']=='cancelled'
    asyncio.run(orchestration.reconcile(db,run.id))
    assert run.status=='cancelled' and not list(tmp_path.glob('job-*'))
    with pytest.raises(ProcessLookupError): os.kill(pid,0)


@pytest.mark.parametrize('scenario,state',[('complete','ready'),('permission_filtered','permission_limited')])
def test_candidate_actual_probe_preserves_bounded_capability_diagnostics(db,candidate,tmp_path,scenario,state):
    configured,runtime,client,callbacks=candidate
    row=configured[0]
    row.config_json={**row.config_json,'fixture_scenario':scenario}
    provider=AtlasEncryptedSecretProvider(db)
    with provider.materialize_for_job(row,row.id,provider.state(row)) as lease:
        result=asyncio.run(client.test_connection({'connector_id':row.connector_id,'version':row.connector_version,
            'digest':row.connector_digest},row.config_json,lease.values,row.id))
    assert result['success'] and result['capability_diagnostics'][0]['state']==state
    assert not list(tmp_path.glob('probe-*')) and not callbacks


def test_unqualified_real_candidate_is_rejected_and_production_bootstrap_stays_probe_only(tmp_path):
    manifest=json.loads((FIXTURES/'candidate-manifest.json').read_text())
    candidate=CataloguePackage(manifest['id'],manifest['version'],manifest['distribution']['bundle_digest'],manifest,'bootstrap',True,FIXTURES/'bundle.tar.gz')
    with pytest.raises(ValueError,match='package_not_qualified'):
        PackageStore(tmp_path/'store').install(candidate,catalogue.verifier())
    production=catalogue.get('proxmox','0.1.0')
    assert production.manifest['capabilities']['discover'] is False
    assert production.manifest['source_versions']['qualification']=='unqualified'
    with tarfile.open(fileobj=io.BytesIO(production.archive_path.read_bytes())) as archive:
        assert 'discover.yml' not in archive.getnames()
