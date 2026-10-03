import asyncio
import io
import uuid
from types import SimpleNamespace
from unittest.mock import AsyncMock, Mock

import aiohttp
import pytest
from PIL import Image

from app.services import asset_icons as icons


def image_bytes(format="PNG", size=(32, 32), color="red"):
    output = io.BytesIO()
    Image.new("RGB", size, color).save(output, format=format)
    return output.getvalue()


@pytest.mark.parametrize("format", ["PNG", "JPEG", "WEBP"])
def test_rasters_normalized_to_png(format):
    result = icons.normalize_image(image_bytes(format, (512, 256)))
    with Image.open(io.BytesIO(result)) as image:
        assert image.format == "PNG"
        assert image.size == (256, 128)
        assert not image.info


@pytest.mark.parametrize("data", [b"<html>not an icon</html>", b'<svg xmlns="http://www.w3.org/2000/svg"/>', b"arbitrary", image_bytes("GIF"), image_bytes()[:40]])
def test_invalid_content(data):
    with pytest.raises(icons.IconRejected):
        icons.normalize_image(data)


def test_limits():
    with pytest.raises(icons.IconRejected, match="download_too_large"):
        icons.normalize_image(b"x" * (icons.MAX_DOWNLOAD + 1))
    for size in [(2049, 1), (2001, 2000)]:
        with pytest.raises(icons.IconRejected, match="dimensions_too_large"):
            icons.normalize_image(image_bytes(size=size))


@pytest.mark.parametrize("url", [
    "http://example.com/a.png", "file:///etc/passwd", "data:image/png;base64,a", "ftp://example.com/a",
    "https://localhost/a", "https://localhost./a", "https://x.localhost/a", "https://127.0.0.1/a",
    "https://10.0.0.1/a", "https://172.16.0.1/a", "https://192.168.1.1/a", "https://169.254.169.254/a",
    "https://100.100.100.200/a", "https://[::1]/a", "https://[fe80::1]/a", "https://[fc00::1]/a",
    "https://[::ffff:127.0.0.1]/a", "https://[64:ff9b::a00:1]/a", "https://[2002:7f00:1::]/a",
    "https://0.0.0.0/a", "https://224.0.0.1/a", "https://192.0.2.1/a", "https://example.com:8443/a",
    "https://user:secret@example.com/a", "https://example.com/a\r\nHost:localhost", "https://[fe80::1%25eth0]/a",
])
def test_unsafe_urls_rejected(url):
    with pytest.raises(icons.IconRejected):
        icons.validate_url(url)


def test_dns_all_answers_validated(monkeypatch):
    async def run():
        resolver = icons.PublicResolver()
        monkeypatch.setattr(aiohttp.ThreadedResolver, "resolve", AsyncMock(return_value=[{"host": "1.1.1.1"}, {"host": "10.1.2.3"}]))
        with pytest.raises(icons.IconRejected):
            await resolver.resolve("public-looking.example", 443)
    asyncio.run(run())


def test_connected_peer_checked_before_http(monkeypatch):
    async def run():
        transport = Mock()
        transport.get_extra_info.return_value = ("127.0.0.1", 443)
        monkeypatch.setattr(aiohttp.TCPConnector, "_wrap_create_connection", AsyncMock(return_value=(transport, object())))
        connector = icons.PublicConnector()
        with pytest.raises(icons.IconRejected):
            await connector._wrap_create_connection()
        transport.close.assert_called_once()
        await connector.close()
    asyncio.run(run())


class Response:
    def __init__(self, status=200, headers=None, data=None, length=None):
        self.status, self.headers = status, headers or {}
        self.data = image_bytes() if data is None else data
        self.content_length = length
        self.content = self
    async def __aenter__(self): return self
    async def __aexit__(self, *args): pass
    async def iter_chunked(self, size):
        for offset in range(0, len(self.data), size):
            yield self.data[offset:offset + size]


def fake_client(monkeypatch, responses):
    calls = []
    class Client:
        def __init__(self, **kwargs):
            self.connector = kwargs["connector"]
            assert kwargs["trust_env"] is False
            assert isinstance(kwargs["cookie_jar"], aiohttp.DummyCookieJar)
            assert kwargs["auto_decompress"] is False
            assert "Authorization" not in kwargs["headers"]
        async def __aenter__(self): return self
        async def __aexit__(self, *args): await self.connector.close()
        def get(self, url, **kwargs):
            assert kwargs == {"allow_redirects": False}
            calls.append(str(url))
            response = responses.pop(0)
            if isinstance(response, Exception): raise response
            return response
    monkeypatch.setattr(icons.aiohttp, "ClientSession", Client)
    return calls


@pytest.mark.parametrize("format", ["PNG", "JPEG", "WEBP"])
def test_https_fetch(format, monkeypatch):
    calls = fake_client(monkeypatch, [Response(data=image_bytes(format))])
    assert asyncio.run(icons.fetch_icon("https://example.com/icon")) == icons.normalize_image(image_bytes(format))
    assert calls == ["https://example.com/icon"]


@pytest.mark.parametrize("response,reason", [
    (Response(data=b"<html>error</html>", headers={"Content-Type": "image/png"}), "invalid_image"),
    (Response(length=icons.MAX_DOWNLOAD + 1), "download_too_large"),
    (Response(data=b"x" * (icons.MAX_DOWNLOAD + 1)), "download_too_large"),
    (Response(headers={"Content-Encoding": "gzip"}), "encoded_content"),
    (Response(302, {"Location": "https://192.168.0.1/x"}), "blocked_destination"),
    (Response(302, {"Location": "http://example.com/x"}), "https_required"),
])
def test_fetch_rejections(monkeypatch, response, reason):
    fake_client(monkeypatch, [response])
    with pytest.raises(icons.IconRejected, match=reason):
        asyncio.run(icons.fetch_icon("https://example.com/icon"))


def test_redirect_limit_and_relative_redirect(monkeypatch):
    calls = fake_client(monkeypatch, [Response(302, {"Location": "/next"})] * 4)
    with pytest.raises(icons.IconRejected, match="redirect_limit"):
        asyncio.run(icons.fetch_icon("https://example.com/icon"))
    assert len(calls) == 4 and calls[1] == "https://example.com/next"


def test_timeout_is_safe_and_secret_free(monkeypatch, caplog):
    fake_client(monkeypatch, [TimeoutError("secret URL")])
    icons.refresh_icon(uuid.uuid4(), "https://example.com/?secret=hidden", uuid.uuid4())
    assert "reason=timeout" in caplog.text
    assert "secret" not in caplog.text


def test_cache_integrity_and_source():
    data = icons.normalize_image(image_bytes())
    cache = SimpleNamespace(source_hash=icons.digest("https://example.com/old"), data=data, content_hash=icons.digest(data))
    assert icons.current_bytes(cache, "https://example.com/old") == data
    assert icons.current_bytes(cache, "https://example.com/new") is None
    cache.data = b"corrupt"
    assert icons.current_bytes(cache, "https://example.com/old") is None
    assert icons.current_bytes(None, "https://example.com/old") is None
