"""ADR 0013 sequence-one adapter over the existing bounded reader/verifier.

No general publication or package authority. Only a completed operation can mint
the typed, immutable candidate consumed by B1.3; a publication dictionary cannot.
"""
from __future__ import annotations

import base64
from dataclasses import asdict, dataclass, field
from datetime import datetime
import hashlib
import json
import re
import time
import uuid

from app.services import catalogue_source as source
from app.services.catalogue_bootstrap_authorization import BootstrapExceptionAuthorization, evaluate_bootstrap_exception
from app.services.catalogue_trust import approved_bootstrap_policy
from app.services.connector_verification import GithubSigstoreVerifier
from app.services.official_catalogue import MAX_CATALOGUE_BYTES, parse_official_catalogue
from app.services.official_catalogue_selection import MAX_POINTER_BYTES, parse_official_catalogue_selection
from app.services.official_provenance import MAX_BUNDLE_BYTES, TIMEOUT_SECONDS, TrustProfile, VerifiedProvenance
from app.utils.json_values import to_json_value

CURRENT = "/git/ref/heads/catalogue-current"
ROOT_TAG = "/git/ref/tags/catalogue-bootstrap-root"
ASSET_KEYS = ("id", "name", "size", "digest", "updated_at", "url", "state", "browser_download_url")
RELEASE_KEYS = ("id", "tag_name", "url", "html_url", "draft", "prerelease", "immutable",
                "target_commitish", "created_at", "published_at", "updated_at")
MAX_DURABLE_EVIDENCE_BYTES = 3 * 1024 * 1024
_AUTHENTICATED = object()


def canonical(value):
    return (json.dumps(value, sort_keys=True, indent=2, ensure_ascii=False, allow_nan=False) + "\n").encode()


def blob_sha(raw):
    return hashlib.sha1(b"blob " + str(len(raw)).encode() + b"\0" + raw).hexdigest()


def _sha(value):
    return type(value) is str and re.fullmatch(r"[a-f0-9]{40}", value) is not None


def _git_object(value):
    source.require(type(value) is dict and _sha(value.get("sha"))
        and value.get("type") in ("tag", "commit")
        and value.get("url") == f"{source.BASE}/git/{'tags' if value['type'] == 'tag' else 'commits'}/{value['sha']}",
        "invalid_git_identity")
    return {key: value[key] for key in ("sha", "type", "url")}


async def read_ref(reader, path, *, expected=None):
    value = await reader.selection_metadata(path)
    source.require(type(value) is dict and value.get("ref") == "refs/" + path.removeprefix("/git/ref/")
        and value.get("url") == source.BASE + path.replace("/git/ref/", "/git/refs/"), "invalid_selection_ref")
    obj = _git_object(value.get("object"))
    if expected is not None:
        source.require(obj["type"] == "commit" and obj["sha"] == expected, "unapproved_selection_root")
    return {"ref": value["ref"], "url": value["url"], "object": obj}


