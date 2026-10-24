"""Complete operation: genuine frozen crypto, deterministic HTTP, disposable PG.

Provider metadata is synthetic, shaped to the actual approved immutable release.
All positive cryptographic paths run the actual pinned offline CLI and roots.
"""
import asyncio
import base64
from copy import deepcopy
from dataclasses import replace
import hashlib
import json
import time
import uuid

from fastapi import FastAPI
from fastapi.testclient import TestClient
import pytest
from sqlalchemy import func, select, text
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.orm import Session

from app.authorization import get_principal
from app.database import get_db
from app.models import AuditEvent, InstalledConnectorPackage
from app.routes import integrations as routes
from app.services import catalogue_source as source, catalogue_trust as trust, trusted_catalogue as consumer
from app.services import official_catalogue_ingestion as ingestion
from app.services.official_provenance import ProvenanceError
from tests.test_administration import make_principal
from tests.test_catalogue_bootstrap_authorization import bootstrap_provider
from tests.test_catalogue_publication_evidence import provider, review_document
from tests.test_catalogue_source import FIXTURES, RAW, BUNDLE, DIGEST, Response, Session as HttpSession
from tests.test_trusted_catalogue import db, allow_attempt

PINS = trust.BOOTSTRAP_POLICY_PROPOSAL.identity
POINTER = (FIXTURES / "current.json").read_bytes()
SELECTION_BUNDLE = (FIXTURES / "current.sigstore.json").read_bytes()
FILES = {"catalogue-000001.json": RAW, "catalogue.sigstore.json": BUNDLE,
         "current.json": POINTER, "current.sigstore.json": SELECTION_BUNDLE}


@pytest.fixture
def official_http(monkeypatch, bootstrap_provider):
    values = deepcopy(bootstrap_provider)
    root = PINS.root_commit
    for path, ref, sha in [(ingestion.CURRENT, "heads/catalogue-current", root),
                           (ingestion.ROOT_TAG, "tags/catalogue-bootstrap-root", root),
                           ("/git/ref/tags/catalogue-000001", "tags/catalogue-000001", PINS.catalogue_build_source)]:
        values[path] = {"ref": "refs/" + ref, "url": source.BASE + "/git/refs/" + ref,
            "object": {"type": "commit", "sha": sha, "url": f"{source.BASE}/git/commits/{sha}"}}
    tree_sha = "4ae470b1439711d4b866557e7b8b7c4209f6d6a3"
    values[f"/git/commits/{root}"] = {"sha": root, "url": f"{source.BASE}/git/commits/{root}",
        "parents": [], "tree": {"sha": tree_sha, "url": f"{source.BASE}/git/trees/{tree_sha}"}}
    tree = values[f"/git/trees/{tree_sha}"] = {"sha": tree_sha, "truncated": False,
        "url": f"{source.BASE}/git/trees/{tree_sha}", "tree": []}
    for name in ("current.json", "current.sigstore.json"):
        raw = FILES[name]
        sha = ingestion.blob_sha(raw)
        tree["tree"].append({"type": "blob", "mode": "100644", "path": name, "sha": sha,
                             "url": f"{source.BASE}/git/blobs/{sha}"})
        path = f"/contents/{name}?ref={root}"
        values[path] = {"type": "file", "path": name, "name": name, "sha": sha, "size": len(raw),
            "encoding": "base64", "url": source.BASE + path, "content": base64.b64encode(raw).decode() + "\n",
            "download_url": "https://attacker.invalid/never-follow"}
    release = values[f"/releases/{PINS.release_id}"] = {"id": PINS.release_id, "tag_name": PINS.release_tag,
        "url": f"{source.BASE}/releases/{PINS.release_id}",
        "html_url": f"https://github.com/{source.REPOSITORY}/releases/tag/{PINS.release_tag}",
        "draft": False, "prerelease": False, "immutable": True, "target_commitish": PINS.catalogue_build_source,
        "published_at": "2026-10-23T06:36:18Z", "updated_at": "2026-10-23T06:36:18Z", "assets": []}
    for (name, raw), identifier in zip(FILES.items(), (667867351, 667867380, 667867419, 667868363)):
        release["assets"].append({"name": name, "id": identifier, "size": len(raw), "state": "uploaded",
            "url": f"{source.BASE}/releases/assets/{identifier}", "digest": "sha256:" + hashlib.sha256(raw).hexdigest(),
            "browser_download_url": f"https://github.com/{source.REPOSITORY}/releases/download/{PINS.release_tag}/{name}"})
        values[f"/releases/assets/{identifier}"] = raw
    state = {"values": values, "calls": [], "after": {}, "override": {}}
    def respond(url):
        path = url.removeprefix(source.BASE) if url.startswith(source.BASE) else url.removeprefix(source.API)
        state["calls"].append(path)
        assert path in values, "Unexpected endpoint, package or provider URL"
        value = state["override"].get(path, values[path])
        if state["calls"].count(path) > 1:
            value = state["after"].get(path, value)
        return value if isinstance(value, Response) else Response(value if type(value) is bytes else json.dumps(value).encode())
    async def enter(self):
        self.session, self.deadline = HttpSession(respond), time.monotonic() + 90
        return self
    monkeypatch.setattr(source.GithubReader, "__aenter__", enter)
    return state


