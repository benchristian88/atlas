"""Simulated discovery vertical slice for testing the knowledge pipeline."""

from __future__ import annotations

import hashlib
import json
import uuid
from datetime import datetime, timezone

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models import (
    AssetRelationship,
    DataSource,
    DiscoveryRun,
    EvidenceRecord,
    ReconciliationItem,
)
from app.schemas import SimulatedDiscoveryRequest
from app.services.knowledge_assertions import record_assertion
from app.services.reconciliation import create_item, find_asset


def _payload_hash(payload: dict) -> str:
    encoded = json.dumps(payload, sort_keys=True, separators=(",", ":")).encode()
    return hashlib.sha256(encoded).hexdigest()


def _source(db: Session, payload: SimulatedDiscoveryRequest) -> DataSource:
    if payload.data_source_id is not None:
        source = db.get(DataSource, payload.data_source_id)
        if source is None:
            raise ValueError("Data source not found")
        if source.customer_id != payload.customer_id or source.site_id not in {
            None,
            payload.site_id,
        }:
            raise ValueError("Data source does not match the requested customer and site")
        return source
    source = db.scalar(
        select(DataSource).where(
            DataSource.customer_id == payload.customer_id,
            DataSource.site_id == payload.site_id,
            DataSource.name == "Manual Discovery Simulation",
            DataSource.source_type == "simulated_discovery",
        )
    )
    if source is None:
        source = DataSource(
            customer_id=payload.customer_id,
            site_id=payload.site_id,
            name="Manual Discovery Simulation",
            source_type="simulated_discovery",
            status="active",
            trust_level="test",
            notes="Created automatically by the simulated discovery endpoint.",
        )
        db.add(source)
        db.flush()
    return source


