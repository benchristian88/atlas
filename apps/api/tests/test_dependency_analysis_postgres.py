"""Opt-in integration check against a disposable, Alembic-migrated database.

Set ATLAS_TEST_DATABASE_URL to a disposable database. Fixture writes are
committed there; analysis then runs in a PostgreSQL READ ONLY transaction.
"""
import os
import uuid

import pytest
from sqlalchemy import create_engine, select, text
from sqlalchemy.orm import Session

from app.authorization import ActiveContext
from app.models import Customer, Site, Workspace
from app.schemas_dependency_analysis import DependencyAnalysisRequest
from app.services.dependency_analysis import DependencyAnalysisEngine
from app.services.operational_graph import OperationalGraphBuilder
from tests.test_dependency_analysis import PERMISSIONS, Topology, assert_paths, by_name
from tests.test_operational_graph import NOW, principal


@pytest.mark.skipif(not os.getenv("ATLAS_TEST_DATABASE_URL"), reason="requires disposable migrated PostgreSQL")
def test_postgres_analysis_groups_temporal_and_read_only_transaction():
    engine = create_engine(os.environ["ATLAS_TEST_DATABASE_URL"])
    # Dedicated disposable database only: commit fixture data so PostgreSQL can
    # enforce READ ONLY on the subsequent analysis transaction.
    with Session(engine) as db:
        t = Topology()
        refs = []
        for item in t.refs:
            existing = db.scalar(select(type(item)).where(type(item).key == item.key))
            refs.append(existing or item)
            if existing is None:
                db.add(item)
        db.flush()
        t.refs = tuple(refs)
        t.records = [t.focus]
        workspace = Workspace(id=t.focus.workspace_id, name="C2.3 test", slug=f"c23-{uuid.uuid4()}")
        db.add(workspace)
        db.flush()
        db.add(Customer(id=t.customer, workspace_id=workspace.id, name="C2.3 test"))
        db.flush()
        db.add(Site(id=t.site, customer_id=t.customer, name="C2.3 test"))
        db.flush()
        dns, proxy, alternate = t.service("DNS"), t.service("Proxy"), t.asset("Alternate")
        alternate.workspace_id = workspace.id
        dns_dependency, _ = t.dependency(dns, t.focus)
        _, group = t.dependency(proxy, dns, strategy="any")
        t.dependency(proxy, alternate, group=group)
        alternate_membership_id = t.records[-1].id
        dns_dependency_id = dns_dependency.id
        # Flush fixture categories in FK order; these models intentionally have
        # no ORM relationship cascade ordering.
        from app.models import Asset, Service, ServiceAssetDependency, ServiceDependency, DependencyGroup, DependencyGroupMembership
        for model in (Asset, Service, ServiceAssetDependency, ServiceDependency, DependencyGroup, DependencyGroupMembership):
            db.add_all(record for record in t.records if isinstance(record, model))
            db.flush()
        db.commit()
        focus_id, customer_id, site_id = t.focus.id, t.customer, t.site
    with Session(engine) as db:
        db.execute(text("SET TRANSACTION READ ONLY"))
        analysis = DependencyAnalysisEngine(OperationalGraphBuilder(db, principal(*PERMISSIONS), clock=lambda: NOW))
        result = analysis.analyze(DependencyAnalysisRequest(focus_type="asset", focus_id=focus_id), ActiveContext(customer_id, site_id))
        rows = by_name(result)
        assert rows["DNS"].state == "unavailable"
        assert rows["Proxy"].state == "unaffected"
        assert len(rows["Proxy"].reasons[0].members) == 2
        assert_paths(result)
        db.commit()
    with Session(engine) as db:
        from sqlalchemy import update
        db.execute(update(DependencyGroupMembership).where(
            DependencyGroupMembership.id == alternate_membership_id
        ).values(valid_to=NOW))
        db.commit()
    with Session(engine) as db:
        db.execute(text("SET TRANSACTION READ ONLY"))
        analysis = DependencyAnalysisEngine(OperationalGraphBuilder(db, principal(*PERMISSIONS), clock=lambda: NOW))
        result = analysis.analyze(DependencyAnalysisRequest(focus_type="asset", focus_id=focus_id), ActiveContext(customer_id, site_id))
        assert by_name(result)["Proxy"].state == "unavailable"
        assert_paths(result)
        db.commit()
    with Session(engine) as db:
        db.execute(update(ServiceAssetDependency).where(
            ServiceAssetDependency.id == dns_dependency_id
        ).values(valid_to=NOW))
        db.commit()
    with Session(engine) as db:
        db.execute(text("SET TRANSACTION READ ONLY"))
        analysis = DependencyAnalysisEngine(OperationalGraphBuilder(db, principal(*PERMISSIONS), clock=lambda: NOW))
        result = analysis.analyze(DependencyAnalysisRequest(focus_type="asset", focus_id=focus_id), ActiveContext(customer_id, site_id))
        assert result.results == []
        db.commit()
    engine.dispose()
