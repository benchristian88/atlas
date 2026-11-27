"""Prepare Connector and discovery fixtures for disposable browser runs.

Run using python -m tests.seed_onboarding_integration_browser. Commands require
a local disposable database and private temporary state.
"""
import asyncio
import hashlib
import json
from pathlib import Path
import sys
from tempfile import TemporaryDirectory
from uuid import UUID

from sqlalchemy import func, insert, select
from sqlalchemy.engine import make_url

from app.database import DATABASE_URL, SessionLocal
from app.models import (Asset, AssetRelationship, AuditEvent, DataSource, DiscoveryRun, EntitySourceLink,
                        EvidenceRecord, Integration, KnowledgeAssertion, KnowledgeChange, ReconciliationItem,
                        BusinessFunction, Customer, KnowledgeGap, Network, Service, ServiceAssetDependency,
                        ServiceBusinessFunction, SiteOnboarding)
from app.services import connector_lifecycle as lifecycle
from app.services.backup_runtime import state_directory
from app.services.integration_runtime import runtime
from tests.i3_fixtures import fixture_bundle


async def install():
    health = await runtime.health()
    if health["status"] != "healthy":
        raise ValueError("The pinned local runtime must be healthy")
    store = lifecycle.package_store()
    with TemporaryDirectory(prefix="atlas-e1d-fixture-", dir=store.root.parent) as directory:
        package, verifier = fixture_bundle(Path(directory), with_probe=True)
        stored = store.install(package, verifier)
        verified = await runtime.verify_connector({
            "connector_id": stored.connector_id, "version": stored.version, "digest": stored.bundle_digest[7:],
        })
        if verified["state"] != "verified":
            raise ValueError("The local runtime did not verify the test package")
        with SessionLocal.begin() as db:
            lifecycle.activate(db, stored, health)


def seed_history(customer, site):
    with SessionLocal.begin() as db:
        source = DataSource(name="Existing Proxmox history", customer_id=customer, site_id=site,
            source_type="connector", status="active", trust_level="observed")
        db.add(source)
        db.flush()
        integration = Integration(name=source.name, plugin_id="proxmox", customer_id=customer, site_id=site,
            data_source_id=source.id, base_url="", username_or_token_id="", secret_reference="")
        db.add(integration)
        db.flush()
        db.add(DiscoveryRun(customer_id=customer, site_id=site, integration_id=integration.id,
            data_source_id=source.id, status="completed", dispatch_state="settled"))


def seed_review_history(customer, site):
    with SessionLocal.begin() as db:
        for name, status in (
            ("Failed discovery " + "LongIntegrationName" * 6, "failed"),
            ("Running discovery fixture", "running"),
            ("Incomplete configuration fixture", None),
        ):
            source = DataSource(name=name, customer_id=customer, site_id=site,
                source_type="connector", status="active", trust_level="observed")
            db.add(source)
            db.flush()
            integration = Integration(name=name, plugin_id="proxmox", customer_id=customer, site_id=site,
                data_source_id=source.id, base_url="", username_or_token_id="", secret_reference="",
                status="configured" if status else "unconfigured")
            db.add(integration)
            db.flush()
            if status:
                db.add(DiscoveryRun(customer_id=customer, site_id=site, integration_id=integration.id,
                    data_source_id=source.id, status=status, dispatch_state="running" if status == "running" else "settled"))


def snapshot(customer, site):
    with SessionLocal() as db:
        records = db.scalars(select(Integration).where(Integration.customer_id == customer, Integration.site_id == site)).all()
        runs = db.scalars(select(DiscoveryRun).where(DiscoveryRun.customer_id == customer, DiscoveryRun.site_id == site)).all()
        def count(model, *conditions):
            return db.scalar(select(func.count()).select_from(model).where(
                model.customer_id == customer, model.site_id == site, *conditions,
            ))
        return {
            "integrations": [{"id": str(row.id), "name": row.name, "schedule": row.schedule_preset or "manual"} for row in records],
            "runs": [{"id": str(row.id), "integrationId": str(row.integration_id), "status": row.status,
                "observations": row.observation_count} for row in runs],
            "assets": count(Asset),
            "acceptedSourceLinks": count(EntitySourceLink),
            "reconciliationItems": count(ReconciliationItem),
            "reconciliationDecisions": count(ReconciliationItem, ReconciliationItem.status != "open"),
            "actions": list(db.scalars(select(AuditEvent.event_type).where(AuditEvent.site_id == site))),
        }


