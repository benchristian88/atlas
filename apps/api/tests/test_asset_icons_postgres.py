"""Run against an isolated, migrated PostgreSQL database (never production)."""
import os
import uuid
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, timedelta, timezone
from types import SimpleNamespace
from unittest.mock import AsyncMock

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine, select, update
from sqlalchemy.orm import Session, sessionmaker

from app.authorization import ActiveContext, get_active_context, get_principal
from app.database import get_db
from app.main import app
from app.models import Asset, AssetIconCache, AssetType, Customer, Site, Workspace
from app.permissions import PERMISSIONS
from app.services import asset_icons as icons
from tests.test_asset_icons import image_bytes
from tests.test_operational_graph import principal

pytestmark = pytest.mark.skipif(not os.getenv("ATLAS_TEST_DATABASE_URL"), reason="requires disposable migrated PostgreSQL")


@pytest.fixture
def env(monkeypatch):
    engine = create_engine(os.environ["ATLAS_TEST_DATABASE_URL"])
    factory = sessionmaker(engine, expire_on_commit=False)
    actor = principal(*PERMISSIONS)
    actor.user.email = f"icons-{uuid.uuid4()}@example.test"
    with factory() as db:
        db.add(actor.user)
        workspace = Workspace(name="Icon tests", slug=f"icons-{uuid.uuid4()}")
        db.add(workspace); db.flush()
        customer = Customer(workspace_id=workspace.id, name="Icon tests")
        db.add(customer); db.flush()
        site = Site(customer_id=customer.id, name="Homelab")
        db.add(site); db.flush()
        asset_type = db.scalar(select(AssetType).limit(1))
        db.commit()
    current = [actor]
    def database():
        with factory() as db: yield db
    app.dependency_overrides[get_db] = database
    app.dependency_overrides[get_principal] = lambda: current[0]
    app.dependency_overrides[get_active_context] = lambda: ActiveContext(None, None)
    monkeypatch.setattr(icons, "SessionLocal", factory)
    fetch = AsyncMock(return_value=icons.normalize_image(image_bytes()))
    monkeypatch.setattr(icons, "fetch_icon", fetch)
    with TestClient(app) as client:
        def create(url="https://example.com/icon.png"):
            response = client.post("/api/assets", json={"name": "AdGuard Home", "customer_id": str(customer.id), "site_id": str(site.id), "asset_type": asset_type.key, "icon_url": url})
            assert response.status_code == 201, response.text
            return SimpleNamespace(id=uuid.UUID(response.json()["id"]), icon=response.json()["cached_icon_url"])
        yield SimpleNamespace(db=factory, client=client, create=create, current=current, actor=actor, customer=customer, site=site, fetch=fetch)
    app.dependency_overrides.clear()
    engine.dispose()


def test_lazy_fetch_unchanged_etag_and_clear(env):
    asset = env.create()
    env.fetch.assert_not_called()  # Saving/list serialization never contacts origin.
    assert env.client.get(asset.icon).status_code == 204
    response = env.client.get(asset.icon)
    assert response.status_code == 200
    assert response.headers["content-type"] == "image/png"
    assert response.headers["x-content-type-options"] == "nosniff"
    assert response.headers["cache-control"] == "private, no-cache"
    assert env.client.get(asset.icon, headers={"If-None-Match": response.headers["etag"]}).status_code == 304
    env.fetch.assert_awaited_once()
    assert env.client.patch(f"/api/assets/{asset.id}", json={"description": "same URL"}).status_code == 200
    assert env.client.get(asset.icon).status_code == 200
    env.fetch.assert_awaited_once()
    assert env.client.patch(f"/api/assets/{asset.id}", json={"icon_url": None}).status_code == 200
    assert env.client.get(asset.icon).status_code == 204
    with env.db() as db: assert db.get(AssetIconCache, asset.id) is None


def test_initial_failure_save_and_retry_backoff(env, caplog):
    env.fetch.side_effect = TimeoutError("https://example.com/?secret=hidden")
    asset = env.create()
    assert env.client.get(asset.icon).status_code == 204
    assert env.client.get(asset.icon).status_code == 204
    env.fetch.assert_awaited_once()
    with env.db() as db:
        cache = db.get(AssetIconCache, asset.id)
        assert cache.source_hash is None and cache.data is None
        cache.retry_after = datetime.now(timezone.utc) - timedelta(seconds=1)
        db.commit()
    env.fetch.side_effect = None
    assert env.client.get(asset.icon).status_code == 204
    assert env.client.get(asset.icon).status_code == 200
    assert "secret" not in caplog.text


