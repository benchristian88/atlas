"""Root-only native preparation of fixed release-approved bootstrap packages."""
import os
from pathlib import Path

from app.services.connector_catalogue import catalogue
from app.services.connector_store import PackageStore


def main():
    if os.geteuid() != 0:
        raise SystemExit("Native Connector staging requires the installation authority")
    store = PackageStore(Path("/var/lib/atlas-connectors"))
    # No input paths, URLs or package selectors. Do not change DB activation.
    _, packages = catalogue._load()
    for package in packages:
        if package.package_available:
            store.install(package, catalogue.verifier())
    print("Approved bootstrap packages verified and staged; activation remains an administrator action.")


if __name__ == "__main__":
    main()
