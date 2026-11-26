"""Checkpoint 1 uses PostgreSQL storage fixtures, with no decision routes."""
from datetime import datetime, timezone
import os
import re
from types import SimpleNamespace
import uuid

import pytest
from sqlalchemy import inspect, text
from sqlalchemy.exc import IntegrityError, OperationalError

from app.database import SessionLocal
from app.models import (
    Asset, AssetInterface, Customer, DataSource, DiscoveryBatchReceipt, DiscoveryRun,
    EntitySourceLink, EvidenceRecord, Integration, KnowledgeAssertion, KnowledgeChange,
    ProxmoxGuestIdentityDecision, ReconciliationItem, RunObservedEntity, Site, Workspace,
)
from tests.test_backup_postgres import installations, portable_backup, restore
from tests.test_knowledge_integrity_migration import migrated_history, pytestmark


BASELINE = "20261101_0032"
HEAD = "20261119_0033"
LIFETIME_KEY = "uq_entity_source_links_source_type_external"
CURRENT_KEY = "uq_entity_source_links_current_source_type_external"
HISTORICAL_KEY = "uq_entity_source_links_source_type_external_epoch"
DECISION_TABLE = "proxmox_guest_identity_decisions"
ADDED_COLUMNS = {
    "assets": ["identity_retirement_revision"],
    "asset_interfaces": [],
    "data_sources": ["identity_epoch"],
    "discovery_runs": ["identity_epoch"],
    "discovery_batch_receipts": [],
    "entity_source_links": ["opened_epoch", "ended_epoch"],
    "evidence_records": [],
    "knowledge_assertions": ["identity_epoch"],
    "knowledge_changes": [],
    "reconciliation_items": [],
    "run_observed_entities": [],
}


def _insert(db, model, **values):
    # Core writes against the 0032 tables never refer to the new ORM columns.
    db.execute(model.__table__.insert().inline().values(**values))


