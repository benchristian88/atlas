"""R1/R2/R4 gates: real HTTP, production sessions, committed PostgreSQL state."""
from concurrent.futures import ThreadPoolExecutor
from threading import Event

import pytest
from sqlalchemy import event, func, select, text

from app.models import Asset, AssetRelationship, AuditEvent, DataSource, DiscoveryRun, EntitySourceLink, KnowledgeAssertion, KnowledgeChange, ReconciliationItem, Site
from app.services.entity_resolution import ensure_asset_link
from app.services.knowledge_assertions import record_assertion
from app.services.reconciliation import create_item
from tests.test_reconciliation_integrity_postgres import committed, review, accept, pytestmark


@pytest.mark.parametrize("field,observed,manual", [
    ("name", "Observed", "New manual value"), ("asset_type", "virtual_machine", "hypervisor_node"),
    ("hostname", "observed-host", "manual-host"), ("status", "inactive", "retired"),
    ("vendor", "observed-vendor", "manual-vendor"), ("model", "observed-model", "manual-model"),
    ("ip_address", "192.0.2.1", "192.0.2.2"), ("description", "Observed", "New manual value"),
])
@pytest.mark.parametrize("bulk", [False, True])
def test_r1_refreshed_display_version_and_locked_changes_agree(committed, field, observed, manual, bulk):
    s = committed
    identifier, claim_id = s.proposal(field, observed)
    original, _ = review(s, identifier)
    with s.session() as db:
        assert original["current"] == getattr(db.get(Asset, s.asset.id), field)
        proposal_snapshot = db.get(ReconciliationItem, identifier).current_value_json
    assert s.client.patch(f'/assets/{s.asset.id}', json={field: manual}).status_code == 200
    fresh, _ = review(s, identifier)
    assert fresh["current"] == manual
    assert fresh["current_value_json"] == {"field": field, "value": manual}
    assert fresh["version"] != original["version"]
    stale = accept(s, identifier, version=original["version"], bulk=bulk)
    assert (stale.status_code == 200 and len(stale.json()["failed"]) == 1) if bulk else stale.status_code == 409
    result = accept(s, identifier, version=fresh["version"], bulk=bulk)
    assert result.status_code == 200, result.text
    if bulk:
        assert len(result.json()["accepted"]) == 1 and not result.json()["failed"]
    with s.session() as db:
        assert getattr(db.get(Asset, s.asset.id), field) == observed
        assert db.get(KnowledgeAssertion, claim_id).is_accepted
        item = db.get(ReconciliationItem, identifier)
        assert item.status == "accepted" and item.current_value_json == proposal_snapshot
        change = db.scalar(select(KnowledgeChange).where(KnowledgeChange.reconciliation_item_id == identifier))
        assert change.previous_value_json == {"field": field, "value": manual}
        assert change.new_value_json == {"field": field, "value": observed}
        assert db.scalar(select(func.count()).select_from(AuditEvent).where(
            AuditEvent.customer_id == s.customer.id, AuditEvent.event_type == "reconciliation.accepted")) == 1
        selected = list(db.scalars(select(KnowledgeAssertion).where(KnowledgeAssertion.subject_id == s.asset.id,
            KnowledgeAssertion.predicate == field, KnowledgeAssertion.is_accepted.is_(True))))
        assert [claim.id for claim in selected] == [claim_id]


DISPOSITIONS = {"mark_missing": "missing", "mark_inactive": "inactive", "mark_retired": "retired",
                "retire": "retired", "keep_active": None, "exception": None}


def absence(s):
    with s.session() as db:
        claim, _ = record_assertion(db, customer_id=s.customer.id, site_id=s.site.id,
            subject_type="asset", subject_id=s.asset.id, subject_external_id="source-0",
            predicate="observation_state", value="not_observed", data_source_id=s.sources[0].id)
        item, _ = create_item(db, assertion=claim, category="no_longer_observed", entity_type="asset",
            entity_id=s.asset.id, candidate_external_id="source-0", current_value={"status": "active"},
            observed_value={"state": "not_observed", "coverage_key": "synthetic-complete"}, recommended_action="Review absence")
        db.commit()
        return item.id, claim.id