def run_simulation(
    db: Session,
    *,
    payload: SimulatedDiscoveryRequest,
    user_id: uuid.UUID,
) -> tuple[DiscoveryRun, int, int, list[ReconciliationItem]]:
    now = datetime.now(timezone.utc)
    source = _source(db, payload)
    run = DiscoveryRun(
        integration_id=None,
        data_source_id=source.id,
        customer_id=payload.customer_id,
        site_id=payload.site_id,
        status="running",
        started_at=now,
        created_by_user_id=user_id,
        summary={},
    )
    db.add(run)
    db.flush()

    evidence_count = 0
    assertions_created = 0
    items: list[ReconciliationItem] = []

    def remember(result: tuple[ReconciliationItem, bool]) -> None:
        item, created = result
        if created:
            items.append(item)

    for observation in payload.observations:
        external_id = observation.external_id or (
            f"simulated:{observation.asset_type}:{observation.name}"
        )
        raw = observation.model_dump(mode="json")
        evidence = EvidenceRecord(
            discovery_run_id=run.id,
            data_source_id=source.id,
            customer_id=payload.customer_id,
            site_id=payload.site_id,
            external_id=external_id,
            entity_kind=observation.entity_kind,
            payload_json=raw,
            payload_hash=_payload_hash(raw),
            observed_at=now,
        )
        db.add(evidence)
        db.flush()
        evidence_count += 1

        if observation.entity_kind != "asset":
            continue
        asset = find_asset(
            db,
            customer_id=payload.customer_id,
            site_id=payload.site_id,
            external_id=external_id,
            name=observation.name,
            asset_type=observation.asset_type,
        )
        assertion_by_field = {}
        selected = {
            "asset_type": observation.asset_type,
            "name": observation.name,
            "hostname": observation.facts.get("hostname"),
            "status": observation.facts.get("status"),
        }
        for field, value in selected.items():
            if value is None:
                continue
            assertion, created = record_assertion(
                db,
                customer_id=payload.customer_id,
                site_id=payload.site_id,
                subject_type="asset",
                subject_id=asset.id if asset else None,
                subject_external_id=external_id,
                predicate=field,
                value=value,
                data_source_id=source.id,
                discovery_run_id=run.id,
                evidence_record_id=evidence.id,
                observed_at=now,
            )
            assertion_by_field[field] = assertion
            assertions_created += int(created)

        for interface in observation.interfaces:
            if interface.ip_address is None:
                continue
            _, created = record_assertion(
                db,
                customer_id=payload.customer_id,
                site_id=payload.site_id,
                subject_type="asset",
                subject_id=asset.id if asset else None,
                subject_external_id=external_id,
                predicate=f"interface.{interface.name}.ip_address",
                value={
                    "ip_address": interface.ip_address,
                    "network_name": interface.network_name,
                },
                data_source_id=source.id,
                discovery_run_id=run.id,
                evidence_record_id=evidence.id,
                observed_at=now,
            )
            assertions_created += int(created)

        if asset is None:
            anchor = assertion_by_field.get("name") or assertion_by_field["asset_type"]
            remember(
                create_item(
                    db,
                    assertion=anchor,
                    category="newly_discovered",
                    entity_type="asset",
                    entity_id=None,
                    candidate_external_id=external_id,
                    current_value=None,
                    observed_value={
                        "name": observation.name,
                        "asset_type": observation.asset_type,
                        "facts": observation.facts,
                        "interfaces": [item.model_dump(mode="json") for item in observation.interfaces],
                    },
                    recommended_action="Create asset",
                )
            )
        else:
            for field, assertion in assertion_by_field.items():
                current_value = getattr(asset, field, None)
                observed_value = assertion.value_json
                if current_value == observed_value:
                    continue
                category = "contradiction" if asset.source == "manual" else "changed"
                remember(
                    create_item(
                        db,
                        assertion=assertion,
                        category=category,
                        entity_type="asset",
                        entity_id=asset.id,
                        candidate_external_id=external_id,
                        current_value={"field": field, "value": current_value},
                        observed_value={"field": field, "value": observed_value},
                        recommended_action=f"Update asset {field}",
                    )
                )

        for relationship in observation.relationships:
            target = find_asset(
                db,
                customer_id=payload.customer_id,
                site_id=payload.site_id,
                external_id=relationship.target_external_id,
            )
            assertion, created = record_assertion(
                db,
                customer_id=payload.customer_id,
                site_id=payload.site_id,
                subject_type="asset",
                subject_id=asset.id if asset else None,
                subject_external_id=external_id,
                predicate=relationship.relationship_type,
                object_type="asset",
                object_id=target.id if target else None,
                object_external_id=relationship.target_external_id,
                data_source_id=source.id,
                discovery_run_id=run.id,
                evidence_record_id=evidence.id,
                observed_at=now,
            )
            assertions_created += int(created)
            existing_relationship = None
            if asset is not None and target is not None:
                existing_relationship = db.scalar(
                    select(AssetRelationship).where(
                        AssetRelationship.source_asset_id == asset.id,
                        AssetRelationship.target_asset_id == target.id,
                        AssetRelationship.relationship_type == relationship.relationship_type,
                    )
                )
            if existing_relationship is None:
                remember(
                    create_item(
                        db,
                        assertion=assertion,
                        category="inferred_relationship",
                        entity_type="asset_relationship",
                        entity_id=None,
                        candidate_external_id=external_id,
                        current_value=None,
                        observed_value={
                            "source_external_id": external_id,
                            "target_external_id": relationship.target_external_id,
                            "relationship_type": relationship.relationship_type,
                        },
                        recommended_action="Create relationship",
                    )
                )

    run.status = "completed"
    run.finished_at = datetime.now(timezone.utc)
    run.completed_at = run.finished_at
    run.summary = {
        "observations": len(payload.observations),
        "evidence_records_created": evidence_count,
        "assertions_created": assertions_created,
        "reconciliation_items_created": len(items),
    }
    source.last_success_at = run.finished_at
    return run, evidence_count, assertions_created, items
