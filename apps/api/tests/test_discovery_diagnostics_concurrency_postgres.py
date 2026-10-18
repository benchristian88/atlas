"""Committed PostgreSQL arming while a creator retains a stale Integration."""
import asyncio
from contextlib import nullcontext
from datetime import timedelta
import os
from types import SimpleNamespace

import pytest
from sqlalchemy import create_engine, delete, event, inspect, select
from sqlalchemy.orm import Session, sessionmaker

from app.models import AuditEvent, DiscoveryRun, Integration
from app.routes import integration_discovery as routes
from app.services import connector_lifecycle as lifecycle, discovery_orchestration as orchestration
from tests.i3_fixtures import ROOT
from tests.test_administration import request
from tests.test_discovery_diagnostics import administrator
from tests.test_i3_discovery import configured

pytestmark = pytest.mark.skipif(not os.getenv("ATLAS_TEST_DATABASE_URL"), reason="requires disposable migrated PostgreSQL")


@pytest.fixture
def db():
    # Real commits are required: a second connection must see and arm the fixture.
    engine = create_engine(os.environ["ATLAS_TEST_DATABASE_URL"], hide_parameters=True)
    inserted = []
    with Session(engine, autoflush=False, expire_on_commit=False) as session:
        @event.listens_for(session, "after_flush")
        def remember_fixture_rows(current, context):
            for instance in current.new:
                table = inspect(instance).mapper.local_table
                inserted.append((table, {column.name: getattr(instance, column.name) for column in table.primary_key}))

        try:
            yield session
        finally:
            session.rollback()
            customers = [key["id"] for table, key in inserted if table.name == "customers"]
            integrations = [key["id"] for table, key in inserted if table.name == "integrations"]
            # Runs and audit events were committed through other sessions. No job
            # executes, so these fixtures have no receipts or accepted knowledge.
            session.execute(delete(AuditEvent).where(AuditEvent.customer_id.in_(customers)))
            session.execute(delete(DiscoveryRun).where(DiscoveryRun.integration_id.in_(integrations)))
            for table, key in reversed(inserted):
                session.execute(delete(table).where(*(table.c[name] == value for name, value in key.items())))
            session.commit()
    engine.dispose()


@pytest.mark.parametrize("creation_path", ["manual", "schedule"])
def test_committed_arming_refreshes_stale_creator_and_is_consumed_once(db, configured, monkeypatch, creation_path):
    row, principal, _, _ = configured
    identifier = row.id
    assert row.debug_next_run is False
    if creation_path == "schedule":
        row.schedule_preset = "hourly"
        row.next_run_at = orchestration.utcnow() - timedelta(seconds=1)
        db.commit()
    sessions = sessionmaker(bind=db.get_bind(), autoflush=False, expire_on_commit=False)
    real_lock = lifecycle.lock_connector
    stale_rows = []
    armed = False

    def arm_before_creator_lock(creator, connector_id):
        nonlocal armed
        if not armed:
            # The normal API/worker path has already loaded this ORM instance.
            stale = creator.get(Integration, identifier)
            assert stale.debug_next_run is False and creator.in_transaction()
            stale_rows.append(stale)  # Retain it in the identity map until creation.
            armed = True
            creator_pid = creator.connection().exec_driver_sql("SELECT pg_backend_pid()").scalar_one()
            with sessions() as armer:
                armer_pid = armer.connection().exec_driver_sql("SELECT pg_backend_pid()").scalar_one()
                assert creator_pid != armer_pid
                routes.set_debug_next_run(identifier, routes.DebugNextRunInput(enabled=True),
                    request(), administrator(configured), armer)
            assert creator.scalar(select(Integration.debug_next_run).where(Integration.id == identifier)) is True
            assert stale.debug_next_run is False  # B committed; A is still stale.
        real_lock(creator, connector_id)

    monkeypatch.setattr(lifecycle, "lock_connector", arm_before_creator_lock)
    enqueued = []
    monkeypatch.setattr(orchestration, "enqueue", enqueued.append)
    # Exercise scheduling/creation without dispatching a source job.
    monkeypatch.setattr(orchestration, "redis_client",
        lambda: nullcontext(SimpleNamespace(lpop=lambda *args, **kwargs: None)))
    async def no_dispatch(session, run_id):
        pass
    monkeypatch.setattr(orchestration, "dispatch", no_dispatch)
    monkeypatch.syspath_prepend(str(ROOT / "apps/worker"))
    from worker.main import tick

    def create():
        if creation_path == "manual":
            with sessions() as creator:
                asyncio.run(routes.run_now(identifier, request(), principal, creator))
        else:
            asyncio.run(tick(session_factory=sessions))

    create()
    assert armed and len(stale_rows) == 1 and len(enqueued) == 1
    with sessions() as verifier:
        runs = list(verifier.scalars(select(DiscoveryRun).where(DiscoveryRun.integration_id == identifier)))
        assert len(runs) == 1
        first = runs[0]
        assert first.id == enqueued[0] and first.debug_enabled is True
        assert first.execution_provenance["debug_enabled"] is True
        assert first.execution_provenance["trigger"] == creation_path
        assert first.debug_expires_at == first.created_at + timedelta(hours=48)
        assert verifier.scalar(select(Integration.debug_next_run).where(Integration.id == identifier)) is False
        first_id = first.id
        orchestration.cancel_intent(first)
        if creation_path == "schedule":
            verifier.get(Integration, identifier).next_run_at = orchestration.utcnow() - timedelta(seconds=1)
        verifier.commit()

    create()
    with sessions() as verifier:
        runs = list(verifier.scalars(select(DiscoveryRun).where(DiscoveryRun.integration_id == identifier)))
        assert len(runs) == 2 and len(enqueued) == 2
        assert [run.id for run in runs if run.debug_enabled] == [first_id]
        following = next(run for run in runs if run.id != first_id)
        assert following.id == enqueued[1] and following.debug_enabled is False
        assert following.execution_provenance["debug_enabled"] is False and following.debug_expires_at is None
        assert verifier.scalar(select(Integration.debug_next_run).where(Integration.id == identifier)) is False
