"""Offline B1.1 contract, publication, resource and trust boundary regressions."""
from copy import deepcopy
import hashlib
import json
from pathlib import Path
import socket

import pytest

from app.services import official_catalogue as catalogue
from app.services.official_catalogue import OfficialCatalogueError, parse_official_catalogue

FIXTURE = Path(__file__).parent / "fixtures/official_catalogue/catalogue-000001.json"
PUBLISHED_SHA256 = "55533ca67e7e9a14f82961e0a8c34ad78e2596049b3db02fde787494e3975afd"


def canonical(value):
    # Producer-defined independent measurement, including the final newline.
    return (json.dumps(value, sort_keys=True, indent=2, ensure_ascii=False, allow_nan=False) + "\n").encode("utf-8")


def compact(value):
    return json.dumps(value, separators=(",", ":"), ensure_ascii=False).encode("utf-8")


@pytest.fixture
def document():
    return json.loads(FIXTURE.read_bytes())


def release(entry, version, asset_id):
    value = deepcopy(entry)
    value["manifest"]["version"] = version
    value["release_asset_id"] = asset_id
    value["release_tag"] = f"proxmox-v{version}"
    value["manifest"]["distribution"]["asset_uri"] = (
        f"https://github.com/{catalogue.REPOSITORY}/releases/download/"
        f"proxmox-v{version}/proxmox-{version}.tar.gz"
    )
    return value


def test_published_bytes_and_complete_entry():
    raw = FIXTURE.read_bytes()
    assert len(raw) == 10585
    assert hashlib.sha256(raw).hexdigest() == PUBLISHED_SHA256
    result = parse_official_catalogue(raw)
    assert result.source_bytes is raw
    assert result.document.keys() == catalogue.CATALOGUE_FIELDS
    assert result.document["schema_version"] == "1.0"
    assert result.document["sequence"] == 1
    assert result.document["generated_at"] == "2026-10-18T16:04:26Z"
    assert "expires_at" not in result.document
    entry, = result.document["entries"]
    assert entry["status"] == "active"
    assert (entry["manifest"]["id"], entry["manifest"]["version"]) == ("proxmox", "0.2.0")
    assert len(canonical(entry)) <= catalogue.MAX_ENTRY_BYTES
    assert canonical(result.document) == raw
    # One frozen copy covers both independently downloaded, identical assets.
    expectations = json.loads(FIXTURE.with_name("publication.json").read_bytes())
    assert set(expectations["assets"]) == {"catalogue.json", "catalogue-000001.json"}
    for asset in expectations["assets"].values():
        assert asset["bytes"] == len(raw)
        assert asset["sha256"] == hashlib.sha256(raw).hexdigest()


@pytest.mark.parametrize("raw", [
    b"", b"{", b"{} {}", b'{"a":1,}', b"[]", b"null", b"true", b'"text"', b"123",
    b"\xff", b"\xef\xbb\xbf{}", "{}".encode("utf-16"), "{}".encode("utf-32"),
    b'{"a":1,"a":2}', b'{"a":1,"\\u0061":2}',
    b'{"nested":{"key":1,"k\\u0065y":2}}',
    b'{"a":NaN}', b'{"a":Infinity}', b'{"a":-Infinity}', b'{"a":1e9999}',
    b'{"a":' + b"9" * 10000 + b"}", b'{"a":"\\ud800"}',
])
def test_invalid_json_or_root_has_typed_safe_failure(raw):
    with pytest.raises(OfficialCatalogueError) as caught:
        parse_official_catalogue(raw)
    assert str(caught.value) == caught.value.code
    assert len(str(caught.value)) < 80


@pytest.mark.parametrize("escaped", [False, True])
@pytest.mark.parametrize("nested", [False, True])
def test_duplicate_keys_in_otherwise_valid_document(document, escaped, nested):
    raw = compact(document)
    if nested:
        key = b"sta\\u0074us" if escaped else b"status"
        raw = raw.replace(b'"status":"active"', b'"status":"active","' + key + b'":"active"')
    else:
        key = b"seque\\u006ece" if escaped else b"sequence"
        raw = raw.replace(b'"sequence":1', b'"sequence":1,"' + key + b'":1')
    with pytest.raises(OfficialCatalogueError, match="^duplicate_metadata_key$"):
        parse_official_catalogue(raw)