@pytest.mark.parametrize("disposition", DISPOSITIONS)
@pytest.mark.parametrize("versioned", [False, True])
@pytest.mark.parametrize("changed_back", [False, True])
def test_r2_stale_absence_cannot_replace_manual_status(committed, disposition, versioned, changed_back):
    s = committed
    identifier, claim_id = absence(s)
    old, _ = review(s, identifier)
    assert s.client.patch(f'/assets/{s.asset.id}', json={"status": "retired"}).status_code == 200
    if changed_back:
        assert s.client.patch(f'/assets/{s.asset.id}', json={"status": "active"}).status_code == 200
    payload = {"disposition": disposition}
    if versioned:
        payload["expected_version"] = old["version"]
    result = s.client.post(f'/reconciliation-items/{identifier}/accept', json=payload)
    assert result.status_code == 409, result.text
    with s.session() as db:
        expected = "active" if changed_back else "retired"
        assert db.get(Asset, s.asset.id).status == expected
        assert db.get(ReconciliationItem, identifier).status == "open"
        assert db.get(KnowledgeAssertion, claim_id).value_json == "not_observed"
        assert db.scalar(select(KnowledgeAssertion.value_json).where(KnowledgeAssertion.subject_id == s.asset.id,
            KnowledgeAssertion.predicate == "status", KnowledgeAssertion.is_accepted.is_(True))) == expected
        assert db.scalar(select(func.count()).select_from(KnowledgeChange).where(
            KnowledgeChange.reconciliation_item_id == identifier)) == 0
        assert db.scalar(select(func.count()).select_from(AuditEvent).where(
            AuditEvent.customer_id == s.customer.id, AuditEvent.event_type == "reconciliation.accepted")) == 0


@pytest.mark.parametrize("disposition,target", DISPOSITIONS.items())
@pytest.mark.parametrize("versioned", [False, True])
def test_r2_fresh_explicit_lifecycle_has_consistent_selected_knowledge(committed, disposition, target, versioned):
    s = committed
    # Retain accepted manual knowledge before the explicit lifecycle decision.
    assert s.client.patch(f'/assets/{s.asset.id}', json={"status": "inactive"}).status_code == 200
    identifier, claim_id = absence(s)
    row, group = review(s, identifier)
    assert row["current"] == {"status": "inactive"} and not row["can_accept"]
    bulk = s.client.post(f'/reconciliation-entities/{group["id"]}/accept',
        json={"items": [{"id": str(identifier), "version": row["version"]}]})
    assert bulk.status_code == 200 and len(bulk.json()["blocked"]) == 1
    payload = {"disposition": disposition, "reason": "Explicit reviewed lifecycle choice"}
    if versioned:
        payload["expected_version"] = row["version"]
    result = s.client.post(f'/reconciliation-items/{identifier}/accept', json=payload)
    assert result.status_code == (200 if versioned else 409), result.text
    with s.session() as db:
        expected = (target or "inactive") if versioned else "inactive"
        assert db.get(Asset, s.asset.id).status == expected
        selected = list(db.scalars(select(KnowledgeAssertion).where(KnowledgeAssertion.subject_id == s.asset.id,
            KnowledgeAssertion.predicate == "status", KnowledgeAssertion.is_accepted.is_(True))))
        assert [claim.value_json for claim in selected] == [expected]
        observation = db.get(KnowledgeAssertion, claim_id)
        assert observation.value_json == "not_observed" and observation.is_source_current and not observation.is_accepted
        item = db.get(ReconciliationItem, identifier)
        assert item.observed_value_json["coverage_key"] == "synthetic-complete"
        assert item.status == (("exception" if disposition == "exception" else "accepted") if versioned else "open")
        changes = list(db.scalars(select(KnowledgeChange).where(KnowledgeChange.reconciliation_item_id == identifier)))
        assert len(changes) == int(versioned)
        if versioned:
            assert changes[0].previous_value_json == "inactive" and changes[0].new_value_json == expected
            if disposition == "keep_active":
                assert changes[0].summary == "Retained Curated's inactive status after absence review"
            if expected != "inactive":
                assert changes[0].assertion_id == selected[0].id and changes[0].predicate == "status"
                prior = next(c for c in db.scalars(select(KnowledgeAssertion).where(
                    KnowledgeAssertion.subject_id == s.asset.id, KnowledgeAssertion.predicate == "status"))
                    if c.value_json == "inactive")
                assert prior and not prior.is_accepted and prior.acceptance_replaced_by_id == selected[0].id
                assert not prior.is_source_current and prior.superseded_by_id == selected[0].id
        assert db.scalar(select(func.count()).select_from(AuditEvent).where(
            AuditEvent.customer_id == s.customer.id, AuditEvent.event_type == "reconciliation.accepted")) == int(versioned)


