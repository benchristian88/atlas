"""Release-packaged catalogue truth, independent from installed DB state."""
from __future__ import annotations

from dataclasses import dataclass
import hashlib
from pathlib import Path
import re
from typing import Mapping

from app.release import Version, build_metadata
from app.services.connector_contracts import (ConnectorPackageError, SDK_VERSION,
    bootstrap_manifest_root, strict_json, validate_manifest, version_in_range)
from app.services.connector_verification import BootstrapReleaseVerifier, OfficialBundleVerifier

BOOTSTRAP_DIGEST = "641361fd2a41ab5f36ff542b9fef7f8b5080cffc3c71b9016bcad8a4acee71ed"
BOOTSTRAP_PATH = Path(__file__).resolve().parents[1] / "integration_bootstrap/catalogue.json"


class CatalogueUnavailable(ConnectorPackageError):
    pass


@dataclass(frozen=True)
class CataloguePackage:
    connector_id: str
    version: str | None
    bundle_digest: str | None
    manifest: dict
    source: str
    package_available: bool
    archive_path: Path | None = None
    display: dict | None = None


def compatibility(manifest: dict, runtime: dict | None, *, atlas_version: str | None = None) -> dict:
    """Evaluate version bounds and exact approved dependencies without mutation."""
    validate_manifest(manifest)
    atlas_version = atlas_version or build_metadata()["version"]
    if (not version_in_range(atlas_version, manifest["compatibility"]["atlas"])
            or not version_in_range(SDK_VERSION, manifest["compatibility"]["sdk"])):
        return {"state": "incompatible", "message": "This package requires a different Atlas or protocol SDK version."}
    if not isinstance(runtime, dict) or runtime.get("status", runtime.get("state")) not in ("healthy", "ready"):
        return {"state": "runtime_unavailable", "message": "The local runtime must be healthy before installing this package."}
    capabilities = runtime.get("capabilities") or runtime
    if not isinstance(capabilities, dict):
        return {"state": "incompatible", "message": "The runtime capability report is invalid."}
    protocols = capabilities.get("aip_versions", runtime.get("aip_versions", []))
    if not isinstance(protocols, list) or any(not isinstance(item, str) for item in protocols):
        return {"state": "incompatible", "message": "The runtime protocol report is invalid."}
    if not set(manifest["compatibility"]["aip"]) <= set(protocols):
        return {"state": "incompatible", "message": "The runtime does not support this package's protocol version."}
    advertised = capabilities.get("capabilities", [])
    if isinstance(advertised, str):
        advertised = [advertised]
    protocol = capabilities.get("protocol_version", runtime.get("protocol_version"))
    required_capability = manifest["compatibility"]["runtime"]["capability"]
    if not isinstance(advertised, list) or (required_capability not in advertised and protocol != required_capability):
        return {"state": "incompatible", "message": "The runtime does not support this package's control protocol."}
    baseline_record = runtime.get("baseline")
    baseline = (runtime.get("baseline_version") or capabilities.get("baseline_version")
                or (baseline_record.get("version") if isinstance(baseline_record, dict) else None))
    try:
        baseline_matches = baseline is not None and version_in_range(baseline, manifest["compatibility"]["runtime"]["baseline"])
    except ValueError:
        baseline_matches = False
    if not baseline_matches:
        return {"state": "runtime_update_required", "message": "This package requires a newer approved runtime baseline."}
    if manifest["implementation"]["runtime"] != capabilities.get("runtime_kind", runtime.get("runtime_kind", "ansible")):
        return {"state": "incompatible", "message": "This package requires a different runtime implementation."}
    actual = capabilities.get("dependencies", runtime.get("dependencies", []))
    if isinstance(actual, dict):
        # Python version maps carry no verified artefact digest. Collections
        # have canonical installed-content identities from validated health.
        actual = []
        collections = capabilities.get("collections", {})
        if not isinstance(collections, dict) or len(collections) > 32:
            return {"state": "runtime_update_required", "message": "The approved dependency baseline could not be confirmed."}
        for name, identity in collections.items():
            if (isinstance(name, str) and re.fullmatch(r"[a-z][a-z0-9_]{0,63}\.[a-z][a-z0-9_]{0,63}", name)
                    and isinstance(identity, dict) and identity.get("state") == "compatible"
                    and isinstance(identity.get("version"), str)
                    and isinstance(identity.get("digest"), str)
                    and re.fullmatch(r"sha256:[a-f0-9]{64}", identity["digest"])):
                actual.append({"kind": "collection", "name": name, "version": identity["version"], "digest": identity["digest"]})
    if not isinstance(actual, list):
        return {"state": "runtime_update_required", "message": "The approved dependency baseline could not be confirmed."}
    identities = {(row.get("kind"), row.get("name"), row.get("version"), row.get("digest"))
                  for row in actual if isinstance(row, dict)}
    required = {(row["kind"], row["name"], row["version"], row["digest"])
                for row in manifest["implementation"]["dependencies"]}
    if not required <= identities:
        return {"state": "runtime_update_required", "message": "Required dependencies are outside the approved runtime baseline."}
    return {"state": "compatible", "message": "Compatible with the approved local runtime baseline."}


