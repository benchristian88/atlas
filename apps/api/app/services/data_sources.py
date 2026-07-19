"""Shared data-source construction helpers."""

from __future__ import annotations

import uuid

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models import DataSource


def manual_inventory_source(
    db: Session, customer_id: uuid.UUID, site_id: uuid.UUID | None
) -> DataSource:
    source = db.scalar(
        select(DataSource).where(
            DataSource.customer_id == customer_id,
            DataSource.site_id == site_id,
            DataSource.name == "Atlas Manual Inventory",
            DataSource.source_type == "manual",
        )
    )
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