def retrieve():
    operation = uuid.uuid4()
    return asyncio.run(source.retrieve_candidate({}, operation_id=operation)), operation


def test_complete_genuine_crypto_and_operation_binding(official_http):
    candidate, operation = retrieve()
    source.require_publication(candidate, operation_id=operation)
    assert candidate.raw == RAW
    assert candidate.provenance.subject_name == "catalogue-000001.json"
    assert candidate.provenance.source_commit == PINS.catalogue_build_source
    public = candidate.authorization.public_observations
    assert public.authorization_blockers == ("reviewed_ruleset_evidence_required", "consumer_trust_approval_required")
    evidence = candidate.publication
    assert base64.b64decode(evidence["selection"]["source_bytes"]) == POINTER
    assert base64.b64decode(evidence["catalogue_bundle_base64"]) == BUNDLE
    assert base64.b64decode(evidence["pointer_bundle_base64"]) == SELECTION_BUNDLE
    assert evidence["approval_reference"] == trust.BOOTSTRAP_APPROVAL_REFERENCE
    assert evidence["transport"]["root_commit"] == PINS.root_commit
    assert len(evidence["missing_bypass_ruleset_ids"]) == 5
    assert all("tar.gz" not in path and "attacker" not in path for path in official_http["calls"])
    assert len(official_http["calls"]) <= 30  # Budget for anonymous first + unchanged acceptance.
    with pytest.raises(source.SourceError, match="catalogue_operation_mismatch"):
        source.require_publication(candidate, operation_id=uuid.uuid4())
    with pytest.raises(source.SourceError, match="authenticated_selection_required"):
        source.require_publication(replace(candidate, raw=RAW + b"\n"), operation_id=operation)