def accepted_official_metadata(db):
    """Read-only global metadata; deliberately never returned by get/install.

    B2 may project lifecycle/compatibility later. An accepted catalogue alone
    cannot make executable packages available to the existing bootstrap facade.
    """
    from app.models import ConnectorCatalogueRevision, ConnectorCatalogueState
    from app.services.official_catalogue import parse_official_catalogue
    state = db.get(ConnectorCatalogueState, 1)
    if state is None or state.highest_sequence is None:
        return []
    revision = db.get(ConnectorCatalogueRevision, state.highest_sequence)
    return [{"connector_id": entry["manifest"]["id"], "version": entry["manifest"]["version"],
             "status": entry["status"], "manifest": entry["manifest"], "source": "official",
             "package_available": False, "supported_actions": []}
            for entry in parse_official_catalogue(revision.original_bytes).document["entries"]]


class CatalogueService:
    def __init__(self, index_path: Path | None = None, *, expected_digest: str = BOOTSTRAP_DIGEST):
        self.index_path = index_path or BOOTSTRAP_PATH
        self.expected_digest = expected_digest

    def _load(self) -> tuple[dict, list[CataloguePackage]]:
        try:
            raw = self.index_path.read_bytes()
            if hashlib.sha256(raw).hexdigest() != self.expected_digest:
                raise CatalogueUnavailable("bootstrap_catalogue_changed")
            index = strict_json(raw)
            if (set(index) != {"catalogue_version", "release_identity", "entries"}
                    or index["catalogue_version"] != "1.0" or not isinstance(index["entries"], list)
                    or len(index["entries"]) > 100
                    or not isinstance(index["release_identity"], str)
                    or not re.fullmatch(r"[A-Za-z0-9._+-]{1,128}", index["release_identity"])):
                raise CatalogueUnavailable("invalid_bootstrap_catalogue")
            packages, identities = [], set()
            for entry in index["entries"]:
                if (not isinstance(entry, dict) or set(entry) != {"connector_id", "name", "description",
                        "category", "icon_key", "publisher", "trust_tier", "licence", "manifest_ref",
                        "manifest_digest", "package"}
                        or any(not isinstance(entry.get(key), str) or not 1 <= len(entry[key]) <= maximum
                               for key, maximum in (("name", 255), ("description", 1000),
                                    ("publisher", 255), ("licence", 255), ("icon_key", 100)))
                        or entry["category"] not in {"virtualization", "containers", "networking"}):
                    raise CatalogueUnavailable("invalid_bootstrap_catalogue")
                if not re.fullmatch(r"[a-z][a-z0-9]*(?:[._-][a-z0-9]+)*", entry["connector_id"]):
                    raise CatalogueUnavailable("invalid_bootstrap_catalogue")
                filename = entry["manifest_ref"]
                if not re.fullmatch(r"[a-z0-9_-]+\.json", filename):
                    raise CatalogueUnavailable("invalid_bootstrap_catalogue")
                manifest_raw = (bootstrap_manifest_root() / "manifests" / filename).read_bytes()
                if hashlib.sha256(manifest_raw).hexdigest() != entry["manifest_digest"]:
                    raise CatalogueUnavailable("bootstrap_manifest_changed")
                manifest = validate_manifest(strict_json(manifest_raw))
                if manifest["id"] != entry["connector_id"] or entry["trust_tier"] != "atlas_official":
                    raise CatalogueUnavailable("invalid_bootstrap_catalogue")
                package = entry["package"]
                version, digest, archive_path = None, None, None
                if package is not None:
                    # Only fixed local release-packaged archives are supported.
                    # Neither remote URLs nor arbitrary upload/path fields exist.
                    if set(package) != {"version", "bundle_digest", "archive"}:
                        raise CatalogueUnavailable("invalid_bootstrap_package")
                    if not re.fullmatch(r"[A-Za-z0-9._-]+\.tar\.gz", package["archive"]):
                        raise CatalogueUnavailable("invalid_bootstrap_package")
                    version, digest = package["version"], package["bundle_digest"]
                    validate_manifest(manifest, activation=True)
                    if version != manifest["version"] or digest != manifest["distribution"]["bundle_digest"]:
                        raise CatalogueUnavailable("bootstrap_package_mismatch")
                    archive_path = self.index_path.parent / "bundles" / package["archive"]
                identity = (entry["connector_id"], version)
                if identity in identities:
                    raise CatalogueUnavailable("duplicate_catalogue_identity")
                identities.add(identity)
                packages.append(CataloguePackage(entry["connector_id"], version, digest, manifest,
                    "bootstrap", package is not None, archive_path, entry))
            return index, packages
        except (OSError, KeyError, TypeError, ValueError, RecursionError) as exc:
            if isinstance(exc, ConnectorPackageError):
                raise
            raise CatalogueUnavailable("bootstrap_catalogue_unavailable") from None

    def get(self, connector_id: str, version: str | None = None) -> CataloguePackage:
        _, packages = self._load()
        matching = [package for package in packages if package.connector_id == connector_id
                    and (version is None or package.version == version)]
        if not matching:
            raise CatalogueUnavailable("connector_not_in_catalogue")
        return max(matching, key=lambda package: Version(package.version or "0.0.0-0"))

    def verifier(self) -> OfficialBundleVerifier:
        index, packages = self._load()
        approved = frozenset((package.connector_id, package.version, package.bundle_digest)
                             for package in packages if package.package_available)
        return OfficialBundleVerifier(BootstrapReleaseVerifier(approved, index["release_identity"]))

    def entries(self, *, runtime: dict | None = None, installed: Mapping[str, object] | None = None) -> list[dict]:
        _, packages = self._load()
        installed = installed or {}
        entries = []
        for package in packages:
            display = package.display
            current = installed.get(package.connector_id)
            installed_version = current.get("version") if isinstance(current, dict) else getattr(current, "version", None)
            if not package.package_available:
                result = {"state": "unavailable", "message": display["description"]}
                verification, actions = "metadata_only", []
            else:
                result = compatibility(package.manifest, runtime)
                verification, actions = "unavailable", []
                try:
                    # Authenticate executable availability before presenting an
                    # install action. Immutable release metadata alone does not
                    # prove that the package bytes are present and unchanged.
                    from app.services.connector_store import MAX_ARCHIVE_BYTES, _read_regular
                    self.verifier().verify(_read_regular(package.archive_path, MAX_ARCHIVE_BYTES), package)
                    verification = "verified"
                except ConnectorPackageError:
                    result = {"state": "verification_unavailable", "message": "The released package could not be verified."}
                if result["state"] == "compatible" and verification == "verified":
                    result["state"] = "installable"
                    actions = ["install"]
            if installed_version:
                if package.version and Version(package.version) > Version(installed_version):
                    if result["state"] == "installable":
                        result["state"], actions = "update_available", ["update"]
                else:
                    result = {"state": "installed", "message": "An approved package version is installed."}
                    actions = ["remove"]
            entries.append({key: display[key] for key in ("connector_id", "name", "description", "category",
                "icon_key", "publisher", "trust_tier", "licence")} | result | {
                "version": package.version, "bundle_digest": package.bundle_digest,
                "digest": package.bundle_digest.removeprefix("sha256:") if package.bundle_digest else None,
                "package_available": package.package_available, "verification_status": verification,
                "installed_version": installed_version, "supported_actions": actions,
                "source_versions": package.manifest["source_versions"] if package.package_available else {
                    "qualification": "not_qualified", "qualified_versions": [], "known_incompatible": []},
                "manifest_version": package.manifest["manifest_version"],
                "sdk_status": "canonical", "sdk_version": SDK_VERSION, "capabilities": package.manifest["capabilities"]})
        return entries

    def status(self) -> dict:
        index, _ = self._load()
        return {"source": "bootstrap", "catalogue_version": index["catalogue_version"],
                "verification_status": "metadata_verified", "refresh_supported": False,
                "message": "Offline catalogue with a pinned Proxmox connection probe. Discovery packages and remote installation remain unqualified."}


catalogue = CatalogueService()
