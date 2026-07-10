import uuid

from atlas_plugin_sdk import (
    ConnectionConfig,
    ConnectionValidation,
    DiscoveryPlugin,
    DiscoveryResult,
    NormalizationResult,
    NormalizedAsset,
    RawDiscoveryItem,
    SyncBackend,
    SyncContext,
    SyncResult,
)


class ExamplePlugin:
    plugin_id = "example"

    async def validate_connection(self, config):
        return ConnectionValidation(valid=True)

    async def discover(self, config):
        return DiscoveryResult(
            items=(
                RawDiscoveryItem(
                    external_id="server/1",
                    resource_type="server",
                    payload={"vendor_name": "example-01"},
                ),
            )
        )

    def normalize(self, discovery):
        item = discovery.items[0]
        return NormalizationResult(
            assets=(
                NormalizedAsset(
                    external_id=item.external_id,
                    name="example-01",
                    asset_type="server",
                    vendor="Example Vendor",
                ),
            )
        )


class ExampleSyncBackend:
    async def sync(self, context, normalized):
        return SyncResult(created=len(normalized.assets))


def test_structural_plugin_and_sync_contracts() -> None:
    assert isinstance(ExamplePlugin(), DiscoveryPlugin)
    assert isinstance(ExampleSyncBackend(), SyncBackend)


def test_connection_repr_never_contains_credentials() -> None:
    config = ConnectionConfig(
        integration_id=uuid.uuid4(),
        base_url="https://infrastructure.example.test",
        credentials={"token": "do-not-log-this"},
    )
    assert "do-not-log-this" not in repr(config)
    assert "credentials" not in repr(config)


def test_raw_payload_is_separate_from_normalized_assets() -> None:
    raw = DiscoveryResult(
        items=(RawDiscoveryItem("node/1", "node", {"vendor_field": 42}),),
        raw_payload={"debug": {"request_id": "abc"}},
    )
    normalized = ExamplePlugin().normalize(raw)
    assert normalized.assets[0].external_id == raw.items[0].external_id
    assert not hasattr(normalized.assets[0], "raw_payload")


def test_sync_result_reports_seen_assets() -> None:
    result = SyncResult(created=2, updated=3, unchanged=4)
    assert result.assets_seen == 9


def test_sync_context_contains_atlas_scope() -> None:
    context = SyncContext(
        workspace_id=uuid.uuid4(),
        customer_id=uuid.uuid4(),
        integration_id=uuid.uuid4(),
        discovery_run_id=uuid.uuid4(),
    )
    assert context.site_id is None