@pytest.mark.parametrize("value", ["NaN", "Infinity", "-Infinity", "1e400"])
def test_nonfinite_numbers_in_complete_document(document, value):
    entry = document["entries"][0]
    entry["manifest"]["connection_fields"][0]["validation"] = {"maximum": 123456789}
    raw = compact(document).replace(b'"maximum":123456789', b'"maximum":' + value.encode())
    with pytest.raises(OfficialCatalogueError, match="^invalid_metadata_number$"):
        parse_official_catalogue(raw)


def test_out_of_range_integer_in_manifest_is_not_silently_rounded(document):
    document["entries"][0]["manifest"]["connection_fields"][0]["validation"] = {"maximum": 2**53}
    with pytest.raises(OfficialCatalogueError, match="^invalid_catalogue_json$"):
        parse_official_catalogue(compact(document))


def test_bootstrap_and_aggregate_formats_remain_distinct(tmp_path):
    from app.services.connector_catalogue import BOOTSTRAP_PATH, CatalogueService, CatalogueUnavailable

    with pytest.raises(OfficialCatalogueError, match="invalid_catalogue_fields"):
        parse_official_catalogue(BOOTSTRAP_PATH.read_bytes())
    raw = FIXTURE.read_bytes()
    index = tmp_path / "catalogue.json"
    index.write_bytes(raw)
    with pytest.raises(CatalogueUnavailable, match="invalid_bootstrap_catalogue"):
        CatalogueService(index, expected_digest=hashlib.sha256(raw).hexdigest()).get("proxmox")


@pytest.mark.parametrize("value", [None, {}, "{}", bytearray(b"{}")])
def test_bytes_are_required(value):
    with pytest.raises(OfficialCatalogueError, match="catalogue_bytes_required"):
        parse_official_catalogue(value)


@pytest.mark.parametrize("field", sorted(catalogue.CATALOGUE_FIELDS))
def test_missing_top_level_fields(document, field):
    del document[field]
    with pytest.raises(OfficialCatalogueError, match="invalid_catalogue_fields"):
        parse_official_catalogue(compact(document))


@pytest.mark.parametrize("field", ["unexpected", "expires_at"])
def test_unknown_top_level_fields(document, field):
    document[field] = "2026-10-25T16:04:26Z"
    with pytest.raises(OfficialCatalogueError, match="invalid_catalogue_fields"):
        parse_official_catalogue(compact(document))


@pytest.mark.parametrize("field,value", [
    ("schema_version", "2.0"), ("schema_version", 1.0), ("schema_version", None),
    ("publisher_id", "other"), ("publisher_id", []), ("repository", "other/repo"), ("repository", {}),
    ("entries", {}), ("entries", None), ("entries", "[]"),
])
def test_wrong_aggregate_types_and_identities(document, field, value):
    document[field] = value
    with pytest.raises(OfficialCatalogueError):
        parse_official_catalogue(compact(document))


@pytest.mark.parametrize("field", ["sequence", "release_asset_id"])
@pytest.mark.parametrize("value", [0, -1, True, False, 1.0, "1", None, [], 2**53])
def test_literal_positive_safe_integers(document, field, value):
    target = document if field == "sequence" else document["entries"][0]
    target[field] = value
    with pytest.raises(OfficialCatalogueError):
        parse_official_catalogue(compact(document))


def test_maximum_literal_integer_and_zero_entries(document):
    document["sequence"] = document["entries"][0]["release_asset_id"] = 2**53 - 1
    parse_official_catalogue(compact(document))
    document["entries"] = []
    assert parse_official_catalogue(compact(document)).document == document


@pytest.mark.parametrize("value", [
    "2026-10-18T16:04:26+00:00", "2026-10-18T16:04:26.0Z", "2026-02-30T16:04:26Z",
    "2026-1-18T16:04:26Z", "2026-10-18T16:04:60Z", "0000-01-01T00:00:00Z",
    "2026-10-18T16:04:26Z\n", "not a date", True, None, [],
])
def test_exact_utc_timestamp(document, value):
    document["generated_at"] = value
    with pytest.raises(OfficialCatalogueError, match="invalid_catalogue_timestamp"):
        parse_official_catalogue(compact(document))


@pytest.mark.parametrize("field", sorted(catalogue.ENTRY_FIELDS))
def test_missing_entry_fields(document, field):
    del document["entries"][0][field]
    with pytest.raises(OfficialCatalogueError, match="invalid_release_fields"):
        parse_official_catalogue(compact(document))


