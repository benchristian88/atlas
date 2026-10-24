"""Bounded public GitHub retrieval. Build provenance is NOT publication approval."""
from __future__ import annotations

import asyncio
from dataclasses import dataclass
from datetime import datetime, timezone
from email.utils import parsedate_to_datetime
import hashlib
import ipaddress
import json
import re
import time
from urllib.parse import urlsplit

import aiohttp

from app.services.connector_contracts import ConnectorPackageError
from app.services.connector_verification import GithubSigstoreVerifier
from app.services.official_catalogue import MAX_CATALOGUE_BYTES, parse_official_catalogue
from app.services.official_provenance import MAX_BUNDLE_BYTES, TIMEOUT_SECONDS, ProvenanceError, VerifiedProvenance

REPOSITORY = "benchristian88/atlas-connectors"
REPOSITORY_ID = 1414494920
OWNER_ID = 93822871
API = "https://api.github.com"
BASE = f"{API}/repos/{REPOSITORY}"
SOURCE = "github-official-catalogue-v1"
CHANNEL_TAG = "catalogue-v1"
CHANNEL_RELEASE_ID = 416561696
BOOTSTRAP_SEQUENCE = 1
BOOTSTRAP_DIGEST = "55533ca67e7e9a14f82961e0a8c34ad78e2596049b3db02fde787494e3975afd"
POLICY = "atlas-catalogue-channel-v1-blocked"
METADATA_LIMIT = 256 * 1024
EVIDENCE_LIMIT = MAX_BUNDLE_BYTES  # total response, not per unbounded result
REFRESH_SECONDS = 90


class SourceError(ConnectorPackageError):
    def __init__(self, code: str, *, retry_after: int = 60):
        super().__init__(code)
        self.retry_after = retry_after


def utcnow():
    return datetime.now(timezone.utc)


def require(condition, code):
    if not condition:
        raise SourceError(code)


def decode(raw):
    def pairs(items):
        result = {}
        for key, value in items:
            if key in result:
                raise ValueError()
            result[key] = value
        return result
    def constant(_):
        raise ValueError()
    try:
        return json.loads(raw, object_pairs_hook=pairs, parse_constant=constant)
    except (ValueError, UnicodeError, RecursionError):
        raise SourceError("invalid_source_metadata") from None


def checked_url(url: str, *, distribution: bool = False):
    try:
        parsed = urlsplit(url)
        origins = {"release-assets.githubusercontent.com"} if distribution else {"api.github.com"}
        require(parsed.scheme == "https" and parsed.hostname in origins
                and parsed.username is None and parsed.password is None
                and parsed.port in (None, 443) and not parsed.fragment
                and not any(c.isspace() or ord(c) < 32 for c in url)
                and "\\" not in url, "invalid_source_destination")
    except ValueError:
        raise SourceError("invalid_source_destination") from None


class PublicResolver(aiohttp.resolver.ThreadedResolver):
    async def resolve(self, host, port=0, family=0):
        records = await super().resolve(host, port, family)
        addresses = [ipaddress.ip_address(r["host"]) for r in records]
        require(bool(addresses) and all(a.is_global and not a.is_multicast and not a.is_reserved for a in addresses),
                "invalid_source_destination")
        return records


def retry_delay(headers) -> int:
    """Honor Retry-After/reset without sleeping in a request for a long period."""
    delay = 60
    value = headers.get("Retry-After")
    if value:
        try:
            delay = max(delay, int(value))
        except ValueError:
            try:
                delay = max(delay, int((parsedate_to_datetime(value) - utcnow()).total_seconds()) + 1)
            except (ValueError, TypeError, OverflowError):
                pass
    try:
        delay = max(delay, int(headers.get("X-RateLimit-Reset", "0")) - int(time.time()) + 1)
    except ValueError:
        pass
    # GitHub headers are untrusted. A pathological value fails closed for a
    # bounded day, rather than overflowing DB timestamps or sleeping forever.
    return min(delay, 86400)