def test_replacement_failure_preserves_bytes_but_does_not_serve_stale(env):
    asset = env.create()
    env.client.get(asset.icon)
    old = env.client.get(asset.icon).content
    env.fetch.side_effect = icons.IconRejected("blocked_destination")
    result = env.client.patch(f"/api/assets/{asset.id}", json={"icon_url": "https://10.0.0.1/private"})
    assert result.status_code == 200
    assert env.client.get(result.json()["cached_icon_url"]).status_code == 204
    assert env.client.get(asset.icon).status_code == 204  # stale version URL also checks current source
    with env.db() as db:
        cache = db.get(AssetIconCache, asset.id)
        assert cache.data == old
        assert cache.source_hash == icons.digest("https://example.com/icon.png")
    env.fetch.side_effect = None
    new = icons.normalize_image(image_bytes(color="blue"))
    env.fetch.return_value = new
    result = env.client.patch(f"/api/assets/{asset.id}", json={"icon_url": "https://example.com/new.png"})
    assert env.client.get(result.json()["cached_icon_url"]).status_code == 204
    assert env.client.get(result.json()["cached_icon_url"]).content == new
    with env.db() as db: assert db.get(AssetIconCache, asset.id).source_hash == icons.digest("https://example.com/new.png")


@pytest.mark.parametrize("damage", ["missing", "corrupt"])
def test_broken_cache_recovers_lazily(env, damage):
    asset = env.create()
    env.client.get(asset.icon)
    with env.db() as db:
        cache = db.get(AssetIconCache, asset.id)
        if damage == "missing": db.delete(cache)
        else:
            cache.data = b"corrupt"
            cache.retry_after = datetime.now(timezone.utc) - timedelta(seconds=1)
        db.commit()
    assert env.client.get(asset.icon).status_code == 204
    assert env.client.get(asset.icon).status_code == 200
    assert env.fetch.await_count == 2


def test_scope_non_disclosure_even_with_etag(env):
    asset = env.create()
    env.client.get(asset.icon)
    etag = env.client.get(asset.icon).headers["etag"]
    for denied in [principal("assets.view", customer_id=uuid.uuid4()), principal("assets.view", customer_id=env.customer.id, site_id=uuid.uuid4())]:
        env.current[0] = denied
        response = env.client.get(asset.icon, headers={"If-None-Match": etag})
        assert response.status_code == 404
        assert response.json() == env.client.get(f"/api/assets/{uuid.uuid4()}/icon").json()
    env.current[0] = principal()
    assert env.client.get(asset.icon).status_code == 403
    app.dependency_overrides.pop(get_principal)
    assert env.client.get(asset.icon).status_code == 401
    env.fetch.assert_awaited_once()


def test_concurrent_claim_and_stale_completion(env):
    asset = env.create()
    source = "https://example.com/icon.png"
    def claim(_):
        with env.db() as db: return icons.claim_attempt(db, asset.id, source)
    with ThreadPoolExecutor(max_workers=6) as pool:
        tokens = list(pool.map(claim, range(6)))
    assert sum(token is not None for token in tokens) == 1
    token = next(token for token in tokens if token)
    assert env.client.patch(f"/api/assets/{asset.id}", json={"icon_url": "https://example.com/changed.png"}).status_code == 200
    icons.refresh_icon(asset.id, source, token)
    with env.db() as db: assert db.get(AssetIconCache, asset.id).data is None


def test_no_source_and_delete_cleanup(env):
    empty = env.create(None)
    assert env.client.get(f"/api/assets/{empty.id}/icon").status_code == 204
    env.fetch.assert_not_called()
    asset = env.create()
    env.client.get(asset.icon)
    assert env.client.patch(f"/api/assets/{asset.id}", json={"status": "archived"}).status_code == 200
    assert env.client.get(asset.icon).status_code == 200
    assert env.client.delete(f"/api/assets/{asset.id}").status_code == 204
    assert env.client.get(asset.icon).status_code == 404
    with env.db() as db: assert db.get(AssetIconCache, asset.id) is None
