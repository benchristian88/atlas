"""Isolated I1 contract adapter pending the separate canonical SDK extraction.

The sole schema remains the unchanged I0 staged document. This adapter is an
application consumer, not an SDK or a permissive re-licensing of existing code.
The fixed schema identity/digest prevents a missing or changed staging contract
from silently changing package acceptance. Replace this adapter with the pinned
canonical SDK after the separately owned project and licence review exist.
"""
from __future__ import annotations

from functools import lru_cache
import hashlib
import json
import math
import os
from pathlib import Path
from urllib.parse import urlsplit

from jsonschema import Draft202012Validator, FormatChecker
from jsonschema.exceptions import ValidationError

from app.release import Version

SCHEMA_DIGEST = "e1305db294527ea6645c9bc17d0325c3cf05adf1aa23d3084f6899f0bed896c0"
SCHEMA_ID = "urn:atlas-connector-sdk:manifest:1.0"
STAGING_CONTRACT_COMPATIBILITY_VERSION = "1.0.0"
MAX_MANIFEST_BYTES = 256 * 1024


class ConnectorPackageError(ValueError):
    """Only the bounded code, never input/file/vendor errors, crosses the API."""

    def __init__(self, code: str):
        self.code = code
        super().__init__(code)


class ManifestValidationError(ConnectorPackageError):
    pass


def strict_json(raw: str | bytes, *, maximum: int = MAX_MANIFEST_BYTES):
    try:
        if len(raw.encode("utf-8") if isinstance(raw, str) else raw) > maximum:
            raise ManifestValidationError("metadata_too_large")
    except UnicodeError:
        raise ManifestValidationError("invalid_metadata") from None

    def pairs(values):
        result = {}
        for key, value in values:
            if key in result:
                raise ManifestValidationError("duplicate_metadata_key")
            result[key] = value
        return result

    def invalid_constant(_):
        raise ManifestValidationError("invalid_metadata_number")

    def finite_float(value):
        number = float(value)
        if not math.isfinite(number):
            raise ManifestValidationError("invalid_metadata_number")
        return number

    try:
        return json.loads(raw, object_pairs_hook=pairs, parse_constant=invalid_constant,
                          parse_float=finite_float)
    except (ValueError, UnicodeError, RecursionError) as exc:
        if isinstance(exc, ManifestValidationError):
            raise
        raise ManifestValidationError("invalid_metadata") from None


def staging_contract_root() -> Path:
    # Source checkout and standard packaged release retain the original document
    # at its original path; there is no copied competing schema in app source.
    deployed_schema = os.environ.get("ATLAS_CONNECTOR_SCHEMA_FILE")
    if deployed_schema:
        # Installer-controlled deployment configuration, never a request field.
        # Authenticity still requires the same exact staged schema digest.
        path = Path(deployed_schema)
        if not path.is_absolute() or path.name != "connector-manifest-v1.schema.json" or path.is_symlink():
            raise ManifestValidationError("sdk_contract_unavailable")
        return path.parent
    for ancestor in Path(__file__).resolve().parents:
        candidate = ancestor / "docs/architecture/integrations/contracts"
        if candidate.is_dir():
            return candidate
    raise ManifestValidationError("sdk_contract_unavailable")


@lru_cache(maxsize=1)
def manifest_validator() -> Draft202012Validator:
    try:
        raw = (staging_contract_root() / "connector-manifest-v1.schema.json").read_bytes()
    except OSError:
        raise ManifestValidationError("sdk_contract_unavailable") from None
    if hashlib.sha256(raw).hexdigest() != SCHEMA_DIGEST:
        raise ManifestValidationError("sdk_contract_changed")
    schema = strict_json(raw)
    if schema.get("$id") != SCHEMA_ID:
        raise ManifestValidationError("sdk_contract_changed")
    return Draft202012Validator(schema, format_checker=FormatChecker())


def version_in_range(version: str, bounds: dict) -> bool:
    current, lower, upper = Version(version), Version(bounds["minimum"]), Version(bounds["exclusive_maximum"])
    return lower <= current < upper


def _unique(rows: list[dict], name: str) -> dict:
    result = {row["key"]: row for row in rows}
    if len(result) != len(rows):
        raise ManifestValidationError("duplicate_" + name)
    return result


