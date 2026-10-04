import asyncio
import json
from unittest.mock import AsyncMock

import aiohttp
from fastapi.testclient import TestClient
import pytest

from app.release import REPOSITORY_URL, Version, validate_metadata, validate_tag
from app.services import updates


def release(version="0.1.0", channel="beta", **changes):
    return {"id": 1, "tag_name": "v" + version, "draft": False,
            "prerelease": channel == "beta", "published_at": "2026-10-04T00:00:00Z",
            "html_url": f"{REPOSITORY_URL}/releases/tag/v{version}", **changes}


def metadata(version="0.1.0", channel="beta", method="development"):
    return {"version": version, "release_channel": channel, "build_id": "test-build", "install_method": method}


@pytest.mark.parametrize("version", ["0.1.0", "1.2.3", "1.10.0", "1.0.0-beta.0", "1.0.0-beta.10+build.2"])
def test_valid_metadata(version):
    assert validate_metadata({"version": version, "release_channel": "beta"})["version"] == version


@pytest.mark.parametrize("version", [None, True, 1, "01.0.0", "1.0", "v1.0.0", "1.0.0-beta.01", "1.0.0;id", "1.0.0\n", "1.0.0-rc.1", "1.0.0-alpha", "1.0.0/../../"])
def test_invalid_metadata(version):
    with pytest.raises(ValueError):
        validate_metadata({"version": version, "release_channel": "beta"})


@pytest.mark.parametrize("channel", [None, "nightly", "BETA", True, [], {}])
def test_invalid_channel(channel):
    with pytest.raises(ValueError):
        validate_metadata({"version": "0.1.0", "release_channel": channel})


def test_tag_and_stable_policy():
    validate_tag(metadata(), "v0.1.0")
    for tag in ("v0.2.0", "v0.1.0; echo unsafe"):
        with pytest.raises(ValueError): validate_tag(metadata(), tag)
    with pytest.raises(ValueError): validate_metadata(metadata("1.0.0-beta.1", "stable"))


def test_semver_precedence_and_build_identifiers():
    versions = ["1.0.0-alpha", "1.0.0-alpha.1", "1.0.0-alpha.beta", "1.0.0-beta", "1.0.0-beta.2", "1.0.0-beta.11", "1.0.0-rc.1", "1.0.0", "1.0.1", "1.9.0", "1.10.0", "2.0.0"]
    assert all(Version(left) < Version(right) for left, right in zip(versions, versions[1:]))
    assert Version("1.0.0+a") == Version("1.0.0+b")


@pytest.mark.parametrize("current,channel,remote,expected,latest", [
    ("0.1.0", "beta", [release()], "up_to_date", "0.1.0"),
    ("0.1.0", "stable", [release(channel="stable")], "up_to_date", "0.1.0"),
    ("0.1.0", "beta", [release("0.2.0")], "update_available", "0.2.0"),
    ("0.3.0", "beta", [release("0.2.0")], "ahead_of_release", "0.2.0"),
    ("0.1.0", "stable", [release("9.0.0"), release(channel="stable")], "up_to_date", "0.1.0"),
    ("0.1.0", "beta", [release(channel="stable")], "update_available", "0.1.0"),
    ("0.1.0", "stable", [release("0.0.9-beta.9"), release(channel="stable")], "up_to_date", "0.1.0"),
    ("0.1.0", "beta", [release("0.2.0-beta.2"), release("0.2.0-beta.10")], "update_available", "0.2.0-beta.10"),
    ("0.2.0-beta.10", "beta", [release("0.2.0", "stable"), release("0.2.0-beta.11")], "update_available", "0.2.0"),
    ("0.1.0", "beta", [release("9.0.0", draft=True), release()], "up_to_date", "0.1.0"),
    ("0.1.0", "beta", [release("wrong"), release()], "up_to_date", "0.1.0"),
    ("0.1.0", "stable", [release("9.0.0")], "unavailable", None),
    ("0.1.0", "beta", [], "unavailable", None),
])
def test_selection(current, channel, remote, expected, latest):
    checker = updates.UpdateChecker(AsyncMock(return_value=remote))
    result = asyncio.run(checker.status(metadata=metadata(current, channel)))
    assert result.status == expected
    assert result.latest_version == latest
    assert result.cached is False
    assert "body" not in result.model_dump()


