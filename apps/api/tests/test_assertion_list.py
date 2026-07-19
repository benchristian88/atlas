import uuid
from datetime import datetime, timezone
from decimal import Decimal

import pytest
from fastapi.testclient import TestClient

from app.authorization import Principal, ScopeGrant, get_principal
from app.database import get_db
from app.main import app
from app.models import DataSource, KnowledgeAssertion, User

DOCKER01_ID = uuid.UUID("a0877d05-048a-4c8f-a6cf-025e4b9317f5")
FAILING_ASSERTION_ID = uuid.UUID("07dfcef9-032e-47b9-954e-1c2fe19f0783")


@pytest.fixture(autouse=True)
def clear_overrides():
    app.dependency_overrides.clear()
    yield
    app.dependency_overrides.clear()


def make_assertion(
    *,
    assertion_id=None,
    subject_id=DOCKER01_ID,
    predicate="hostname",
    value="docker01",
    confirmation_status="unreviewed",
    data_source_id=None,
    discovery_run_id=None,
    evidence_record_id=None,
    retracted_at=None,
    retracted_by_user_id=None,
    retraction_reason=None,
    superseded_by_id=None,
    object_type=None,
    object_id=None,
    object_external_id=None,
):
    now = datetime(2026, 7, 19, 12, 0, tzinfo=timezone.utc)
    return KnowledgeAssertion(
        id=assertion_id or uuid.uuid4(),
        customer_id=uuid.UUID("1f042640-afcb-4711-b018-a98d704b1e24"),
        site_id=uuid.UUID("f671f55e-135a-4c54-abc6-e0d395d9be51"),
        subject_type="asset",
        subject_id=subject_id,
        subject_external_id="manual:docker01",
        predicate=predicate,
        value_json=value,
        object_type=object_type,
        object_id=object_id,
        object_external_id=object_external_id,
        truth_classification="observed",
        confirmation_status=confirmation_status,
        data_source_id=data_source_id,
        discovery_run_id=discovery_run_id,
        evidence_record_id=evidence_record_id,
        confidence=Decimal("1.0"),
        first_observed_at=now,
        last_observed_at=now,
        valid_from=None,
        valid_to=retracted_at,
        superseded_by_id=superseded_by_id,
        is_current=confirmation_status != "superseded" and retracted_at is None,
        retracted_at=retracted_at,
        retracted_by_user_id=retracted_by_user_id,
        retraction_reason=retraction_reason,
        created_at=now,
        updated_at=now,
    )


class AssertionListDatabase:
    def __init__(self, assertions, sources):
        self.assertions = assertions
        self.sources = {source.id: source for source in sources}
        self.provenance_queries = []

    @staticmethod
    def _entity(statement):
        return statement.column_descriptions[0].get("entity")

    def get(self, model, record_id):
        if model is DataSource:
            return self.sources.get(record_id)
        if model is KnowledgeAssertion:
            return next((row for row in self.assertions if row.id == record_id), None)
        return None

    def scalar(self, statement):
        # Deletion-safety count queries have no blockers in this read-path fixture.
        return 0

    def scalars(self, statement):
        if self._entity(statement) is not KnowledgeAssertion:
            return []
        sql = str(statement)
        params = statement.compile().params
        if "ORDER BY knowledge_assertions.last_observed_at DESC" in sql:
            subject_id = next(
                (value for key, value in params.items() if key.startswith("subject_id")),
                None,
            )
            return [row for row in self.assertions if row.subject_id == subject_id]
        self.provenance_queries.append(statement)
        assertion_id = next(
            (value for key, value in params.items() if key.startswith("id_")),
            None,
        )
        current = self.get(KnowledgeAssertion, assertion_id)
        if current is None:
            return []
        return [
            row
            for row in self.assertions
            if row.id != current.id
            and row.subject_id == current.subject_id
            and row.predicate == current.predicate
            and row.confirmation_status == "confirmed"
            and row.retracted_at is None
            and row.is_current
        ]


def principal():
    user = User(
        id=uuid.uuid4(),
        email="admin@example.com",
        display_name="Admin",
        force_password_change=False,
    )
    return Principal(
        user=user,
        grants=(
            ScopeGrant(
                assignment_id=uuid.uuid4(),
                role_id=uuid.uuid4(),
                role_name="Master Administrator",
                scope_type="global",
                customer_id=None,
                site_id=None,
                permissions=frozenset({"assets.view"}),
            ),
        ),
    )