def _https_url(url: str) -> None:
    try:
        parsed = urlsplit(url)
        if (parsed.scheme != "https" or not parsed.hostname or parsed.username is not None
                or parsed.password is not None or parsed.port not in (None, 443)
                or parsed.fragment or any(ord(char) < 33 for char in url)):
            raise ValueError
    except ValueError:
        raise ManifestValidationError("unsafe_metadata_url") from None


def validate_manifest(manifest: dict, *, activation: bool = False) -> dict:
    try:
        manifest_validator().validate(manifest)
        Version(manifest["version"])
        for key in ("sdk", "atlas"):
            bounds = manifest["compatibility"][key]
            if not Version(bounds["minimum"]) < Version(bounds["exclusive_maximum"]):
                raise ManifestValidationError("invalid_version_range")
        bounds = manifest["compatibility"]["runtime"]["baseline"]
        if not Version(bounds["minimum"]) < Version(bounds["exclusive_maximum"]):
            raise ManifestValidationError("invalid_version_range")
        _https_url(manifest["display"]["documentation_uri"])
        _https_url(manifest["distribution"]["asset_uri"])
        _https_url(manifest["distribution"]["provenance"]["evidence_uri"])
        classes = _unique(manifest["object_classes"], "object_class")
        fields = _unique(manifest["connection_fields"], "connection_field")
        _unique(manifest["facts"], "fact")
        _unique(manifest["relationship_classes"], "relationship_class")
        _unique(manifest["discovery_scopes"], "scope")
        dependencies = [(row["kind"], row["name"]) for row in manifest["implementation"]["dependencies"]]
        if len(dependencies) != len(set(dependencies)):
            raise ManifestValidationError("duplicate_dependency")
        for field in fields.values():
            condition = field.get("visible_when")
            if condition:
                control = fields.get(condition["field"])
                if (control is None or control["secret"] or control["key"] == field["key"]
                        or "visible_when" in control):
                    raise ManifestValidationError("invalid_field_visibility")
                if "options" in control and condition["equals"] not in control["options"]:
                    raise ManifestValidationError("invalid_field_visibility")
            if field["type"] == "enum" and "default" in field and field["default"] not in field["options"]:
                raise ManifestValidationError("invalid_field_default")
            constraints = field.get("validation", {})
            for lower, upper in (("min_length", "max_length"), ("minimum", "maximum")):
                if lower in constraints and upper in constraints and constraints[lower] > constraints[upper]:
                    raise ManifestValidationError("invalid_field_bounds")
        canonical = {"status", "name", "hostname", "asset_type", "vlan_id", "cidr", "gateway", "ip_address", "mac_address"}
        for fact in manifest["facts"]:
            namespace, suffix = fact["key"].split(".", 1)
            if (not set(fact["object_classes"]) <= classes.keys() or suffix in canonical
                    or any(key.split(".", 1)[0] != namespace for key in fact["object_classes"])):
                raise ManifestValidationError("invalid_fact_declaration")
        for relationship in manifest["relationship_classes"]:
            for side in ("source_object_classes", "target_object_classes"):
                if (not set(relationship[side]) <= classes.keys()
                        or any(classes[key]["kind"] != "asset" for key in relationship[side])):
                    raise ManifestValidationError("invalid_relationship_class")
        for scope in manifest["discovery_scopes"]:
            if (not set(scope["object_classes"]) <= classes.keys()
                    or scope["required"] and not scope["default_enabled"]):
                raise ManifestValidationError("invalid_scope")
            for selection in scope.get("filters", []):
                if not set(selection["default_values"]) <= set(selection["allowed_values"]):
                    raise ManifestValidationError("invalid_scope_filter")
        if manifest["publisher"]["id"] != manifest["distribution"]["provenance"]["publisher_id"]:
            raise ManifestValidationError("publisher_mismatch")
        if activation and manifest["source_versions"]["qualification"] != "qualified":
            raise ManifestValidationError("package_not_qualified")
    except (ValidationError, KeyError, TypeError, ValueError, RecursionError) as exc:
        if isinstance(exc, ManifestValidationError):
            raise
        raise ManifestValidationError("invalid_manifest") from None
    return manifest
