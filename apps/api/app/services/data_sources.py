"""Shared data-source construction helpers."""

from __future__ import annotations

import uuid

from sqlalchemy import select, text
from sqlalchemy.orm import Session

from app.models import DataSource


def lock_customer_manual_inventory(db: Session, customer_id: uuid.UUID) -> None:
    """Serialize Customer-wide Service writes and catalogue batches before they claim unique keys."""
    db.execute(
        text("SELECT pg_advisory_xact_lock(hashtextextended(:name, 0))"),
        {"name": f"atlas-manual-customer-source:{customer_id}"},
    )


def manual_inventory_source(
    db: Session, customer_id: uuid.UUID, site_id: uuid.UUID | None
) -> DataSource:
    query = select(DataSource).where(
        DataSource.customer_id == customer_id,
        DataSource.site_id == site_id,
        DataSource.name == "Atlas Manual Inventory",
        DataSource.source_type == "manual",
    )
    source = db.scalar(query)
    if source is None and site_id is None:
        lock_customer_manual_inventory(db, customer_id)
        source = db.scalar(query)
    if source is None:
        source = DataSource(
            customer_id=customer_id,
            site_id=site_id,
            name="Atlas Manual Inventory",
            source_type="manual",
            status="active",
            trust_level="declared",
            notes="Represents accepted operational knowledge entered in Atlas.",
        )
        db.add(source)
        db.flush()
    return source
