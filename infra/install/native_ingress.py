"""Narrowly owned, validated nginx configuration for Debian/Ubuntu hosts."""
import argparse
import ipaddress
import os
from pathlib import Path
import stat
import subprocess
import tempfile

from configuration import ROOT, compose_ingress_settings, detect_bind_address

SITE = Path("/etc/nginx/conf.d/atlas.conf")
ORDERING = Path("/etc/systemd/system/nginx.service.d/atlas.conf")
MARKER = "# Atlas managed native ingress."
ORDERING_CONTENT = MARKER + "\n[Unit]\nWants=atlas-api.service atlas-web.service\nAfter=atlas-api.service atlas-web.service\n"


def settings(values=None):
    ingress = compose_ingress_settings() if values is None else {
        key: values.get(key, default) for key, default in (
            ("ATLAS_BIND_ADDRESS", "127.0.0.1"), ("ATLAS_PORT", "3000"), ("ATLAS_TRUSTED_PROXIES", ""))}
    if values is not None and "ATLAS_BIND_ADDRESS" not in values:
        ingress["ATLAS_BIND_ADDRESS"] = detect_bind_address()
    # Revalidate persisted upgrade settings; only numeric values enter nginx.
    address = ipaddress.IPv4Address(ingress["ATLAS_BIND_ADDRESS"])
    if address.is_unspecified or address.is_multicast or address.is_link_local or address.is_reserved:
        raise ValueError("Native ATLAS_BIND_ADDRESS must be a usable LAN or loopback IPv4 address")
    port = ingress["ATLAS_PORT"]
    if not port.isascii() or not port.isdecimal() or not 1 <= int(port) <= 65535:
        raise ValueError("ATLAS_PORT must be an integer from 1 to 65535")
    if int(port) in {3001, 8000}:
        raise ValueError("Native ATLAS_PORT must differ from private web/API ports 3001 and 8000")
    proxies = ingress["ATLAS_TRUSTED_PROXIES"]
    networks = [ipaddress.ip_network(value, strict=False) for value in proxies.split(",")] if proxies else []
    if any(network.prefixlen == 0 for network in networks):
        raise ValueError("ATLAS_TRUSTED_PROXIES must use explicit peers or narrow CIDRs, not all addresses")
    return {"ATLAS_BIND_ADDRESS": str(address), "ATLAS_PORT": str(int(port)),
            "ATLAS_TRUSTED_PROXIES": ",".join(str(network) for network in networks)}


def render(values):
    values = settings(values)
    content = (ROOT / "infra/nginx/native.conf").read_text()
    return (content.replace("@BIND_ADDRESS@", values["ATLAS_BIND_ADDRESS"])
            .replace("@PORT@", values["ATLAS_PORT"])
            .replace("@TRUSTED_PROXIES@", "\n    ".join(
                f"{network} 1;" for network in values["ATLAS_TRUSTED_PROXIES"].split(",") if network)))


def safe_path(path):
    paths = (path, *path.parents)
    for parent in paths:
        if parent.is_symlink():
            raise ValueError(f"Managed path must not be a symlink: {parent}")
    for parent in reversed(paths):
        if parent.exists():
            info = parent.stat()
            if info.st_uid != 0 or info.st_mode & 0o022:
                raise ValueError(f"Managed path must be root-owned and not writable by other users: {parent}")
            if parent != path and not parent.is_dir():
                raise ValueError(f"Managed parent must be a directory: {parent}")


def check_managed_paths():
    for path in (SITE, ORDERING):
        safe_path(path)
        if path.exists():
            if not stat.S_ISREG(path.stat().st_mode) or path.stat().st_nlink != 1:
                raise ValueError(f"Managed ingress must be a regular, unlinked file: {path}")
            if not path.read_text().startswith(MARKER):
                raise ValueError(f"Refusing to replace operator-owned configuration: {path}")


def atomic_write(path, content):
    safe_path(path)
    path.parent.mkdir(mode=0o755, parents=True, exist_ok=True)
    descriptor, temporary = tempfile.mkstemp(prefix=".atlas-", dir=path.parent)
    try:
        with os.fdopen(descriptor, "w") as stream:
            os.fchmod(stream.fileno(), 0o644)
            stream.write(content)
            stream.flush()
            os.fsync(stream.fileno())
        os.replace(temporary, path)
    finally:
        if os.path.exists(temporary):
            os.unlink(temporary)


def command(arguments):
    # Configuration tests and systemctl failures must not dump host config/logs.
    subprocess.run(arguments, check=True, capture_output=True, text=True, timeout=60)


def install(values):
    """Restore the old files on validation/activation failure; never touch other sites."""
    check_managed_paths()
    content = render(values)
    command(["nginx", "-t"])
    originals = {path: path.read_text() if path.exists() else None for path in (SITE, ORDERING)}
    activating = False
    try:
        atomic_write(SITE, content)
        atomic_write(ORDERING, ORDERING_CONTENT)
        command(["nginx", "-t"])
        command(["systemctl", "daemon-reload"])
        command(["systemctl", "enable", "nginx.service"])
        activating = True
        command(["systemctl", "reload-or-restart", "nginx.service"])
    except (OSError, ValueError, subprocess.SubprocessError):
        for path, original in originals.items():
            if original is None:
                path.unlink(missing_ok=True)
            else:
                atomic_write(path, original)
        command(["nginx", "-t"])
        command(["systemctl", "daemon-reload"])
        if activating:
            command(["systemctl", "reload-or-restart", "nginx.service"])
        raise ValueError("Atlas ingress activation failed; previous nginx configuration restored. Inspect nginx service health.") from None


def main():
    argparse.ArgumentParser(description="Refresh Atlas-owned nginx ingress from /etc/atlas/atlas.env").parse_args()
    if os.geteuid() != 0:
        raise SystemExit("Run this ingress helper as root on the supported native host.")
    from upgrade import protected_configuration
    try:
        configuration = Path("/etc/atlas/atlas.env")
        safe_path(configuration)
        values = protected_configuration(configuration, "systemd")
        install(values)
    except (OSError, ValueError, subprocess.SubprocessError):
        raise SystemExit("Cannot refresh Atlas ingress; inspect protected configuration, nginx -t and service health. No secrets are displayed.") from None
    print("Atlas ingress configuration validated and activated.")


if __name__ == "__main__":
    main()