def test_api_accept_unchanged_durable_evidence_and_no_execution(db, official_http):
    app = FastAPI()
    app.include_router(routes.router, prefix="/api")
    principal = make_principal("integration_runtime.view", "integration_runtime.manage")
    db.add(principal.user); db.commit()
    app.dependency_overrides[get_db] = lambda: db
    app.dependency_overrides[get_principal] = lambda: principal
    with TestClient(app) as client:
        result = client.post("/api/integration-catalogue/refresh", json={}).json()
        assert result["result"] == "accepted", result
        accepted = client.get("/api/integration-catalogue/status").json()
        assert accepted["sequence"] == 1 and accepted["content_digest"] == DIGEST
        assert accepted["publication_policy"] == trust.BOOTSTRAP_POLICY_PROPOSAL.policy_version
        assert accepted["trusted_remote_available"] is True
        assert all(e["package_available"] is False and e["supported_actions"] == [] for e in accepted["entries"])
        # Accepted remote metadata never enters the packaged installer provider.
        package_digest = accepted["entries"][0]["manifest"]["distribution"]["bundle_digest"].removeprefix("sha256:")
        assert client.post("/api/integration-catalogue/proxmox/install", json={
            "version": "0.2.0", "digest": package_digest}).status_code == 409
        assert client.post("/api/integration-catalogue/refresh").json()["result"] == "cooldown"
        allow_attempt(db)
        assert client.post("/api/integration-catalogue/refresh").json()["result"] == "unchanged"
        assert db.scalar(select(func.count()).select_from(consumer.Revision)) == 1
        revision = db.get(consumer.Revision, 1)
        assert revision.original_bytes == RAW and revision.publication_evidence["pointer_sha256"] == PINS.pointer_sha256
        assert revision.verification_evidence["selection"]["profile"] == "official-catalogue-selection"
        assert db.scalar(select(func.count()).select_from(InstalledConnectorPackage)) == 0
        assert db.scalar(select(func.count()).select_from(AuditEvent).where(AuditEvent.success.is_(True))) == 2
        with Session(bind=db.get_bind(), join_transaction_mode="create_savepoint") as reopened:
            assert consumer.status(reopened)["content_digest"] == DIGEST


@pytest.mark.parametrize("kind", ["network", "pointer", "contents", "release"])
def test_later_failure_preserves_acceptance_without_freshness(db, official_http, kind):
    assert consumer.refresh(db)["result"] == "accepted"
    previous = consumer.status(db)
    allow_attempt(db)
    if kind == "network":
        official_http["override"][ingestion.CURRENT] = Response(status=429)
    elif kind == "pointer":
        value = deepcopy(official_http["values"][ingestion.CURRENT])
        value["object"]["sha"] = "a" * 40
        value["object"]["url"] = f"{source.BASE}/git/commits/" + "a" * 40
        official_http["override"][ingestion.CURRENT] = value
    elif kind == "contents":
        path = f"/contents/current.json?ref={PINS.root_commit}"
        official_http["values"][path]["content"] = base64.b64encode(POINTER.replace(b"667867351", b"667867352")).decode()
    else:
        official_http["values"][f"/releases/{PINS.release_id}"]["immutable"] = False
    result = consumer.refresh(db)
    assert result["result"] == "failed"
    assert result["status"]["content_digest"] == DIGEST
    assert result["status"]["last_confirmed_current_at"] == previous["last_confirmed_current_at"]
    if kind in ("pointer", "contents"):
        assert result["status"]["source_conflict"] in ("unapproved_selection_root", "selection_contents_identity_mismatch")
    assert db.scalar(select(func.count()).select_from(consumer.Revision)) == 1


@pytest.mark.parametrize("field,value", [("id", 2), ("tag_name", "catalogue-000002"), ("draft", True),
    ("prerelease", True), ("immutable", False), ("immutable", "true"), ("target_commitish", "a" * 40)])
def test_invalid_immutable_release(official_http, field, value):
    official_http["values"][f"/releases/{PINS.release_id}"][field] = value
    with pytest.raises(source.SourceError):
        retrieve()


@pytest.mark.parametrize("field,value", [("id", 2), ("name", "other"), ("state", "new"), ("size", True),
    ("size", 0), ("size", 4_194_305), ("url", "https://attacker.invalid"), ("digest", "sha256:" + "a" * 64)])
def test_wrong_selected_asset(official_http, field, value):
    official_http["values"][f"/releases/{PINS.release_id}"]["assets"][0][field] = value
    with pytest.raises(source.SourceError):
        retrieve()


@pytest.mark.parametrize("path", [ingestion.CURRENT, ingestion.ROOT_TAG])
def test_root_ref_replacement_no_sequence_one_fallback(official_http, path):
    obj = official_http["values"][path]["object"]
    obj.update(sha="a" * 40, url=f"{source.BASE}/git/commits/" + "a" * 40)
    with pytest.raises(source.SourceError, match="unapproved_selection_root"):
        retrieve()
    assert not any("/releases/" in c for c in official_http["calls"])


