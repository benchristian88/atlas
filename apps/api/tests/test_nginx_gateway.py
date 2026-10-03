"""Run the repository nginx config against real HTTP upstreams when available.

Set ATLAS_TEST_NGINX to an nginx >=1.28 binary, or install nginx on PATH.
Docker/LAN/TLS termination/reboot acceptance remains a separate Linux check.
"""
from contextlib import ExitStack
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
import json
import os
from pathlib import Path
import shutil
import socket
import subprocess
import threading
import time
from urllib.request import Request, urlopen

import pytest

GATEWAY = Path(__file__).resolve().parents[3] / "infra/docker/gateway"


def start_upstream(stack, service):
    class Handler(BaseHTTPRequestHandler):
        def do_GET(self):
            content = json.dumps({"service": service, "path": self.path, "headers": dict(self.headers)}).encode()
            self.send_response(200)
            self.send_header("Content-Type", "application/json")
            self.send_header("Content-Length", str(len(content)))
            self.end_headers()
            self.wfile.write(content)

        def log_message(self, *args):
            pass
    upstream = ThreadingHTTPServer(("127.0.0.1", 0), Handler)
    thread = threading.Thread(target=upstream.serve_forever, daemon=True)
    thread.start()
    stack.callback(upstream.server_close)
    stack.callback(thread.join, 2)
    stack.callback(upstream.shutdown)
    return upstream.server_port


@pytest.fixture(params=["", "127.0.0.1"])
def gateway(request, tmp_path):
    binary = os.getenv("ATLAS_TEST_NGINX") or shutil.which("nginx")
    if not binary:
        pytest.skip("requires nginx >=1.28 or ATLAS_TEST_NGINX")
    trust = tmp_path / "trusted.conf"
    subprocess.run(["sh", str(GATEWAY / "15-atlas-trusted-proxies.sh")], check=True,
        env={**os.environ, "ATLAS_TRUSTED_PROXIES": request.param, "ATLAS_TRUSTED_PROXIES_FILE": str(trust)})
    with ExitStack() as stack:
        api_port = start_upstream(stack, "api")
        web_port = start_upstream(stack, "web")
        with socket.socket() as sock:
            sock.bind(("127.0.0.1", 0))
            port = sock.getsockname()[1]
        config = (GATEWAY / "default.conf").read_text()
        config = config.replace("/etc/nginx/atlas-trusted-proxies.conf", str(trust))
        (tmp_path / "logs").mkdir()
        production = tmp_path / "production.conf"
        production.write_text(f"pid {tmp_path}/production.pid;\nerror_log {tmp_path}/error.log;\n"
                              f"events {{}}\nhttp {{\n{config}\n}}\n")
        validation = subprocess.run([binary, "-p", str(tmp_path), "-c", str(production), "-t"],
                                    capture_output=True, text=True)
        assert validation.returncode == 0, validation.stderr
        # Production uses Docker DNS; local test uses ephemeral loopback servers.
        config = config.replace("api:8000 resolve", f"127.0.0.1:{api_port}")
        config = config.replace("web:3000 resolve", f"127.0.0.1:{web_port}")
        config = config.replace("listen 80;", f"listen 127.0.0.1:{port};")
        path = tmp_path / "nginx.conf"
        path.write_text(f"pid {tmp_path}/nginx.pid;\nerror_log {tmp_path}/error.log;\ndaemon off;\n"
                        f"events {{}}\nhttp {{ access_log off; client_body_temp_path {tmp_path}/body; "
                        f"proxy_temp_path {tmp_path}/proxy;\n{config}\n}}\n")
        validation = subprocess.run([binary, "-p", str(tmp_path), "-c", str(path), "-t"], capture_output=True, text=True)
        assert validation.returncode == 0, validation.stderr
        process = subprocess.Popen([binary, "-p", str(tmp_path), "-c", str(path)], stdout=subprocess.DEVNULL,
                                   stderr=subprocess.DEVNULL)
        stack.callback(process.wait, 5)
        stack.callback(process.terminate)
        for _ in range(100):
            if process.poll() is not None:
                pytest.fail((tmp_path / "error.log").read_text())
            try:
                with socket.create_connection(("127.0.0.1", port), timeout=.1):
                    break
            except OSError:
                time.sleep(.02)
        else:
            pytest.fail("nginx did not become ready")
        yield f"http://127.0.0.1:{port}", bool(request.param)


@pytest.mark.parametrize("path,service", [("/", "web"), ("/setup", "web"), ("/login", "web"),
    ("/dashboard", "web"), ("/api", "api"), ("/api/health", "api"),
    ("/api/setup/status?probe=1", "api"), ("/api/auth/me", "api"), ("/apiary", "web")])
def test_actual_nginx_routes_and_preserves_host_and_uri(gateway, path, service):
    url, _ = gateway
    with urlopen(url + path, timeout=3) as response:
        result = json.load(response)
    assert result["service"] == service
    assert result["path"] == path
    assert result["headers"]["Host"] == url.removeprefix("http://")
    assert result["headers"]["X-Forwarded-Proto"] == "http"
    assert result["headers"]["X-Real-IP"] == "127.0.0.1"


@pytest.mark.parametrize("protocol,expected", [("https", "https"), ("http", "http"),
                                             ("https,http", "http"), ("invalid", "http")])
def test_actual_nginx_only_accepts_protocol_from_trusted_peer(gateway, protocol, expected):
    url, trusted = gateway
    request = Request(url + "/api/health", headers={"X-Forwarded-Proto": protocol,
        "X-Forwarded-For": "192.0.2.10", "X-Real-IP": "192.0.2.11",
        "X-Forwarded-Host": "attacker.example", "Forwarded": "proto=https;host=attacker.example"})
    with urlopen(request, timeout=3) as response:
        result = json.load(response)
    headers = result["headers"]
    assert headers["X-Forwarded-Proto"] == (expected if trusted else "http")
    assert headers["X-Forwarded-For"] == ("192.0.2.10, 127.0.0.1" if trusted else "127.0.0.1")
    assert headers["X-Real-IP"] == "127.0.0.1"
    assert headers["X-Forwarded-Host"] == url.removeprefix("http://")
    assert "Forwarded" not in headers
