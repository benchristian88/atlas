"""Structural tests only. Real cryptographic tests live in a separate module."""
from dataclasses import FrozenInstanceError
import hashlib
import json
from pathlib import Path

import pytest

from app.services.official_catalogue import MAX_INTEGER
from app.services.official_catalogue_selection import (
    MAX_POINTER_BYTES, OfficialCatalogueSelectionError, parse_official_catalogue_selection as parse,
)

FIXTURES = Path(__file__).parent / "fixtures/official_catalogue"
RAW = (FIXTURES / "current.json").read_bytes()
DIGEST = "a275f63d0ac818a193826478328ee324be62353addc5c97a2ed0a28d217b5372"


def canonical(document):
    return (json.dumps(document, sort_keys=True, indent=2, ensure_ascii=False, allow_nan=False) + "\n").encode()


def changed(**values):
    return canonical({**json.loads(RAW), **values})


def test_genuine_canonical_pointer_retains_original_bytes_and_immutable_values():
    parsed = parse(RAW)
    assert hashlib.sha256(RAW).hexdigest() == DIGEST == parsed.pointer_sha256
    assert parsed.source_bytes is RAW
    assert parsed.schema_version == "1.0" and parsed.sequence == 1
    assert parsed.release_tag == "catalogue-000001"
    assert parsed.release_id == 421426993 and parsed.asset_id == 667867351
    assert parsed.previous_pointer_sha256 is None
    assert parsed.sha256 == "55533ca67e7e9a14f82961e0a8c34ad78e2596049b3db02fde787494e3975afd"
    with pytest.raises(FrozenInstanceError):
        parsed.sequence = 2
    with pytest.raises(FrozenInstanceError):
        parsed.source_bytes = b"changed"
    assert parse(RAW).sequence == 1


def test_later_sequence_and_safe_integer_bound_are_structural_only():
    parsed = parse(changed(sequence=2, release_tag="catalogue-000002", previous_pointer_sha256="a" * 64))
    assert parsed.sequence == 2 and parsed.previous_pointer_sha256 == "a" * 64
    for field in ("sequence", "release_id", "asset_id"):
        values = {field: MAX_INTEGER}
        if field == "sequence":
            values.update(release_tag=f"catalogue-{MAX_INTEGER:06d}", previous_pointer_sha256="b" * 64)
        assert getattr(parse(changed(**values)), field) == MAX_INTEGER


@pytest.mark.parametrize("raw", [None, "{}", bytearray(RAW), memoryview(RAW), b"", b" " * (MAX_POINTER_BYTES + 1)])
def test_original_bytes_and_size_required(raw):
    with pytest.raises(OfficialCatalogueSelectionError):
        parse(raw)


@pytest.mark.parametrize("field", list(json.loads(RAW)))
def test_every_field_required(field):
    value = json.loads(RAW)
    del value[field]
    with pytest.raises(OfficialCatalogueSelectionError, match="pointer_fields"):
        parse(canonical(value))


@pytest.mark.parametrize("raw", [
    changed(extra="ignored?"), b"[]\n", b"null\n", b"true\n", b"1\n", b'"text"\n',
    RAW.replace(b'"sequence": 1', b'"sequence": 1, "sequence": 1'),
    RAW.replace(b'"sequence": 1', b'"sequence": 1, "\\u0073equence": 1'),
    RAW + b"{}", RAW + b"\xff", b"\xef\xbb\xbf" + RAW,
    RAW.decode().encode("utf-16"), RAW.decode().encode("utf-32"),
    b"[" * 500 + b"]" * 500,
    RAW.replace(b'"sequence": 1', b'"sequence": NaN'),
    RAW.replace(b'"sequence": 1', b'"sequence": Infinity'),
    RAW.replace(b'"sequence": 1', b'"sequence": -Infinity'),
    RAW.replace(b'"sequence": 1', b'"sequence": 1e999'),
    RAW.replace(b'"sequence": 1', b'"sequence": +1'),
    RAW.replace(b'"sequence": 1', b'"sequence": 01'),
    RAW.replace(b'"sequence": 1', b'"sequence": -0'),
    RAW.replace(b'"sequence": 1', b'"sequence": 0x1'),
])
def test_ambiguous_or_malformed_json_rejected(raw):
    with pytest.raises(OfficialCatalogueSelectionError):
        parse(raw)