@pytest.mark.parametrize("first", ["manual", "retract"])
def test_r4_manual_patch_retraction_implicit_fk_lock_race(committed, first):
    s = committed
    assert s.client.patch(f'/assets/{s.asset.id}', json={"description": "first declaration"}).status_code == 200
    with s.session() as db:
        old = db.scalar(select(KnowledgeAssertion).where(KnowledgeAssertion.subject_id == s.asset.id,
            KnowledgeAssertion.predicate == "description", KnowledgeAssertion.is_accepted.is_(True)))
        identifier, source_id = old.id, old.data_source_id
    asset_locked, source_locked = Event(), Event()
    states, source_sql = [], []
    def after(conn, cursor, sql, parameters, context, executemany):
        actor = context.execution_options.get("test_actor")
        if actor == "manual" and "FROM assets" in sql and "FOR UPDATE" in sql and not asset_locked.is_set():
            asset_locked.set()
            assert source_locked.wait(8)
        if actor == "retract" and "FROM data_sources" in sql and "FOR " in sql:
            source_sql.append(sql)
            source_locked.set()
            assert asset_locked.wait(8)
    def errors(context):
        states.append(getattr(context.original_exception, "sqlstate", None))
    event.listen(s.engine, "after_cursor_execute", after)
    event.listen(s.engine, "handle_error", errors)
    try:
        operations = {
            "manual": lambda: s.client.patch(f'/assets/{s.asset.id}', json={"description": "second declaration"}, headers={"x-test-actor": "manual"}),
            "retract": lambda: s.client.post(f'/assertions/{identifier}/retract', json={"reason": "Retraction under concurrent edit", "confirm_provenance_gap": True}, headers={"x-test-actor": "retract"}),
        }
        with ThreadPoolExecutor(max_workers=2) as pool:
            a = pool.submit(operations[first])
            assert (asset_locked if first == "manual" else source_locked).wait(8)
            b = pool.submit(operations["retract" if first == "manual" else "manual"])
            results = [f.result(timeout=25) for f in (a, b)]
        assert [r.status_code for r in results] == [200, 200], [r.text for r in results]
        assert not states and source_sql and all("FOR NO KEY UPDATE" in sql for sql in source_sql)
    finally:
        event.remove(s.engine, "after_cursor_execute", after)
        event.remove(s.engine, "handle_error", errors)
    with s.session() as db:
        assert db.get(Asset, s.asset.id).description == "second declaration"
        assert db.get(KnowledgeAssertion, identifier).retracted_at is not None
        declarations = list(db.scalars(select(KnowledgeAssertion).where(KnowledgeAssertion.subject_id == s.asset.id,
            KnowledgeAssertion.predicate == "description")))
        assert len(declarations) == 2
        assert [c.value_json for c in declarations if c.is_accepted] == ["second declaration"]
        assert all(c.data_source_id == source_id for c in declarations)
        assert db.scalar(select(func.count()).select_from(KnowledgeChange).where(KnowledgeChange.customer_id == s.customer.id,
            KnowledgeChange.predicate == "description")) == 3
        assert db.scalar(select(func.count()).select_from(AuditEvent).where(AuditEvent.customer_id == s.customer.id)) == 3


