"""Opt-in acceptance harness, excluded from every release package.

Run with a disposable production-configured DB and uvicorn tests.h4_browser_app:app.
Only this harness redirects the fixed GitHub transport to a loopback HTTP server;
normal Atlas exposes no configurable repository or test/control endpoint.
"""
from contextlib import asynccontextmanager
import os

from aiohttp import web
from app.main import app, lifespan as atlas_lifespan
from app.release import REPOSITORY_URL
from app.services import updates

SCENARIO = "current"


async def releases(request):
    if SCENARIO == "unavailable":
        return web.Response(status=503)
    version = "0.2.0" if SCENARIO == "newer" else "0.1.0"
    record = {"id": 1, "draft": False, "prerelease": True, "tag_name": f"v{version}",
              "html_url": f"{REPOSITORY_URL}/releases/tag/v{version}",
              "published_at": "2026-10-04T00:00:00Z", "body": "<script>untrusted</script>"}
    return web.json_response([record])


async def control(request):
    global SCENARIO
    payload = await request.json()
    assert payload["scenario"] in {"current", "newer", "unavailable"}
    assert payload["method"] in {"docker_compose", "systemd", "development"}
    SCENARIO = payload["scenario"]
    updates.REFRESH_SECONDS = 0 if payload.get("allow_refresh") else 60
    os.environ["ATLAS_INSTALL_METHOD"] = payload["method"]
    updates.checker.expires = float("-inf")
    updates.checker.checked = float("-inf")
    return web.json_response({"controlled": True})


@asynccontextmanager
async def test_lifespan(application):
    updates.RELEASE_API_URL = "http://127.0.0.1:3191/releases"
    server = web.Application()
    server.router.add_get("/releases", releases)
    server.router.add_post("/control", control)
    runner = web.AppRunner(server, access_log=None)
    await runner.setup()
    await web.TCPSite(runner, "127.0.0.1", 3191).start()
    try:
        async with atlas_lifespan(application):
            yield
    finally:
        await runner.cleanup()


app.router.lifespan_context = test_lifespan
