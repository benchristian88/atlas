"""Simulated discovery vertical slice for testing the knowledge pipeline."""

from __future__ import annotations

import hashlib
import json
import uuid
from datetime import datetime, timezone

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models import (
    AssetInterface,
    AssetRelationship,
    DataSource,
    DiscoveryRun,
    EvidenceRecord,
    ReconciliationItem,
    Network,
)
from app.schemas import SimulatedDiscoveryRequest
from app.services.entity_resolution import (
    AssetResolution,
    normalized_name,
    resolve_asset_identity,
    technical_link,
)
from app.services.data_sources import manual_inventory_source
from app.services.knowledge_assertions import accept_assertion, confirm, record_assertion
from app.services.discovery_observations import (
    SnapshotReconciliation,
    default_coverage_key,
    reconcile_complete_snapshot,
    record_observed_entity,
)
from app.services.knowledge_changes import record_assertion_change
from app.services.reconciliation import create_item
from app.utils.json_values import to_json_value


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
        coverage_key=payload.coverage_key
        or default_coverage_key(payload.customer_id, payload.site_id),
        is_complete_snapshot=payload.is_complete_snapshot,
        completeness_status="unknown",
        started_at=now,
        created_by_user_id=user_id,
        summary={},
    )
    db.add(run)
    db.flush()

    return ingest_observations(db, payload=payload, user_id=user_id, source=source,
        run=run, observed_at=now, finalise=True)