@pytest.mark.parametrize("kind,bulk", [("name", False), ("name", True), ("absence", False)])
def test_r1_r2_further_manual_patch_cannot_be_overwritten_after_refresh(committed, kind, bulk):
    s = committed
    identifier, claim_id = absence(s) if kind == "absence" else s.proposal("name", "Observed")
    field = "status" if kind == "absence" else "name"
    assert s.client.patch(f'/assets/{s.asset.id}', json={field: "inactive" if kind == "absence" else "First manual"}).status_code == 200
    fresh, group = review(s, identifier)
    locked, attempting = Event(), Event()
    def before(conn, cursor, sql, parameters, context, executemany):
        if context.execution_options.get("test_actor") == "decision" and "FROM assets" in sql and "FOR UPDATE" in sql:
            assert locked.wait(8)
            attempting.set()
    def after(conn, cursor, sql, parameters, context, executemany):
        if context.execution_options.get("test_actor") == "manual" and "FROM assets" in sql and "FOR UPDATE" in sql:
            locked.set()
            assert attempting.wait(8)
    def decide():
        if kind == "absence":
            return s.client.post(f'/reconciliation-items/{identifier}/accept', headers={"x-test-actor": "decision"},
                json={"disposition": "mark_missing", "expected_version": fresh["version"]})
        return accept(s, identifier, version=fresh["version"], bulk=bulk, actor="decision")
    event.listen(s.engine, "before_cursor_execute", before)
    event.listen(s.engine, "after_cursor_execute", after)
    expected = "retired" if kind == "absence" else "Second manual"
    try:
        with ThreadPoolExecutor(max_workers=2) as pool:
            manual = pool.submit(s.client.patch, f'/assets/{s.asset.id}', json={field: expected}, headers={"x-test-actor": "manual"})
            assert locked.wait(8)
            decision = pool.submit(decide)
            assert manual.result(timeout=25).status_code == 200
            result = decision.result(timeout=25)
            assert (result.status_code == 200 and len(result.json()["failed"]) == 1) if bulk else result.status_code == 409
    finally:
        event.remove(s.engine, "before_cursor_execute", before)
        event.remove(s.engine, "after_cursor_execute", after)
    with s.session() as db:
        assert getattr(db.get(Asset, s.asset.id), field) == expected
        assert not db.get(KnowledgeAssertion, claim_id).is_accepted
        assert db.get(ReconciliationItem, identifier).status == "open"
        assert db.scalar(select(func.count()).select_from(KnowledgeChange).where(KnowledgeChange.reconciliation_item_id == identifier)) == 0


def test_r4_independent_assets_do_not_wait_for_manual_source_fk(committed):
    s = committed
    assert s.client.patch(f'/assets/{s.asset.id}', json={"description": "Seed manual source"}).status_code == 200
    locked, unrelated_done = Event(), Event()
    def after(conn, cursor, sql, parameters, context, executemany):
        if context.execution_options.get("test_actor") == "held" and "FROM assets" in sql and "FOR UPDATE" in sql:
            locked.set()
            assert unrelated_done.wait(8)
    event.listen(s.engine, "after_cursor_execute", after)
    try:
        with ThreadPoolExecutor(max_workers=2) as pool:
            held = pool.submit(s.client.patch, f'/assets/{s.asset.id}', json={"description": "Held change"}, headers={"x-test-actor": "held"})
            assert locked.wait(8)
            try:
                independent = pool.submit(s.client.patch, f'/assets/{s.other.id}', json={"description": "Independent change"})
                assert independent.result(timeout=5).status_code == 200
            finally:
                unrelated_done.set()
            assert held.result(timeout=25).status_code == 200
    finally:
        event.remove(s.engine, "after_cursor_execute", after)
    with s.session() as db:
        assert db.get(Asset, s.asset.id).description == "Held change"
        assert db.get(Asset, s.other.id).description == "Independent change"


@pytest.mark.parametrize("victim", ["manual", "retract"])
def test_r4_both_conflict_victims_roll_back_after_real_flush(committed, victim):
    from app.database import SessionLocal
    s = committed
    assert s.client.patch(f'/assets/{s.asset.id}', json={"description": "Committed declaration"}).status_code == 200
    with s.session() as db:
        identifier = db.scalar(select(KnowledgeAssertion.id).where(KnowledgeAssertion.subject_id == s.asset.id,
            KnowledgeAssertion.predicate == "description", KnowledgeAssertion.is_accepted.is_(True)))
        before_changes = db.scalar(select(func.count()).select_from(KnowledgeChange).where(KnowledgeChange.customer_id == s.customer.id))
        before_audits = db.scalar(select(func.count()).select_from(AuditEvent).where(AuditEvent.customer_id == s.customer.id))
    reached = []
    def force_post_flush_victim(db):
        if not db.in_nested_transaction() and db.connection().get_execution_options().get("test_actor") == "victim":
            db.flush()
            reached.append(True)
            # PostgreSQL marks the real transaction failed with the same driver
            # exception as a deadlock victim, after all decision writes flushed.
            db.execute(text("DO $$ BEGIN RAISE EXCEPTION 'synthetic transaction victim' USING ERRCODE = '40P01'; END $$"))
    event.listen(SessionLocal.class_, "before_commit", force_post_flush_victim)
    try:
        if victim == "manual":
            result = s.client.patch(f'/assets/{s.asset.id}', json={"description": "Rolled back declaration"}, headers={"x-test-actor": "victim"})
        else:
            result = s.client.post(f'/assertions/{identifier}/retract', json={"reason": "Rolled back retraction", "confirm_provenance_gap": True}, headers={"x-test-actor": "victim"})
        assert result.status_code == 409 and reached == [True], result.text
    finally:
        event.remove(SessionLocal.class_, "before_commit", force_post_flush_victim)
    with s.session() as db:
        assert db.get(Asset, s.asset.id).description == "Committed declaration"
        old = db.get(KnowledgeAssertion, identifier)
        assert old.is_accepted and old.retracted_at is None and old.acceptance_replaced_by_id is None
        assert db.scalar(select(func.count()).select_from(KnowledgeAssertion).where(KnowledgeAssertion.subject_id == s.asset.id)) == 1
        assert db.scalar(select(func.count()).select_from(KnowledgeChange).where(KnowledgeChange.customer_id == s.customer.id)) == before_changes
        assert db.scalar(select(func.count()).select_from(AuditEvent).where(AuditEvent.customer_id == s.customer.id)) == before_audits