@pytest.mark.parametrize("raw", [
    RAW[:-1], RAW + b"\n", b" " + RAW, RAW.replace(b"\n", b"\r\n"),
    RAW.replace(b"  ", b"    "), json.dumps(json.loads(RAW)).encode() + b"\n",
    (json.dumps(dict(reversed(list(json.loads(RAW).items()))), indent=2) + "\n").encode(),
    RAW.replace(b'"schema_version"', b'"schema_\\u0076ersion"'),
    RAW.replace(b"catalogue-000001", b"catalogue-00000\\u0031"),
])
def test_exact_canonical_bytes_required(raw):
    with pytest.raises(OfficialCatalogueSelectionError, match="noncanonical_pointer"):
        parse(raw)


@pytest.mark.parametrize("field", ["sequence", "release_id", "asset_id"])
@pytest.mark.parametrize("value", [True, False, 1.0, "1", None, 0, -1, MAX_INTEGER + 1, [], {}])
def test_literal_positive_safe_integer_required(field, value):
    with pytest.raises(OfficialCatalogueSelectionError, match="pointer_integer"):
        parse(changed(**{field: value}))


@pytest.mark.parametrize("token", [b"1e0", b"1.0", b"1E+0", b"1.00000000000000001"])
def test_float_source_tokens_never_become_integer_identity(token):
    with pytest.raises(OfficialCatalogueSelectionError, match="pointer_integer"):
        parse(RAW.replace(b'"sequence": 1', b'"sequence": ' + token))


@pytest.mark.parametrize("schema", [1.0, 1, None, True, "1", "1.1", [], {}])
def test_schema_is_literal_supported_string(schema):
    with pytest.raises(OfficialCatalogueSelectionError, match="pointer_schema"):
        parse(changed(schema_version=schema))


@pytest.mark.parametrize("tag", ["catalogue-000002", "catalogue-1", "catalogue-0000001", "catalogue-000001\n", 1, None, []])
def test_exact_sequence_tag(tag):
    with pytest.raises(OfficialCatalogueSelectionError, match="pointer_tag"):
        parse(changed(release_tag=tag))


@pytest.mark.parametrize("digest", ["A" * 64, "a" * 63, "a" * 65, "g" * 64,
    "sha256:" + "a" * 64, "a" * 64 + "\n", None, 1, True, {}, []])
@pytest.mark.parametrize("field", ["sha256", "previous_pointer_sha256"])
def test_lowercase_exact_sha256_required(field, digest):
    values = {field: digest}
    if field == "previous_pointer_sha256":
        values.update(sequence=2, release_tag="catalogue-000002")
    with pytest.raises(OfficialCatalogueSelectionError, match="pointer_digest|pointer_predecessor"):
        parse(changed(**values))


def test_sequence_one_predecessor_must_be_null():
    with pytest.raises(OfficialCatalogueSelectionError, match="pointer_predecessor"):
        parse(changed(previous_pointer_sha256="a" * 64))


def test_later_sequence_cannot_omit_predecessor():
    value = json.loads(changed(sequence=2, release_tag="catalogue-000002"))
    del value["previous_pointer_sha256"]
    with pytest.raises(OfficialCatalogueSelectionError, match="pointer_fields"):
        parse(canonical(value))


def test_diagnostics_never_echo_source():
    with pytest.raises(OfficialCatalogueSelectionError) as caught:
        parse(changed(sha256="untrusted-secret-marker"))
    assert "untrusted-secret-marker" not in str(caught.value)
