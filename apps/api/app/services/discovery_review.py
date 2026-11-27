"""Site review over the canonical reconciliation projection."""

from collections import Counter
import hmac

from fastapi import HTTPException
from sqlalchemy import select

from app.auth import _secret_key
from app.models import DiscoveryRun, Integration
from app.services.entity_resolution import AssetIdentityCandidates, AssetResolution
from app.services.reconciliation import resolve_asset_proposal
from app.services.reconciliation_entities import ACTIVE, EntityReview


def _version(namespace, *values):
    return hmac.digest(_secret_key().encode(), repr((namespace, values)).encode(), "sha256").hex()


class DiscoveryReview:
    def __init__(self, db, context, principal, *, review=None):
        self.db, self.context, self.principal = db, context, principal
        self.review = review
        self.inventory = None
        self.asset_resolutions = {}
        self.active_runs = None
        if principal.can("integrations.view", context.customer_id, context.site_id):
            self.active_runs = db.execute(select(DiscoveryRun.id, DiscoveryRun.status).join(
                Integration, Integration.id == DiscoveryRun.integration_id,
            ).where(
                DiscoveryRun.customer_id == context.customer_id, DiscoveryRun.site_id == context.site_id,
                Integration.customer_id == context.customer_id, Integration.site_id == context.site_id,
                Integration.retired_at.is_(None), DiscoveryRun.archived_at.is_(None),
                DiscoveryRun.status.in_(("pending", "running")),
            ).order_by(DiscoveryRun.id)).all()
        self.runs = {}
        if principal.can("reconciliation.view", context.customer_id, context.site_id):
            self.review = review or EntityReview(db, context, principal)
            claim_runs = {claim.discovery_run_id for claim in self.review.claims.values() if claim.discovery_run_id}
            retired_source = select(Integration.id).where(
                Integration.data_source_id == DiscoveryRun.data_source_id,
                Integration.customer_id == DiscoveryRun.customer_id, Integration.site_id == DiscoveryRun.site_id,
                Integration.retired_at.is_not(None),
            ).correlate(DiscoveryRun).exists()
            self.runs = dict(db.execute(select(DiscoveryRun.id, DiscoveryRun.status).outerjoin(
                Integration, Integration.id == DiscoveryRun.integration_id,
            ).where(
                DiscoveryRun.id.in_(claim_runs), DiscoveryRun.customer_id == context.customer_id,
                DiscoveryRun.site_id == context.site_id, Integration.retired_at.is_(None), ~retired_source,
            )).tuples().all())

    def outstanding(self, item):
        claim = self.review.claims[item.id]
        return (item.status in ACTIVE and self.runs.get(claim.discovery_run_id) == "completed"
                and item.id not in self.review.stale_items and claim.is_source_current is not False
                and not claim.retracted_at and not claim.superseded_by_id)

    def batch_exclusion(self, item):
        if not self.outstanding(item):
            return "This discovery proposal is no longer available for acceptance"
        return self._classify_outstanding(item)[1]

    def _classify_outstanding(self, item):
        eligibility = self.review.eligibility(item)
        if not eligibility["can_accept"]:
            return "exceptions", eligibility["blocked_reason"]
        if item.category in {"contradiction", "possible_duplicate"}:
            return "conflicts", "Review this conflict individually"
        if item.status == "deferred":
            return "exceptions", "Review this deferred decision individually"
        if self.is_asset_proposal(item):
            if not self.principal.can("assets.view", item.customer_id, item.site_id):
                return "exceptions", "Permission required to review asset identity"
            if self.requires_asset_identity_review(item):
                return "conflicts", "An existing asset match requires an individual identity decision"
        return "eligible", None

    @staticmethod
    def is_asset_proposal(item):
        return item.entity_type == "asset" and item.category == "newly_discovered"

    def asset_resolution(self, item):
        if not self.is_asset_proposal(item) or not self.principal.can("assets.view", item.customer_id, item.site_id):
            return None
        if item.id not in self.asset_resolutions:
            if self.inventory is None:
                self.inventory = AssetIdentityCandidates(self.db, self.context.customer_id, self.context.site_id)
            try:
                resolution = resolve_asset_proposal(self.db, item, self.review.claims[item.id], inventory=self.inventory)
            except HTTPException as exc:
                if exc.status_code != 409:
                    raise
                resolution = AssetResolution("conflict")
            self.asset_resolutions[item.id] = resolution
        return self.asset_resolutions[item.id]

    def requires_asset_identity_review(self, item):
        resolution = self.asset_resolution(item)
        return resolution is not None and resolution.status in {"possible_duplicate", "conflict"}

    def refresh_projection(self, review):
        self.review = review
        self.principal = review.principal
        self.inventory = None
        self.asset_resolutions.clear()

    def present_item(self, item, reason, name):
        result = self.review.present_item(item)
        if reason and result["can_accept"] and self.requires_asset_identity_review(item):
            result.update(can_accept=False, blocked_reason=reason)
        resolution = self.asset_resolution(item) if reason is None else None
        identity = None
        if resolution is not None:
            identity = ({"action": "associate", "asset_name": resolution.asset.name}
                        if resolution.asset else {"action": "create"})
        return {**result, "entity_name": name,
                "batch_version": self.batch_version(item) if reason is None else None, "batch_exclusion": reason,
                "batch_identity": identity}

    def batch_version(self, item):
        claim = self.review.claims[item.id]
        resolution = self.asset_resolution(item)
        identity = None
        if resolution is not None:
            asset = resolution.asset
            identity = (resolution.status, (asset.id, asset.name, asset.asset_type) if asset else None)
        if item.entity_type == "asset_relationship":
            targets = tuple(
                self.review.target(item, claim, "asset", *self.review.relationship_endpoint(item, claim, side))
                for side in ("source", "target")
            )
            endpoints = tuple((target.id, target.name, target.asset_type) if target else None for target in targets)
        else:
            endpoints = ()
        return _version("discovery-batch", self.review.version(item), endpoints, identity)

    def _outstanding_items(self):
        if self.review is not None:
            yield from (item for item in self.review.items.values() if self.outstanding(item))

    def classify(self):
        return [(item, self._classify_outstanding(item)[1]) for item in self._outstanding_items()]

    def attention_counts(self):
        """Summarize the same outstanding queue without building decision versions."""
        counts = None
        if self.review is not None:
            counts = dict.fromkeys(("eligible", "conflicts", "exceptions"), 0)
            for item in self._outstanding_items():
                category, _ = self._classify_outstanding(item)
                counts[category] += 1
        return {"decisions": counts, "active_runs": None if self.active_runs is None else len(self.active_runs)}

    def summary(self, classified):
        visible = self.review is not None
        eligible = sum(reason is None for _, reason in classified)
        # Include changes in membership, content, exceptions and run state.
        proposal_state = tuple((item.id, self.batch_version(item), reason) for item, reason in classified)
        run_state = None if self.active_runs is None else tuple(tuple(row) for row in self.active_runs)
        return {
            "eligible": eligible if visible else None,
            "needs_review": len(classified) - eligible if visible else None,
            "accepted": sum(item.status == "accepted" and self.runs.get(claim.discovery_run_id) == "completed"
                            for item, claim in self.review.rows) if visible else None,
            "active_runs": len(run_state) if run_state is not None else None,
            "version": _version("discovery-progress", visible, proposal_state, run_state),
        }

    def page(self, *, search, source_id, category, offset, limit, decision_ids):
        classified = self.classify()
        sources, categories, selected = {}, set(), []
        search = search.strip().casefold()
        for item, reason in classified:
            claim = self.review.claims[item.id]
            source = self.review.sources.get(claim.data_source_id)
            if source:
                sources[source.id] = source.name
            categories.add(item.category)
            if (source_id and source_id != claim.data_source_id) or (category and category != item.category):
                continue
            entity = self.review.display(self.review.group_for_item[item.id])
            if search and search not in entity["name"].casefold():
                continue
            selected.append((item, reason, entity["name"]))
        # Use durable creation order, newest first, with a UUID tie-breaker.
        selected.reverse()
        counts = Counter(reason is None for _, reason, _ in selected)
        return {
            "items": [self.present_item(item, reason, name) for item, reason, name in selected[offset:offset + limit]],
            "eligible": counts[True], "needs_review": counts[False], "sources": sources,
            "categories": sorted(categories), "summary": self.summary(classified),
            "decisions": {identifier: self.review.items[identifier].status for identifier in decision_ids
                          if self.review is not None and identifier in self.review.items
                          and self.review.claims[identifier].discovery_run_id in self.runs},
        }