@pytest.mark.parametrize("changes", [
    {"draft": True}, {"draft": None}, {"prerelease": 1}, {"id": True}, {"id": -1},
    {"tag_name": "v1.0.0-rc.1"}, {"published_at": "wrong"}, {"published_at": "2026-10-04"},
    {"html_url": "http://github.com/benchristian88/atlas/releases/tag/v0.1.0"},
    {"html_url": "https://github.com.evil.test/benchristian88/atlas/releases/tag/v0.1.0"},
    {"html_url": "javascript:alert(1)"}, {"html_url": "https://user@github.com/benchristian88/atlas/releases/tag/v0.1.0"},
    {"html_url": f"{REPOSITORY_URL}/releases/tag/v0.1.0?redirect=unsafe"},
    {"html_url": "https://github.com/another/repo/releases/tag/v0.1.0"},
])
def test_malformed_or_unsafe_records_ignored(changes):
    assert updates.normalize_release(release(**changes)) is None


@pytest.mark.parametrize("failure", [TimeoutError(), OSError("DNS unavailable"), aiohttp.ClientError("TLS"), ValueError("invalid JSON")])
def test_unavailable_without_raw_errors(failure):
    checker = updates.UpdateChecker(AsyncMock(side_effect=failure))
    result = asyncio.run(checker.status(metadata=metadata()))
    assert result.status == "unavailable"
    assert result.release_url is None
    assert "DNS" not in result.model_dump_json()


def test_cache_expiry_refresh_limits_and_concurrent_calls():
    async def exercise():
        now = [0]
        fetch = AsyncMock(return_value=[release()])
        checker = updates.UpdateChecker(fetch, clock=lambda: now[0])
        results = await asyncio.gather(*(checker.status(metadata=metadata()) for _ in range(8)))
        assert fetch.await_count == 1
        assert sum(not result.cached for result in results) == 1
        assert (await checker.status(metadata=metadata(), refresh=True)).cached
        now[0] = 60
        assert not (await checker.status(metadata=metadata(), refresh=True)).cached
        now[0] += updates.CACHE_SECONDS - 1
        assert (await checker.status(metadata=metadata())).cached
        now[0] += 1
        await checker.status(metadata=metadata())
        assert fetch.await_count == 3
        fetch.side_effect = OSError()
        now[0] += 60
        await checker.status(metadata=metadata(), refresh=True)
        now[0] += updates.FAILURE_CACHE_SECONDS - 1
        assert (await checker.status(metadata=metadata())).cached
        now[0] += 1
        assert not (await checker.status(metadata=metadata())).cached
    asyncio.run(exercise())


@pytest.mark.parametrize("method,anchor", [("docker_compose", "docker-compose-upgrade"), ("systemd", "nativesystemd-upgrade"), ("development", None)])
def test_guidance_is_method_specific(method, anchor):
    checker = updates.UpdateChecker(AsyncMock(return_value=[release("0.2.0")]))
    result = asyncio.run(checker.status(metadata=metadata(method=method)))
    assert result.upgrade_guide_url == (f"{REPOSITORY_URL}/blob/v0.2.0/docs/deployment/h4-upgrades.md#{anchor}" if anchor else None)


class Stream:
    def __init__(self, body): self.body = body
    async def iter_chunked(self, size):
        for position in range(0, len(self.body), size):
            yield self.body[position:position + size]


class Response:
    def __init__(self, body, status=200, content_type="application/json", content_length=None):
        self.status, self.content_type, self.content_length = status, content_type, content_length
        self.content = Stream(body)
    async def __aenter__(self): return self
    async def __aexit__(self, *args): pass


def mock_transport(monkeypatch, responses):
    calls = []
    class Session:
        def __init__(self, **kwargs):
            assert kwargs["trust_env"] is False and kwargs["auto_decompress"] is False
            assert kwargs["timeout"].total == 5
            assert not any(key in kwargs["headers"] for key in ("Authorization", "Cookie"))
        async def __aenter__(self): return self
        async def __aexit__(self, *args): pass
        def get(self, url, **kwargs):
            assert url == updates.RELEASE_API_URL and kwargs["allow_redirects"] is False
            calls.append(kwargs)
            return responses[len(calls) - 1]
    monkeypatch.setattr(updates.aiohttp, "ClientSession", Session)
    return calls


