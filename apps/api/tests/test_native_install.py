"""Native installer contracts; real Debian lifecycle acceptance is a separate gate."""
import importlib
from pathlib import Path
import subprocess
import sys
from unittest.mock import MagicMock
from types import SimpleNamespace

import pytest

ROOT = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(ROOT / "infra/install"))
native = importlib.import_module("native")
ingress = importlib.import_module("native_ingress")
upgrade = importlib.import_module("upgrade")

SETTINGS = {"ATLAS_BIND_ADDRESS": "192.0.2.10", "ATLAS_PORT": "3000", "ATLAS_TRUSTED_PROXIES": ""}


@pytest.fixture
def prepared_host(monkeypatch, tmp_path):
    calls = []
    monkeypatch.setattr(native, "host_errors", lambda: [])
    monkeypatch.setattr(native, "account_errors", lambda **kwargs: [])
    monkeypatch.setattr(native.os, "geteuid", lambda: 0)
    monkeypatch.setattr(native, "DESTINATION", tmp_path / "opt/atlas")
    native.DESTINATION.parent.mkdir(parents=True)
    monkeypatch.setattr(native, "CONFIGURATION", tmp_path / "etc/atlas/atlas.env")
    monkeypatch.setattr(native, "STATE", tmp_path / "var/lib/atlas")
    monkeypatch.setattr(native, "UNITS", tmp_path / "units")
    monkeypatch.setattr(ingress, "SITE", tmp_path / "nginx/atlas.conf")
    monkeypatch.setattr(ingress, "ORDERING", tmp_path / "nginx-unit/atlas.conf")
    monkeypatch.setattr(ingress, "safe_path", lambda path: None)
    monkeypatch.setattr(native.shutil, "which", lambda name: "/usr/bin/" + name)
    monkeypatch.setattr(native.socket, "socket", MagicMock())
    monkeypatch.setattr(ingress, "settings", lambda values=None: {
        **SETTINGS, "ATLAS_BIND_ADDRESS": "127.0.0.1", "ATLAS_PORT": "49381"})
    def probe(arguments, **kwargs):
        calls.append(arguments)
        stdout = ""
        if arguments == ["/usr/bin/node", "--version"]:
            stdout = "v22.20.0"
        elif arguments[0] in {"pg_dump", "pg_restore"}:
            stdout = f"{arguments[0]} (PostgreSQL) 17.6 (Debian 17.6-0+deb13u1)"
        elif arguments[0] == "runuser":
            stdout = "170006|f|f"
        return SimpleNamespace(returncode=0, stdout=stdout)
    monkeypatch.setattr(native, "probe", probe)
    return calls, probe


def test_help_is_side_effect_free_even_without_root_or_supported_host(monkeypatch, tmp_path):
    monkeypatch.setattr(sys, "argv", ["native.py", "--help"])
    monkeypatch.setattr(native, "preflight", lambda: pytest.fail("help must not preflight"))
    monkeypatch.setattr(native, "install", lambda *args: pytest.fail("help must not install"))
    with pytest.raises(SystemExit) as result:
        native.main()
    assert result.value.code == 0
    result = subprocess.run([sys.executable, str(ROOT / "infra/install/native.py"), "--help"], capture_output=True, text=True)
    assert result.returncode == 0 and "usage:" in result.stdout and not result.stderr
    fresh = tmp_path / "infra/install"
    fresh.mkdir(parents=True)
    for name in ("native.py", "configuration.py", "native_ingress.py"):
        (fresh / name).write_bytes((ROOT / "infra/install" / name).read_bytes())
    before = sorted(path.relative_to(tmp_path) for path in tmp_path.rglob("*"))
    result = subprocess.run([sys.executable, str(fresh / "native.py"), "--help"], capture_output=True, text=True)
    assert result.returncode == 0 and not result.stderr
    assert sorted(path.relative_to(tmp_path) for path in tmp_path.rglob("*")) == before


def test_preflight_collects_missing_services_tools_and_venv_before_any_install_mutation(prepared_host, monkeypatch):
    _, healthy_probe = prepared_host
    monkeypatch.setattr(sys, "argv", ["native.py"])
    monkeypatch.setattr(native.shutil, "which", lambda name: None if name in {"pg_dump", "pg_restore"} else "/usr/bin/" + name)
    def broken_probe(arguments, **kwargs):
        if "venv" in arguments or arguments[:2] == ["systemctl", "cat"]:
            return SimpleNamespace(returncode=1, stdout="")
        return healthy_probe(arguments, **kwargs)
    monkeypatch.setattr(native, "probe", broken_probe)
    monkeypatch.setattr(native, "install", lambda *args: pytest.fail("failed preflight must not mutate"))
    with pytest.raises(SystemExit) as result:
        native.main()
    message = str(result.value)
    for expected in ("pg_dump", "pg_restore", "python3-venv", "postgresql.service", "redis-server.service", "nginx.service"):
        assert expected in message
    assert "Traceback" not in message and "CalledProcessError" not in message
    assert not native.DESTINATION.exists() and not native.CONFIGURATION.exists()