def _seed(engine):
    now = datetime.now(timezone.utc)
    ids = SimpleNamespace(**{key: uuid.uuid4() for key in (
        "workspace", "customer", "site", "other_site", "source", "generic", "integration",
        "run", "guest", "reactivated", "legacy", "interface", "binding", "interface_binding",
        "generic_binding", "evidence", "claim", "item", "incomplete_claim", "incomplete_item",
    )})
    ids.guest_key = "guest/lxc/801"
    ids.scope = {"customer_id": ids.customer, "site_id": ids.site}
    origin = {"data_source_id": ids.source, **ids.scope}
    with engine.begin() as db:
        _insert(db, Workspace, id=ids.workspace, name="Identity", slug="identity-checkpoint")
        _insert(db, Customer, id=ids.customer, workspace_id=ids.workspace, name="Identity")
        _insert(db, Site, id=ids.site, customer_id=ids.customer, name="Identity")
        _insert(db, Site, id=ids.other_site, customer_id=ids.customer, name="Other site")
        _insert(db, DataSource, id=ids.source, name="Proxmox", source_type="connector", **ids.scope)
        _insert(db, DataSource, id=ids.generic, name="Import", source_type="imported_file", customer_id=ids.customer)
        _insert(db, Integration, id=ids.integration, plugin_id="proxmox", name="Proxmox",
                base_url="", username_or_token_id="", secret_reference="", connector_id="proxmox",
                connector_version="0.2.2", connector_digest="b" * 64, config_schema_version="1.0", **origin)
        for identifier, status in ((ids.guest, "retired"), (ids.reactivated, "active"), (ids.legacy, "active")):
            _insert(db, Asset, id=identifier, workspace_id=ids.workspace, name="Curated guest",
                    asset_type="virtual_machine", status=status, **ids.scope)
        _insert(db, AssetInterface, id=ids.interface, asset_id=ids.guest, name="net0")
        dates = {"first_observed_at": now, "last_observed_at": now}
        for identifier, key, target in (
            (ids.binding, ids.guest_key, ids.guest),
            (uuid.uuid4(), "guest/qemu/802", ids.reactivated),
            (uuid.uuid4(), "guest/qemu/803", ids.legacy),
        ):
            _insert(db, EntitySourceLink, id=identifier, entity_type="asset", external_id=key,
                    entity_id=target, **origin, **dates)
        _insert(db, EntitySourceLink, id=ids.generic_binding, entity_type="asset", external_id=ids.guest_key,
                entity_id=ids.guest, data_source_id=ids.generic, **ids.scope, **dates)
        _insert(db, EntitySourceLink, id=ids.interface_binding, entity_type="asset_interface",
                external_id=ids.guest_key + "/interface/net0", interface_id=ids.interface,
                interface_owner_id=ids.guest, **origin, **dates)
        _insert(db, DiscoveryRun, id=ids.run, integration_id=ids.integration, status="completed",
                dispatch_state="settled", completeness_status="complete", coverage_key="inventory",
                finalisation_hash="c" * 64, execution_provenance={"connector_id": "proxmox"},
                ingestion_generation=uuid.uuid4(), **origin)
        relationship = {"external_id": "relationship/1", "relationship_class": "proxmox.runs_on",
                        "source": {"kind": "asset", "external_id": ids.guest_key},
                        "target": {"kind": "asset", "external_id": "node/host"}}
        _insert(db, DiscoveryBatchReceipt, discovery_run_id=ids.run, sequence=1, body_hash="d" * 64,
                payload_json={"assets": [], "networks": [], "interfaces": [], "relationships": [relationship]})
        _insert(db, EvidenceRecord, id=ids.evidence, discovery_run_id=ids.run, entity_kind="relationship",
                external_id=relationship["external_id"], observed_at=now, payload_json=relationship, **origin)
        _insert(db, RunObservedEntity, discovery_run_id=ids.run, entity_type="relationship",
                external_id=relationship["external_id"], coverage_key="inventory", observed_at=now,
                evidence_record_id=ids.evidence, **origin)
        for claim, item, target, key, provenance in (
            (ids.claim, ids.item, ids.guest, ids.guest_key, {
                "discovery_run_id": ids.run, "evidence_record_id": ids.evidence,
                "value_json": {"guest_observed": False, "held_evidence_ids": [str(ids.evidence)]},
            }),
            (ids.incomplete_claim, ids.incomplete_item, ids.legacy, "guest/qemu/803", {
                "value_json": {"guest_observed": False, "held_evidence_ids": ["broken-id"]},
            }),
        ):
            _insert(db, KnowledgeAssertion, id=claim, subject_type="source_identity", subject_external_id=key,
                    predicate="source_key_present", truth_classification="observed", **origin, **dates, **provenance)
            _insert(db, ReconciliationItem, id=item, category="possible_duplicate", entity_type="source_identity",
                    assertion_id=claim, entity_id=target, candidate_external_id=key, **ids.scope)
        for target, site in ((ids.reactivated, ids.site), (ids.legacy, ids.other_site)):
            _insert(db, KnowledgeChange, id=uuid.uuid4(), entity_type="asset", entity_id=target,
                    entity_name_snapshot="Curated guest", predicate="status", change_type="fact_changed",
                    truth_classification="declared", customer_id=ids.customer, site_id=site,
                    previous_value_json="retired", new_value_json="active", summary="Declared status", occurred_at=now,
                    metadata_json={"origin": "manual_asset_edit", "accepted": True})
    return ids


@pytest.fixture
def baseline(migrated_history):
    migrated_history.migrate("upgrade", BASELINE)
    return migrated_history, _seed(migrated_history.engine)


def _snapshot(engine, *, upgraded=False, decisions=False, restore_comparison=False):
    order = {"discovery_batch_receipts": "discovery_run_id, sequence",
             DECISION_TABLE: "reconciliation_item_id"}
    columns = {table: [] if upgraded else fields for table, fields in ADDED_COLUMNS.items()}
    if restore_comparison:
        # Restore intentionally revokes run generations and updates the row.
        columns["discovery_runs"] += ["ingestion_generation", "updated_at"]
    if decisions:
        columns[DECISION_TABLE] = []
    with engine.connect() as db:
        return {table: db.scalars(text(f"""
            SELECT to_jsonb(row) - CAST(:exclude AS text[]) FROM {table} AS row
            ORDER BY {order.get(table, "id")}
        """), {"exclude": exclude}).all() for table, exclude in columns.items()}


def _revision(engine):
    with engine.connect() as db:
        return db.scalar(text("SELECT version_num FROM alembic_version"))