async def contents(reader, name, root, expected_blob, maximum):
    path = f"/contents/{name}?ref={root}"
    value = await reader.selection_metadata(path)
    source.require(type(value) is dict and value.get("type") == "file"
        and value.get("path") == name and value.get("name") == name
        and value.get("sha") == expected_blob and type(value.get("size")) is int
        and 0 < value["size"] <= maximum and value.get("encoding") == "base64"
        and value.get("url") == source.BASE + path
        and type(value.get("content")) is str
        and re.fullmatch(r"[A-Za-z0-9+/=\n]+", value["content"]) is not None,
        "invalid_selection_contents")
    encoded = value["content"].replace("\n", "")
    source.require(len(encoded) <= 4 * ((maximum + 2) // 3), "source_response_too_large")
    try:
        raw = base64.b64decode(encoded, validate=True)
    except ValueError:
        raise source.SourceError("invalid_selection_contents") from None
    source.require(base64.b64encode(raw).decode() == encoded and len(raw) == value["size"]
        and blob_sha(raw) == expected_blob, "selection_contents_identity_mismatch")
    # download_url/html_url/_links are deliberately never routing inputs.
    return raw


async def read_root(reader, root):
    current = await read_ref(reader, CURRENT, expected=root)
    marker = await read_ref(reader, ROOT_TAG, expected=root)
    commit = await reader.selection_metadata(f"/git/commits/{root}")
    source.require(type(commit) is dict and commit.get("sha") == root and commit.get("parents") == []
        and commit.get("url") == f"{source.BASE}/git/commits/{root}"
        and type(commit.get("tree")) is dict and _sha(commit["tree"].get("sha")), "invalid_bootstrap_commit")
    tree_sha = commit["tree"]["sha"]
    source.require(commit["tree"].get("url") == f"{source.BASE}/git/trees/{tree_sha}", "invalid_bootstrap_tree")
    tree = await reader.selection_metadata(f"/git/trees/{tree_sha}")
    source.require(type(tree) is dict and tree.get("sha") == tree_sha and tree.get("truncated") is False
        and tree.get("url") == f"{source.BASE}/git/trees/{tree_sha}"
        and type(tree.get("tree")) is list and len(tree["tree"]) == 2, "invalid_bootstrap_tree")
    files = {}
    for row in tree["tree"]:
        source.require(type(row) is dict and row.get("path") in ("current.json", "current.sigstore.json")
            and row["path"] not in files and row.get("mode") == "100644" and row.get("type") == "blob"
            and _sha(row.get("sha")) and row.get("url") == f"{source.BASE}/git/blobs/{row['sha']}",
            "invalid_bootstrap_tree")
        files[row["path"]] = row["sha"]
    tree_bytes = b"".join(b"100644 " + name.encode() + b"\0" + bytes.fromhex(sha) for name, sha in sorted(files.items()))
    source.require(hashlib.sha1(b"tree " + str(len(tree_bytes)).encode() + b"\0" + tree_bytes).hexdigest() == tree_sha,
                   "invalid_bootstrap_tree")
    raw = await contents(reader, "current.json", root, files["current.json"], MAX_POINTER_BYTES)
    bundle = await contents(reader, "current.sigstore.json", root, files["current.sigstore.json"], MAX_BUNDLE_BYTES)
    return raw, bundle, {"current_ref": current, "bootstrap_ref": marker, "root_commit": root,
                         "parents": [], "tree_sha": tree_sha, "blobs": files}


async def release_source(reader, tag, expected):
    ref = await read_ref(reader, "/git/ref/tags/" + tag)
    obj, tags = ref["object"], []
    for _ in range(2):
        if obj["type"] == "commit":
            source.require(obj["sha"] == expected, "catalogue_tag_source_mismatch")
            return {"ref": ref, "annotated_tags": tags, "source_commit": expected}
        value = await reader.selection_metadata(f"/git/tags/{obj['sha']}")
        source.require(type(value) is dict and value.get("sha") == obj["sha"]
            and value.get("url") == obj["url"] and value.get("tag") == tag, "invalid_catalogue_tag")
        obj = _git_object(value.get("object"))
        tags.append({"sha": value["sha"], "object": obj})
    raise source.SourceError("catalogue_tag_depth")


async def selected_release(reader, selection, build_source):
    value = await reader.selection_metadata(f"/releases/{selection.release_id}")
    source.require(type(value) is dict and type(value.get("id")) is int and value["id"] == selection.release_id
        and value.get("tag_name") == selection.release_tag
        and value.get("url") == f"{source.BASE}/releases/{selection.release_id}"
        and value.get("html_url") == f"https://github.com/{source.REPOSITORY}/releases/tag/{selection.release_tag}"
        and value.get("draft") is False and value.get("prerelease") is False, "invalid_selected_release")
    source.require(value.get("immutable") is True, "publication_not_immutable")
    source.require(value.get("target_commitish") == build_source, "catalogue_release_source_mismatch")
    names = {selection.release_tag + ".json": MAX_CATALOGUE_BYTES, "catalogue.sigstore.json": MAX_BUNDLE_BYTES,
             "current.json": MAX_POINTER_BYTES, "current.sigstore.json": MAX_BUNDLE_BYTES}
    source.require(type(value.get("assets")) is list and len(value["assets"]) == 4
        and all(type(a) is dict and type(a.get("name")) is str for a in value["assets"])
        and {a["name"] for a in value["assets"]} == names.keys(), "invalid_selected_asset_inventory")
    assets = {name: reader.asset(value, name, tag=selection.release_tag, maximum=maximum) for name, maximum in names.items()}
    source.require(len({a["id"] for a in assets.values()}) == 4
        and assets[selection.release_tag + ".json"]["id"] == selection.asset_id, "selected_asset_mismatch")
    snapshot = {k: value.get(k) for k in RELEASE_KEYS}
    snapshot["assets"] = {name: {k: a.get(k) for k in ASSET_KEYS} for name, a in assets.items()}
    return assets, snapshot


@dataclass(frozen=True, slots=True)
class VerifiedBootstrapCandidate:
    raw: bytes = field(repr=False)
    provenance: VerifiedProvenance
    authorization: BootstrapExceptionAuthorization
    pointer_bundle: bytes = field(repr=False)
    catalogue_bundle: bytes = field(repr=False)
    transport_json: bytes = field(repr=False)
    release_json: bytes = field(repr=False)
    operation_id: uuid.UUID
    confirmed_at: datetime
    _seal: object = field(init=False, default=None, repr=False, compare=False)

    @property
    def publication(self):
        authorization = self.authorization
        result = to_json_value(asdict(authorization))
        # Original bytes are lossless base64, never decoded/reformatted evidence.
        result["selection"]["source_bytes"] = base64.b64encode(authorization.selection.source_bytes).decode()
        result.update(policy=authorization.policy_version, immutable=True,
            release_id=authorization.identity.release_id, asset_id=authorization.identity.catalogue_asset_id,
            pointer_sha256=authorization.selection.pointer_sha256,
            catalogue_sha256=self.provenance.artifact_sha256,
            pointer_bundle_base64=base64.b64encode(self.pointer_bundle).decode(),
            catalogue_bundle_base64=base64.b64encode(self.catalogue_bundle).decode(),
            transport=source.decode(self.transport_json), release=source.decode(self.release_json),
            confirmed_at=self.confirmed_at.isoformat(), operation_id=str(self.operation_id))
        source.require(len(canonical(result)) <= MAX_DURABLE_EVIDENCE_BYTES, "catalogue_evidence_too_large")
        return result


def require_authenticated(candidate, *, operation_id):
    source.require(type(candidate) is VerifiedBootstrapCandidate and candidate._seal is _AUTHENTICATED,
                   "authenticated_selection_required")
    source.require(type(operation_id) is uuid.UUID and candidate.operation_id == operation_id, "catalogue_operation_mismatch")
    policy = approved_bootstrap_policy()
    auth, evidence = candidate.authorization, candidate.provenance
    source.require(auth.approval_reference == policy.approval_reference and auth.policy_version == policy.proposal.policy_version
        and auth.identity == policy.proposal.identity, "approved_selection_required")
    selection = parse_official_catalogue_selection(auth.selection.source_bytes)
    source.require(selection == auth.selection and selection.pointer_sha256 == auth.identity.pointer_sha256
        and evidence.profile == TrustProfile.CATALOGUE and evidence.subject_name == selection.release_tag + ".json"
        and evidence.source_commit == auth.identity.catalogue_build_source
        and hashlib.sha256(candidate.raw).hexdigest() == selection.sha256 == evidence.artifact_sha256,
        "catalogue_evidence_mismatch")
    source.require(candidate.confirmed_at <= source.utcnow()
        and (source.utcnow() - candidate.confirmed_at).total_seconds() < source.REFRESH_SECONDS, "catalogue_confirmation_expired")


async def retrieve_bootstrap(progress, *, operation_id):
    source.require(type(operation_id) is uuid.UUID, "catalogue_operation_required")
    policy = approved_bootstrap_policy()
    pins = policy.proposal.identity
    async with source.GithubReader() as reader:
        pointer, pointer_bundle, transport = await read_root(reader, pins.root_commit)
        selection = parse_official_catalogue_selection(pointer)
        verifier = GithubSigstoreVerifier()
        source.require(reader.deadline - time.monotonic() > TIMEOUT_SECONDS + 2, "source_timeout")
        selection_evidence = verifier.verify_selection(pointer, pointer_bundle)
        authorization = await evaluate_bootstrap_exception(selection, selection_evidence,
            root_commit=pins.root_commit, policy=policy, reader=reader)
        assets, release = await selected_release(reader, selection, pins.catalogue_build_source)
        raw = await reader.download(assets[selection.release_tag + ".json"])
        progress["last_download_at"] = source.utcnow()
        source.require(hashlib.sha256(raw).hexdigest() == selection.sha256 == pins.catalogue_sha256,
                       "selected_catalogue_digest_mismatch")
        document = parse_official_catalogue(raw).document
        source.require(document["sequence"] == selection.sequence and canonical(document) == raw, "noncanonical_catalogue")
        catalogue_bundle = await reader.download(assets["catalogue.sigstore.json"], maximum=MAX_BUNDLE_BYTES)
        source.require(reader.deadline - time.monotonic() > TIMEOUT_SECONDS + 2, "source_timeout")
        evidence = verifier.verify_catalogue(raw, catalogue_bundle, subject_name=selection.release_tag + ".json")
        source.require(evidence.source_commit == pins.catalogue_build_source, "catalogue_build_source_mismatch")
        progress["last_authenticity_verified_at"] = evidence.verified_at
        transport["release_source"] = await release_source(reader, selection.release_tag, evidence.source_commit)
        source.require(await reader.download(assets["current.json"], maximum=MAX_POINTER_BYTES) == pointer
            and await reader.download(assets["current.sigstore.json"], maximum=MAX_BUNDLE_BYTES) == pointer_bundle,
            "retained_selection_mismatch")
        # Fresh public rereads, not a cached signature or immutable-release check.
        _, after_release = await selected_release(reader, selection, pins.catalogue_build_source)
        source.require(after_release == release, "channel_changed")
        after_pointer = await contents(reader, "current.json", pins.root_commit,
            transport["blobs"]["current.json"], MAX_POINTER_BYTES)
        source.require(after_pointer == pointer, "channel_changed")
        # The exact commit/tree/bundle were checked above. An unchanged current
        # ref plus fresh exact-commit pointer bytes confirms that same selection;
        # no second read of immutable root metadata or cached-signature fallback.
        source.require(await read_ref(reader, CURRENT, expected=pins.root_commit) == transport["current_ref"], "channel_changed")
        source.require(time.monotonic() < reader.deadline, "source_timeout")
        candidate = VerifiedBootstrapCandidate(raw, evidence, authorization, pointer_bundle, catalogue_bundle,
            canonical(transport), canonical(release), operation_id, source.utcnow())
        object.__setattr__(candidate, "_seal", _AUTHENTICATED)
        require_authenticated(candidate, operation_id=operation_id)
        return candidate
