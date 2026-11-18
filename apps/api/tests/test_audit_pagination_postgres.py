"""Audit paging against a disposable, Alembic-migrated PostgreSQL database."""

import os
import uuid
from datetime import datetime, timedelta, timezone

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from app.authorization import Principal, ScopeGrant, get_principal
from app.database import get_db
from app.models import AuditEvent, Customer, Site, Workspace
from app.routes.audit import router
from tests.test_administration import make_principal
from tests.test_infrastructure_topology_postgres import db

pytestmark = pytest.mark.skipif(
    not os.getenv("ATLAS_TEST_DATABASE_URL"), reason="requires disposable migrated PostgreSQL"
)


def test_audit_pages_filter_and_scope_before_lookahead(db):
    key = uuid.uuid4().hex
    now = datetime(2026, 11, 19, tzinfo=timezone.utc)
    workspace = Workspace(name="Audit pagination", slug=key)
    db.add(workspace)
    db.flush()
    customer = Customer(workspace_id=workspace.id, name="Visible customer")
    other_customer = Customer(workspace_id=workspace.id, name="Hidden customer")
    db.add_all([customer, other_customer])
    db.flush()
    site = Site(customer_id=customer.id, name="Visible site")
    sibling = Site(customer_id=customer.id, name="Hidden sibling site")
    other_site = Site(customer_id=other_customer.id, name="Hidden other site")
    db.add_all([site, sibling, other_site])
    db.flush()

    def audit_event(**overrides):
        return AuditEvent(**{
            "id": uuid.uuid4(),
            "workspace_id": workspace.id,
            "customer_id": customer.id,
            "site_id": site.id,
            "actor_email": f"{key}@example.test",
            "event_type": "asset.updated",
            "target_type": "asset",
            "created_at": now,
            **overrides,
        })

    matching = [
        audit_event(created_at=now - timedelta(minutes=index // 7))
        for index in range(235)
    ]
    db.add_all(matching + [
        audit_event(site_id=sibling.id),
        audit_event(customer_id=other_customer.id, site_id=other_site.id),
        audit_event(customer_id=None, site_id=None, created_at=now - timedelta(minutes=34)),
        audit_event(actor_email="other@example.test"),
        audit_event(actor_email=None, actor_display_name=key, event_type="asset.created"),
        audit_event(target_type="service"),
        audit_event(created_at=now + timedelta(minutes=1)),
        audit_event(created_at=now - timedelta(minutes=36)),
    ])
    db.flush()
    expected = [
        str(event.id)
        for event in sorted(matching, key=lambda event: (event.created_at, event.id), reverse=True)
    ]

    global_viewer = make_principal("audit.view")
    grant = ScopeGrant(
        assignment_id=uuid.uuid4(),
        role_id=uuid.uuid4(),
        role_name="Site audit viewer",
        scope_type="site",
        customer_id=customer.id,
        site_id=site.id,
        permissions=frozenset({"audit.view"}),
    )
    site_viewer = Principal(global_viewer.user, (grant,))
    app = FastAPI()
    app.include_router(router, prefix="/api")
    app.dependency_overrides[get_db] = lambda: db
    app.dependency_overrides[get_principal] = lambda: site_viewer
    filters = {
        "actor": key,
        "action": "asset.updated",
        "entity_type": "asset",
        "date_from": (now - timedelta(minutes=35)).isoformat(),
        "date_to": now.isoformat(),
    }

    with TestClient(app) as client:
        def read(**params):
            response = client.get("/api/audit-events", params=filters | params)
            assert response.status_code == 200, response.text
            return [item["id"] for item in response.json()]

        assert read() == expected[:100]
        assert read(limit=200) == expected[:200]
        displayed = []
        for offset in range(0, len(expected), 30):
            rows = read(limit=31, offset=offset)
            assert rows == expected[offset:offset + 31]
            displayed.extend(rows[:30])
        assert displayed == expected
        assert len(set(displayed)) == 235
        assert read(limit=31, offset=180)[20] == expected[200]
        assert read(limit=31, offset=150)[:30] == displayed[150:180]
        assert read(limit=31, offset=205) == expected[205:]
        assert read(limit=31, offset=235) == []
        assert read(limit=31, site_id=str(sibling.id)) == []
        assert read(limit=31, customer_id=str(other_customer.id)) == []
        assert read(limit=31, action="asset.created") != []
        assert read(limit=31, action="asset.deleted") == []

        app.dependency_overrides[get_principal] = lambda: global_viewer
        assert read(limit=31, offset=205, customer_id=str(customer.id), site_id=str(site.id)) == expected[205:]
        assert len(read(limit=31, offset=205)) == 31