@pytest.mark.parametrize("response", [
    Response(b"[]", status=403), Response(b"[]", status=302), Response(b"[]", content_type="text/html"),
    Response(b"not-json"), Response(b"{}"), Response(b"[]", content_length=updates.MAX_RESPONSE_BYTES + 1),
    Response(b" " * (updates.MAX_RESPONSE_BYTES + 1)), Response(json.dumps([release()] * 101).encode()),
])
def test_transport_hardening(monkeypatch, response):
    mock_transport(monkeypatch, [response])
    checker = updates.UpdateChecker(updates.fetch_releases)
    assert asyncio.run(checker.status(metadata=metadata())).status == "unavailable"


def test_pagination_bounded(monkeypatch):
    first = Response(json.dumps([release()] * 100).encode())
    calls = mock_transport(monkeypatch, [first, Response(json.dumps([release("0.2.0")]).encode())])
    assert len(asyncio.run(updates.fetch_releases())) == 101
    assert [call["params"]["page"] for call in calls] == ["1", "2"]
    mock_transport(monkeypatch, [first, first, first])
    with pytest.raises(ValueError, match="bound"): asyncio.run(updates.fetch_releases())


def test_total_transport_timeout(monkeypatch):
    class SlowSession:
        def __init__(self, **kwargs): pass
        async def __aenter__(self):
            await asyncio.sleep(1)
        async def __aexit__(self, *args): pass
    monkeypatch.setattr(updates.aiohttp, "ClientSession", SlowSession)
    monkeypatch.setattr(updates, "TIMEOUT_SECONDS", 0.01)
    checker = updates.UpdateChecker(updates.fetch_releases)
    assert asyncio.run(checker.status(metadata=metadata())).status == "unavailable"


def test_deeply_nested_json_fails_safely(monkeypatch):
    mock_transport(monkeypatch, [Response(b"[" * 2000 + b"]" * 2000)])
    checker = updates.UpdateChecker(updates.fetch_releases)
    assert asyncio.run(checker.status(metadata=metadata())).status == "unavailable"


def test_update_endpoints_enforce_global_settings_authorization(monkeypatch):
    from app.authorization import Principal, ScopeGrant, get_principal
    from app.main import app
    from tests.test_administration import make_principal
    principal = make_principal("system_settings.manage")
    checker = updates.UpdateChecker(AsyncMock(return_value=[release()]))
    monkeypatch.setattr("app.routes.system_settings.checker", checker)
    app.dependency_overrides[get_principal] = lambda: principal
    try:
        with TestClient(app) as client:
            for path, method in [("/api/system-settings/updates", "get"), ("/api/system-settings/updates/check", "post")]:
                assert getattr(client, method)(path).status_code == 200
            no_access = make_principal()
            app.dependency_overrides[get_principal] = lambda: no_access
            assert client.get("/api/system-settings/updates").status_code == 403
            grant = principal.grants[0]
            scoped = Principal(principal.user, (ScopeGrant(grant.assignment_id, grant.role_id, grant.role_name, "customer", principal.user.id, None, grant.permissions),))
            app.dependency_overrides[get_principal] = lambda: scoped
            for method, path in [("get", "/api/system-settings/updates"), ("post", "/api/system-settings/updates/check")]:
                assert getattr(client, method)(path).status_code == 403
            app.dependency_overrides.pop(get_principal)
            assert client.get("/api/system-settings/updates").status_code == 401
    finally:
        app.dependency_overrides.pop(get_principal, None)


def test_no_startup_dependency_or_remote_execution():
    from pathlib import Path
    root = Path(__file__).resolve().parents[3]
    for name in ("apps/api/app/main.py", "apps/api/scripts/start.py"):
        assert "fetch_releases" not in (root / name).read_text()
    source = (root / "apps/api/app/services/updates.py").read_text()
    assert not any(word in source for word in ("subprocess", "os.system", "eval(", "exec(", "shell=True"))