def test_r2_r4_manual_declaration_refresh_preserves_pending_source_history(committed):
    s = committed
    for description in ("First manual", "Second manual"):
        assert s.client.patch(f'/assets/{s.asset.id}', json={"description": description}).status_code == 200
    with s.session() as db:
        claims = list(db.scalars(select(KnowledgeAssertion).where(KnowledgeAssertion.subject_id == s.asset.id,
            KnowledgeAssertion.predicate == "description")))
        old = next(c for c in claims if c.value_json == "First manual")
        current = next(c for c in claims if c.value_json == "Second manual")
        assert current.is_accepted and current.is_source_current
        assert not old.is_accepted and not old.is_source_current
        assert old.superseded_by_id == old.acceptance_replaced_by_id == current.id


@pytest.mark.parametrize("disposition,target", [(k, v) for k, v in DISPOSITIONS.items() if v])
@pytest.mark.parametrize("legacy_selected", [None, "active"])
def test_r2_explicit_status_choice_selects_knowledge_even_without_field_delta(committed, disposition, target, legacy_selected):
    s = committed
    with s.session() as db:
        # A legacy operational value may lack a selected assertion or disagree
        # with it. A fresh explicit lifecycle choice must select its own value,
        # even if the operational column already equals that chosen status.
        db.get(Asset, s.asset.id).status = target
        prior_id = None
        if legacy_selected:
            from app.services.knowledge_assertions import accept_assertion
            prior, _ = record_assertion(db, customer_id=s.customer.id, site_id=s.site.id,
                subject_type="asset", subject_id=s.asset.id, predicate="status", value=legacy_selected,
                data_source_id=s.sources[0].id)
            accept_assertion(db, prior)
            prior_id = prior.id
        db.commit()
    identifier, observation_id = absence(s)
    row, _ = review(s, identifier)
    assert row["current"] == {"status": target}
    result = s.client.post(f'/reconciliation-items/{identifier}/accept',
        json={"disposition": disposition, "expected_version": row["version"]})
    assert result.status_code == 200, result.text
    with s.session() as db:
        selected = list(db.scalars(select(KnowledgeAssertion).where(KnowledgeAssertion.subject_id == s.asset.id,
            KnowledgeAssertion.predicate == "status", KnowledgeAssertion.is_accepted.is_(True))))
        assert [c.value_json for c in selected] == [target]
        assert selected[0].truth_classification == "declared"
        if prior_id:
            prior = db.get(KnowledgeAssertion, prior_id)
            assert prior.value_json == legacy_selected and not prior.is_accepted
            assert prior.acceptance_replaced_by_id == selected[0].id and prior.is_source_current
        change = db.scalar(select(KnowledgeChange).where(KnowledgeChange.reconciliation_item_id == identifier))
        assert change.previous_value_json == change.new_value_json == target
        assert change.assertion_id == selected[0].id and change.predicate == "status"
        assert db.get(KnowledgeAssertion, observation_id).value_json == "not_observed"


def test_r1_legacy_item_projection_uses_attached_canonical_subject(committed):
    s = committed
    identifier, _ = s.proposal("name", "Observed")
    with s.session() as db:
        # Existing field items can retain a null entity_id after source identity
        # attachment; their assertion already identifies the canonical Asset.
        db.get(ReconciliationItem, identifier).entity_id = None
        db.commit()
    assert s.client.patch(f'/assets/{s.asset.id}', json={"name": "New manual value"}).status_code == 200
    response = s.client.get('/reconciliation-items')
    assert response.status_code == 200, response.text
    row = next(row for row in response.json() if row["id"] == str(identifier))
    assert row["current_value_json"] == {"field": "name", "value": "New manual value"}
    assert row["entity_name"] == "New manual value"
    fresh, _ = review(s, identifier)
    assert fresh["current"] == row["current_value_json"]["value"]
    assert accept(s, identifier, version=fresh["version"]).status_code == 200


