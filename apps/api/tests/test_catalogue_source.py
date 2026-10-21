"""Deterministic HTTP fixtures with REAL B1.2 crypto for pipeline acceptance."""
import asyncio
from copy import deepcopy
import hashlib
import json
from pathlib import Path
import time

import aiohttp
import pytest

from app.services import catalogue_source as source
from app.services.official_provenance import ProvenanceError

FIXTURES = Path(__file__).parent / "fixtures/official_catalogue"
RAW = (FIXTURES / "catalogue-000001.json").read_bytes()
BUNDLE = (FIXTURES / "catalogue.sigstore.json").read_bytes()
DIGEST = hashlib.sha256(RAW).hexdigest()


def release():
    value = {"id": source.CHANNEL_RELEASE_ID, "tag_name": source.CHANNEL_TAG,
        "url": f"{source.BASE}/releases/{source.CHANNEL_RELEASE_ID}",
        "html_url": f"https://github.com/{source.REPOSITORY}/releases/tag/catalogue-v1",
        "draft": False, "prerelease": False, "immutable": False, "updated_at": "2026-10-18T16:20:00Z",
        "assets": []}
    for name, identifier in [("catalogue.json", 653915685), ("catalogue-000001.json", 653915743)]:
        value["assets"].append({"id": identifier, "name": name, "size": len(RAW), "state": "uploaded",
            "url": f"{source.BASE}/releases/assets/{identifier}", "digest": "sha256:" + DIGEST,
            "browser_download_url": f"https://github.com/{source.REPOSITORY}/releases/download/catalogue-v1/{name}"})
    return value


class Content:
    def __init__(self, raw, exception=None):
        self.raw, self.exception = raw, exception

    async def iter_chunked(self, size):
        for i in range(0, len(self.raw), size):
            yield self.raw[i:i + size]
        if self.exception:
            raise self.exception


class Response:
    def __init__(self, raw=b"{}", status=200, headers=None, length=None, exception=None):
        self.status, self.headers = status, headers or {}
        self.content_length = length
        self.content = Content(raw, exception)

    async def __aenter__(self):
        return self

    async def __aexit__(self, *args):
        pass


class Session:
    def __init__(self, respond):
        self.respond, self.calls = respond, []

    def get(self, url, **kwargs):
        self.calls.append((url, kwargs))
        return self.respond(url)

    async def close(self):
        pass


def reader(respond):
    result = source.GithubReader()
    result.session = Session(respond)
    result.deadline = time.monotonic() + 90
    return result


def test_bounded_binary_redirect_and_exact_bytes():
    url = "https://release-assets.githubusercontent.com/asset?signature=private"
    r = reader(lambda u: Response(status=302, headers={"Location": url}) if u.startswith(source.API) else Response(RAW))
    assert asyncio.run(r.get(source.BASE + "/releases/assets/1", len(RAW), asset=True)) == RAW
    assert len(r.session.calls) == 2
    assert all(c[1]["allow_redirects"] is False for c in r.session.calls)


@pytest.mark.parametrize("url", ["http://api.github.com/x", "https://127.0.0.1/x", "https://[::1]/x",
    "https://169.254.169.254/x", "https://api.github.com.evil.test/x", "https://user:secret@api.github.com/x",
    "https://api.github.com:8443/x", "file:///tmp/x", "https://api.github.com/x#fragment", "https://api.github.com\\@evil.test/x"])
def test_destination_rejected(url):
    with pytest.raises(source.SourceError, match="invalid_source_destination"):
        source.checked_url(url)


@pytest.mark.parametrize("location", ["http://release-assets.githubusercontent.com/a", "https://localhost/a",
    "https://10.0.0.1/a", "https://169.254.169.254/a", "https://github.com/a", "/relative"])
def test_redirect_rejected(location):
    r = reader(lambda _: Response(status=302, headers={"Location": location}))
    with pytest.raises(source.SourceError):
        asyncio.run(r.get(source.BASE, 100, asset=True))


