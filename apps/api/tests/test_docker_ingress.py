"""H1.1 installation and production/development ingress contracts."""
import importlib.util
import json
import os
from pathlib import Path
import subprocess
import sys
from types import SimpleNamespace

import pytest
import yaml

ROOT = Path(__file__).resolve().parents[3]
GATEWAY = ROOT / "infra/docker/gateway"


def load_installer(name):
    spec = importlib.util.spec_from_file_location(name, ROOT / f"infra/install/{name}.py")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


@pytest.fixture
def configuration(monkeypatch):
    for name in ("ATLAS_BIND_ADDRESS", "ATLAS_PORT", "ATLAS_TRUSTED_PROXIES"):
        monkeypatch.delenv(name, raising=False)
    return load_installer("configuration")


def network_inspection(monkeypatch, module, routes=None, selected=None, addresses=None):
    outputs = {
        ("route", "show", "default"): routes if routes is not None else [{"dev": "eth0", "gateway": "192.168.3.1"}],
        ("route", "get", "1.1.1.1"): selected if selected is not None else [{"dev": "eth0", "prefsrc": "192.168.3.195"}],
        ("address", "show", "dev", "eth0"): addresses if addresses is not None else [{"addr_info": [
            {"family": "inet6", "local": "fd00::1", "scope": "global"},
            {"family": "inet", "local": "192.168.3.195", "scope": "global"}]}],
    }
    def run(arguments, **kwargs):
        assert arguments[:3] == ["ip", "-j", "-4"]
        assert kwargs["timeout"] == 5
        return SimpleNamespace(stdout=json.dumps(outputs[tuple(arguments[3:])]))
    monkeypatch.setattr(module.subprocess, "run", run)


def test_default_route_ipv4_and_ipv6_presence(configuration, monkeypatch):
    network_inspection(monkeypatch, configuration)
    assert configuration.detect_bind_address() == "192.168.3.195"


def test_multiple_interfaces_use_lowest_default_route_metric(configuration, monkeypatch):
    network_inspection(monkeypatch, configuration, routes=[
        {"dev": "wlan0", "metric": 600}, {"dev": "eth0", "metric": 100}])
    assert configuration.detect_bind_address() == "192.168.3.195"


@pytest.mark.parametrize("routes,selected,addresses", [
    ([], None, None),
    ([{"dev": "lo"}], None, None),
    ([{"dev": "eth0"}, {"dev": "wlan0"}], None, None),
    (None, [{"dev": "wlan0", "prefsrc": "192.168.3.195"}], None),
    (None, [{"dev": "eth0"}], None),
    (None, None, []),
    (None, [{"dev": "eth0", "prefsrc": "127.0.0.1"}], None),
    (None, [{"dev": "eth0", "prefsrc": "0.0.0.0"}], None),
    (None, [{"dev": "eth0", "prefsrc": "169.254.1.2"}], None),
    (None, [{"dev": "eth0", "prefsrc": "224.0.0.1"}], None),
    (None, [{"dev": "eth0", "prefsrc": "fd00::1"}], None),
])
def test_unsafe_or_missing_routes_fall_back_to_loopback(configuration, monkeypatch, capsys, routes, selected, addresses):
    network_inspection(monkeypatch, configuration, routes, selected, addresses)
    assert configuration.detect_bind_address() == "127.0.0.1"
    assert "local-only" in capsys.readouterr().out


@pytest.mark.parametrize("failure", [FileNotFoundError(), subprocess.TimeoutExpired("ip", 5),
                                        subprocess.CalledProcessError(1, "ip")])
def test_network_inspection_failure_is_safe(configuration, monkeypatch, capsys, failure):
    def fail(*args, **kwargs):
        raise failure
    monkeypatch.setattr(configuration.subprocess, "run", fail)
    assert configuration.detect_bind_address() == "127.0.0.1"
    assert "ATLAS_BIND_ADDRESS" in capsys.readouterr().out


@pytest.mark.parametrize("output", ["not JSON", "{}", '["invalid"]'])
def test_malformed_network_output_is_safe(configuration, monkeypatch, output):
    monkeypatch.setattr(configuration.subprocess, "run", lambda *a, **kw: SimpleNamespace(stdout=output))
    assert configuration.detect_bind_address() == "127.0.0.1"


@pytest.mark.parametrize("address", ["192.168.50.10", "127.0.0.1", "0.0.0.0"])
def test_explicit_address_and_custom_port_are_persisted(configuration, monkeypatch, tmp_path, address):
    monkeypatch.setenv("ATLAS_BIND_ADDRESS", address)
    monkeypatch.setenv("ATLAS_PORT", "4300")
    monkeypatch.setattr(configuration, "detect_bind_address", lambda: pytest.fail("Override must skip detection"))
    settings = configuration.generate_configuration(tmp_path / "atlas.env", "docker_compose")
    assert settings["ATLAS_BIND_ADDRESS"] == address
    assert settings["ATLAS_PORT"] == "4300"
    content = (tmp_path / "atlas.env").read_text()
    assert f"ATLAS_BIND_ADDRESS={address}\n" in content
    assert "ATLAS_PORT=4300\n" in content
    assert "AUTH_COOKIE_SECURE=auto\nCORS_ORIGINS=\n" in content