def test_r4_ingestion_locks_known_subjects_before_claims_and_relationship_declarations(committed):
    s = committed
    first, old_id = s.proposal("hostname", "host-A")
    assert accept(s, first).status_code == 200
    second, selected_id = s.proposal("hostname", "host-B", source=1)
    version = review(s, second)[0]["version"]
    with s.session() as db:
        for asset, external in ((s.asset, "source-0"), (s.other, "target")):
            ensure_asset_link(db, data_source_id=s.sources[0].id, asset=db.get(Asset, asset.id), external_id=external)
        db.add(AssetRelationship(source_asset_id=s.asset.id, target_asset_id=s.other.id,
            customer_id=s.customer.id, site_id=s.site.id, relationship_type="runs_on", legacy_cross_context=False))
        db.commit()
    payload = {"customer_id": str(s.customer.id), "site_id": str(s.site.id), "data_source_id": str(s.sources[0].id),
        "observations": [{"entity_kind": "asset", "external_id": "source-0", "name": "Curated",
            "asset_type": "virtual_machine", "facts": {"hostname": "host-C"},
            "relationships": [{"relationship_type": "runs_on", "target_external_id": "target"}]}]}
    decision_locked, ingestion_reached = Event(), Event()
    steps, states = [], []
    def before(conn, cursor, sql, parameters, context, executemany):
        if context.execution_options.get("test_actor") == "ingest" and "FROM assets" in sql and "FOR UPDATE" in sql:
            steps.append("subject")
            ingestion_reached.set()
    def after(conn, cursor, sql, parameters, context, executemany):
        actor = context.execution_options.get("test_actor")
        if actor == "decision" and "FROM assets" in sql and "FOR UPDATE" in sql and not decision_locked.is_set():
            decision_locked.set()
            assert ingestion_reached.wait(8)
        if actor == "ingest" and sql.startswith("UPDATE knowledge_assertions") and str(old_id) in str(parameters):
            steps.append("claim")
            ingestion_reached.set()
    def errors(context):
        states.append(getattr(context.original_exception, "sqlstate", None))
    event.listen(s.engine, "before_cursor_execute", before)
    event.listen(s.engine, "after_cursor_execute", after)
    event.listen(s.engine, "handle_error", errors)
    try:
        with ThreadPoolExecutor(max_workers=2) as pool:
            decision = pool.submit(accept, s, second, version=version, actor="decision")
            assert decision_locked.wait(8)
            ingestion = pool.submit(s.client.post, '/discovery/simulate', json=payload, headers={"x-test-actor": "ingest"})
            results = [f.result(timeout=25) for f in (decision, ingestion)]
        assert not states, states
        assert [r.status_code for r in results] == [200, 200], [r.text for r in results]
        assert steps.index("subject") < steps.index("claim")
    finally:
        event.remove(s.engine, "before_cursor_execute", before)
        event.remove(s.engine, "after_cursor_execute", after)
        event.remove(s.engine, "handle_error", errors)
    with s.session() as db:
        old = db.get(KnowledgeAssertion, old_id)
        assert old.acceptance_replaced_by_id == selected_id and old.superseded_by_id
        assert db.get(KnowledgeAssertion, old.superseded_by_id).value_json == "host-C"
        assert db.get(Asset, s.asset.id).hostname == "host-B"
        assert db.get(KnowledgeAssertion, selected_id).is_accepted and not old.is_accepted


def test_r4_ingestion_does_not_lock_unreferenced_source_linked_assets(committed):
    s = committed
    with s.session() as db:
        for asset, external in ((s.asset, "source-0"), (s.other, "unrelated")):
            ensure_asset_link(db, data_source_id=s.sources[0].id, asset=db.get(Asset, asset.id), external_id=external)
        db.commit()
    locked, ingestion_done = Event(), Event()
    def after(conn, cursor, sql, parameters, context, executemany):
        if context.execution_options.get("test_actor") == "held" and "FROM assets" in sql and "FOR UPDATE" in sql:
            locked.set()
            assert ingestion_done.wait(8)
    event.listen(s.engine, "after_cursor_execute", after)
    try:
        with ThreadPoolExecutor(max_workers=2) as pool:
            manual = pool.submit(s.client.patch, f'/assets/{s.other.id}', json={"description": "Independent manual edit"}, headers={"x-test-actor": "held"})
            assert locked.wait(8)
            try:
                ingestion = pool.submit(s.client.post, '/discovery/simulate', json={"customer_id": str(s.customer.id),
                    "site_id": str(s.site.id), "data_source_id": str(s.sources[0].id),
                    "observations": [{"entity_kind": "asset", "external_id": "source-0", "name": "Curated", "asset_type": "virtual_machine", "facts": {}}]})
                response = ingestion.result(timeout=5)
                assert response.status_code == 200, response.text
            finally:
                ingestion_done.set()
            assert manual.result(timeout=25).status_code == 200
    finally:
        event.remove(s.engine, "after_cursor_execute", after)