def test_populated_upgrade_and_predecision_downgrade(baseline, caplog):
    history, ids = baseline
    before = _snapshot(history.engine)
    history.migrate("upgrade", HEAD)
    assert _revision(history.engine) == HEAD
    assert _snapshot(history.engine) == before
    assert "preserved 1 incomplete open case(s)" in caplog.text
    with history.session() as db:
        assert db.get(DataSource, ids.source).identity_epoch == 0
        assert db.get(DataSource, ids.generic).site_id is None
        assert db.get(DiscoveryRun, ids.run).identity_epoch == 0
        assert db.get(KnowledgeAssertion, ids.claim).identity_epoch is None
        for key in (ids.binding, ids.generic_binding, ids.interface_binding):
            link = db.get(EntitySourceLink, key)
            assert (link.opened_epoch, link.ended_epoch) == (0, None)
        assert [db.get(Asset, key).identity_retirement_revision for key in (
            ids.guest, ids.reactivated, ids.legacy
        )] == [1, 1, 0]

    history.migrate("downgrade", BASELINE)
    assert _revision(history.engine) == BASELINE
    assert _snapshot(history.engine) == before
    keys = inspect(history.engine).get_unique_constraints("entity_source_links")
    assert {row["name"]: row["column_names"] for row in keys}[LIFETIME_KEY] == [
        "data_source_id", "entity_type", "external_id"
    ]
    with pytest.raises(IntegrityError, match=LIFETIME_KEY), history.engine.begin() as db:
        _insert(db, EntitySourceLink, id=uuid.uuid4(), entity_type="asset", external_id=ids.guest_key,
                entity_id=ids.guest, data_source_id=ids.source, **ids.scope,
                first_observed_at=datetime.now(timezone.utc), last_observed_at=datetime.now(timezone.utc))
    history.migrate("upgrade", HEAD)
    assert _snapshot(history.engine) == before


@pytest.mark.parametrize("conflict", ["link_scope", "case_scope", "held_membership_scope", "duplicate"])
def test_preflight_refuses_contradictions_without_repair(baseline, conflict):
    history, ids = baseline
    with history.engine.begin() as db:
        if conflict == "link_scope":
            asset = uuid.uuid4()
            _insert(db, Asset, id=asset, workspace_id=ids.workspace, customer_id=ids.customer, site_id=ids.other_site,
                    name="Other site asset", asset_type="virtual_machine")
            _insert(db, EntitySourceLink, id=uuid.uuid4(), entity_type="asset", external_id="other-site",
                    entity_id=asset, data_source_id=ids.source, customer_id=ids.customer, site_id=ids.other_site,
                    first_observed_at=datetime.now(timezone.utc), last_observed_at=datetime.now(timezone.utc))
        elif conflict == "duplicate":
            _insert(db, ReconciliationItem, id=uuid.uuid4(), category="possible_duplicate",
                    entity_type="source_identity", assertion_id=ids.claim, entity_id=ids.guest,
                    candidate_external_id=ids.guest_key, **ids.scope)
        else:
            table = "reconciliation_items" if conflict == "case_scope" else "run_observed_entities"
            condition = "id" if conflict == "case_scope" else "evidence_record_id"
            db.execute(text(f"UPDATE {table} SET site_id=:site WHERE {condition}=:key"),
                       {"site": ids.other_site, "key": ids.item if conflict == "case_scope" else ids.evidence})
    before = _snapshot(history.engine)
    expected = {"link_scope": "contradict Integration scope", "duplicate": "1 duplicate open scope/key",
                "case_scope": "1 open case(s) have contradictory context",
                "held_membership_scope": "1 open case(s) have contradictory context"}
    with pytest.raises(RuntimeError, match=re.escape(expected[conflict])):
        history.migrate("upgrade", HEAD)
    assert _revision(history.engine) == BASELINE
    assert _snapshot(history.engine) == before
    assert "identity_epoch" not in {row["name"] for row in inspect(history.engine).get_columns("data_sources")}