def historical_assertions():
    source_id = uuid.uuid4()
    run_id = uuid.uuid4()
    archived_run_id = uuid.uuid4()
    evidence_id = uuid.uuid4()
    replacement_id = uuid.uuid4()
    retracted_at = datetime(2026, 7, 20, 9, 30, tzinfo=timezone.utc)
    target_id = uuid.uuid4()
    rows = [
        # Complete provenance.
        make_assertion(
            data_source_id=source_id,
            discovery_run_id=run_id,
            evidence_record_id=evidence_id,
        ),
        # Safely deleted/missing discovery run.
        make_assertion(predicate="vendor", value="Debian", discovery_run_id=None),
        # Archived run IDs remain ordinary UUID provenance references.
        make_assertion(predicate="model", value="VM", discovery_run_id=archived_run_id),
        # Missing evidence.
        make_assertion(predicate="ip_address", value="192.168.5.8", evidence_record_id=None),
        # Retracted assertion with no actor/reason retained from incomplete history.
        make_assertion(
            predicate="name",
            value="docker01",
            confirmation_status="confirmed",
            retracted_at=retracted_at,
            retracted_by_user_id=None,
            retraction_reason=None,
        ),
        # Superseded historical assertion.
        make_assertion(
            predicate="hostname",
            value="docker-old",
            confirmation_status="superseded",
            superseded_by_id=replacement_id,
        ),
        # Structured relationship value remains JSON, not a string assumption.
        make_assertion(
            predicate="runs_on",
            value={
                "source_external_id": "manual:docker01",
                "target_external_id": "manual:pve1",
                "resolved_target_asset_id": target_id,
                "resolution": ["existing", {"confidence": 1.0}],
            },
            object_type="asset",
            object_id=target_id,
            object_external_id="manual:pve1",
        ),
        # Exact row from the supplied docker01 traceback: JSONB scalar string.
        make_assertion(
            assertion_id=FAILING_ASSERTION_ID,
            predicate="status",
            value="running",
            confirmation_status="confirmed",
            data_source_id=source_id,
            discovery_run_id=run_id,
            evidence_record_id=evidence_id,
        ),
        # Multiple current assertions for one predicate are compared in Python.
        make_assertion(
            predicate="status",
            value="running",
            confirmation_status="confirmed",
            data_source_id=None,
            discovery_run_id=None,
            evidence_record_id=None,
        ),
        # Control row for a different asset.
        make_assertion(subject_id=uuid.uuid4(), predicate="status", value="active"),
    ]
    source = DataSource(
        id=source_id,
        customer_id=rows[0].customer_id,
        site_id=rows[0].site_id,
        name="Manual Discovery Simulation",
        source_type="simulated_discovery",
        status="active",
    )
    return rows, [source]


def test_exact_docker01_assertion_list_serializes_all_historical_states():
    rows, sources = historical_assertions()
    db = AssertionListDatabase(rows, sources)
    app.dependency_overrides[get_principal] = principal
    app.dependency_overrides[get_db] = lambda: db

    with TestClient(app) as client:
        response = client.get(
            "/api/assertions",
            params={
                "subject_type": "asset",
                "subject_id": str(DOCKER01_ID),
                "current_only": "false",
            },
        )

    assert response.status_code == 200
    payload = response.json()
    assert len(payload) == 9
    by_id = {row["id"]: row for row in payload}
    failing = by_id[str(FAILING_ASSERTION_ID)]
    assert failing["value_json"] == "running"
    assert failing["deletion_safety"]["identifiers"]["assertion_id"] == str(
        FAILING_ASSERTION_ID
    )
    assert failing["discovery_run_id"] is not None
    assert failing["evidence_record_id"] is not None
    assert isinstance(failing["last_observed_at"], str)
    assert failing["provenance_gap_warning"] is False

    null_run = next(row for row in payload if row["predicate"] == "vendor")
    assert null_run["discovery_run_id"] is None
    assert null_run["data_source_id"] is None
    assert null_run["source_name"] is None
    null_evidence = next(row for row in payload if row["predicate"] == "ip_address")
    assert null_evidence["evidence_record_id"] is None
    retracted = next(row for row in payload if row["retracted_at"] is not None)
    assert retracted["retracted_by_user_id"] is None
    assert retracted["retraction_reason"] is None
    superseded = next(row for row in payload if row["confirmation_status"] == "superseded")
    assert superseded["superseded_by_id"] is not None
    structured = next(row for row in payload if row["predicate"] == "runs_on")
    assert structured["value_json"]["resolved_target_asset_id"] == str(
        structured["object_id"]
    )
    assert isinstance(structured["value_json"]["resolution"], list)

    # Regression: no provenance query may compare JSONB against a VARCHAR bind.
    assert db.provenance_queries
    assert all("value_json =" not in str(query) for query in db.provenance_queries)


def test_other_asset_assertion_list_remains_independent():
    rows, sources = historical_assertions()
    other = rows[-1]
    db = AssertionListDatabase(rows, sources)
    app.dependency_overrides[get_principal] = principal
    app.dependency_overrides[get_db] = lambda: db

    with TestClient(app) as client:
        response = client.get(
            "/api/assertions",
            params={
                "subject_type": "asset",
                "subject_id": str(other.subject_id),
                "current_only": "false",
            },
        )

    assert response.status_code == 200
    assert [row["id"] for row in response.json()] == [str(other.id)]