def test_metadata_redirect_and_second_distribution_redirect_rejected():
    r = reader(lambda _: Response(status=302, headers={"Location": "https://release-assets.githubusercontent.com/a"}))
    for asset in (False, True):
        with pytest.raises(source.SourceError, match="invalid_source_redirect"):
            asyncio.run(r.get(source.BASE, 100, asset=asset))


@pytest.mark.parametrize("response,code,calls", [
    (Response(status=403), "source_forbidden", 1), (Response(status=404), "source_not_found", 1),
    (Response(status=429, headers={"Retry-After": "120"}), "source_rate_limited", 1),
    (Response(status=403, headers={"X-RateLimit-Remaining": "0"}), "source_rate_limited", 1),
    (Response(status=500), "source_unavailable", 2), (Response(status=503, headers={"Retry-After": "180"}), "source_unavailable", 1),
    (Response(status=501), "unexpected_source_response", 1),
    (Response(status=206), "unexpected_source_response", 1),
    (Response(b"x" * 101), "source_response_too_large", 1),
    (Response(length=101), "source_response_too_large", 1),
    (Response(b"x", length=5), "truncated_source_response", 1),
    (Response(headers={"Content-Encoding": "gzip"}), "invalid_source_encoding", 1),
    (Response(exception=aiohttp.ClientPayloadError()), "truncated_source_response", 1),
    (Response(exception=asyncio.TimeoutError()), "source_timeout", 1),
    (Response(exception=aiohttp.ClientSSLError(None, OSError("certificate details"))), "source_tls_failed", 1),
])
def test_transport_failures(response, code, calls):
    r = reader(lambda _: response)
    with pytest.raises(source.SourceError, match=code):
        asyncio.run(r.get(source.BASE, 100))
    assert len(r.session.calls) == calls


def test_total_deadline_and_transient_recovery():
    r = reader(lambda _: Response())
    r.deadline = time.monotonic() - 1
    with pytest.raises(source.SourceError, match="source_timeout"):
        asyncio.run(r.get(source.BASE, 100))
    assert not r.session.calls
    responses = iter([Response(status=502), Response(b"ok")])
    r = reader(lambda _: next(responses))
    assert asyncio.run(r.get(source.BASE, 100)) == b"ok"


def test_retry_after_date_and_reset():
    assert source.retry_delay({"Retry-After": "bad"}) == 60
    assert source.retry_delay({"Retry-After": "9999999999999999999"}) == 86400
    assert source.retry_delay({"X-RateLimit-Reset": str(int(time.time()) + 300)}) >= 300
    from email.utils import format_datetime
    from datetime import timedelta
    assert source.retry_delay({"Retry-After": format_datetime(source.utcnow() + timedelta(seconds=180))}) >= 179


@pytest.mark.parametrize("ip", ["127.0.0.1", "10.2.0.1", "169.254.2.1", "::1", "fe80::1", "224.0.0.1", "ff02::1"])
def test_resolver_rejects_private_addresses(monkeypatch, ip):
    async def resolve(*args):
        return [{"host": ip}]
    monkeypatch.setattr(aiohttp.resolver.ThreadedResolver, "resolve", resolve)
    async def run():
        r = source.PublicResolver()
        try:
            await r.resolve("api.github.com")
        finally:
            await r.close()
    with pytest.raises(source.SourceError, match="invalid_source_destination"):
        asyncio.run(run())


@pytest.mark.parametrize("mutation,code", [
    (lambda d: d.update(id=7), "invalid_channel_identity"),
    (lambda d: d.update(tag_name="other"), "invalid_channel_identity"),
    (lambda d: d.update(draft=True), "invalid_channel_identity"),
    (lambda d: d.update(immutable="true"), "invalid_channel_identity"),
    (lambda d: d.update(url="https://elsewhere.test"), "invalid_channel_identity"),
    (lambda d: d.update(assets=[]), "missing_catalogue_asset"),
    (lambda d: d["assets"].append(d["assets"][0]), "ambiguous_catalogue_asset"),
    (lambda d: d["assets"][0].update(id=999), "invalid_asset_identity"),
    (lambda d: d["assets"][0].update(browser_download_url="https://elsewhere.test"), "invalid_asset_identity"),
])
def test_release_and_asset_policy(mutation, code):
    d = release()
    mutation(d)
    r = reader(lambda _: Response(json.dumps(d).encode()))
    async def run():
        return r.asset(await r.resolve_channel(), "catalogue.json")
    with pytest.raises(source.SourceError, match=code):
        asyncio.run(run())


