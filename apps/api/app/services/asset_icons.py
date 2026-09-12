"""Bounded, source-keyed icon cache. Only this module retrieves remote icons."""
from __future__ import annotations

import asyncio
import hashlib
import ipaddress
import io
import logging
import socket
import threading
import uuid
from datetime import datetime, timedelta, timezone
from urllib.parse import urljoin

import aiohttp
from PIL import Image, UnidentifiedImageError
from sqlalchemy import delete, or_, select, update
from sqlalchemy.dialects.postgresql import insert
from yarl import URL

from app.database import SessionLocal
from app.models import Asset, AssetIconCache

MAX_DOWNLOAD = 2 * 1024 * 1024
MAX_CACHE = 512 * 1024
MAX_DIMENSION = 2048
MAX_PIXELS = 4_000_000
MAX_REDIRECTS = 3
RETRY_DELAY = timedelta(minutes=5)
FETCH_SLOTS = threading.BoundedSemaphore(4)
logger = logging.getLogger(__name__)


class IconRejected(ValueError):
    """Messages are fixed reason codes, never URLs or response contents."""


def digest(value: bytes | str) -> str:
    return hashlib.sha256(value.encode() if isinstance(value, str) else value).hexdigest()


def icon_fields(asset, asset_type=None) -> dict:
    # No cache queries/remote work in list or graph serialization. The endpoint
    # rechecks current knowledge, visibility and cache integrity on every request.
    local = f"/api/assets/{asset.id}/icon?v={digest(asset.icon_url)}" if asset.icon_url else None
    default = asset_type.default_icon_url if asset_type else None
    return {"cached_icon_url": local, "default_icon_url": default, "resolved_icon_url": local or default}


def public_ip(value: str) -> None:
    address = ipaddress.ip_address(value)
    # Exclude transition/translation ranges too: a public IPv6 address must not
    # tunnel a connection to a special-use IPv4 destination.
    blocked_v6 = ("64:ff9b::/96", "64:ff9b:1::/48", "2001::/23", "2002::/16", "3fff::/20")
    blocked_v4 = ("192.0.0.0/24", "192.88.99.0/24")
    if (not address.is_global or address.is_multicast or address.is_reserved
            or (address.version == 4 and any(address in ipaddress.ip_network(net) for net in blocked_v4))
            or (address.version == 6 and (address.ipv4_mapped is not None
                or any(address in ipaddress.ip_network(net) for net in blocked_v6)))):
        raise IconRejected("blocked_destination")


def validate_url(value: str) -> URL:
    try:
        if len(value) > 2048 or any(ord(char) < 33 for char in value) or "\\" in value:
            raise IconRejected("invalid_url")
        url = URL(value)
        host = url.host
        if url.scheme != "https" or not host or url.user is not None or url.password is not None or url.port != 443:
            raise IconRejected("https_required")
        if "%" in host or host.rstrip(".").lower() == "localhost" or host.rstrip(".").lower().endswith(".localhost"):
            raise IconRejected("blocked_destination")
        try:
            ipaddress.ip_address(host)
        except ValueError:
            pass  # All DNS answers are checked by PublicResolver before connecting.
        else:
            public_ip(host)
        return url.with_fragment(None)
    except (ValueError, UnicodeError) as exc:
        if isinstance(exc, IconRejected):
            raise
        raise IconRejected("invalid_url") from None


class PublicResolver(aiohttp.ThreadedResolver):
    async def resolve(self, host, port=0, family=socket.AF_INET):
        answers = await super().resolve(host, port, family)
        if not answers:
            raise IconRejected("dns_empty")
        for answer in answers:
            public_ip(answer["host"])
        return answers


class PublicConnector(aiohttp.TCPConnector):
    async def _wrap_create_connection(self, *args, **kwargs):
        # aiohttp connects to the resolver's numeric addresses (no second lookup).
        # Verify the actual TLS peer before handing the transport to HTTP code.
        transport, protocol = await super()._wrap_create_connection(*args, **kwargs)
        try:
            peer = transport.get_extra_info("peername")
            if not peer:
                raise IconRejected("missing_peer")
            public_ip(peer[0])
        except Exception:
            transport.close()
            raise
        return transport, protocol