def test_r1_versionless_changed_back_rejects_transactions_started_before_proposal(committed):
    s = committed
    first_locked, second_started, release_first = Event(), Event(), Event()
    def before(conn, cursor, sql, parameters, context, executemany):
        if context.execution_options.get("test_actor") == "back" and "FROM assets" in sql and "FOR UPDATE" in sql and not second_started.is_set():
            # PostgreSQL now()/updated_at uses transaction start, not commit or
            # statement time. Start this PATCH before the proposal is created.
            conn.exec_driver_sql("SELECT transaction_timestamp()")
            second_started.set()
    def after(conn, cursor, sql, parameters, context, executemany):
        if context.execution_options.get("test_actor") == "first" and "FROM assets" in sql and "FOR UPDATE" in sql and not first_locked.is_set():
            first_locked.set()
            assert release_first.wait(8)
    event.listen(s.engine, "before_cursor_execute", before)
    event.listen(s.engine, "after_cursor_execute", after)
    try:
        with ThreadPoolExecutor(max_workers=2) as pool:
            first = pool.submit(s.client.patch, f'/assets/{s.asset.id}', json={"status": "retired"}, headers={"x-test-actor": "first"})
            assert first_locked.wait(8)
            back = pool.submit(s.client.patch, f'/assets/{s.asset.id}', json={"status": "active"}, headers={"x-test-actor": "back"})
            assert second_started.wait(8)
            try:
                identifier, claim_id = s.proposal("status", "missing")
            finally:
                release_first.set()
            assert first.result(timeout=25).status_code == back.result(timeout=25).status_code == 200
    finally:
        release_first.set()
        event.remove(s.engine, "before_cursor_execute", before)
        event.remove(s.engine, "after_cursor_execute", after)
    with s.session() as db:
        asset, item = db.get(Asset, s.asset.id), db.get(ReconciliationItem, identifier)
        assert asset.status == item.current_value_json["value"] == "active"
        assert asset.updated_at < item.created_at  # The old greater-than guard cannot detect this race.
    result = s.client.post(f'/reconciliation-items/{identifier}/accept', json={})
    assert result.status_code == 409, result.text
    with s.session() as db:
        assert db.get(Asset, s.asset.id).status == "active"
        assert not db.get(KnowledgeAssertion, claim_id).is_accepted


def test_r1_versionless_legacy_item_without_canonical_baseline_requires_review(committed):
    s = committed
    identifier, _ = s.proposal("name", "Observed")
    with s.session() as db:
        db.get(ReconciliationItem, identifier).current_value_json = {"field": "name", "value": "Curated"}
        db.commit()
    assert s.client.post(f'/reconciliation-items/{identifier}/accept', json={}).status_code == 409
    assert accept(s, identifier).status_code == 200


@pytest.mark.parametrize("unavailable", ["missing", "other_site"])
def test_r1_unavailable_canonical_value_never_falls_back_to_original_snapshot(committed, unavailable):
    import uuid
    s = committed
    identifier, claim_id = s.proposal("name", "Observed")
    with s.session() as db:
        target_id = uuid.uuid4()
        if unavailable == "other_site":
            site = Site(customer_id=s.customer.id, name="Other site")
            db.add(site); db.flush()
            asset = Asset(customer_id=s.customer.id, site_id=site.id, workspace_id=s.asset.workspace_id,
                name="Hidden canonical value", asset_type="virtual_machine")
            db.add(asset); db.flush()
            target_id = asset.id
        db.get(ReconciliationItem, identifier).entity_id = target_id
        db.get(KnowledgeAssertion, claim_id).subject_id = target_id
        db.commit()
    row, _ = review(s, identifier)
    assert row["current"] is None and row["current_value_json"] is None and not row["can_accept"]
    response = s.client.get('/reconciliation-items')
    projected = next(r for r in response.json() if r["id"] == str(identifier))
    assert projected["current_value_json"] is None and "Hidden canonical value" not in response.text
    assert accept(s, identifier, version=row["version"]).status_code == 409


