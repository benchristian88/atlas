import uuid
from datetime import datetime, timezone
from types import SimpleNamespace
from unittest.mock import MagicMock, patch

import pytest
from fastapi import HTTPException

from app.authorization import Principal, ScopeGrant
from app.models import AuditEvent, DataSource, DiscoveryRun, KnowledgeAssertion, User
from app.permissions import MASTER_ADMINISTRATOR, ROLE_PERMISSION_KEYS, VIEWER
from app.routes.knowledge import (
    _lifecycle_assertion,
    archive_run,
    delete_run,
    retract_knowledge_assertion,
)
from app.schemas import AssertionRetractionRequest, LifecycleReasonRequest
from app.services.knowledge_lifecycle import (
    DeletionSafety,
    archive_discovery_run,
    can_delete_assertion,
    can_delete_discovery_run,
    delete_assertion,
    delete_discovery_run,
    restore_discovery_run,
    retract_assertion,
)


def run_record(*, status="failed"):
    return DiscoveryRun(
        id=uuid.uuid4(),
        customer_id=uuid.uuid4(),
        site_id=uuid.uuid4(),
        data_source_id=uuid.uuid4(),
        status=status,
        started_at=datetime.now(timezone.utc),
        archived_at=None,
        archived_by_user_id=None,
        archive_reason=None,
    )


def assertion_record(*, status="unreviewed", subject_id=None):
    now = datetime.now(timezone.utc)
    return KnowledgeAssertion(
        id=uuid.uuid4(),
        customer_id=uuid.uuid4(),
        site_id=uuid.uuid4(),
        subject_type="asset",
        subject_id=subject_id,
        subject_external_id=None,
        predicate="hostname",
        value_json="docker01",
        truth_classification="observed",
        confirmation_status=status,
        confidence=1,
        first_observed_at=now,
        last_observed_at=now,
        is_current=True,
        retracted_at=None,
        retracted_by_user_id=None,
        retraction_reason=None,
    )


def safety_session(run, *, counts=(0, 0, 0, 0), scalar_rows=None):
    db = MagicMock()
    db.scalar.side_effect = list(counts)
    db.scalars.side_effect = scalar_rows or [[], [], [], []]
    db.get.return_value = DataSource(
        id=run.data_source_id,
        customer_id=run.customer_id,
        site_id=run.site_id,
        name="Simulation",
        source_type="simulated_discovery",
        status="active",
    )
    return db


def test_empty_failed_simulated_run_is_deletable():
    run = run_record()
    safety = can_delete_discovery_run(safety_session(run), run)
    assert safety.allowed is True
    assert safety.counts == {
        "confirmed_assertions": 0,
        "accepted_reconciliation_items": 0,
        "linked_entities": 0,
        "later_dependencies": 0,
    }


def test_confirmed_assertion_blocks_run_deletion_with_archive_recommendation():
    run = run_record(status="completed")
    safety = can_delete_discovery_run(safety_session(run, counts=(2, 0, 0, 0)), run)
    assert safety.allowed is False
    assert safety.counts["confirmed_assertions"] == 2
    assert safety.recommended_alternative == "archive"


def test_accepted_reconciliation_item_and_operational_link_block_run_deletion():
    run = run_record(status="completed")
    entity_id = uuid.uuid4()
    db = safety_session(
        run,
        counts=(0, 1, 0, 0),
        scalar_rows=[[entity_id], [], [], []],
    )
    safety = can_delete_discovery_run(db, run)
    assert safety.allowed is False
    assert safety.counts["accepted_reconciliation_items"] == 1
    assert safety.counts["linked_entities"] == 1


def test_archive_and_restore_preserve_run_identity():
    run = run_record(status="completed")
    user = User(id=uuid.uuid4(), email="admin@example.com", display_name="Admin")
    archive_discovery_run(run, user=user, reason="Keep accepted provenance")
    assert run.archived_at is not None
    assert run.archived_by_user_id == user.id
    assert run.archive_reason == "Keep accepted provenance"
    restore_discovery_run(run)
    assert run.archived_at is None
    assert run.archived_by_user_id is None
    assert run.archive_reason is None


def test_safe_run_delete_uses_explicit_dependency_order():
    run = run_record()
    db = MagicMock()
    with patch(
        "app.services.knowledge_lifecycle.can_delete_discovery_run",
        return_value=DeletionSafety(allowed=True),
    ):
        delete_discovery_run(db, run)
    assert db.execute.call_count == 3
    db.delete.assert_called_once_with(run)


@pytest.mark.parametrize("status", ["unreviewed", "rejected", "superseded"])
def test_unused_assertion_statuses_are_deletable(status):
    assertion = assertion_record(status=status)
    db = MagicMock()
    db.scalar.side_effect = [0, 0]
    assert can_delete_assertion(db, assertion).allowed is True


def test_confirmed_assertion_cannot_be_hard_deleted():
    assertion = assertion_record(status="confirmed")
    db = MagicMock()
    db.scalar.side_effect = [0, 0]
    safety = can_delete_assertion(db, assertion)
    assert safety.allowed is False
    assert safety.recommended_alternative == "retract"


def test_delete_assertion_removes_only_unaccepted_reconciliation_items():
    assertion = assertion_record(status="unreviewed")
    db = MagicMock()
    with patch(
        "app.services.knowledge_lifecycle.can_delete_assertion",
        return_value=DeletionSafety(allowed=True),
    ):
        delete_assertion(db, assertion)
    db.execute.assert_called_once()
    db.delete.assert_called_once_with(assertion)