def test_detected_address_and_default_port_are_persisted(configuration, monkeypatch, tmp_path):
    monkeypatch.setattr(configuration, "detect_bind_address", lambda: "192.168.3.195")
    monkeypatch.setattr(configuration, "build_id", lambda: "test")
    settings = configuration.generate_configuration(tmp_path / "atlas.env", "docker_compose")
    assert settings == {"ATLAS_BIND_ADDRESS": "192.168.3.195", "ATLAS_PORT": "3000", "ATLAS_TRUSTED_PROXIES": ""}


@pytest.mark.parametrize("name,value", [("ATLAS_PORT", "0"), ("ATLAS_PORT", "65536"),
    ("ATLAS_PORT", "port"), ("ATLAS_PORT", "3000\nBAD=1"), ("ATLAS_BIND_ADDRESS", "host.example"),
    ("ATLAS_BIND_ADDRESS", ""), ("ATLAS_BIND_ADDRESS", "::1"), ("ATLAS_TRUSTED_PROXIES", "invalid;default 1;")])
def test_invalid_settings_do_not_create_configuration(configuration, monkeypatch, tmp_path, name, value):
    monkeypatch.setenv("ATLAS_BIND_ADDRESS", "127.0.0.1")
    monkeypatch.setenv(name, value)
    with pytest.raises(ValueError):
        configuration.generate_configuration(tmp_path / "atlas.env", "docker_compose")
    assert not (tmp_path / "atlas.env").exists()


def test_production_gateway_is_the_only_published_service():
    services = yaml.safe_load((ROOT / "infra/docker/docker-compose.yml").read_text())["services"]
    assert [name for name, service in services.items() if "ports" in service] == ["gateway"]
    assert services["gateway"]["ports"] == ["${ATLAS_BIND_ADDRESS:-127.0.0.1}:${ATLAS_PORT:-3000}:80"]
    assert services["api"]["environment"]["FORWARDED_ALLOW_IPS"] == "*"
    assert services["api"]["environment"]["CORS_ORIGINS"] == "${CORS_ORIGINS:-}"
    for name in ("gateway", "api", "web"):
        assert services[name]["restart"] == "unless-stopped"
        assert "healthcheck" in services[name]
    dev = yaml.safe_load((ROOT / "infra/docker/docker-compose.dev.yml").read_text())["services"]
    assert dev["api"]["ports"] == ["127.0.0.1:8000:8000"]
    assert dev["web"]["ports"] == ["127.0.0.1:3001:3000"]
    assert dev["postgres"]["ports"] == ["127.0.0.1:5432:5432"]
    assert dev["redis"]["ports"] == ["127.0.0.1:6379:6379"]
    assert dev["api"]["environment"]["FORWARDED_ALLOW_IPS"] != "*"


@pytest.mark.parametrize("proxies,expected", [("", ""), ("192.168.3.10", "192.168.3.10 1;\n"),
    ("192.168.3.10,10.0.0.0/24,fd00::1", "192.168.3.10 1;\n10.0.0.0/24 1;\nfd00::1 1;\n")])
def test_gateway_trust_allowlist_rendering(tmp_path, proxies, expected):
    target = tmp_path / "trusted.conf"
    result = subprocess.run(["sh", str(GATEWAY / "15-atlas-trusted-proxies.sh")],
        env={**os.environ, "ATLAS_TRUSTED_PROXIES": proxies, "ATLAS_TRUSTED_PROXIES_FILE": str(target)},
        capture_output=True, text=True)
    assert result.returncode == 0
    assert target.read_text() == expected


def test_gateway_trust_rejects_configuration_injection(tmp_path):
    result = subprocess.run(["sh", str(GATEWAY / "15-atlas-trusted-proxies.sh")],
        env={**os.environ, "ATLAS_TRUSTED_PROXIES": "1;default 1;", "ATLAS_TRUSTED_PROXIES_FILE": str(tmp_path / "trusted.conf")},
        capture_output=True, text=True)
    assert result.returncode != 0


def test_gateway_routing_preserves_api_and_host_port():
    config = (GATEWAY / "default.conf").read_text()
    assert "location /api/ {" in config
    assert "proxy_pass http://atlas_api;" in config
    assert "proxy_pass http://atlas_api/;" not in config
    assert "location / {\n        proxy_pass http://atlas_web;" in config
    assert "proxy_set_header Host $http_host;" in config
    assert '"1:https" https;' in config
    assert "default $scheme;" in config
    assert "default $remote_addr;" in config
    assert (GATEWAY / "15-atlas-trusted-proxies.sh").stat().st_mode & 0o111


def test_installer_passes_actual_url_without_printing_secrets(configuration, monkeypatch, tmp_path, capsys):
    monkeypatch.setitem(sys.modules, "configuration", configuration)
    installer = load_installer("compose")
    monkeypatch.setenv("ATLAS_BIND_ADDRESS", "192.168.50.10")
    monkeypatch.setenv("ATLAS_PORT", "4300")
    monkeypatch.setattr(configuration, "build_id", lambda: "test")
    monkeypatch.setattr(sys, "argv", ["compose.py", "--env-file", str(tmp_path / "atlas.env")])
    commands = []
    monkeypatch.setattr(installer.subprocess, "run", lambda command, **kw: commands.append(command))
    installer.main()
    assert commands[-1][-2:] == ["--access-url", "http://192.168.50.10:4300"]
    assert "--wait" in commands[0]
    content = (tmp_path / "atlas.env").read_text()
    settings = dict(line.split("=", 1) for line in content.splitlines() if line and not line.startswith("#"))
    output = capsys.readouterr().out + repr(commands)
    assert settings["POSTGRES_PASSWORD"] not in output
    assert settings["AUTH_SECRET_KEY"] not in output