@pytest.fixture
def http_fixture(monkeypatch):
    state = {"release": release(), "raw": RAW, "bundle": json.loads(BUNDLE), "requests": [], "mutation": False}
    def respond(url):
        state["requests"].append(url)
        if url == source.BASE:
            value = {"id": source.REPOSITORY_ID, "full_name": source.REPOSITORY, "owner": {"id": source.OWNER_ID}}
        elif "/releases/tags/" in url:
            value = deepcopy(state["release"])
            if state["mutation"] and state["requests"].count(url) > 1:
                value["updated_at"] = "2026-10-21T00:00:00Z"
        elif "/attestations/" in url:
            value = {"attestations": [{"repository_id": source.REPOSITORY_ID, "bundle": state["bundle"]}]}
        elif "/releases/assets/" in url:
            return Response(state["raw"])
        else:
            pytest.fail("Unexpected request; executable package retrieval is forbidden")
        return Response(json.dumps(value).encode())
    async def enter(self):
        self.session = Session(respond)
        self.deadline = time.monotonic() + 90
        return self
    monkeypatch.setattr(source.GithubReader, "__aenter__", enter)
    return state


def test_genuine_retrieval_authentication_and_explicit_publication_block(http_fixture):
    progress = {}
    candidate = asyncio.run(source.retrieve_candidate(progress))
    assert candidate.raw == RAW and candidate.provenance.artifact_sha256 == DIGEST
    assert candidate.provenance.profile == "official-catalogue"
    assert candidate.provenance.source_ref == "refs/heads/main"
    assert set(progress) == {"last_download_at", "last_authenticity_verified_at"}
    with pytest.raises(source.SourceError, match="publication_not_immutable"):
        source.require_publication(candidate)
    from dataclasses import replace
    with pytest.raises(source.SourceError, match="current_channel_policy_unavailable"):
        source.require_publication(replace(candidate, publication={**candidate.publication, "immutable": True}))
    assert all(".tar.gz" not in u and "/latest" not in u for u in http_fixture["requests"])


def test_channel_mutation_does_not_establish_currentness(http_fixture):
    http_fixture["mutation"] = True
    progress = {}
    with pytest.raises(source.SourceError, match="channel_changed"):
        asyncio.run(source.retrieve_candidate(progress))
    assert progress["last_authenticity_verified_at"]
    assert "last_confirmed_current_at" not in progress


def test_modified_bytes_fail_real_verifier_in_pipeline(http_fixture):
    http_fixture["raw"] = RAW + b"\n"
    for a in http_fixture["release"]["assets"]:
        a.update(size=len(RAW) + 1, digest="sha256:" + hashlib.sha256(RAW + b"\n").hexdigest())
    progress = {}
    with pytest.raises(ProvenanceError):
        asyncio.run(source.retrieve_candidate(progress))
    assert "last_download_at" in progress and "last_authenticity_verified_at" not in progress


def test_session_disables_ambient_authority(monkeypatch):
    seen = {}
    original = aiohttp.ClientSession
    def make(**kwargs):
        seen.update(kwargs)
        return original(**kwargs)
    monkeypatch.setenv("HTTPS_PROXY", "http://127.0.0.1:1")
    monkeypatch.setenv("GH_TOKEN", "not-a-token")
    monkeypatch.setattr(aiohttp, "ClientSession", make)
    async def run():
        async with source.GithubReader():
            pass
    asyncio.run(run())
    assert seen["trust_env"] is False and seen["auto_decompress"] is False
    assert isinstance(seen["cookie_jar"], aiohttp.DummyCookieJar)
    assert "Authorization" not in seen["headers"]