@pytest.mark.parametrize("value", [None, [], True, "entry"])
def test_non_object_entry(document, value):
    document["entries"] = [value]
    with pytest.raises(OfficialCatalogueError, match="invalid_release_fields"):
        parse_official_catalogue(compact(document))


@pytest.mark.parametrize("mutation,code", [
    ("duplicate_identity", "duplicate_connector_version"),
    ("duplicate_asset", "duplicate_release_asset_id"),
    ("unsorted", "unsorted_catalogue_entries"),
    ("extra_field", "invalid_release_fields"),
])
def test_entry_collection_rules(document, mutation, code):
    entry = document["entries"][0]
    if mutation == "duplicate_identity":
        document["entries"].append(release(entry, "0.2.0", 1))
    elif mutation == "duplicate_asset":
        document["entries"].append(release(entry, "0.3.0", entry["release_asset_id"]))
    elif mutation == "unsorted":
        document["entries"].insert(0, release(entry, "0.3.0", 1))
    else:
        entry["unexpected"] = True
    with pytest.raises(OfficialCatalogueError, match=code):
        parse_official_catalogue(compact(document))


@pytest.mark.parametrize("value", ["unknown", "revoked", None, True, [], {}])
def test_invalid_status(document, value):
    document["entries"][0]["status"] = value
    with pytest.raises(OfficialCatalogueError, match="invalid_release_status"):
        parse_official_catalogue(compact(document))


def test_withdrawn_entry_and_lexical_version_order(document):
    entry = document["entries"][0]
    document["entries"] = [release(entry, "0.10.0", 1), release(entry, "0.9.0", 2)]
    document["entries"][0]["status"] = "withdrawn"
    assert parse_official_catalogue(compact(document)).document == document


@pytest.mark.parametrize("path,value", [
    (("release_tag",), "v0.2.0"), (("release_tag",), True),
    (("manifest",), []), (("manifest", "manifest_version"), "9.9"),
    (("manifest", "manifest_version"), []), (("manifest", "compatibility"), {}),
    (("manifest", "compatibility", "aip"), []),
    (("manifest", "publisher", "id"), "other"),
    (("manifest", "distribution", "asset_uri"), "https://example.test/package.tar.gz"),
    (("manifest", "distribution", "bundle_digest"), "sha256:" + "A" * 64),
    (("manifest", "distribution", "bundle_digest"), "sha256:" + "a" * 63),
    (("manifest", "distribution", "provenance", "repository"), "other/atlas-connectors"),
    (("manifest", "distribution", "provenance", "workflow"), ".github/workflows/catalogue.yml"),
    (("manifest", "distribution", "provenance", "method"), "approved-publisher-signature"),
    (("manifest", "distribution", "provenance", "source_commit"), "A" * 40),
    (("manifest", "distribution", "provenance", "source_commit"), "a" * 39),
    (("manifest", "distribution", "provenance", "evidence_uri"), "https://example.test/attestations"),
    (("manifest", "display", "description"), "\ud800"),
])
def test_manifest_and_official_declarations(document, path, value):
    target = document["entries"][0]
    for name in path[:-1]:
        target = target[name]
    target[path[-1]] = value
    # ASCII escapes permit testing unpaired surrogate input at the parser.
    with pytest.raises(OfficialCatalogueError):
        parse_official_catalogue(json.dumps(document).encode())


@pytest.mark.parametrize("delta", [-1, 0, 1])
def test_raw_byte_limit_before_decode(document, delta, monkeypatch):
    raw = compact(document)
    raw += b" " * (4_194_304 + delta - len(raw))
    if delta > 0:
        monkeypatch.setattr(catalogue, "strict_json", lambda *a, **k: pytest.fail("oversize input decoded"))
        with pytest.raises(OfficialCatalogueError, match="catalogue_too_large"):
            parse_official_catalogue(raw)
    else:
        assert parse_official_catalogue(raw).source_bytes == raw


@pytest.mark.parametrize("delta", [-1, 0, 1])
def test_canonical_aggregate_limit_independent_of_raw(document, delta):
    entry = document["entries"][0]
    document["entries"] = [release(entry, f"0.3.{i}", i + 1) for i in range(20)]
    document["entries"].sort(key=lambda row: (row["manifest"]["id"], row["manifest"]["version"]))
    padding, remainder = divmod(4_194_304 + delta - len(canonical(document)), 20)
    for i, row in enumerate(document["entries"]):
        row["manifest"]["display"]["documentation_uri"] += "a" * (padding + (i < remainder))
        assert len(canonical(row)) < 262_144
    assert len(canonical(document)) == 4_194_304 + delta
    raw = compact(document)
    assert len(raw) < 4_194_304
    if delta > 0:
        with pytest.raises(OfficialCatalogueError, match="catalogue_too_large"):
            parse_official_catalogue(raw)
    else:
        parse_official_catalogue(raw)