def test_subprocess_prerequisite_failure_is_clean_and_precedes_install(prepared_host, monkeypatch):
    _, healthy_probe = prepared_host
    def broken_probe(arguments, **kwargs):
        if arguments[:2] == ["systemctl", "cat"]:
            raise subprocess.CalledProcessError(1, arguments)
        return healthy_probe(arguments, **kwargs)
    monkeypatch.setattr(native, "probe", broken_probe)
    with pytest.raises(ValueError, match="Cannot inspect required service") as result:
        native.preflight()
    assert "Traceback" not in str(result.value)


def test_preflight_probes_actual_interpreter_and_unit_node_path(prepared_host):
    calls, _ = prepared_host
    settings, needs_nginx = native.preflight()
    assert not needs_nginx and settings["ATLAS_PORT"] == "49381"
    assert any(call[:3] == [sys.executable, "-m", "venv"] for call in calls)
    assert ["/usr/bin/node", "--version"] in calls
    assert not any(call[0] in {"useradd", "apt-get"} for call in calls)


def test_preflight_groups_old_node_inactive_services_and_bad_nginx(prepared_host, monkeypatch):
    _, healthy_probe = prepared_host
    def broken(arguments, **kwargs):
        if arguments == ["/usr/bin/node", "--version"]:
            return SimpleNamespace(returncode=0, stdout="v18.19.0")
        if arguments[:2] == ["systemctl", "is-active"] or arguments == ["nginx", "-t"]:
            return SimpleNamespace(returncode=1, stdout="")
        return healthy_probe(arguments, **kwargs)
    monkeypatch.setattr(native, "probe", broken)
    with pytest.raises(ValueError) as result:
        native.preflight()
    for message in ("Node.js 22", "Start postgresql.service", "Start redis-server.service", "nginx -t"):
        assert message in str(result.value)


def test_preflight_reports_unavailable_bind_before_install(prepared_host, monkeypatch):
    listener = MagicMock()
    listener.__enter__.return_value.bind.side_effect = OSError("occupied")
    monkeypatch.setattr(native.socket, "socket", lambda: listener)
    with pytest.raises(ValueError, match="listener is unavailable"):
        native.preflight()
    assert not native.CONFIGURATION.exists()


def test_preflight_refuses_existing_postgres_role_before_configuration(prepared_host, monkeypatch):
    _, healthy_probe = prepared_host
    def conflict(arguments, **kwargs):
        return SimpleNamespace(returncode=0, stdout="170006|t|f") if arguments[0] == "runuser" else healthy_probe(arguments, **kwargs)
    monkeypatch.setattr(native, "probe", conflict)
    with pytest.raises(ValueError, match="role/database already exists"):
        native.preflight()
    assert not native.CONFIGURATION.exists()


def test_nginx_package_installability_is_checked_without_installing(prepared_host, monkeypatch):
    calls, healthy_probe = prepared_host
    monkeypatch.setattr(native.shutil, "which", lambda name: None if name == "nginx" else "/usr/bin/" + name)
    assert native.preflight()[1]
    assert ["apt-get", "--simulate", "install", "--no-install-recommends", "nginx"] in calls
    monkeypatch.setattr(native, "probe", lambda args, **kwargs: SimpleNamespace(returncode=1, stdout="") if args[0] == "apt-get" else healthy_probe(args, **kwargs))
    with pytest.raises(ValueError, match="nginx cannot be installed"):
        native.preflight()


def test_package_failure_precedes_atlas_files_and_account(prepared_host, monkeypatch):
    monkeypatch.setattr(native, "run", lambda *args, **kwargs: (_ for _ in ()).throw(subprocess.CalledProcessError(1, args)))
    with pytest.raises(ValueError, match="no Atlas files/accounts/database"):
        native.install(SETTINGS, True)
    assert not native.CONFIGURATION.exists() and not native.DESTINATION.exists()


def test_main_runs_complete_preflight_before_install(monkeypatch):
    monkeypatch.setattr(sys, "argv", ["native.py"])
    order = []
    monkeypatch.setattr(native, "preflight", lambda: order.append("preflight") or (SETTINGS, False))
    monkeypatch.setattr(native, "install", lambda values, needed: order.append("install"))
    native.main()
    assert order == ["preflight", "install"]


