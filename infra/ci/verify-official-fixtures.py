"""Opt-in acceptance of frozen public evidence; never installs/executes a package.

Run from a source checkout with an already prepared pinned verifier:
  python infra/ci/verify-official-fixtures.py [--package /absolute/package.tar.gz]
The optional package must be acquired separately; this script has no network IO.
"""
import argparse
from dataclasses import asdict
import json
import os
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "apps/api"))

from app import attestation_distribution as distribution
from app.services.connector_verification import GithubSigstoreVerifier
from app.services.official_catalogue import parse_official_catalogue
from app.services.official_provenance import PackageArtifactContext, ProvenanceError

FIXTURES = ROOT / "apps/api/tests/fixtures/official_catalogue"


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--package", type=Path)
    parser.add_argument("--require-protected", action="store_true")
    args = parser.parse_args()
    lock = distribution.distribution_lock()
    binary = distribution.checked_binary(lock)
    if args.require_protected:
        for path in (binary, distribution.DISTRIBUTION / "trusted-root.jsonl",
                     distribution.DISTRIBUTION / "distribution.json", binary.parent):
            assert path.stat().st_uid == 0 and not os.access(path, os.W_OK), "Unprotected verifier distribution"
    verifier = GithubSigstoreVerifier()
    artifact = (FIXTURES / "catalogue-000001.json").read_bytes()
    bundle = (FIXTURES / "catalogue.sigstore.json").read_bytes()
    catalogue = parse_official_catalogue(artifact)
    evidence = verifier.verify_catalogue(catalogue.source_bytes, bundle)
    print(json.dumps(asdict(evidence), default=str, sort_keys=True))
    failures = 0
    for changed, proof in [(artifact + b"\n", bundle), (artifact, (FIXTURES / "package.sigstore.json").read_bytes())]:
        try:
            verifier.verify_catalogue(changed, proof)
        except ProvenanceError:
            failures += 1
        else:
            raise AssertionError("Unauthorized catalogue accepted")
    if args.package:
        package = distribution.regular_bytes(args.package.absolute(), 20 * 1024 * 1024)
        manifest = catalogue.document["entries"][0]["manifest"]
        context = PackageArtifactContext(manifest["id"], manifest["version"],
            manifest["distribution"]["bundle_digest"][7:], manifest["distribution"]["provenance"]["source_commit"])
        package_bundle = (FIXTURES / "package.sigstore.json").read_bytes()
        print(json.dumps(asdict(verifier.verify_package(package, package_bundle, context)), default=str, sort_keys=True))
        # Both genuine artifacts under the opposite signer policy, with their
        # actual bytes and digests. Neither may authorize the other profile.
        for check in (
            lambda: verifier.verify_catalogue(package, package_bundle),
            lambda: verifier.verify_package(artifact, bundle, PackageArtifactContext(
                context.connector_id, context.version, evidence.artifact_sha256, evidence.source_commit)),
            lambda: verifier.verify_package(package + b"\n", package_bundle, context),
        ):
            try:
                check()
            except ProvenanceError:
                failures += 1
            else:
                raise AssertionError("Unauthorized package accepted")
    print(f"Acceptance passed; {failures} tamper/profile rejection checks.")


if __name__ == "__main__":
    main()

