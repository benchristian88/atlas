"""Offline structural validation of Official Connector Catalogue v1 bytes.

This is NOT a trusted catalogue provider or verification evidence. No result is
connected to catalogue APIs, package installation or activation. The original
bytes must be independently authenticated before any future consumer trusts them.
Envelope policy and serialization match atlas-connectors/tools/build_catalogue.py;
the pinned SDK remains the sole owner of the combined Manifest grammar.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime
import json
import math
import re

from atlas_connector_sdk.contracts import ContractError, strict_json, validate_manifest

from app.services.connector_contracts import ConnectorPackageError

MAX_CATALOGUE_BYTES = 4_194_304
MAX_ENTRY_BYTES = 262_144
MAX_ENTRIES = 200
MAX_INTEGER = 2**53 - 1
# The v1 Manifest has no recursive containers. Reject hostile nesting before
# allocating a decoded tree or invoking recursive schema/serialization code.
MAX_JSON_DEPTH = 32
PUBLISHER = "atlas-official"
REPOSITORY = "benchristian88/atlas-connectors"
PACKAGE_WORKFLOW = ".github/workflows/release.yml"
CATALOGUE_FIELDS = {"schema_version", "sequence", "generated_at", "publisher_id", "repository", "entries"}
ENTRY_FIELDS = {"status", "release_tag", "release_asset_id", "manifest"}


class OfficialCatalogueError(ConnectorPackageError):
    """Stable diagnostic code only; never includes untrusted input."""


@dataclass(frozen=True)
class StructurallyValidCatalogue:
    """Parsed metadata only, with no package availability or trust authority.

    document is ordinary caller-owned data. Mutating it does not change the
    source_bytes snapshot and cannot authenticate it. Future verification must
    bind its result to source_bytes, never a reserialized or modified document.
    """

    source_bytes: bytes = field(repr=False)
    document: dict = field(repr=False)


def _check_depth(raw: bytes) -> None:
    depth, in_string, escaped = 0, False, False
    for char in raw:
        if in_string:
            if escaped:
                escaped = False
            elif char == 92:  # backslash
                escaped = True
            elif char == 34:
                in_string = False
        elif char == 34:
            in_string = True
        elif char in (91, 123):
            depth += 1
            if depth > MAX_JSON_DEPTH:
                raise OfficialCatalogueError("catalogue_nesting_too_deep")
        elif char in (93, 125):
            depth -= 1
            if depth < 0:
                raise OfficialCatalogueError("invalid_catalogue_json")
    # The SDK parser handles grammar, unmatched delimiters and string escaping.


def _check_numbers(value) -> None:
    if isinstance(value, dict):
        for item in value.values():
            _check_numbers(item)
    elif isinstance(value, list):
        for item in value:
            _check_numbers(item)
    elif type(value) is int and abs(value) > MAX_INTEGER:
        raise OfficialCatalogueError("invalid_catalogue_json")
    elif type(value) is float and not math.isfinite(value):
        raise OfficialCatalogueError("invalid_catalogue_json")


def _check_canonical_size(value, maximum: int, code: str) -> None:
    # Exactly the producer's UTF-8 json.dumps(sort_keys=True, indent=2,
    # ensure_ascii=False, allow_nan=False) + '\n'. Count chunks to stop early;
    # never allocate a potentially expanded whole canonical document.
    size = 1  # terminal newline
    encoder = json.JSONEncoder(sort_keys=True, indent=2, ensure_ascii=False, allow_nan=False)
    for chunk in encoder.iterencode(value):
        size += len(chunk.encode("utf-8"))
        if size > maximum:
            raise OfficialCatalogueError(code)


def _positive_integer(value) -> bool:
    return type(value) is int and 0 < value <= MAX_INTEGER


def _validate_entry(entry: dict) -> tuple[str, str]:
    if not isinstance(entry, dict) or entry.keys() != ENTRY_FIELDS:
        raise OfficialCatalogueError("invalid_release_fields")
    _check_canonical_size(entry, MAX_ENTRY_BYTES, "release_entry_too_large")
    if not isinstance(entry["status"], str) or entry["status"] not in {"active", "withdrawn"}:
        raise OfficialCatalogueError("invalid_release_status")
    if not _positive_integer(entry["release_asset_id"]):
        raise OfficialCatalogueError("invalid_release_asset_id")
    manifest = entry["manifest"]
    if not isinstance(manifest, dict):
        raise OfficialCatalogueError("invalid_manifest")
    validate_manifest(manifest)
    connector, version = manifest["id"], manifest["version"]
    if re.fullmatch(r"[a-z][a-z0-9]*(?:[._-][a-z0-9]+)*", connector) is None:
        raise OfficialCatalogueError("invalid_connector_id")
    distribution = manifest["distribution"]
    provenance = distribution["provenance"]
    if manifest["publisher"]["id"] != PUBLISHER or provenance["publisher_id"] != PUBLISHER:
        raise OfficialCatalogueError("invalid_official_publisher")
    if provenance.get("repository") != REPOSITORY:
        raise OfficialCatalogueError("invalid_official_repository")
    if provenance["method"] != "github-artifact-attestation-sigstore":
        raise OfficialCatalogueError("invalid_official_provenance")
    if provenance.get("workflow") != PACKAGE_WORKFLOW:
        raise OfficialCatalogueError("invalid_release_workflow")
    if provenance.get("evidence_uri") != f"https://github.com/{REPOSITORY}/attestations":
        raise OfficialCatalogueError("invalid_attestation_uri")
    if re.fullmatch(r"[a-f0-9]{40}", provenance["source_commit"]) is None:
        raise OfficialCatalogueError("invalid_source_commit")
    if re.fullmatch(r"sha256:[a-f0-9]{64}", distribution["bundle_digest"]) is None:
        raise OfficialCatalogueError("invalid_bundle_digest")
    tag = f"{connector}-v{version}"
    if entry["release_tag"] != tag:
        raise OfficialCatalogueError("invalid_release_tag")
    expected_uri = f"https://github.com/{REPOSITORY}/releases/download/{tag}/{connector}-{version}.tar.gz"
    if distribution["asset_uri"] != expected_uri:
        raise OfficialCatalogueError("invalid_release_asset_uri")
    return connector, version


def _validate_document(document: dict) -> None:
    if not isinstance(document, dict) or document.keys() != CATALOGUE_FIELDS:
        raise OfficialCatalogueError("invalid_catalogue_fields")
    if document["schema_version"] != "1.0":
        raise OfficialCatalogueError("invalid_catalogue_schema")
    if not _positive_integer(document["sequence"]):
        raise OfficialCatalogueError("invalid_catalogue_sequence")
    if document["publisher_id"] != PUBLISHER:
        raise OfficialCatalogueError("invalid_official_publisher")
    if document["repository"] != REPOSITORY:
        raise OfficialCatalogueError("invalid_official_repository")
    timestamp = document["generated_at"]
    if (not isinstance(timestamp, str) or re.fullmatch(
            r"[0-9]{4}-[0-9]{2}-[0-9]{2}T[0-9]{2}:[0-9]{2}:[0-9]{2}Z", timestamp) is None):
        raise OfficialCatalogueError("invalid_catalogue_timestamp")
    try:
        datetime.strptime(timestamp, "%Y-%m-%dT%H:%M:%SZ")
    except ValueError:
        raise OfficialCatalogueError("invalid_catalogue_timestamp") from None
    entries = document["entries"]
    if not isinstance(entries, list) or len(entries) > MAX_ENTRIES:
        raise OfficialCatalogueError("invalid_catalogue_entry_count")
    _check_numbers(document)
    _check_canonical_size(document, MAX_CATALOGUE_BYTES, "catalogue_too_large")
    identities, assets = [], set()
    for entry in entries:
        identities.append(_validate_entry(entry))
        if entry["release_asset_id"] in assets:
            raise OfficialCatalogueError("duplicate_release_asset_id")
        assets.add(entry["release_asset_id"])
    if len(set(identities)) != len(identities):
        raise OfficialCatalogueError("duplicate_connector_version")
    if identities != sorted(identities):
        raise OfficialCatalogueError("unsorted_catalogue_entries")


def parse_official_catalogue(raw: bytes) -> StructurallyValidCatalogue:
    """Validate bounded untrusted bytes without I/O or granting authenticity."""
    if not isinstance(raw, bytes):
        raise OfficialCatalogueError("catalogue_bytes_required")
    if len(raw) > MAX_CATALOGUE_BYTES:
        raise OfficialCatalogueError("catalogue_too_large")
    if raw.startswith(b"\xef\xbb\xbf"):
        raise OfficialCatalogueError("invalid_catalogue_json")
    try:
        _check_depth(raw)
        # Decode explicitly: json.loads(bytes) would also accept UTF-16/32/BOM.
        document = strict_json(raw.decode("utf-8"), maximum=MAX_CATALOGUE_BYTES)
        _validate_document(document)
    except OfficialCatalogueError:
        raise
    except ContractError as error:
        raise OfficialCatalogueError(error.code) from None
    except (ValueError, TypeError, KeyError, UnicodeError, RecursionError, OverflowError):
        raise OfficialCatalogueError("invalid_catalogue_json") from None
    return StructurallyValidCatalogue(raw, document)