@pytest.mark.parametrize("key,value", [("ATLAS_PORT", "3000; include /tmp/evil;"), ("ATLAS_PORT", "65536"),
    ("ATLAS_PORT", "3001"), ("ATLAS_PORT", "8000"), ("ATLAS_BIND_ADDRESS", "0.0.0.0"),
    ("ATLAS_BIND_ADDRESS", "192.0.2.1;"), ("ATLAS_TRUSTED_PROXIES", "0.0.0.0/0"),
    ("ATLAS_TRUSTED_PROXIES", "192.0.2.1;include /tmp/evil;")])
def test_native_ingress_rejects_unsafe_or_conflicting_settings(key, value):
    with pytest.raises(ValueError):
        ingress.render({**SETTINGS, key: value})


def test_native_config_matches_public_private_and_h3_boundaries():
    from app.services.backup_archive import MAX_ARCHIVE_BYTES
    config = ingress.render(SETTINGS)
    assert "listen 192.0.2.10:3000;" in config
    assert "proxy_pass http://127.0.0.1:8000;" in config
    assert "proxy_pass http://127.0.0.1:8000/;" not in config
    assert "proxy_pass http://127.0.0.1:3001;" in config
    assert "client_max_body_size 2g;" in config and MAX_ARCHIVE_BYTES == 2 * 1024**3
    assert "proxy_request_buffering off;" in config
    assert "client_max_body_size 20m;" in config
    api = (ROOT / "infra/systemd/atlas-api.service").read_text()
    web = (ROOT / "infra/systemd/atlas-web.service").read_text()
    assert "ATLAS_API_HOST=127.0.0.1" in api and "FORWARDED_ALLOW_IPS=127.0.0.1" in api
    assert "ExecStart=/usr/bin/env ATLAS_API_HOST=127.0.0.1 FORWARDED_ALLOW_IPS=127.0.0.1" in api
    assert "HOSTNAME=127.0.0.1 PORT=3001" in web
    assert "After=atlas-api.service atlas-web.service" in ingress.ORDERING_CONTENT


def test_install_validates_and_only_replaces_atlas_owned_nginx_paths(monkeypatch, tmp_path):
    site, ordering = tmp_path / "nginx/atlas.conf", tmp_path / "unit/atlas.conf"
    site.parent.mkdir(); ordering.parent.mkdir()
    unrelated = site.parent / "operator.conf"
    unrelated.write_text("operator configuration")
    monkeypatch.setattr(ingress, "SITE", site); monkeypatch.setattr(ingress, "ORDERING", ordering)
    monkeypatch.setattr(ingress, "safe_path", lambda path: None)
    calls = []
    monkeypatch.setattr(ingress, "command", lambda args: calls.append(args))
    ingress.install(SETTINGS)
    assert unrelated.read_text() == "operator configuration"
    assert site.read_text() == ingress.render(SETTINGS)
    assert site.stat().st_mode & 0o777 == 0o644
    assert calls[:2] == [["nginx", "-t"], ["nginx", "-t"]]
    assert calls[-1] == ["systemctl", "reload-or-restart", "nginx.service"]
    site.write_text("operator site")
    with pytest.raises(ValueError, match="operator-owned"):
        ingress.install(SETTINGS)
    assert site.read_text() == "operator site"


@pytest.mark.parametrize("existing", [False, True])
def test_invalid_candidate_restores_previous_config_without_activation(monkeypatch, tmp_path, existing):
    site, ordering = tmp_path / "atlas.conf", tmp_path / "atlas-unit.conf"
    monkeypatch.setattr(ingress, "SITE", site); monkeypatch.setattr(ingress, "ORDERING", ordering)
    monkeypatch.setattr(ingress, "safe_path", lambda path: None)
    if existing:
        site.write_text(ingress.MARKER + "\nold site"); ordering.write_text(ingress.ORDERING_CONTENT)
    calls = []
    def command(args):
        calls.append(args)
        if len(calls) == 2:
            raise subprocess.CalledProcessError(1, args)
    monkeypatch.setattr(ingress, "command", command)
    with pytest.raises(ValueError, match="previous nginx configuration restored"):
        ingress.install(SETTINGS)
    assert not any("reload-or-restart" in call for call in calls)
    if existing:
        assert site.read_text() == ingress.MARKER + "\nold site"
        assert ordering.read_text() == ingress.ORDERING_CONTENT
    else:
        assert not site.exists() and not ordering.exists()
    assert not list(tmp_path.glob(".atlas-*"))


