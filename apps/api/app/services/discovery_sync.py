from copy import deepcopy
from datetime import datetime, timezone

from atlas_plugin_sdk import (
    DiscoveryResult,
    NormalizationResult,
    SyncContext,
    SyncError,
    SyncResult,
)
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models import (
    Asset,
    AssetFact,
    AssetRelationship,
    DiscoveryRun,
    Document,
)
from app.services.markdown_docs import generate_asset_document


class AtlasDiscoverySync:
    """Persist one discovery result using Atlas-owned, idempotent identities."""

    def __init__(self, db: Session) -> None:
        self.db = db

    def persist(
        self,
        context: SyncContext,
        discovery: DiscoveryResult,
        normalized: NormalizationResult,
    ) -> SyncResult:
        """Save raw data and normalized data in one database transaction."""

        try:
            run = self.db.get(DiscoveryRun, context.discovery_run_id)
            if run is None or run.integration_id != context.integration_id:
                raise SyncError("Discovery run does not match the sync context")

            run.raw_payload = deepcopy(discovery.raw_payload)
            run.started_at = run.started_at or discovery.observed_at
            result = self._sync(context, normalized, discovery.observed_at)
            documents_generated = self._upsert_documents(
                context, normalized, discovery.observed_at
            )
            run.status = "completed"
            run.completed_at = datetime.now(timezone.utc)
            run.error_message = None
            run.summary = {
                "raw_items": len(discovery.items),
                "assets_seen": result.assets_seen,
                "created": result.created,
                "updated": result.updated,
                "unchanged": result.unchanged,
                "stale_marked": result.stale_marked,
                "relationships_upserted": result.relationships_upserted,
                "facts_upserted": result.facts_upserted,
                "documents_generated": documents_generated,
            }
            self.db.commit()
            return result
        except SyncError:
            self.db.rollback()
            raise
        except Exception as exc:
            self.db.rollback()
            raise SyncError("Could not persist discovery results") from exc

    async def sync(
        self, context: SyncContext, normalized: NormalizationResult
    ) -> SyncResult:
        """Implement SyncBackend when raw persistence is managed separately."""

        try:
            observed_at = datetime.now(timezone.utc)
            result = self._sync(context, normalized, observed_at)
            self._upsert_documents(context, normalized, observed_at)
            self.db.commit()
            return result
        except Exception as exc:
            self.db.rollback()
            if isinstance(exc, SyncError):
                raise
            raise SyncError("Could not synchronize normalized assets") from exc

    def _sync(
        self,
        context: SyncContext,
        normalized: NormalizationResult,
        observed_at: datetime,
    ) -> SyncResult:
        external_ids = {asset.external_id for asset in normalized.assets}
        if len(external_ids) != len(normalized.assets):
            raise SyncError("Normalized results contain duplicate asset identities")

        existing_assets = list(
            self.db.scalars(
                select(Asset).where(
                    Asset.source_integration_id == context.integration_id
                )
            )
        )
        assets_by_external_id = {
            asset.external_id: asset
            for asset in existing_assets
            if asset.external_id is not None
        }
        created = updated = unchanged = stale_marked = 0

        for normalized_asset in normalized.assets:
            asset = assets_by_external_id.get(normalized_asset.external_id)
            values = {
                "workspace_id": context.workspace_id,
                "customer_id": context.customer_id,
                "site_id": context.site_id,
                "name": normalized_asset.name,
                "asset_type": normalized_asset.asset_type,
                "vendor": normalized_asset.vendor,
                "status": normalized_asset.status,
                "description": normalized_asset.description,
                "metadata_": dict(normalized_asset.metadata),
                "last_seen_at": observed_at,
            }
            if asset is None:
                asset = Asset(
                    source_integration_id=context.integration_id,
                    external_id=normalized_asset.external_id,
                    first_seen_at=observed_at,
                    **values,
                )
                self.db.add(asset)
                assets_by_external_id[normalized_asset.external_id] = asset
                created += 1
            else:
                changed = any(
                    getattr(asset, field) != value
                    for field, value in values.items()
                    if field != "last_seen_at"
                )
                for field, value in values.items():
                    setattr(asset, field, value)
                if changed:
                    updated += 1
                else:
                    unchanged += 1

        for asset in existing_assets:
            if asset.external_id not in external_ids and asset.status != "stale":
                asset.status = "stale"
                stale_marked += 1

        self.db.flush()
        asset_ids = [asset.id for asset in assets_by_external_id.values()]
        existing_facts = list(
            self.db.scalars(select(AssetFact).where(AssetFact.asset_id.in_(asset_ids)))
        )
        facts_by_identity = {
            (fact.asset_id, fact.key, fact.source): fact for fact in existing_facts
        }
        facts_upserted = 0
        for normalized_asset in normalized.assets:
            asset = assets_by_external_id[normalized_asset.external_id]
            for normalized_fact in normalized_asset.facts:
                identity = (asset.id, normalized_fact.key, normalized_fact.source)
                fact = facts_by_identity.get(identity)
                if fact is None:
                    fact = AssetFact(
                        asset_id=asset.id,
                        key=normalized_fact.key,
                        source=normalized_fact.source,
                        value=normalized_fact.value,
                    )
                    self.db.add(fact)
                    facts_by_identity[identity] = fact
                else:
                    fact.value = normalized_fact.value
                facts_upserted += 1

        existing_relationships = list(
            self.db.scalars(
                select(AssetRelationship).where(
                    AssetRelationship.source_asset_id.in_(asset_ids),
                    AssetRelationship.target_asset_id.in_(asset_ids),
                )
            )
        )
        relationships_by_identity = {
            (
                relationship.source_asset_id,
                relationship.target_asset_id,
                relationship.relationship_type,
            ): relationship
            for relationship in existing_relationships
        }
        relationships_upserted = 0
        for normalized_relationship in normalized.relationships:
            source = assets_by_external_id.get(
                normalized_relationship.source_external_id
            )
            target = assets_by_external_id.get(
                normalized_relationship.target_external_id
            )
            if source is None or target is None:
                raise SyncError("Relationship references an unknown normalized asset")
            identity = (
                source.id,
                target.id,
                normalized_relationship.relationship_type,
            )
            relationship = relationships_by_identity.get(identity)
            if relationship is None:
                relationship = AssetRelationship(
                    source_asset_id=source.id,
                    target_asset_id=target.id,
                    relationship_type=normalized_relationship.relationship_type,
                    metadata_=dict(normalized_relationship.metadata),
                )
                self.db.add(relationship)
                relationships_by_identity[identity] = relationship
            else:
                relationship.metadata_ = dict(normalized_relationship.metadata)
            relationships_upserted += 1

        return SyncResult(
            created=created,
            updated=updated,
            unchanged=unchanged,
            relationships_upserted=relationships_upserted,
            facts_upserted=facts_upserted,
            stale_marked=stale_marked,
        )

    def _upsert_documents(
        self,
        context: SyncContext,
        normalized: NormalizationResult,
        observed_at: datetime,
    ) -> int:
        if not normalized.assets:
            return 0
        external_ids = {asset.external_id for asset in normalized.assets}
        persisted_assets = list(
            self.db.scalars(
                select(Asset).where(
                    Asset.source_integration_id == context.integration_id,
                    Asset.external_id.in_(external_ids),
                )
            )
        )
        persisted_by_external_id = {
            asset.external_id: asset
            for asset in persisted_assets
            if asset.external_id in external_ids
        }
        if set(persisted_by_external_id) != external_ids:
            raise SyncError("Cannot generate documents for unpersisted assets")

        asset_ids = [asset.id for asset in persisted_by_external_id.values()]
        generated_documents = list(
            self.db.scalars(
                select(Document).where(
                    Document.asset_id.in_(asset_ids),
                    Document.generated_from_discovery_run_id.is_not(None),
                )
            )
        )
        documents_by_asset_id = {}
        for document in generated_documents:
            if (
                document.asset_id in asset_ids
                and document.generated_from_discovery_run_id is not None
            ):
                documents_by_asset_id.setdefault(document.asset_id, document)
        normalized_by_external_id = {
            asset.external_id: asset for asset in normalized.assets
        }

        for normalized_asset in normalized.assets:
            persisted_asset = persisted_by_external_id[normalized_asset.external_id]
            generated = generate_asset_document(
                normalized_asset,
                normalized_by_external_id,
                normalized.relationships,
                discovery_run_id=context.discovery_run_id,
                observed_at=observed_at,
            )
            document = documents_by_asset_id.get(persisted_asset.id)
            if document is None:
                document = Document(
                    asset_id=persisted_asset.id,
                    title=generated.title,
                    content_markdown=generated.content_markdown,
                    generated_from_discovery_run_id=context.discovery_run_id,
                )
                self.db.add(document)
                documents_by_asset_id[persisted_asset.id] = document
            else:
                document.title = generated.title
                document.content_markdown = generated.content_markdown
                document.generated_from_discovery_run_id = context.discovery_run_id
        return len(normalized.assets)