class GithubReader:
    """One operation-local session, no ambient auth, cookies, proxy or decompression."""
    async def __aenter__(self):
        self.deadline = time.monotonic() + REFRESH_SECONDS
        self.session = aiohttp.ClientSession(
            connector=aiohttp.TCPConnector(resolver=PublicResolver(), limit=2),
            trust_env=False, cookie_jar=aiohttp.DummyCookieJar(), auto_decompress=False,
            timeout=aiohttp.ClientTimeout(total=15, connect=5, sock_connect=5, sock_read=5),
            headers={"User-Agent": "Atlas-Official-Catalogue", "Accept-Encoding": "identity",
                     "X-GitHub-Api-Version": "2022-11-28", "Cache-Control": "no-cache"})
        return self

    async def __aexit__(self, *args):
        await self.session.close()

    async def get(self, url, maximum, *, asset=False, reject_pagination=False):
        checked_url(url)
        for attempt in range(2):
            try:
                remaining = self.deadline - time.monotonic()
                require(remaining > 0, "source_timeout")
                async with asyncio.timeout(remaining):
                    return await self._get(url, maximum, asset=asset, reject_pagination=reject_pagination)
            except SourceError as error:
                if error.code != "source_unavailable" or error.retry_after > 0 or attempt:
                    raise
            except (asyncio.TimeoutError, aiohttp.ServerTimeoutError):
                raise SourceError("source_timeout") from None
            except aiohttp.ClientPayloadError:
                raise SourceError("truncated_source_response") from None
            except (aiohttp.ClientSSLError, aiohttp.ClientConnectorCertificateError):
                raise SourceError("source_tls_failed") from None
            except (aiohttp.ClientConnectionError, OSError):
                if attempt:
                    raise SourceError("source_unavailable") from None
            except aiohttp.ClientError:
                raise SourceError("unexpected_source_response") from None
            await asyncio.sleep(0.25)
        raise SourceError("source_unavailable")

    async def _get(self, url, maximum, *, asset, reject_pagination=False):
        # API metadata never redirects. Binary asset API permits exactly one
        # redirect to the fixed public distribution origin, checked by DNS too.
        for hop in range(2):
            async with self.session.get(url, allow_redirects=False,
                    headers={"Accept": "application/octet-stream" if asset else "application/vnd.github+json"}) as response:
                if response.status in (301, 302, 303, 307, 308):
                    require(asset and hop == 0 and response.status == 302, "invalid_source_redirect")
                    url = response.headers.get("Location", "")
                    checked_url(url, distribution=True)
                    continue
                if response.status in (403, 429):
                    limited = response.status == 429 or response.headers.get("X-RateLimit-Remaining") == "0" or "Retry-After" in response.headers
                    raise SourceError("source_rate_limited" if limited else "source_forbidden",
                                      retry_after=retry_delay(response.headers))
                if response.status == 404:
                    raise SourceError("source_not_found")
                if response.status in (500, 502, 503, 504):
                    delay = retry_delay(response.headers) if any(
                        key in response.headers for key in ("Retry-After", "X-RateLimit-Reset")) else 0
                    raise SourceError("source_unavailable", retry_after=delay)
                require(response.status == 200, "unexpected_source_response")
                require(not reject_pagination or not response.headers.get("Link"), "incomplete_source_pagination")
                require(response.headers.get("Content-Encoding", "identity").lower() == "identity",
                        "invalid_source_encoding")
                require(response.content_length is None or response.content_length <= maximum, "source_response_too_large")
                result = bytearray()
                async for chunk in response.content.iter_chunked(16384):
                    require(len(result) + len(chunk) <= maximum, "source_response_too_large")
                    result.extend(chunk)
                require(response.content_length is None or len(result) == response.content_length, "truncated_source_response")
                return bytes(result)
        raise SourceError("invalid_source_redirect")

    async def publication_metadata(self, path: str):
        """Phase 2A public observations only; never follow provider-supplied URLs.

        Fixed repository endpoints plus validated account/App routing. Lists use
        an overflow slot and reject pagination, including unsolicited Link headers.
        The ordinary B1.3 retrieval/publication policy is unchanged.
        """
        number = r"[1-9][0-9]{0,15}"
        repository_path = (r"(?:/branches/main|/environments/catalogue-publication"
            r"|/actions/runs/" + number + r"(?:/attempts/1)?"
            r"|/actions/workflows/" + number
            + r"|/commits/[a-f0-9]{40}/check-runs\?check_name=validate&filter=latest&per_page=2&page=1"
            r"|/rulesets\?includes_parents=true&per_page=6&page=1"
            r"|/rulesets/" + number + r"\?includes_parents=true)?")
        require(type(path) is str, "invalid_source_destination")
        if re.fullmatch(repository_path, path):
            identifier = re.search(r"/(?:runs|workflows|rulesets)/([0-9]+)", path)
            require(identifier is None or int(identifier[1]) <= 2**53 - 1, "invalid_source_destination")
            url = BASE + path
        else:
            require((re.fullmatch(r"/users/[A-Za-z0-9]+(?:-[A-Za-z0-9]+)*", path) is not None
                     and len(path.removeprefix("/users/")) <= 39)
                    or re.fullmatch(r"/apps/[a-z0-9][a-z0-9-]{0,99}", path) is not None,
                    "invalid_source_destination")
            url = API + path
        raw = await self.get(url, METADATA_LIMIT, reject_pagination=True)
        try:
            return decode(raw.decode("utf-8"))
        except UnicodeError:
            raise SourceError("invalid_source_metadata") from None

    async def repository(self):
        value = decode(await self.get(BASE, METADATA_LIMIT))
        require(isinstance(value, dict) and value.get("id") == REPOSITORY_ID
                and value.get("full_name") == REPOSITORY
                and isinstance(value.get("owner"), dict) and value["owner"].get("id") == OWNER_ID,
                "invalid_source_repository")

    async def resolve_channel(self):
        value = decode(await self.get(f"{BASE}/releases/tags/{CHANNEL_TAG}", METADATA_LIMIT))
        require(isinstance(value, dict) and value.get("id") == CHANNEL_RELEASE_ID
                and value.get("tag_name") == CHANNEL_TAG and value.get("draft") is False
                and value.get("prerelease") is False and type(value.get("immutable")) is bool
                and value.get("url") == f"{BASE}/releases/{CHANNEL_RELEASE_ID}"
                and value.get("html_url") == f"https://github.com/{REPOSITORY}/releases/tag/{CHANNEL_TAG}"
                and isinstance(value.get("assets"), list) and len(value["assets"]) <= 100,
                "invalid_channel_identity")
        return value

    def asset(self, release, name):
        matches = [a for a in release["assets"] if isinstance(a, dict) and a.get("name") == name]
        require(len(matches) == 1, "missing_catalogue_asset" if not matches else "ambiguous_catalogue_asset")
        asset = matches[0]
        identifier = asset.get("id")
        require(type(identifier) is int and 0 < identifier <= 2**53 - 1
                and asset.get("state") == "uploaded"
                and type(asset.get("size")) is int and 0 < asset["size"] <= MAX_CATALOGUE_BYTES
                and asset.get("url") == f"{BASE}/releases/assets/{identifier}"
                and asset.get("browser_download_url") == f"https://github.com/{REPOSITORY}/releases/download/{CHANNEL_TAG}/{name}",
                "invalid_asset_identity")
        return asset

    async def download(self, asset):
        raw = await self.get(f"{BASE}/releases/assets/{asset['id']}", MAX_CATALOGUE_BYTES, asset=True)
        require(len(raw) == asset["size"], "truncated_source_response")
        require(asset.get("digest") == "sha256:" + hashlib.sha256(raw).hexdigest(), "asset_digest_mismatch")
        return raw

    async def attestations(self, digest):
        value = decode(await self.get(f"{BASE}/attestations/sha256:{digest}?per_page=4", EVIDENCE_LIMIT))
        require(isinstance(value, dict) and isinstance(value.get("attestations"), list)
                and 0 < len(value["attestations"]) <= 3, "missing_or_excessive_attestations")
        result = []
        for item in value["attestations"]:
            require(isinstance(item, dict) and item.get("repository_id") == REPOSITORY_ID
                    and isinstance(item.get("bundle"), dict), "invalid_attestation_response")
            bundle = json.dumps(item["bundle"], separators=(",", ":")).encode()
            require(len(bundle) <= MAX_BUNDLE_BYTES, "oversized_attestation_bundle")
            result.append(bundle)
        # Never follow untrusted bundle_url or pagination links.
        return result

    async def confirm_channel(self, before, current, snapshot):
        await self.repository()
        after = await self.resolve_channel()
        # download_count is mutable even during a successful read; do not bind it.
        keys = ("id", "name", "size", "digest", "updated_at", "url", "state", "browser_download_url")
        identity = lambda a: tuple(a.get(k) for k in keys)
        require(all(before.get(k) == after.get(k) for k in ("id", "tag_name", "immutable", "updated_at", "published_at", "target_commitish"))
                and identity(current) == identity(self.asset(after, current["name"]))
                and identity(snapshot) == identity(self.asset(after, snapshot["name"])), "channel_changed")
        return utcnow()


