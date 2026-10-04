"""Thin GitHub publication adapter; run only after the read-only build job."""
import argparse
from pathlib import Path
import subprocess

from release import ROOT, git, verify
from app.release import OFFICIAL_REPOSITORY


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--tag", required=True)
    args = parser.parse_args()
    release = verify(args.output, tag=args.tag, require_committed=True)
    commit = git("rev-parse", "HEAD").decode().strip()
    tagged = git("rev-parse", "--verify", f"refs/tags/{args.tag}^{{commit}}").decode().strip()
    if release["commit_sha"] != commit or tagged != commit:
        raise SystemExit("Release assets must match the checked-out tag commit")
    subprocess.run(["git", "merge-base", "--is-ancestor", commit, "origin/dev"], cwd=ROOT, check=True)
    assets = [str(args.output / artifact["filename"]) for artifact in release["artifacts"]]
    assets += [str(args.output / f"atlas-release-{release['version']}.json"), str(args.output / "SHA256SUMS")]
    command = ["gh", "release", "create", args.tag, *assets, "--repo", OFFICIAL_REPOSITORY,
               "--verify-tag", "--draft", "--generate-notes", "--title", f"Atlas {release['version']}"]
    if release["release_channel"] == "beta":
        command += ["--prerelease", "--latest=false"]
    subprocess.run(command, check=True)
    # If upload/creation fails the release remains unpublished; never overwrite
    # an existing release or create a tag as an implicit side effect.
    subprocess.run(["gh", "release", "edit", args.tag, "--repo", OFFICIAL_REPOSITORY, "--draft=false"], check=True)


if __name__ == "__main__":
    main()
