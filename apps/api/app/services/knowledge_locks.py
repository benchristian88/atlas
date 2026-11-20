"""Canonical knowledge serialization shared by manual and sourced decisions.

Decision transactions lock DataSources FOR NO KEY UPDATE (UUID order), canonical
subjects FOR UPDATE (model order below, then UUID), review items, then assertions.
The source mode serializes decisions but permits the implicit FK KEY SHARE taken
by manual assertion inserts while holding their Asset. FOR UPDATE on a source
would invert that implicit lock against retraction's source -> Asset order.
Source identities/primary keys are never mutated by these operations. Ingestion
uses the same source mode. Do not acquire an unrelated source under subject locks.
Ingestion prelocks the operation's already-linked Assets, Networks and Interfaces
(including owners and relationship endpoints) before writing any claims. AIP
collects the whole run across batches and includes complete-snapshot subjects;
per-observation callers may only reacquire subsets of that ordered set.
Upstream run control retains Integration writer serialization and locks immutable
DiscoveryRun identities FOR NO KEY UPDATE. This still excludes other run writers
but permits provenance FK KEY SHARE from decisions already holding a source;
FOR UPDATE would introduce a Run -> Source -> Run cycle. Lease/state checks and
identity keys are unchanged.
"""
from collections import defaultdict
from contextlib import contextmanager
from functools import wraps
from inspect import signature

from fastapi import HTTPException
from sqlalchemy import select, tuple_
from sqlalchemy.exc import DBAPIError

from app.models import Asset, AssetInterface, AssetRelationship, BusinessFunction, DataSource, EntitySourceLink, Network, Service

SUBJECT_MODELS = {
    "asset": Asset,
    "network": Network,
    "asset_interface": AssetInterface,
    "asset_relationship": AssetRelationship,
    "service": Service,
    "business_function": BusinessFunction,
}


@contextmanager
def decision_conflicts(db):
    """Convert only expected transaction conflicts, including manual PATCH."""
    try:
        yield
    except DBAPIError as exc:
        db.rollback()
        if getattr(exc.orig, "sqlstate", None) not in {"23505", "40001", "40P01", "55P03"}:
            raise
        raise HTTPException(409, "A concurrent change prevented this decision; refresh and review before retrying") from None


def concurrent_decision(operation):
    resolved_signature = signature(operation, eval_str=True)
    @wraps(operation)
    def guarded(*args, **kwargs):
        db = resolved_signature.bind(*args, **kwargs).arguments["db"]
        with decision_conflicts(db):
            return operation(*args, **kwargs)
    # FastAPI must resolve postponed route annotations in the route's globals,
    # rather than in this shared decorator's module.
    guarded.__signature__ = resolved_signature
    return guarded


def lock_subject(db, kind, identifier):
    """Lock without refreshing away the caller's intentional pending changes."""
    model = SUBJECT_MODELS.get(kind)
    if model is not None and identifier is not None:
        return db.get(model, identifier, with_for_update=True)


def lock_subjects(db, identifiers):
    for kind, model in SUBJECT_MODELS.items():
        ids = identifiers.get(kind, set()) - {None}
        if ids:
            list(db.scalars(select(model).where(model.id.in_(ids)).order_by(model.id)
                            .with_for_update().execution_options(populate_existing=True)))


def lock_ingestion_subjects(db, *, source_id, customer_id, site_id, references):
    """Prelock this operation's existing source identities before ANY claims.

    Multi-entity callers must supply their complete reference set before their
    first write, including Interface owners/Networks and relationship endpoints.
    Reacquiring subsets later is safe; discovering another lower-order subject
    after claims have been written is not. No identity is inferred or persisted.
    """
    source = db.get(DataSource, source_id, with_for_update={"key_share": True})
    if source is None or source.customer_id != customer_id or source.site_id not in {None, site_id}:
        raise HTTPException(409, "The ingestion source context is unavailable")
    references = {(kind, external) for kind, external in references if external}
    targets = defaultdict(set)
    if references:
        for link in db.scalars(select(EntitySourceLink).where(
                EntitySourceLink.data_source_id == source_id,
                EntitySourceLink.customer_id == customer_id,
                EntitySourceLink.site_id == site_id,
                EntitySourceLink.ended_epoch.is_(None),
                tuple_(EntitySourceLink.entity_type, EntitySourceLink.external_id).in_(references))):
            targets["asset"].update({link.entity_id, link.interface_owner_id})
            targets["network"].add(link.network_id)
            targets["asset_interface"].add(link.interface_id)
    lock_subjects(db, targets)