def test_managed_ingress_symlinks_are_refused(monkeypatch, tmp_path):
    target = tmp_path / "operator"
    target.write_text("operator site")
    link = tmp_path / "atlas.conf"; link.symlink_to(target)
    monkeypatch.setattr(ingress, "SITE", link)
    with pytest.raises(ValueError, match="symlink"):
        ingress.check_managed_paths()
    assert target.read_text() == "operator site"


def test_managed_ingress_parent_symlink_is_refused(tmp_path):
    real = tmp_path / "real"; real.mkdir()
    parent = tmp_path / "nginx"; parent.symlink_to(real, target_is_directory=True)
    with pytest.raises(ValueError, match="symlink"):
        ingress.safe_path(parent / "atlas.conf")


def test_failed_nginx_activation_restores_original_files_and_reloads_previous_config(monkeypatch, tmp_path):
    site, ordering = tmp_path / "atlas.conf", tmp_path / "atlas-unit.conf"
    site.write_text(ingress.MARKER + "\nold site"); ordering.write_text(ingress.ORDERING_CONTENT)
    monkeypatch.setattr(ingress, "SITE", site); monkeypatch.setattr(ingress, "ORDERING", ordering)
    monkeypatch.setattr(ingress, "safe_path", lambda path: None)
    calls = []
    def command(args):
        calls.append(args)
        if args == ["systemctl", "reload-or-restart", "nginx.service"] and calls.count(args) == 1:
            raise subprocess.CalledProcessError(1, args)
    monkeypatch.setattr(ingress, "command", command)
    with pytest.raises(ValueError, match="previous nginx configuration restored"):
        ingress.install({**SETTINGS, "ATLAS_PORT": "4300"})
    assert site.read_text() == ingress.MARKER + "\nold site"
    assert ordering.read_text() == ingress.ORDERING_CONTENT
    assert calls.count(["systemctl", "reload-or-restart", "nginx.service"]) == 2


def test_native_completion_uses_same_local_setup_code_url_handoff(monkeypatch, tmp_path, capsys):
    account = SimpleNamespace(pw_uid=10001, pw_gid=10001)
    monkeypatch.setattr(native, "CONFIGURATION", tmp_path / "etc/atlas.env")
    monkeypatch.setattr(native, "DESTINATION", tmp_path / "opt/atlas")
    native.DESTINATION.parent.mkdir(parents=True)
    monkeypatch.setattr(native.pwd, "getpwnam", lambda name: account)
    monkeypatch.setattr(native.grp, "getgrnam", lambda name: SimpleNamespace(gr_gid=10001))
    monkeypatch.setattr(native.os, "chown", lambda *args: None)
    monkeypatch.setattr(native, "ensure_nginx", lambda needed: None)
    monkeypatch.setattr(native.shutil, "copytree", lambda *args, **kwargs: None)
    monkeypatch.setattr(native, "build_application", lambda account: None)
    monkeypatch.setattr(native, "install_units", lambda: None)
    monkeypatch.setattr(native, "wait_for_health", lambda values: None)
    monkeypatch.setattr(ingress, "install", lambda values: None)
    calls = []
    monkeypatch.setattr(native, "run", lambda args, **kwargs: calls.append(args) or SimpleNamespace(stdout="Local setup-code handoff\n"))
    previous_umask = native.os.umask(0o022)
    try:
        native.install(SETTINGS, False)
    finally:
        native.os.umask(previous_umask)
    assert "Atlas installed successfully." in capsys.readouterr().out
    assert calls[-1][-4:] == ["scripts.setup_code", "reset", "--access-url", "http://192.0.2.10:3000/"]
    assert "AUTH_COOKIE_SECURE=auto" in native.CONFIGURATION.read_text()


def test_native_upgrade_validate_only_preflights_without_installing_nginx(monkeypatch, tmp_path, capsys):
    monkeypatch.setattr(sys, "argv", ["upgrade.py", "--method", "systemd", "--validate-only"])
    monkeypatch.setattr(upgrade, "package_identity", lambda method: {"version": "0.1.0"})
    monkeypatch.setattr(upgrade, "protected_configuration", lambda path, method: {})
    calls = []
    monkeypatch.setattr(upgrade, "native_upgrade_preflight", lambda values: calls.append("preflight") or (SETTINGS, True))
    monkeypatch.setattr(upgrade, "native_upgrade", lambda *args, **kwargs: pytest.fail("must not upgrade"))
    upgrade.main()
    assert calls == ["preflight"] and "no changes made" in capsys.readouterr().out