@pytest.mark.parametrize("case", ["parents", "inventory", "mode", "truncated", "duplicate"])
def test_bootstrap_structure(official_http, case):
    values = official_http["values"]
    commit = values[f"/git/commits/{PINS.root_commit}"]
    tree = values[f"/git/trees/{commit['tree']['sha']}"]
    if case == "parents":
        commit["parents"] = [{"sha": "a" * 40}]
    elif case == "inventory":
        tree["tree"][0]["path"] = "other.json"
    elif case == "mode":
        tree["tree"][0]["mode"] = "120000"
    elif case == "duplicate":
        tree["tree"][1] = tree["tree"][0]
    else:
        tree["truncated"] = True
    with pytest.raises(source.SourceError, match="invalid_bootstrap"):
        retrieve()


@pytest.mark.parametrize("field,value", [("path", "other"), ("name", "other"), ("type", "symlink"),
    ("encoding", "none"), ("size", True), ("size", 1025), ("content", "YWJj$"),
    ("content", "YR=="), ("content", "e30=\r\n"), ("sha", "a" * 40), ("url", "https://attacker.invalid")])
def test_strict_contents_identity_and_encoding(official_http, field, value):
    official_http["values"][f"/contents/current.json?ref={PINS.root_commit}"][field] = value
    with pytest.raises(source.SourceError):
        retrieve()


@pytest.mark.parametrize("path", [ingestion.CURRENT, f"/releases/{PINS.release_id}",
    f"/contents/current.json?ref={PINS.root_commit}"])
def test_changes_during_verification_never_confirm(db, official_http, path):
    value = deepcopy(official_http["values"][path])
    if path == ingestion.CURRENT:
        value["object"].update(sha="a" * 40, url=f"{source.BASE}/git/commits/" + "a" * 40)
    elif path.startswith("/releases/"):
        value["assets"][0]["updated_at"] = "2026-10-25T00:00:00Z"
    else:
        value["content"] = base64.b64encode(POINTER + b"\n").decode()
    official_http["after"][path] = value
    result = consumer.refresh(db)
    assert result["result"] == "failed"
    assert result["status"]["last_confirmed_current_at"] is None
    assert db.scalar(select(func.count()).select_from(consumer.Revision)) == 0


@pytest.mark.parametrize("name,other", [("catalogue.sigstore.json", SELECTION_BUNDLE),
                                        ("current.sigstore.json", BUNDLE)])
def test_wrong_genuine_profile_bundle(official_http, name, other):
    if name == "current.sigstore.json":
        # Cross-profile verifier regression uses exact frozen original evidence.
        from app.services.connector_verification import GithubSigstoreVerifier
        with pytest.raises(ProvenanceError):
            GithubSigstoreVerifier().verify_selection(POINTER, other)
    else:
        asset = official_http["values"][f"/releases/{PINS.release_id}"]["assets"][1]
        asset.update(size=len(other), digest="sha256:" + hashlib.sha256(other).hexdigest())
        official_http["values"][f"/releases/assets/{asset['id']}"] = other
        with pytest.raises(ProvenanceError):
            retrieve()


def test_audit_failure_rolls_back_genuine_candidate(db, official_http, monkeypatch):
    def fail(*a, **kw):
        raise SQLAlchemyError("private")
    monkeypatch.setattr(consumer, "add_audit_event", fail)
    result = consumer.refresh(db)
    assert result == {"result": "failed", "code": "catalogue_persistence_failed"}
    assert db.scalar(select(func.count()).select_from(consumer.Revision)) == 0
    assert db.get(consumer.State, 1).operation_id is not None


def test_lost_lease_after_genuine_verification_cannot_promote(db, official_http, monkeypatch):
    retrieve_original = source.retrieve_candidate
    async def lose(progress, **kwargs):
        candidate = await retrieve_original(progress, **kwargs)
        db.get(consumer.State, 1).operation_id = uuid.uuid4()
        db.commit()
        return candidate
    monkeypatch.setattr(source, "retrieve_candidate", lose)
    result = consumer.refresh(db)
    assert result["code"] == "refresh_ownership_lost"
    assert db.scalar(select(func.count()).select_from(consumer.Revision)) == 0
    assert consumer.status(db)["last_confirmed_current_at"] is None