def ingest_observations(db, *, payload, user_id, source, run, observed_at,
        finalise=False, evidence_by_identity=None, memberships=None, namespaced_facts=None, relationship_observations=None):
    """Shared evidence/assertion/reconciliation owner for validated observations.

    The simulation creates its own run/evidence. AIP supplies an existing durable
    run and immutable evidence/membership from its receipt transaction. Neither
    adapter changes accepted records or decides absence before finalisation.
    """
    now = observed_at
    memberships = memberships or {}
    namespaced_facts = namespaced_facts or {}

    def membership(**values):
        existing = memberships.get((values["entity_type"], values["external_id"]))
        if existing is not None:
            existing.entity_id = values["entity_id"]
            return existing
        return record_observed_entity(db, run=run, **values)

    evidence_count = 0
    assertions_created = 0
    items: list[ReconciliationItem] = []
    asset_jobs = []
    run_map: dict[str, AssetResolution] = {}

    def remember(result: tuple[ReconciliationItem, bool]) -> None:
        item, created = result
        if created:
            items.append(item)

    # Pass one records evidence and resolves every asset before relationships.
    for observation in payload.observations:
        external_id = observation.external_id or (
            f"simulated:{observation.asset_type}:{observation.name}"
        )
        raw = to_json_value(observation)
        evidence = evidence_by_identity.get((observation.entity_kind, external_id)) if evidence_by_identity is not None else None
        if evidence is None:
            evidence = EvidenceRecord(
                discovery_run_id=run.id,
                data_source_id=source.id,
                customer_id=payload.customer_id,
                site_id=payload.site_id,
                external_id=external_id,
                entity_kind=observation.entity_kind,
                payload_json=to_json_value(raw),
                payload_hash=_payload_hash(raw),
                observed_at=now,
            )
            db.add(evidence)
            db.flush()
            evidence_count += 1
        if observation.entity_kind != "asset":
            membership(
                entity_type=observation.entity_kind,
                external_id=external_id,
                entity_id=None,
                evidence_record_id=evidence.id,
                observed_at=now,
            )
            continue

        resolution = resolve_asset_identity(
            db,
            data_source_id=source.id,
            customer_id=payload.customer_id,
            site_id=payload.site_id,
            external_id=external_id,
            name=observation.name,
            asset_type=observation.asset_type,
            hostname=observation.facts.get("hostname"),
            run_map=run_map,
            observed_at=now,
        )
        if resolution.asset is None and resolution.status == "unresolved":
            resolution.status = "pending_asset_acceptance"
        run_map[external_id] = resolution
        asset = resolution.asset
        membership(
            entity_type="asset",
            external_id=external_id,
            entity_id=asset.id if asset else None,
            evidence_record_id=evidence.id,
            observed_at=now,
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
            possible_duplicate = resolution.status == "possible_duplicate"
            result = create_item(
                    db,
                    assertion=anchor,
                    category=("possible_duplicate" if possible_duplicate else "newly_discovered"),
                    entity_type="asset",
                    entity_id=None,
                    candidate_external_id=external_id,
                    current_value=(
                        {
                            "possible_matches": [
                                {
                                    "id": candidate.id,
                                    "name": candidate.name,
                                    "asset_type": candidate.asset_type,
                                }
                                for candidate in resolution.candidates
                            ]
                        }
                        if possible_duplicate
                        else None
                    ),
                    observed_value={
                        "name": observation.name,
                        "asset_type": observation.asset_type,
                        "facts": observation.facts,
                        "interfaces": [
                            item.model_dump(mode="json")
                            for item in observation.interfaces
                        ],
                    },
                    recommended_action=(
                        "Link to the intended existing asset"
                        if possible_duplicate
                        else "Create asset or link to an existing asset"
                    ),
                )
            remember(result)
            if result[1]:
                record_assertion_change(
                    db,
                    assertion=anchor,
                    item=result[0],
                    change_type="entity_discovered",
                    entity_name=observation.name,
                    summary=f"Discovered {observation.name}",
                    actor_user_id=user_id,
                    new_value=result[0].observed_value_json,
                )
        else:
            for field, assertion in assertion_by_field.items():
                current_value = getattr(asset, field, None)
                observed_value = assertion.value_json
                if current_value == observed_value:
                    continue
                if field in {"name", "hostname"} and normalized_name(
                    current_value
                ) == normalized_name(observed_value):
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
        asset_jobs.append((observation, evidence, external_id))
        for fact in namespaced_facts.get(external_id, []):
            assertion, created = record_assertion(db, customer_id=run.customer_id, site_id=run.site_id,
                subject_type="asset", subject_id=asset.id if asset else None, subject_external_id=external_id,
                predicate=fact["key"], value=fact["value"], data_source_id=source.id, discovery_run_id=run.id,
                evidence_record_id=evidence.id, observed_at=now,
                fact_metadata={name: fact[name] for name in ["value_type", "class", "cardinality"]})
            assertions_created += int(created)
            # One canonical fact carries a scalar or a complete value set. Its
            # classification never grants accepted-record mutation authority.
            if not assertion.is_accepted:
                remember(create_item(db, assertion=assertion, category="changed", entity_type="asset",
                    entity_id=asset.id if asset else None, candidate_external_id=external_id,
                    current_value=None, observed_value={"field": fact["key"], "value": fact["value"]},
                    recommended_action="Review source fact"))

    # Both adapters share relationship reconciliation, including durable sources
    # with no new Asset observation in this run.
    relationship_jobs = [(relationship, evidence, external_id)
        for observation, evidence, external_id in asset_jobs for relationship in observation.relationships]
    relationship_jobs.extend(relationship_observations or [])
    for relationship, evidence, external_id in relationship_jobs:
        source_resolution = run_map.get(external_id) or resolve_asset_identity(
            db, data_source_id=source.id, customer_id=payload.customer_id, site_id=payload.site_id,
            external_id=external_id, run_map=run_map, observed_at=now)
        target_resolution = resolve_asset_identity(
            db,
            data_source_id=source.id,
            customer_id=payload.customer_id,
            site_id=payload.site_id,
            external_id=relationship.target_external_id,
            run_map=run_map,
            allow_external_name_hint=True,
            observed_at=now,
        )
        source_asset = source_resolution.asset
        target_asset = target_resolution.asset
        assertion, created = record_assertion(
            db,
            customer_id=payload.customer_id,
            site_id=payload.site_id,
            subject_type="asset",
            subject_id=source_asset.id if source_asset else None,
            subject_external_id=external_id,
            predicate=relationship.relationship_type,
            object_type="asset",
            object_id=target_asset.id if target_asset else None,
            object_external_id=relationship.target_external_id,
            data_source_id=source.id,
            discovery_run_id=run.id,
            evidence_record_id=evidence.id,
            observed_at=now,
            truth_classification=relationship.truth_classification,
            confidence=relationship.confidence,
        )
        assertions_created += int(created)
        existing_relationship = None
        competing_relationship = None
        if source_asset is not None and target_asset is not None:
            existing_relationship = db.scalar(
                select(AssetRelationship).where(
                    AssetRelationship.source_asset_id == source_asset.id,
                    AssetRelationship.target_asset_id == target_asset.id,
                    AssetRelationship.relationship_type == relationship.relationship_type,
                )
            )
            if existing_relationship is None:
                competing = list(
                    db.scalars(
                        select(AssetRelationship).where(
                            AssetRelationship.source_asset_id == source_asset.id,
                            AssetRelationship.target_asset_id == target_asset.id,
                        )
                    )
                )
                if len(competing) == 1:
                    competing_relationship = competing[0]
        observed_value = {
            "source_external_id": external_id,
            "target_external_id": relationship.target_external_id,
            "relationship_type": relationship.relationship_type,
            "resolved_source_asset_id": source_asset.id if source_asset else None,
            "resolved_target_asset_id": target_asset.id if target_asset else None,
            "resolved_source_name": source_asset.name if source_asset else None,
            "resolved_target_name": target_asset.name if target_asset else None,
            "source_resolution_status": source_resolution.status,
            "target_resolution_status": target_resolution.status,
            "blocked_reason": None,
            "current_relationship_id": (
                existing_relationship.id
                if existing_relationship
                else competing_relationship.id
                if competing_relationship
                else None
            ),
        }
        unresolved = []
        if source_asset is None:
            unresolved.append(f"source {external_id} ({source_resolution.status})")
        if target_asset is None:
            unresolved.append(
                f"target {relationship.target_external_id} ({target_resolution.status})"
            )
        if unresolved:
            observed_value["blocked_reason"] = (
                f"Unresolved relationship endpoint: {', '.join(unresolved)}"
            )
        if existing_relationship is not None:
            confirm(assertion)
            if created:
                record_assertion_change(
                    db,
                    assertion=assertion,
                    change_type="assertion_confirmed",
                    entity_name=f"{source_asset.name} → {target_asset.name}",
                    summary=f"Confirmed {source_asset.name} {relationship.relationship_type.replace('_', ' ')} {target_asset.name}",
                    actor_user_id=user_id,
                    new_value={
                        "source_asset_id": source_asset.id,
                        "target_asset_id": target_asset.id,
                        "relationship_type": relationship.relationship_type,
                    },
                )
            for stale_item in db.scalars(
                select(ReconciliationItem).where(
                    ReconciliationItem.assertion_id == assertion.id,
                    ReconciliationItem.entity_type == "asset_relationship",
                    ReconciliationItem.status.in_(("open", "deferred")),
                )
            ):
                stale_item.status = "accepted"
                stale_item.entity_id = existing_relationship.id
                stale_item.decision_reason = (
                    "Existing operational relationship corroborated by discovery"
                )
                stale_item.decided_by_user_id = user_id
                stale_item.decided_at = now
            manual = manual_inventory_source(
                db, payload.customer_id, payload.site_id
            )
            declared, declared_created = record_assertion(
                db,
                customer_id=payload.customer_id,
                site_id=payload.site_id,
                subject_type="asset",
                subject_id=source_asset.id,
                predicate=relationship.relationship_type,
                object_type="asset",
                object_id=target_asset.id,
                truth_classification="declared",
                data_source_id=manual.id,
                observed_at=existing_relationship.created_at or now,
            )
            accept_assertion(db, declared, user_id=user_id)
            assertions_created += int(declared_created)
            continue
        remember(
            create_item(
                db,
                assertion=assertion,
                category=("contradiction" if competing_relationship else "inferred_relationship"),
                entity_type="asset_relationship",
                entity_id=None,
                candidate_external_id=external_id,
                current_value=(
                    {
                        "relationship_id": competing_relationship.id,
                        "source_asset_id": source_asset.id,
                        "source_name": source_asset.name,
                        "relationship_type": competing_relationship.relationship_type,
                        "target_asset_id": target_asset.id,
                        "target_name": target_asset.name,
                    }
                    if competing_relationship
                    else "No current relationship"
                ),
                observed_value=observed_value,
                recommended_action=(
                    "Resolve relationship endpoints"
                    if unresolved
                    else "Update relationship"
                    if competing_relationship
                    else "Create relationship"
                ),
            )
        )

    if not finalise:
        db.flush()
        return run, evidence_count, assertions_created, items

    run.status = "completed"
    run.finished_at = datetime.now(timezone.utc)
    run.completed_at = run.finished_at
    run.completeness_status = (
        "complete" if run.is_complete_snapshot else "partial"
    )
    db.flush()
    snapshot = reconcile_complete_snapshot(
        db,
        run=run,
        user_id=user_id,
        observed_at=run.finished_at,
    )
    items.extend(snapshot.items)
    run.summary = to_json_value({
        "observations": len(payload.observations),
        "evidence_records_created": evidence_count,
        "assertions_created": assertions_created,
        "reconciliation_items_created": len(items),
        "coverage_key": run.coverage_key,
        "is_complete_snapshot": run.is_complete_snapshot,
        "completeness_status": run.completeness_status,
        "baseline_run_id": snapshot.baseline_run_id,
        "no_longer_observed_count": snapshot.no_longer_observed_count,
        "reobserved_count": snapshot.reobserved_count,
    })
    source.last_success_at = run.finished_at
    run.snapshot_reconciliation = snapshot
    return run, evidence_count, assertions_created, items


def ingest_technical_observation(db, *, run, source, evidence, observation, entity_type, user_id):
    """Canonical Network/Interface evidence enters the same review machinery."""
    link = technical_link(db, data_source_id=source.id, customer_id=run.customer_id, site_id=run.site_id,
        entity_type=entity_type, external_id=observation["external_id"])
    target_id = (link.network_id if entity_type == "network" else link.interface_id) if link else None
    target = db.get(Network if entity_type == "network" else AssetInterface, target_id) if target_id else None
    if link:
        link.last_observed_at = evidence.observed_at
    fields = ["name", "network_type", "vlan_id", "cidr", "gateway"] if entity_type == "network" else [
        "name", "asset_external_id", "network_external_id", "ip_address", "mac_address", "is_primary"]
    observed = {name: observation.get(name) for name in fields}
    assertion, created = record_assertion(db, customer_id=run.customer_id, site_id=run.site_id,
        subject_type=entity_type, subject_id=target_id, subject_external_id=observation["external_id"],
        predicate="configuration", value=observed, data_source_id=source.id,
        discovery_run_id=run.id, evidence_record_id=evidence.id, observed_at=evidence.observed_at)
    item_count = 0
    current = {name: getattr(target, name, None) for name in fields} if target else None
    if target is not None and entity_type == "asset_interface":
        # Source identities resolve through links; canonical interfaces store IDs.
        owner_link = technical_link(db, data_source_id=source.id, customer_id=run.customer_id, site_id=run.site_id,
            entity_type="asset", external_id=observed["asset_external_id"])
        network_link = technical_link(db, data_source_id=source.id, customer_id=run.customer_id, site_id=run.site_id,
            entity_type="network", external_id=observed["network_external_id"]) if observed["network_external_id"] else None
        current["asset_external_id"] = observed["asset_external_id"] if owner_link and owner_link.entity_id == target.asset_id else None
        current["network_external_id"] = observed["network_external_id"] if network_link and network_link.network_id == target.network_id else None
    if not assertion.is_accepted or current != observed:
        item, item_created = create_item(db, assertion=assertion,
            category="changed" if target else "newly_discovered", entity_type=entity_type, entity_id=target_id,
            candidate_external_id=observation["external_id"],
            current_value=current,
            observed_value=observed, recommended_action="Review technical observation")
        item_count += int(item_created)
        if item_created and target is None:
            record_assertion_change(db, assertion=assertion, item=item, change_type="entity_discovered",
                entity_name=observation["name"], summary="Discovered " + observation["name"],
                actor_user_id=user_id, new_value=observed)
    for fact in observation["facts"]:
        claim, new = record_assertion(db, customer_id=run.customer_id, site_id=run.site_id,
            subject_type=entity_type, subject_id=target_id, subject_external_id=observation["external_id"],
            predicate=fact["key"], value=fact["value"], data_source_id=source.id, discovery_run_id=run.id,
            evidence_record_id=evidence.id, observed_at=evidence.observed_at,
            fact_metadata={name: fact[name] for name in ["value_type", "class", "cardinality"]})
        created += int(new)
        if not claim.is_accepted:
            _, new_item = create_item(db, assertion=claim, category="changed", entity_type=entity_type,
                entity_id=target_id, candidate_external_id=observation["external_id"], current_value=None,
                observed_value={"field": fact["key"], "value": fact["value"]}, recommended_action="Review source fact")
            item_count += int(new_item)
    return int(created), item_count, target_id