def test_retract_confirmed_assertion_preserves_evidence_and_operational_subject():
    asset_id = uuid.uuid4()
    evidence_id = uuid.uuid4()
    assertion = assertion_record(status="confirmed", subject_id=asset_id)
    assertion.evidence_record_id = evidence_id
    user = User(id=uuid.uuid4(), email="admin@example.com", display_name="Admin")
    db = MagicMock()
    db.scalar.return_value = None
    gap = retract_assertion(
        db,
        assertion,
        user=user,
        reason="Source is no longer trusted",
        confirm_provenance_gap=True,
    )
    assert gap is True
    assert assertion.subject_id == asset_id
    assert assertion.evidence_record_id == evidence_id
    assert assertion.retracted_at is not None
    assert assertion.is_current is False
    db.delete.assert_not_called()
    db.execute.assert_not_called()


def test_lifecycle_lookup_enforces_customer_scope():
    assertion = assertion_record()
    other_customer = uuid.uuid4()
    user = User(id=uuid.uuid4(), email="viewer@example.com", display_name="Viewer")
    principal = Principal(
        user=user,
        grants=(
            ScopeGrant(
                assignment_id=uuid.uuid4(),
                role_id=uuid.uuid4(),
                role_name="Customer Administrator",
                scope_type="customer",
                customer_id=other_customer,
                site_id=None,
                permissions=frozenset({"assertions.delete"}),
            ),
        ),
    )
    db = MagicMock()
    db.get.return_value = assertion
    with pytest.raises(HTTPException) as exc:
        _lifecycle_assertion(db, principal, assertion.id, "assertions.delete")
    assert exc.value.status_code == 404


def test_viewer_has_no_lifecycle_mutation_permissions():
    mutation_permissions = {
        "discovery_runs.archive",
        "discovery_runs.delete",
        "assertions.retract",
        "assertions.delete",
    }
    assert mutation_permissions <= ROLE_PERMISSION_KEYS[MASTER_ADMINISTRATOR]
    assert mutation_permissions.isdisjoint(ROLE_PERMISSION_KEYS[VIEWER])


def test_unexpected_run_delete_failure_rolls_back_transaction():
    run = run_record()
    user = User(id=uuid.uuid4(), email="admin@example.com", display_name="Admin")
    principal = Principal(
        user=user,
        grants=(
            ScopeGrant(
                assignment_id=uuid.uuid4(),
                role_id=uuid.uuid4(),
                role_name="Master Administrator",
                scope_type="global",
                customer_id=None,
                site_id=None,
                permissions=frozenset({"discovery_runs.delete"}),
            ),
        ),
    )
    db = MagicMock()
    db.get.side_effect = [
        run,
        SimpleNamespace(name="Simulation"),
        SimpleNamespace(workspace_id=uuid.uuid4()),
    ]
    request = SimpleNamespace(client=None, state=SimpleNamespace(request_id="request-1"))
    with (
        patch(
            "app.routes.knowledge.can_delete_discovery_run",
            return_value=DeletionSafety(allowed=True),
        ),
        patch(
            "app.routes.knowledge.delete_discovery_run",
            side_effect=RuntimeError("database failure"),
        ),
        pytest.raises(RuntimeError, match="database failure"),
    ):
        delete_run(run.id, request, principal, db)
    db.rollback.assert_called_once()
    db.commit.assert_not_called()


def test_archive_and_retraction_routes_record_audit_events():
    user = User(id=uuid.uuid4(), email="admin@example.com", display_name="Admin")
    permissions = frozenset({"discovery_runs.archive", "assertions.retract"})
    principal = Principal(
        user=user,
        grants=(
            ScopeGrant(
                assignment_id=uuid.uuid4(),
                role_id=uuid.uuid4(),
                role_name="Master Administrator",
                scope_type="global",
                customer_id=None,
                site_id=None,
                permissions=permissions,
            ),
        ),
    )
    request = SimpleNamespace(client=None, state=SimpleNamespace(request_id="request-2"))
    customer = SimpleNamespace(workspace_id=uuid.uuid4())

    run = run_record(status="completed")
    run_db = MagicMock()
    run_db.get.side_effect = [run, customer]
    with patch("app.routes.knowledge.run_response", return_value={"id": run.id}):
        archive_run(
            run.id,
            LifecycleReasonRequest(reason="Keep provenance"),
            request,
            principal,
            run_db,
        )
    run_events = [
        call.args[0]
        for call in run_db.add.call_args_list
        if isinstance(call.args[0], AuditEvent)
    ]
    assert [event.event_type for event in run_events] == ["discovery_run.archived"]

    assertion = assertion_record(status="confirmed")
    assertion_db = MagicMock()
    assertion_db.get.side_effect = [assertion, customer]
    with patch(
        "app.routes.knowledge.assertion_response",
        return_value={"id": assertion.id},
    ):
        retract_knowledge_assertion(
            assertion.id,
            AssertionRetractionRequest(reason="Source retired"),
            request,
            principal,
            assertion_db,
        )
    assertion_events = [
        call.args[0]
        for call in assertion_db.add.call_args_list
        if isinstance(call.args[0], AuditEvent)
    ]
    assert [event.event_type for event in assertion_events] == ["assertion.retracted"]
