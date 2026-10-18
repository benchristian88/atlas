"""Bounded Atlas worker. PostgreSQL owns intent; Redis provides dispatch hints."""
import asyncio
import logging
import signal
import uuid

from sqlalchemy import select, or_
from sqlalchemy.exc import SQLAlchemyError

from app.database import SessionLocal
from app.models import Integration, DiscoveryRun
from app.services.backup_runtime import normal_operation
from app.services.backup_archive import BackupError
from app.services import discovery_orchestration as discovery
from app.services.discovery_diagnostics import purge_expired

logger = logging.getLogger("atlas.worker")
PAUSED_ERRORS = {"authentication_failed", "tls_trust_required", "source_incompatible", "configuration_unavailable",
    "integration_configuration_changed", "mapping_unavailable", "discovery_unavailable", "invalid_request", "package_unavailable"}


async def tick(session_factory=SessionLocal):
    from redis.exceptions import RedisError
    try:
        with discovery.redis_client() as client:
            client.lpop(discovery.QUEUE, count=32)
    except (RedisError, OSError, ValueError):
        logger.warning("category=dispatch_hints_unavailable")
    # Missed schedules coalesce to one current run, never a backlog of ticks.
    with normal_operation(read_only=True), session_factory() as db:
        purge_expired(db)
        db.commit()
        identifiers = list(db.scalars(select(Integration.id).where(Integration.enabled.is_(True),
            Integration.retired_at.is_(None), Integration.connector_id.is_not(None), Integration.schedule_preset != "manual",
            Integration.next_run_at <= discovery.utcnow(),
            or_(Integration.source_compatibility.is_(None), Integration.source_compatibility != "known_incompatible"),
            or_(Integration.last_error_code.is_(None), Integration.last_error_code.not_in(PAUSED_ERRORS)))
            .order_by(Integration.next_run_at, Integration.id).limit(20)))
    for identifier in identifiers:
        with normal_operation(read_only=True), session_factory() as db:
            # Package lifecycle uses the same connector-before-Integration order.
            identity = db.get(Integration, identifier)
            if identity is None:
                continue
            from app.services.connector_lifecycle import lock_connector
            lock_connector(db, identity.connector_id)
            row = db.scalar(select(Integration).where(Integration.id == identifier).with_for_update(skip_locked=True)
                .execution_options(populate_existing=True))
            if row is None or not row.enabled or row.retired_at or row.next_run_at is None or row.next_run_at > discovery.utcnow():
                continue
            row.next_run_at = discovery.next_run(row.schedule_preset, discovery.utcnow())
            try:
                if discovery.active_run(db, row.id) is None:
                    run = await discovery.create_run(db, row, trigger="schedule")
                    db.commit()
                    discovery.enqueue(run.id)
                else:
                    db.commit()
            except (ValueError, OSError, RuntimeError) as error:
                row.last_error_code = error.code if isinstance(error, discovery.DiscoveryEligibilityError) else "configuration_unavailable"
                db.commit()
    with normal_operation(read_only=True), session_factory() as db:
        recovering = list(db.scalars(select(DiscoveryRun.id).where(DiscoveryRun.execution_provenance.is_not(None),
            DiscoveryRun.dispatch_state.in_(["dispatching", "running"]))
            .order_by(DiscoveryRun.started_at, DiscoveryRun.id).limit(32)))
        pending = list(db.scalars(select(DiscoveryRun.id).where(DiscoveryRun.execution_provenance.is_not(None),
            DiscoveryRun.status == "pending", DiscoveryRun.dispatch_state == "pending",
            or_(DiscoveryRun.dispatch_after.is_(None), DiscoveryRun.dispatch_after <= discovery.utcnow()))
            .order_by(DiscoveryRun.created_at, DiscoveryRun.id).limit(16)))
    for identifier in recovering:
        with normal_operation(read_only=True), session_factory() as db:
            await discovery.reconcile(db, identifier)
    for identifier in pending:
        with normal_operation(read_only=True), session_factory() as db:
            await discovery.dispatch(db, identifier)


async def serve():
    stopping = asyncio.Event()
    loop = asyncio.get_running_loop()
    for number in (signal.SIGTERM, signal.SIGINT):
        loop.add_signal_handler(number, stopping.set)
    while not stopping.is_set():
        try:
            await tick()
        except (BackupError, OSError):
            logger.warning("category=maintenance_or_state_unavailable")
        except SQLAlchemyError:
            logger.warning("category=database_unavailable")
        try:
            await asyncio.wait_for(stopping.wait(), timeout=5)
        except TimeoutError:
            pass


def main() -> None:
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s %(levelname)s %(name)s: %(message)s",
    )
    logger.info("Atlas worker is ready")
    asyncio.run(serve())


if __name__ == "__main__":
    main()