@dataclass(frozen=True)
class AuthenticatedCandidate:
    raw: bytes
    provenance: VerifiedProvenance
    publication: dict
    confirmed_at: datetime


async def retrieve_candidate(progress: dict) -> AuthenticatedCandidate:
    async with GithubReader() as reader:
        await reader.repository()
        release = await reader.resolve_channel()
        current = reader.asset(release, "catalogue.json")
        raw = await reader.download(current)
        progress["last_download_at"] = utcnow()
        document = parse_official_catalogue(raw).document
        digest = hashlib.sha256(raw).hexdigest()
        bundles = await reader.attestations(digest)
        verifier = GithubSigstoreVerifier()
        evidence = None
        for index, bundle in enumerate(bundles):
            # Reserve the verifier's complete subprocess budget before starting
            # synchronous crypto; do not rely on asyncio cancelling that work.
            require(reader.deadline - time.monotonic() > TIMEOUT_SECONDS + 2, "source_timeout")
            try:
                evidence = verifier.verify_catalogue(raw, bundle, subject_name="catalogue.json")
                break
            except ProvenanceError:
                if index == len(bundles) - 1:
                    raise
        progress["last_authenticity_verified_at"] = evidence.verified_at
        snapshot = reader.asset(release, f"catalogue-{document['sequence']:06d}.json")
        require(await reader.download(snapshot) == raw, "historical_snapshot_mismatch")
        confirmed = await reader.confirm_channel(release, current, snapshot)
        require(time.monotonic() < reader.deadline, "source_timeout")
        return AuthenticatedCandidate(raw, evidence, {
            "policy": POLICY, "release_id": release["id"], "asset_id": current["id"],
            "snapshot_asset_id": snapshot["id"], "immutable": release["immutable"],
            "channel_tag": CHANNEL_TAG,
        }, confirmed)


def require_publication(candidate: AuthenticatedCandidate):
    """No override flag: this channel has no approved advancing pointer contract.

    Even immutable=true would freeze the alias. A reviewed publication adapter,
    independent approval evidence and policy revision must precede promotion.
    """
    require(candidate.publication.get("immutable") is True, "publication_not_immutable")
    raise SourceError("current_channel_policy_unavailable")