def test_interrupted_verification_retains_lease_then_recovers_without_duplicate(db, official_http, monkeypatch):
    from datetime import timedelta
    original = source.retrieve_candidate
    async def interrupted(progress, **kwargs):
        await original(progress, **kwargs)
        raise asyncio.CancelledError()
    monkeypatch.setattr(source, "retrieve_candidate", interrupted)
    with pytest.raises(asyncio.CancelledError):
        consumer.refresh(db)
    state = db.get(consumer.State, 1)
    assert state.operation_id is not None and state.highest_sequence is None
    assert db.scalar(select(func.count()).select_from(consumer.Revision)) == 0
    state.lease_until = source.utcnow() - timedelta(seconds=1)
    db.commit()
    monkeypatch.setattr(source, "retrieve_candidate", original)
    assert consumer.refresh(db)["result"] == "accepted"
    assert db.scalar(select(func.count()).select_from(consumer.Revision)) == 1


@pytest.mark.parametrize("mutation,code", [("actor", "publication_evidence_actor"),
    ("rerun", "publication_evidence_first_attempt_required"), ("ci", "publication_evidence_ci"),
    ("workflow", "publication_evidence_workflow"), ("ruleset", "publication_evidence_ruleset_protection"),
    ("bypass", "publication_evidence_ruleset_bypass"), ("inaccessible", "source_not_found")])
def test_public_authority_failure_reaches_api_state_without_trust(db, official_http, mutation, code):
    values = official_http["values"]
    run = f"/actions/runs/{PINS.selection_run_id}"
    if mutation == "actor":
        values[run]["triggering_actor"]["id"] = 999
    elif mutation == "rerun":
        values[run]["run_attempt"] = 2
    elif mutation == "ci":
        path = f"/commits/{PINS.selection_source}/check-runs?check_name=validate&filter=latest&per_page=2&page=1"
        values[path]["check_runs"][0]["conclusion"] = "failure"
    elif mutation == "workflow":
        values[run]["workflow_id"] = 999
    elif mutation == "ruleset":
        values[f"/rulesets/{trust.BOOTSTRAP_POLICY_PROPOSAL.rulesets.main}?includes_parents=true"]["rules"] = []
    elif mutation == "bypass":
        values[f"/rulesets/{trust.BOOTSTRAP_POLICY_PROPOSAL.rulesets.main}?includes_parents=true"]["bypass_actors"] = [
            {"actor_id": 999, "actor_type": "Integration", "bypass_mode": "always"}]
    else:
        official_http["override"][run] = Response(status=404)
    result = consumer.refresh(db)
    assert result["result"] == "failed" and result["status"]["last_error_code"] == code
    assert result["status"]["trusted_remote_available"] is False
    assert db.scalar(select(func.count()).select_from(consumer.Revision)) == 0


@pytest.mark.parametrize("raw", [RAW + b"\n", RAW.replace(b'"sequence": 1', b'"sequence": 2')])
def test_altered_or_noncanonical_original_catalogue_rejected(official_http, raw):
    asset = official_http["values"][f"/releases/{PINS.release_id}"]["assets"][0]
    asset.update(size=len(raw), digest="sha256:" + hashlib.sha256(raw).hexdigest())
    official_http["values"][f"/releases/assets/{asset['id']}"] = raw
    with pytest.raises(source.SourceError, match="selected_catalogue_digest_mismatch"):
        retrieve()


@pytest.mark.parametrize("raw", [b'{"ref":1,"ref":2}', b'{}', b'\xff', b'{}' * 200_000])
def test_selection_metadata_invalid_or_ambiguous_original_response(official_http, raw):
    official_http["override"][ingestion.CURRENT] = Response(raw)
    with pytest.raises(source.SourceError):
        retrieve()