@pytest.mark.parametrize("kind,conflict,expected", [
    pytest.param("canonical", None, 1, id="canonical-same-scope-historical"),
    pytest.param("canonical", "other_site", 0, id="canonical-cross-site"),
    pytest.param("canonical", "missing_site", 0, id="canonical-missing-site"),
    pytest.param("canonical", "other_asset", 0, id="canonical-wrong-asset"),
    pytest.param("canonical", "missing_subject", 0, id="canonical-missing-subject"),
    pytest.param("canonical", "rejected", 0, id="canonical-rejected"),
    pytest.param("absence", None, 1, id="absence-same-scope"),
    pytest.param("absence", "other_site", 0, id="absence-cross-site-declaration"),
    pytest.param("absence", "observation_site", 0, id="absence-cross-site-observation"),
    pytest.param("manual", None, 1, id="manual-same-scope"),
    pytest.param("manual", "other_site", 0, id="manual-cross-site"),
])
def test_backfill_requires_a_proven_status_decision(baseline, kind, conflict, expected):
    history, ids = baseline
    assert _revision(history.engine) == BASELINE
    now = datetime.now(timezone.utc)
    claim, item = uuid.uuid4(), uuid.uuid4()
    absence = kind == "absence"
    manual = kind == "manual"
    item_assertion = uuid.uuid4() if absence else claim
    values = ("active", "retired") if absence or manual else (
        {"field": "status", "value": "active"}, {"field": "status", "value": "retired"}
    )
    claim_site = {"other_site": ids.other_site, "missing_site": None}.get(conflict, ids.site)
    subject_id = {"other_asset": ids.reactivated, "missing_subject": None}.get(conflict, ids.legacy)
    metadata = None
    if absence:
        metadata = {"origin": "absence_review", "disposition": "retire",
                    "observation_assertion_id": str(item_assertion)}
    elif manual:
        metadata = {"origin": "manual_asset_edit", "accepted": True}
    with history.engine.begin() as db:
        _insert(db, KnowledgeAssertion, id=claim, subject_type="asset", subject_id=subject_id,
                predicate="status", truth_classification="declared" if absence or manual else "observed",
                value_json="retired", first_observed_at=now, last_observed_at=now,
                is_current=False, is_source_current=False, customer_id=ids.customer, site_id=claim_site)
        if absence:
            observation_site = ids.other_site if conflict == "observation_site" else ids.site
            _insert(db, KnowledgeAssertion, id=item_assertion, subject_type="asset", subject_id=ids.legacy,
                    predicate="observation_state", truth_classification="observed",
                    value_json={"state": "not_observed"}, first_observed_at=now, last_observed_at=now,
                    customer_id=ids.customer, site_id=observation_site)
        if not manual:
            _insert(db, ReconciliationItem, id=item, entity_type="asset", entity_id=ids.legacy,
                    assertion_id=item_assertion, category="no_longer_observed" if absence else "changed",
                    status="rejected" if conflict == "rejected" else "accepted", decided_at=now, **ids.scope)
        _insert(db, KnowledgeChange, id=uuid.uuid4(), entity_type="asset", entity_id=ids.legacy,
                entity_name_snapshot="Curated guest", predicate="status",
                change_type="lifecycle_changed" if absence else "fact_changed",
                truth_classification="declared" if absence or manual else "observed",
                assertion_id=claim, reconciliation_item_id=None if manual else item,
                previous_value_json=values[0], new_value_json=values[1], occurred_at=now,
                summary="Status decision", metadata_json=metadata, **ids.scope)
    before = _snapshot(history.engine)
    history.migrate("upgrade", HEAD)
    assert _revision(history.engine) == HEAD
    assert _snapshot(history.engine) == before
    with history.session() as db:
        asset = db.get(Asset, ids.legacy)
        assert asset.status == "active"
        assert asset.identity_retirement_revision == expected


def test_upgrade_lock_timeout_leaves_baseline_intact(baseline):
    history, _ = baseline
    before = _snapshot(history.engine)
    with history.engine.begin() as locker:
        locker.execute(text("LOCK TABLE assets IN ROW EXCLUSIVE MODE"))
        with pytest.raises(OperationalError) as failure:
            history.migrate("upgrade", HEAD)
        assert failure.value.orig.sqlstate == "55P03"
    assert _revision(history.engine) == BASELINE
    assert _snapshot(history.engine) == before
    history.migrate("upgrade", HEAD)
    assert _snapshot(history.engine) == before


def _decision(ids, **overrides):
    fields = dict(reconciliation_item_id=ids.item, data_source_id=ids.source, identity_epoch=1,
                  old_binding_id=ids.binding, reviewed_assertion_id=ids.claim, retirement_revision=1,
                  outcome="reactivate")
    return ProxmoxGuestIdentityDecision(**(fields | overrides))


def _successor(db, ids):
    old = db.get(EntitySourceLink, ids.binding)
    old.ended_epoch = 1
    db.get(EntitySourceLink, ids.interface_binding).ended_epoch = 1
    db.flush()
    successor = Asset(workspace_id=ids.workspace, name="New guest", asset_type="virtual_machine", **ids.scope)
    db.add(successor)
    db.flush()
    link = EntitySourceLink(data_source_id=ids.source, entity_type="asset", entity_id=successor.id,
                            external_id=ids.guest_key, opened_epoch=1, **ids.scope,
                            first_observed_at=old.first_observed_at, last_observed_at=old.last_observed_at)
    db.add(link)
    db.flush()
    return link


