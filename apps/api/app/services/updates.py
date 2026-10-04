"""Bounded public release reads. No deployment controls or persistent state."""
from __future__ import annotations

import asyncio
from datetime import datetime, timezone
import json
import time
from typing import Literal

import aiohttp
from pydantic import BaseModel

from app.release import RELEASE_API_URL, REPOSITORY_URL, build_metadata, release_order, validate_metadata

CACHE_SECONDS = 4 * 3600
FAILURE_CACHE_SECONDS = 300
REFRESH_SECONDS = 60
TIMEOUT_SECONDS = 5
MAX_RESPONSE_BYTES = 1024 * 1024
MAX_PAGES = 3


class UpdateStatus(BaseModel):
    current_version: str
    current_channel: Literal["beta", "stable"]
    build_id: str | None
    install_method: Literal["docker_compose", "systemd", "development"]
    status: Literal["up_to_date", "update_available", "ahead_of_release", "unavailable"]
    latest_version: str | None = None
    latest_channel: Literal["beta", "stable"] | None = None
    published_at: str | None = None
    release_url: str | None = None
    upgrade_guide_url: str | None = None
    checked_at: str
    cached: bool
    refresh_after_seconds: int


def normalize_release(record) -> dict | None:
    if not isinstance(record, dict) or record.get("draft") is not False or type(record.get("prerelease")) is not bool:
        return None
    if type(record.get("id")) is not int or record["id"] <= 0:
        return None
    tag = record.get("tag_name")
    if not isinstance(tag, str) or not tag.startswith("v"):
        return None
    channel = "beta" if record["prerelease"] else "stable"
    try:
        validate_metadata({"version": tag[1:], "release_channel": channel})
        published = record["published_at"]
        if not isinstance(published, str) or len(published) > 40:
            return None
        timestamp = datetime.fromisoformat(published.replace("Z", "+00:00"))
        if timestamp.tzinfo is None:
            return None
    except (ValueError, TypeError, KeyError):
        return None
    # Exact URL validation rejects credentials, ports, queries, fragments,
    # misleading hosts and encoded path escapes as well as other repositories.
    url = f"{REPOSITORY_URL}/releases/tag/{tag}"
    if record.get("html_url") != url:
        return None
    return {"latest_version": tag[1:], "latest_channel": channel,
            "published_at": timestamp.astimezone(timezone.utc).isoformat(), "release_url": url}


async def fetch_releases() -> list:
    remaining = MAX_RESPONSE_BYTES
    records = []
    # No token, cookies, environment proxies, response decompression or redirects.
    async with asyncio.timeout(TIMEOUT_SECONDS):
        async with aiohttp.ClientSession(trust_env=False, auto_decompress=False,
                cookie_jar=aiohttp.DummyCookieJar(),
                timeout=aiohttp.ClientTimeout(total=TIMEOUT_SECONDS),
                headers={"Accept": "application/vnd.github+json", "Accept-Encoding": "identity",
                         "X-GitHub-Api-Version": "2022-11-28", "User-Agent": "Atlas-Update-Awareness"}) as session:
            for page in range(1, MAX_PAGES + 1):
                async with session.get(RELEASE_API_URL, params={"per_page": "100", "page": str(page)}, allow_redirects=False) as response:
                    if response.status != 200 or response.content_type != "application/json":
                        raise ValueError("Unavailable release response")
                    if response.content_length is not None and response.content_length > remaining:
                        raise ValueError("Release response too large")
                    chunks = []
                    async for chunk in response.content.iter_chunked(16384):
                        remaining -= len(chunk)
                        if remaining < 0:
                            raise ValueError("Release response too large")
                        chunks.append(chunk)
                    payload = json.loads(b"".join(chunks))
                    if not isinstance(payload, list) or len(payload) > 100:
                        raise ValueError("Invalid release list")
                    records.extend(payload)
                    if len(payload) < 100:
                        return records
    raise ValueError("Release listing exceeds supported bound")


class UpdateChecker:
    def __init__(self, fetch=fetch_releases, clock=time.monotonic):
        self.fetch = fetch
        self.clock = clock
        self.lock = asyncio.Lock()
        self.records = None
        self.checked_at = None
        self.checked = float("-inf")
        self.expires = float("-inf")

    async def status(self, *, refresh=False, metadata=None) -> UpdateStatus:
        metadata = metadata or build_metadata()
        cached = True
        async with self.lock:
            now = self.clock()
            if now >= self.expires or (refresh and now - self.checked >= REFRESH_SECONDS):
                try:
                    payload = await self.fetch()
                    if not isinstance(payload, list):
                        raise ValueError("Invalid release list")
                    normalized = [release for record in payload if (release := normalize_release(record))]
                    self.records = normalized or None
                except (aiohttp.ClientError, OSError, TimeoutError, ValueError, UnicodeError, RecursionError):
                    self.records = None
                self.checked = self.clock()
                self.checked_at = datetime.now(timezone.utc).isoformat()
                self.expires = self.checked + (CACHE_SECONDS if self.records else FAILURE_CACHE_SECONDS)
                cached = False
            result = dict(current_version=metadata["version"], current_channel=metadata["release_channel"],
                          build_id=metadata["build_id"], install_method=metadata["install_method"],
                          checked_at=self.checked_at, cached=cached,
                          refresh_after_seconds=max(0, int(REFRESH_SECONDS - (self.clock() - self.checked) + 0.999)))
            supported = [record for record in self.records or []
                         if metadata["release_channel"] == "beta" or record["latest_channel"] == "stable"]
            if not supported:
                return UpdateStatus(**result, status="unavailable")
            latest = max(supported, key=lambda record: (*release_order(record["latest_version"], record["latest_channel"]),
                                                      record["published_at"], record["release_url"]))
            remote = release_order(latest["latest_version"], latest["latest_channel"])
            current = release_order(metadata["version"], metadata["release_channel"])
            status = "update_available" if remote > current else "ahead_of_release" if remote < current else "up_to_date"
            anchor = {"docker_compose": "docker-compose-upgrade", "systemd": "nativesystemd-upgrade"}.get(metadata["install_method"])
            guide = f"{REPOSITORY_URL}/blob/v{latest['latest_version']}/docs/deployment/upgrades.md#{anchor}" if anchor else None
            return UpdateStatus(**result, **latest, status=status, upgrade_guide_url=guide)


checker = UpdateChecker()