def test_release_annotated_tag_source_binding_is_bounded(official_http):
    values = official_http["values"]
    obj = values["/git/ref/tags/catalogue-000001"]["object"]
    original = deepcopy(obj)
    sha = "a" * 40
    obj.update(type="tag", sha=sha, url=f"{source.BASE}/git/tags/{sha}")
    values[f"/git/tags/{sha}"] = {"sha": sha, "tag": "catalogue-000001", "url": obj["url"], "object": original}
    candidate, _ = retrieve()
    assert candidate.provenance.source_commit == PINS.catalogue_build_source
    values[f"/git/tags/{sha}"]["object"] = obj
    with pytest.raises(source.SourceError, match="catalogue_tag_depth"):
        retrieve()


def test_completed_candidate_cannot_cross_refresh_operation(db, official_http, monkeypatch):
    candidate, _ = retrieve()
    async def replay(progress, **kw):
        return candidate
    monkeypatch.setattr(source, "retrieve_candidate", replay)
    result = consumer.refresh(db)
    assert result["status"]["last_error_code"] == "catalogue_operation_mismatch"
    assert db.scalar(select(func.count()).select_from(consumer.Revision)) == 0


def test_release_tag_must_bind_original_catalogue_source(official_http):
    obj = official_http["values"]["/git/ref/tags/catalogue-000001"]["object"]
    obj.update(sha="a" * 40, url=f"{source.BASE}/git/commits/" + "a" * 40)
    with pytest.raises(source.SourceError, match="catalogue_tag_source_mismatch"):
        retrieve()


def test_retained_pointer_is_identical(official_http):
    asset = official_http["values"][f"/releases/{PINS.release_id}"]["assets"][2]
    changed = POINTER + b"\n"
    asset.update(size=len(changed), digest="sha256:" + hashlib.sha256(changed).hexdigest())
    official_http["values"][f"/releases/assets/{asset['id']}"] = changed
    with pytest.raises(source.SourceError, match="retained_selection_mismatch"):
        retrieve()


def test_approval_fingerprint_and_fixed_decision(monkeypatch):
    approved = trust.approved_bootstrap_policy()
    assert approved.approval_reference == "atlas-owner-2026-10-25-adr-0013"
    monkeypatch.setattr(trust, "BOOTSTRAP_POLICY_PROPOSAL", replace(approved.proposal, workflow_id=999))
    with pytest.raises(trust.CatalogueTrustPolicyError, match="approved_bootstrap_pin_mismatch"):
        trust.approved_bootstrap_policy()


@pytest.mark.parametrize("path", ["/releases/1", "/contents/current.json?ref=main", "/git/ref/heads/main",
    "/git/ref/tags/catalogue-000002", "/contents/other.json?ref=" + PINS.root_commit, "https://attacker.invalid"])
def test_selection_endpoint_allowlist_rejects_arbitrary_routing(path):
    with pytest.raises(source.SourceError, match="invalid_source_destination"):
        asyncio.run(source.GithubReader().selection_metadata(path))


def test_sequence_gap_and_missing_retained_history(db):
    from tests.test_trusted_catalogue import store, changed, STORAGE_ONLY
    with pytest.raises(source.SourceError, match="catalogue_sequence_gap"):
        store(db, changed(2))
    db.rollback()
    store(db)
    with pytest.raises(source.SourceError, match="catalogue_sequence_gap"):
        store(db, changed(3))
    db.rollback()
    raw = changed(3)
    db.add(consumer.Revision(sequence=3, source=source.SOURCE, schema_version="1.0",
        content_digest=hashlib.sha256(raw).hexdigest(), original_bytes=raw, generated_at=source.utcnow(),
        verification_evidence=STORAGE_ONLY, publication_evidence=STORAGE_ONLY, accepted_at=source.utcnow()))
    db.commit()
    with pytest.raises(source.SourceError, match="checkpoint_inconsistent"):
        consumer.claim(db)