def test_r4_run_provenance_fk_and_source_lock_share_one_compatible_order(committed):
    from datetime import datetime, timezone
    from sqlalchemy.exc import DBAPIError
    from app.routes.integration_discovery import debug_run
    from app.schemas import SimulatedDiscoveryRequest
    from app.services.simulated_discovery import ingest_observations
    from tests.test_administration import make_principal
    s = committed
    identifier, claim_id = s.proposal("hostname", "host-B", source=1)
    with s.session() as db:
        run = DiscoveryRun(customer_id=s.customer.id, site_id=s.site.id, data_source_id=s.sources[1].id,
            started_at=datetime.now(timezone.utc), status="running", coverage_key="synthetic-run-lock-scope",
            summary={}, created_by_user_id=s.principal.user.id)
        db.add(run); db.flush()
        db.get(KnowledgeAssertion, claim_id).discovery_run_id = run.id
        ensure_asset_link(db, data_source_id=s.sources[1].id, asset=db.get(Asset, s.asset.id), external_id="source-1")
        db.commit(); run_id = run.id
    version = review(s, identifier)[0]["version"]
    source_locked, run_locked = Event(), Event()
    states, run_sql = [], []
    def after(conn, cursor, sql, parameters, context, executemany):
        actor = context.execution_options.get("test_actor")
        if actor == "decision" and "FROM data_sources" in sql and "FOR " in sql and not source_locked.is_set():
            source_locked.set()
            assert run_locked.wait(8)
        if actor == "run" and "FROM discovery_runs" in sql and "FOR " in sql:
            run_sql.append(sql)
    def errors(context):
        actor = context.execution_context.execution_options.get("test_actor") if context.execution_context else None
        if actor in {"run", "decision"}:
            states.append(getattr(context.original_exception, "sqlstate", None))
    def ingestion():
        with s.session() as db:
            db.connection(execution_options={"test_actor": "run"})
            run = debug_run(db, make_principal("integration_runtime.manage", "integrations.view"), run_id)
            # The weaker mode still excludes another state writer. FK KEY SHARE
            # is the only extra concurrency it permits, not concurrent updates.
            with s.session() as probe:
                probe.connection(execution_options={"test_actor": "probe"})
                with pytest.raises(DBAPIError) as blocked:
                    probe.get(DiscoveryRun, run_id, with_for_update={"key_share": True, "nowait": True})
                assert blocked.value.orig.sqlstate == "55P03"
            run_locked.set()
            source = db.get(DataSource, s.sources[1].id)
            payload = SimulatedDiscoveryRequest.model_validate({"customer_id": str(s.customer.id), "site_id": str(s.site.id),
                "data_source_id": str(source.id), "observations": [{"entity_kind": "asset", "external_id": "source-1",
                    "name": "Curated", "asset_type": "virtual_machine", "facts": {"hostname": "host-B"}}]})
            ingest_observations(db, payload=payload, user_id=s.principal.user.id, source=source, run=run,
                observed_at=datetime.now(timezone.utc))
            db.commit()
            return True
    event.listen(s.engine, "after_cursor_execute", after)
    event.listen(s.engine, "handle_error", errors)
    try:
        with ThreadPoolExecutor(max_workers=2) as pool:
            decision = pool.submit(accept, s, identifier, version=version, actor="decision")
            assert source_locked.wait(8)
            stream = pool.submit(ingestion)
            response, ingested = decision.result(timeout=25), stream.result(timeout=25)
        assert not states, states
        assert response.status_code == 200 and ingested, response.text
        assert run_sql and all("FOR NO KEY UPDATE" in sql for sql in run_sql)
    finally:
        event.remove(s.engine, "after_cursor_execute", after)
        event.remove(s.engine, "handle_error", errors)
    with s.session() as db:
        assert db.get(DiscoveryRun, run_id).status == "running"
        assert db.get(Asset, s.asset.id).hostname == "host-B"
        assert db.get(KnowledgeAssertion, claim_id).is_accepted
        change = db.scalar(select(KnowledgeChange).where(KnowledgeChange.reconciliation_item_id == identifier))
        assert change.discovery_run_id == run_id