@pytest.mark.parametrize("delta", [-1, 0, 1])
def test_standalone_entry_limit_including_utf8_envelope_and_newline(document, delta):
    entry = document["entries"][0]
    entry["manifest"]["display"]["description"] = 'Unicode é and escaped "text"'
    entry["manifest"]["display"]["documentation_uri"] += "a" * (262_144 + delta - len(canonical(entry)))
    assert len(canonical(entry)) == 262_144 + delta
    raw = compact(document)
    assert len(raw) < 262_144  # Compact input cannot evade canonical entry size.
    if delta > 0:
        with pytest.raises(OfficialCatalogueError, match="release_entry_too_large"):
            parse_official_catalogue(raw)
    else:
        parse_official_catalogue(raw)


@pytest.mark.parametrize("count", [199, 200, 201])
def test_entry_count_limit(document, count):
    entry = document["entries"][0]
    document["entries"] = [release(entry, f"0.3.{i}", i + 1) for i in range(count)]
    document["entries"].sort(key=lambda row: (row["manifest"]["id"], row["manifest"]["version"]))
    if count > 200:
        with pytest.raises(OfficialCatalogueError, match="invalid_catalogue_entry_count"):
            parse_official_catalogue(compact(document))
    else:
        parse_official_catalogue(compact(document))


@pytest.mark.parametrize("raw", [b"[" * 10000, b'{"a":' * 10000, b"[" * 33 + b"]" * 33])
def test_excessive_nesting_rejected_before_json_decoding(raw, monkeypatch):
    monkeypatch.setattr(catalogue, "strict_json", lambda *a, **k: pytest.fail("deep input decoded"))
    with pytest.raises(OfficialCatalogueError, match="catalogue_nesting_too_deep"):
        parse_official_catalogue(raw)


def test_delimiters_and_escapes_in_strings_are_not_nesting(document):
    document["entries"][0]["manifest"]["display"]["description"] = '[{"\\' * 100
    parse_official_catalogue(compact(document))


def test_validation_is_offline_and_calls_canonical_sdk(document, monkeypatch):
    calls = []
    validate = catalogue.validate_manifest

    def checked(manifest):
        calls.append(manifest["id"])
        return validate(manifest)

    def forbidden(*args, **kwargs):
        pytest.fail("structural validation attempted network access")

    monkeypatch.setattr(catalogue, "validate_manifest", checked)
    monkeypatch.setattr(socket, "socket", forbidden)
    monkeypatch.setattr(socket, "getaddrinfo", forbidden)
    result = parse_official_catalogue(compact(document))
    assert calls == ["proxmox"]
    assert set(vars(result)) == {"source_bytes", "document"}


def test_structural_success_cannot_bypass_real_package_verifier(document, tmp_path):
    from app.services.connector_catalogue import CataloguePackage, CatalogueService, CatalogueUnavailable
    from app.services.connector_store import PackageStore
    from app.services.connector_verification import OfficialBundleVerifier, VerificationError

    # Inert bytes prove the real store rejects BEFORE extraction/publication.
    archive = tmp_path / "inert.tar.gz"
    archive.write_bytes(b"not executable; must never be extracted")
    document["entries"][0]["manifest"]["distribution"]["bundle_digest"] = (
        "sha256:" + hashlib.sha256(archive.read_bytes()).hexdigest()
    )
    result = parse_official_catalogue(compact(document))
    manifest = result.document["entries"][0]["manifest"]
    package = CataloguePackage(manifest["id"], manifest["version"],
        manifest["distribution"]["bundle_digest"], manifest, "official", True, archive)
    store = PackageStore(tmp_path / "store")
    with pytest.raises(VerificationError, match="missing_attestation"):
        store.install(package, OfficialBundleVerifier())
    assert not store.root.exists()
    # Parsing never inserts the published version into the bootstrap provider.
    with pytest.raises(CatalogueUnavailable, match="connector_not_in_catalogue"):
        CatalogueService().get("proxmox", "0.2.0")