def _fixture_outcome(db, ids, outcome):
    fields = {}
    if outcome == "replace":
        fields["replacement_binding_id"] = _successor(db, ids).id
    db.add(_decision(ids, outcome=outcome, **fields))
    item = db.get(ReconciliationItem, ids.item)
    item.status = "accepted"
    item.decision_reason = "Storage fixture"
    item.decided_at = datetime.now(timezone.utc)


def test_retirement_trigger_uses_only_row_status_transitions(baseline):
    history, ids = baseline
    history.migrate("upgrade", HEAD)
    with history.session() as db, db.begin():
        asset = db.get(Asset, ids.guest)
        for status, expected in (("retired", 1), ("active", 1), ("inactive", 1), ("retired", 2), ("active", 2)):
            asset.status = status
            db.flush()
            db.refresh(asset)
            assert asset.identity_retirement_revision == expected
        new = Asset(workspace_id=ids.workspace, name="Initially retired", asset_type="virtual_machine",
                    status="retired", **ids.scope)
        db.add(new)
        db.flush()
        assert new.identity_retirement_revision == 1
        assert db.get(ReconciliationItem, ids.item).status == "open"


def test_indexes_and_foreign_keys_match_the_models(baseline):
    history, _ = baseline
    history.migrate("upgrade", HEAD)
    schema = inspect(history.engine)
    for model in (EntitySourceLink, ProxmoxGuestIdentityDecision):
        table = model.__table__
        indexes = {index["name"]: index for index in schema.get_indexes(table.name)}
        for expected in table.indexes:
            reflected = indexes[expected.name]
            assert reflected["unique"] == expected.unique
            assert reflected["column_names"] == [
                getattr(expression, "name", None) or str(expression).split()[0]
                for expression in expected.expressions
            ]
        keys = {key["name"]: key for key in schema.get_foreign_keys(table.name)}
        for expected in table.foreign_key_constraints:
            reflected = keys[expected.name]
            assert reflected["constrained_columns"] == [column.name for column in expected.columns]
            assert reflected["referred_table"] == expected.referred_table.name
            assert reflected["referred_columns"] == [element.column.name for element in expected.elements]
            options = {"ondelete": expected.ondelete, "deferrable": expected.deferrable,
                       "initially": expected.initially}
            assert reflected["options"] == {key: value for key, value in options.items() if value is not None}
    scope_index = next(row for row in schema.get_indexes("entity_source_links")
                       if row["name"] == "ix_entity_source_links_current_interface_owner")
    assert "asset_interface" in scope_index["dialect_options"]["postgresql_where"]
    assert "ended_epoch IS NULL" in scope_index["dialect_options"]["postgresql_where"]
    check = next(row for row in schema.get_indexes(DECISION_TABLE)
                 if row["name"] == "ix_proxmox_identity_decision_binding_epoch")
    assert check["column_sorting"] == {"identity_epoch": ("desc",)}


@pytest.mark.parametrize("table,column", [
    ("data_sources", "identity_epoch"),
    ("discovery_runs", "identity_epoch"),
    ("knowledge_assertions", "identity_epoch"),
    ("entity_source_links", "opened_epoch"),
    ("entity_source_links", "ended_epoch"),
    ("assets", "identity_retirement_revision"),
])
def test_invalid_epochs_rejected(baseline, table, column):
    history, _ = baseline
    history.migrate("upgrade", HEAD)
    with pytest.raises(IntegrityError, match=f"ck_{table}_{column}"), history.engine.begin() as db:
        db.execute(text(f"UPDATE {table} SET {column} = -1"))


@pytest.mark.parametrize("fields,check", [
    ({"outcome": "dismiss"}, "outcome"),
    ({"outcome": "replace"}, "outcome"),
    ({"identity_epoch": 0}, "identity_epoch"),
    ({"retirement_revision": -1}, "retirement_revision"),
])
def test_invalid_decisions_rejected(baseline, fields, check):
    history, ids = baseline
    history.migrate("upgrade", HEAD)
    with pytest.raises(IntegrityError, match="ck_proxmox_guest_identity_decisions_" + check):
        with history.session() as db, db.begin():
            db.add(_decision(ids, **fields))


