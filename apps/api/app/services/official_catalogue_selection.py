"""Strict selection structure only; neither authenticity nor acceptance authority."""
from __future__ import annotations

from dataclasses import dataclass, field
import hashlib
import json
import re

from atlas_connector_sdk.contracts import ContractError, strict_json

from app.services.connector_contracts import ConnectorPackageError
from app.services.official_catalogue import MAX_INTEGER

MAX_POINTER_BYTES = 1024
POINTER_FIELDS = {"asset_id", "previous_pointer_sha256", "release_id", "release_tag",
                  "schema_version", "sequence", "sha256"}


class OfficialCatalogueSelectionError(ConnectorPackageError):
    """Stable diagnostic only; never includes untrusted source data."""


@dataclass(frozen=True, slots=True)
class StructurallyValidSelection:
    """Immutable decoded values and original bytes, with no trust implication."""
    source_bytes: bytes = field(repr=False)
    schema_version: str
    sequence: int
    release_tag: str
    release_id: int
    asset_id: int
    sha256: str
    previous_pointer_sha256: str | None

    @property
    def pointer_sha256(self) -> str:
        return hashlib.sha256(self.source_bytes).hexdigest()


def _require(condition: bool, code: str) -> None:
    if not condition:
        raise OfficialCatalogueSelectionError(code)


def _digest(value) -> bool:
    return type(value) is str and re.fullmatch(r"[a-f0-9]{64}", value) is not None


def parse_official_catalogue_selection(raw: bytes) -> StructurallyValidSelection:
    """Bounded SDK strict JSON, then exact producer canonical-byte comparison.

    Explicit UTF-8 decoding excludes Python's automatic UTF-16/32 detection.
    Literal integer checks exclude bool/float, including exponent notation; no
    source value is coerced into an identity before canonical comparison.
    """
    _require(type(raw) is bytes, "pointer_bytes_required")
    _require(0 < len(raw) <= MAX_POINTER_BYTES, "pointer_size")
    try:
        value = strict_json(raw.decode("utf-8"), maximum=MAX_POINTER_BYTES)
        _require(type(value) is dict and value.keys() == POINTER_FIELDS, "pointer_fields")
        _require(type(value["schema_version"]) is str and value["schema_version"] == "1.0", "pointer_schema")
        for name in ("sequence", "release_id", "asset_id"):
            _require(type(value[name]) is int and 0 < value[name] <= MAX_INTEGER, "pointer_integer")
        _require(value["release_tag"] == f"catalogue-{value['sequence']:06d}", "pointer_tag")
        _require(_digest(value["sha256"]), "pointer_digest")
        previous = value["previous_pointer_sha256"]
        _require((value["sequence"] == 1 and previous is None)
                 or (value["sequence"] > 1 and _digest(previous)), "pointer_predecessor")
        canonical = (json.dumps(value, sort_keys=True, indent=2, ensure_ascii=False,
                                allow_nan=False) + "\n").encode("utf-8")
        _require(canonical == raw, "noncanonical_pointer")
    except OfficialCatalogueSelectionError:
        raise
    except ContractError as error:
        raise OfficialCatalogueSelectionError(error.code) from None
    except (ValueError, TypeError, UnicodeError, RecursionError, OverflowError):
        raise OfficialCatalogueSelectionError("invalid_pointer_json") from None
    return StructurallyValidSelection(source_bytes=raw, **value)