def review_snapshot(customer, site):
    with SessionLocal() as db:
        def scoped(model):
            return select(model).where(model.customer_id == customer, model.site_id == site)

        return {
            "evidence": len(db.scalars(scoped(EvidenceRecord)).all()),
            "assets": [{"name": row.name, "status": row.status} for row in db.scalars(scoped(Asset))],
            "relationships": len(db.scalars(scoped(AssetRelationship)).all()),
            "runs": [str(row.id) for row in db.scalars(scoped(DiscoveryRun))],
            "proposals": {
                str(row.id): {"status": row.status, "actor": str(row.decided_by_user_id),
                              "accepted_assertion": claim.is_accepted, "assertion_actor": str(claim.accepted_by_user_id)}
                for row, claim in db.execute(scoped(ReconciliationItem).join(
                    KnowledgeAssertion, KnowledgeAssertion.id == ReconciliationItem.assertion_id,
                ).add_columns(KnowledgeAssertion))
            },
            "changes": sorted(str(row.reconciliation_item_id) for row in db.scalars(scoped(KnowledgeChange))
                              if row.reconciliation_item_id),
            "audits": {str(row.target_id): str(row.user_id) for row in db.scalars(
                scoped(AuditEvent).where(AuditEvent.event_type == "reconciliation.accepted"))},
        }


def showcase_snapshot(customer, site):
    with SessionLocal() as db:
        state = db.scalar(select(SiteOnboarding).where(
            SiteOnboarding.customer_id == customer, SiteOnboarding.site_id == site,
        ))
        domain = {}
        for model in (
            Asset, AssetRelationship, BusinessFunction, DiscoveryRun, Integration, KnowledgeAssertion,
            KnowledgeChange, KnowledgeGap, Network, ReconciliationItem, Service, ServiceAssetDependency, ServiceBusinessFunction,
        ):
            table = model.__table__
            rows = db.execute(select(*table.c).where(table.c.customer_id == customer).order_by(table.c.id))
            domain[table.name] = hashlib.sha256(json.dumps([list(row) for row in rows], default=str).encode()).hexdigest()
        return {
            "domain": domain,
            "workflow": None if state is None else {
                "status": state.status, "version": state.version, "decisions": state.stage_decisions,
                "completed_at": state.completed_at, "last_actor_id": state.last_actor_id,
            },
            "completion_audits": [str(actor) for actor in db.scalars(select(AuditEvent.user_id).where(
                AuditEvent.customer_id == customer, AuditEvent.site_id == site, AuditEvent.event_type == "onboarding.completed",
            ))],
        }


def seed_showcase_inventory(customer, site):
    with SessionLocal.begin() as db:
        workspace = db.scalar(select(Customer.workspace_id).where(Customer.id == customer))
        db.execute(insert(Asset), [
            {"customer_id": customer, "site_id": site, "workspace_id": workspace, "asset_type": "virtual_machine",
             "name": f"Recorded QA asset {index}"}
            for index in range(12345)
        ])


if __name__ == "__main__":
    url = make_url(DATABASE_URL)
    command, *ids = sys.argv[1:]
    if command in {"review-history", "showcase-snapshot", "showcase-inventory"}:
        if (url.host not in {"127.0.0.1", "localhost"}
                or not (url.database or "").startswith(("atlas_e1d_", "atlas_e1g_", "atlas_e1h_"))
                or not state_directory().is_relative_to(Path("/tmp").resolve())):
            raise SystemExit("Select a disposable onboarding browser database and temporary state directory")
        customer, site = (UUID(value) for value in ids)
        if command == "review-history":
            seed_review_history(customer, site)
        elif command == "showcase-inventory":
            seed_showcase_inventory(customer, site)
        else:
            print(json.dumps(showcase_snapshot(customer, site), default=str))
    else:
        store = lifecycle.package_store().root
        if url.host not in {"127.0.0.1", "localhost"} or not (url.database or "").startswith("atlas_e1d_") or not store.is_relative_to(Path("/private/tmp")):
            raise SystemExit("Select a disposable E1-D browser database and temporary Connector store")
        if command == "install":
            asyncio.run(install())
        else:
            customer, site = (UUID(value) for value in ids)
            if command == "history":
                seed_history(customer, site)
            elif command == "snapshot":
                print(json.dumps(snapshot(customer, site)))
            elif command == "review-snapshot":
                print(json.dumps(review_snapshot(customer, site)))
            else:
                raise SystemExit("Expected install, history, snapshot or review-snapshot")