def test_replacement_binding_required_to_be_distinct_and_source_epochs_unique(baseline):
    history, ids = baseline
    history.migrate("upgrade", HEAD)
    with pytest.raises(IntegrityError, match="ck_proxmox_guest_identity_decisions_outcome"):
        with history.session() as db, db.begin():
            db.add(_decision(ids, outcome="replace", replacement_binding_id=ids.binding))
    with history.session() as db, db.begin():
        db.add(_decision(ids))
    with pytest.raises(IntegrityError, match="uq_proxmox_identity_decision_source_epoch"):
        with history.session() as db, db.begin():
            db.add(_decision(ids, reconciliation_item_id=ids.incomplete_item))


def test_deferred_decision_fk_and_current_uniqueness_roll_back(baseline):
    history, ids = baseline
    history.migrate("upgrade", HEAD)
    before = _snapshot(history.engine, upgraded=True, decisions=True)
    with pytest.raises(IntegrityError, match="fk_entity_source_links_ended_decision"):
        with history.session() as db, db.begin():
            _successor(db, ids)
            # Both ends and the successor INSERT have flushed. Commit is the
            # first failure because the source+epoch decision is missing.
    assert _snapshot(history.engine, upgraded=True, decisions=True) == before

    with pytest.raises(IntegrityError, match=CURRENT_KEY), history.engine.begin() as db:
        db.execute(text("""
            INSERT INTO entity_source_links (data_source_id, entity_type, external_id, entity_id,
                customer_id, site_id, first_observed_at, last_observed_at, opened_epoch)
            SELECT data_source_id, entity_type, external_id, entity_id, customer_id, site_id,
                first_observed_at, last_observed_at, 1 FROM entity_source_links WHERE id=:binding
        """), {"binding": ids.binding})
    assert _snapshot(history.engine, upgraded=True, decisions=True) == before


@pytest.mark.parametrize("outcome", ["reactivate", "replace"])
def test_downgrade_refuses_after_decision(baseline, outcome):
    history, ids = baseline
    history.migrate("upgrade", HEAD)
    with history.session() as db, db.begin():
        _fixture_outcome(db, ids, outcome)
    before = _snapshot(history.engine, upgraded=True, decisions=True)
    if outcome == "reactivate":
        # Decisions are a barrier even with no other nonzero epochs or ends.
        assert all(row["ended_epoch"] is None and row["opened_epoch"] == 0
                   for row in before["entity_source_links"])
        assert all(row["identity_epoch"] == 0 for row in before["data_sources"])
    else:
        with pytest.raises(IntegrityError, match=HISTORICAL_KEY), history.engine.begin() as db:
            db.execute(text("UPDATE entity_source_links SET opened_epoch=0 WHERE data_source_id=:id AND opened_epoch=1"),
                       {"id": ids.source})
    with pytest.raises(RuntimeError, match="identity downgrade refused"):
        history.migrate("downgrade", BASELINE)
    assert _revision(history.engine) == HEAD
    assert _snapshot(history.engine, upgraded=True, decisions=True) == before


@pytest.mark.skipif(not (os.getenv("ATLAS_TEST_H3_SOURCE_URL") and os.getenv("ATLAS_TEST_H3_TARGET_URL")),
                    reason="requires two disposable PostgreSQL databases for encrypted restore")
def test_encrypted_restore_preserves_binding_history_and_open_case(installations):
    source, target = installations["source"], installations["target"]
    ids = _seed(source)
    with SessionLocal(bind=source) as db, db.begin():
        _fixture_outcome(db, ids, "replace")
        db.get(DataSource, ids.source).identity_epoch = 1
        db.get(KnowledgeAssertion, ids.incomplete_claim).identity_epoch = 1
    before = _snapshot(source, upgraded=True, decisions=True, restore_comparison=True)
    archive = portable_backup(installations)
    assert archive.suffix == ".atlasbackup"
    restore(installations, archive)
    assert _revision(target) == "20261125_0035"
    assert _snapshot(target, upgraded=True, decisions=True, restore_comparison=True) == before
    with SessionLocal(bind=target) as db:
        assert db.get(DiscoveryRun, ids.run).ingestion_generation is None
    for table in ("entity_source_links", DECISION_TABLE):
        expected = inspect(source).get_indexes(table)
        assert sorted(inspect(target).get_indexes(table), key=lambda index: index["name"]) == sorted(
            expected, key=lambda index: index["name"]
        )
    restored = _snapshot(target, upgraded=True, decisions=True)
    with pytest.raises(IntegrityError, match="fk_entity_source_links_ended_decision"), target.begin() as db:
        db.execute(text("UPDATE entity_source_links SET ended_epoch=2 WHERE id=:binding"), {"binding": ids.binding})
    assert _snapshot(target, upgraded=True, decisions=True) == restored
