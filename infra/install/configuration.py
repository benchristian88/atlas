"""Standard-library production configuration generator, shared by installers."""
import argparse
import importlib.util
import ipaddress
import json
import os
from pathlib import Path
import secrets
import subprocess
import fcntl
import re

ROOT = Path(__file__).resolve().parents[2]


def _network_json(*arguments):
    result = subprocess.run(["ip", "-j", "-4", *arguments], capture_output=True,
                            text=True, check=True, timeout=5)
    records = json.loads(result.stdout)
    if not isinstance(records, list) or not all(isinstance(record, dict) for record in records):
        raise ValueError("Invalid network inspection output")
    return records


def detect_bind_address() -> str:
    """Inspect Linux IPv4 routes/addresses without DNS or sending packets."""
    try:
        routes = [route for route in _network_json("route", "show", "default")
                  if route.get("dev") and route["dev"] != "lo"
                  and route.get("type", "unicast") == "unicast"]
        if not routes:
            raise ValueError("No IPv4 default route")
        best_metric = min(int(route.get("metric", 0)) for route in routes)
        devices = {route["dev"] for route in routes if int(route.get("metric", 0)) == best_metric}
        if len(devices) != 1:
            raise ValueError("Ambiguous IPv4 default routes")
        device = devices.pop()
        # route get consults the kernel, without making an external connection.
        selected = _network_json("route", "get", "1.1.1.1")
        if len(selected) != 1 or selected[0].get("dev") != device:
            raise ValueError("Default-route source is ambiguous")
        source = selected[0].get("prefsrc") or selected[0].get("src")
        address = ipaddress.IPv4Address(source)
        if (address.is_loopback or address.is_unspecified or address.is_multicast
                or address.is_link_local or address.is_reserved):
            raise ValueError("Unsuitable IPv4 source")
        assigned = _network_json("address", "show", "dev", device)
        if not any(info.get("local") == str(address) and info.get("scope") == "global"
                   for interface in assigned for info in interface.get("addr_info", [])):
            raise ValueError("Source address is not assigned to the default-route interface")
        return str(address)
    except (OSError, subprocess.SubprocessError, ValueError, TypeError, KeyError):
        print("Could not safely determine the default-route IPv4 address; using 127.0.0.1 (local-only). "
              "Set ATLAS_BIND_ADDRESS explicitly to enable LAN access.")
        return "127.0.0.1"


def compose_ingress_settings() -> dict[str, str]:
    raw_address = os.environ.get("ATLAS_BIND_ADDRESS")
    if raw_address is None:
        address = detect_bind_address()
    else:
        try:
            address = str(ipaddress.IPv4Address(raw_address))
        except ipaddress.AddressValueError:
            raise ValueError("ATLAS_BIND_ADDRESS must be an IPv4 address") from None
    port = os.getenv("ATLAS_PORT", "3000")
    if not port.isascii() or not port.isdecimal() or not 1 <= int(port) <= 65535:
        raise ValueError("ATLAS_PORT must be an integer from 1 to 65535")
    proxies = os.getenv("ATLAS_TRUSTED_PROXIES", "")
    if proxies:
        try:
            proxies = ",".join(str(ipaddress.ip_network(value, strict=False)) for value in proxies.split(","))
        except ValueError:
            raise ValueError("ATLAS_TRUSTED_PROXIES must contain comma-separated IP addresses or CIDRs") from None
    return {"ATLAS_BIND_ADDRESS": address, "ATLAS_PORT": str(int(port)), "ATLAS_TRUSTED_PROXIES": proxies}


def build_id() -> str:
    spec = importlib.util.spec_from_file_location("atlas_release_policy", ROOT / "apps/api/app/release.py")
    policy = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(policy)
    metadata = policy.load_metadata(ROOT / "apps/api/app/release.json")
    if metadata.get("build_id"):
        return metadata["build_id"]
    try:
        result = subprocess.run(["git", "rev-parse", "HEAD"], cwd=ROOT, capture_output=True, text=True, check=True)
        return result.stdout.strip()
    except (FileNotFoundError, subprocess.CalledProcessError):
        return "unknown"


def generate_configuration(path: Path, method: str, *, ingress=None) -> dict[str, str]:
    if method not in {"docker_compose", "systemd"}:
        raise ValueError("Unsupported production installation method")
    if path.exists() or path.is_symlink():
        raise FileExistsError(path)
    ingress = compose_ingress_settings() if ingress is None else ingress
    content = (
        "# Atlas production bootstrap configuration. Keep this file protected.\n"
        f"POSTGRES_PASSWORD={secrets.token_hex(32)}\n"
        f"AUTH_SECRET_KEY={secrets.token_hex(48)}\n"
        f"ATLAS_DATA_ENCRYPTION_KEY={secrets.token_hex(32)}\n"
        "AUTH_COOKIE_SECURE=auto\n"
        "CORS_ORIGINS=\n"
        f"ATLAS_INSTALL_METHOD={method}\n"
        f"ATLAS_BUILD_ID={build_id()}\n"
    )
    content += "".join(f"{key}={value}\n" for key, value in ingress.items())
    # Exclusive creation also refuses symlinks and empty existing files.
    descriptor = os.open(path, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
    with os.fdopen(descriptor, "w") as output:
        os.fchmod(output.fileno(), 0o600)
        output.write(content)
    # Only non-secret ingress values leave this generator.
    return ingress


def add_data_encryption_key(path: Path) -> None:
    """Upgrade protected configuration without replacing any existing secret."""
    descriptor = os.open(path, os.O_RDWR | os.O_NOFOLLOW)
    with os.fdopen(descriptor, "r+") as output:
        fcntl.flock(output, fcntl.LOCK_EX)
        content = output.read()
        values = [line.split("=", 1)[1] for line in content.splitlines()
                  if line.startswith("ATLAS_DATA_ENCRYPTION_KEY=")]
        if values:
            if len(values) != 1 or not re.fullmatch(r"[0-9a-fA-F]{64}", values[0]):
                raise ValueError("Existing ATLAS_DATA_ENCRYPTION_KEY is invalid; refusing to replace cryptographic material")
            return
        output.seek(0, os.SEEK_END)
        output.write(("\n" if content and not content.endswith("\n") else "")
                     + f"ATLAS_DATA_ENCRYPTION_KEY={secrets.token_hex(32)}\n")
        output.flush()
        os.fsync(output.fileno())


def main():
    parser = argparse.ArgumentParser(description="Generate protected Atlas production configuration")
    parser.add_argument("--method", choices=["docker_compose", "systemd"])
    parser.add_argument("--add-data-encryption-key", action="store_true", help="Add only the missing key to an existing protected file")
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    if args.add_data_encryption_key:
        if args.method:
            parser.error("--method cannot be combined with --add-data-encryption-key")
        try:
            add_data_encryption_key(args.output)
        except (OSError, ValueError):
            raise SystemExit("Cannot add data-encryption material; check the existing file, key and permissions") from None
        print("Data-encryption configuration is ready. Existing secrets were preserved; key is not displayed.")
        return
    if not args.method:
        parser.error("--method is required for fresh configuration")
    try:
        generate_configuration(args.output, args.method)
    except FileExistsError:
        raise SystemExit("Configuration already exists; refusing to overwrite it.") from None
    print(f"Protected configuration created at {args.output}. Secrets are not displayed.")


if __name__ == "__main__":
    main()