def normalize_image(data: bytes) -> bytes:
    if len(data) > MAX_DOWNLOAD:
        raise IconRejected("download_too_large")
    try:
        with Image.open(io.BytesIO(data), formats=("PNG", "JPEG", "WEBP")) as original:
            width, height = original.size
            if max(width, height) > MAX_DIMENSION or width * height > MAX_PIXELS:
                raise IconRejected("dimensions_too_large")
            original.load()  # Reject truncated/corrupt content; only first frame.
            image = original.convert("RGBA")
            image.thumbnail((256, 256))
            # Copy pixels to strip EXIF, ICC, text, animation and other metadata.
            clean = Image.new("RGBA", image.size)
            clean.paste(image)
            output = io.BytesIO()
            clean.save(output, format="PNG")
            result = output.getvalue()
            if len(result) > MAX_CACHE:
                raise IconRejected("cache_too_large")
            return result
    except (UnidentifiedImageError, OSError, SyntaxError, Image.DecompressionBombError):
        raise IconRejected("invalid_image") from None


async def fetch_icon(source: str) -> bytes:
    # Total budget covers DNS, all redirects and slow streaming responses.
    async with asyncio.timeout(10):
        connector = PublicConnector(resolver=PublicResolver(), use_dns_cache=False, limit=1, force_close=True)
        async with aiohttp.ClientSession(
            connector=connector, trust_env=False, cookie_jar=aiohttp.DummyCookieJar(),
            auto_decompress=False,
            timeout=aiohttp.ClientTimeout(total=8, connect=2, sock_connect=2, sock_read=2),
            headers={"User-Agent": "Atlas-Icon-Cache/1", "Accept": "image/png,image/jpeg,image/webp", "Accept-Encoding": "identity"},
        ) as client:
            url = validate_url(source)
            for redirects in range(MAX_REDIRECTS + 1):
                async with client.get(url, allow_redirects=False) as response:
                    if response.status in (301, 302, 303, 307, 308):
                        if redirects == MAX_REDIRECTS:
                            raise IconRejected("redirect_limit")
                        location = response.headers.get("Location")
                        if not location:
                            raise IconRejected("invalid_redirect")
                        url = validate_url(urljoin(str(url), location))
                        continue
                    if response.status != 200:
                        raise IconRejected("http_status")
                    if response.headers.get("Content-Encoding", "identity").lower() != "identity":
                        raise IconRejected("encoded_content")
                    if response.content_length is not None and response.content_length > MAX_DOWNLOAD:
                        raise IconRejected("download_too_large")
                    data = bytearray()
                    async for chunk in response.content.iter_chunked(16384):
                        if len(data) + len(chunk) > MAX_DOWNLOAD:
                            raise IconRejected("download_too_large")
                        data.extend(chunk)
                    return normalize_image(bytes(data))
    raise IconRejected("invalid_response")


def current_bytes(cache, source: str) -> bytes | None:
    if (cache and cache.source_hash == digest(source) and cache.data
            and len(cache.data) <= MAX_CACHE and digest(cache.data) == cache.content_hash):
        return cache.data
    return None


def claim_attempt(db, asset_id, source: str):
    now = datetime.now(timezone.utc)
    token = uuid.uuid4()
    values = dict(asset_id=asset_id, attempted_source_hash=digest(source),
                  retry_after=now + RETRY_DELAY, attempt_token=token)
    statement = insert(AssetIconCache).values(**values)
    statement = statement.on_conflict_do_update(
        index_elements=[AssetIconCache.asset_id],
        set_={key: value for key, value in values.items() if key != "asset_id"},
        where=or_(AssetIconCache.attempted_source_hash != digest(source), AssetIconCache.retry_after <= now),
    ).returning(AssetIconCache.attempt_token)
    claimed = db.scalar(statement)
    db.commit()
    return claimed


def refresh_icon(asset_id, source: str, token) -> None:
    # FastAPI BackgroundTasks: response is sent first; bounded work per process.
    # A rejected slot/crashed process can retry lazily after the persisted lease.
    if not FETCH_SLOTS.acquire(blocking=False):
        return
    try:
        data = asyncio.run(fetch_icon(source))
        with SessionLocal() as db:
            # Lock the Asset only after network work; a concurrent edit/delete
            # must not publish stale content or recreate an orphan cache row.
            asset = db.scalar(select(Asset).where(Asset.id == asset_id).with_for_update())
            if asset is None or asset.icon_url != source:
                return
            db.execute(update(AssetIconCache).where(
                AssetIconCache.asset_id == asset_id, AssetIconCache.attempt_token == token,
            ).values(source_hash=digest(source), content_hash=digest(data), data=data))
            db.commit()
    except Exception as exc:
        reason = str(exc) if isinstance(exc, IconRejected) else ("timeout" if isinstance(exc, TimeoutError) else "retrieval_failed")
        logger.warning("Asset icon retrieval failed asset_id=%s reason=%s", asset_id, reason)
    finally:
        FETCH_SLOTS.release()


def clear_icon_cache(db, asset_id) -> None:
    db.execute(delete(AssetIconCache).where(AssetIconCache.asset_id == asset_id))
