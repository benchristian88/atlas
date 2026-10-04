# Building and qualifying a release

Release tooling is a maintainer workflow, separate from installation.

## Local dry run

From a clean committed release checkout:

```bash
python3 infra/release/release.py metadata --tag v0.1.0
python3 infra/release/release.py build --dry-run --tag v0.1.0 --output /tmp/atlas-release-check
python3 infra/release/release.py verify --tag v0.1.0 --output /tmp/atlas-release-check
cd /tmp/atlas-release-check
sha256sum -c SHA256SUMS
```

Use the actual metadata version instead of the example. Output must be an empty
or new directory. For implementation acceptance before committing, add
`--worktree` to `build --dry-run`. This includes reviewed paths from tracked and
unignored pending source files, records `source_state: working_tree` and a
source digest, and is rejected by publication verification. It does not pretend
that the working tree is the recorded base commit. No command above can publish.

Sorted USTAR entries, normalized owners/modes, commit timestamps and a zero-time
unnamed gzip header make package and manifest bytes deterministic for the same
selected source, version and commit with the same Python/zlib toolchain. A
working-tree dry run also records its actual selected-source digest. This proves
package reproducibility; native dependency builds and Docker images remain
outside the byte-for-byte claim because upstream image tags/wheels/toolchains
are external inputs.

## Deliberate publication

1. Change canonical metadata intentionally, review release/migration notes and
   merge the version commit into `dev` through the usual review process.
2. Run the full product release gates, dependency audit and local dry run.
3. An authorized operator creates and pushes exactly `v<version>` at the reviewed
   commit. This is the explicit release action; ordinary pushes cannot publish.
4. The release workflow checks the tag against metadata and requires its commit
   to be reachable from `dev`. It tests and packages that exact commit, builds the
   production frontend, validates both artifacts and verifies checksums.
5. Only the final job receives `contents: write`. It downloads validated assets,
   rechecks identity/checksums and uses native `gh release create --verify-tag`
   with generated notes and the metadata-derived prerelease flag. It does not
   create a tag, alter versions or publish images. Existing releases are refused.

The workflow uses immutable official Action SHA pins, read-only/default-empty
permissions, no persisted checkout credentials and no PR publication trigger.
`workflow_dispatch` runs the same pipeline **only as a dry run**, on the chosen
checkout. It uploads validated assets for review but cannot publish. Publication
checks exclude working-tree manifests. Tag protection and reviewed `dev` changes
remain repository operator responsibilities. A dry run never authorizes publication. GitHub-hosted execution and publication
are separate from local workflow syntax and policy checks.

GitHub references: [release API](https://docs.github.com/en/rest/releases/releases),
[workflow permission syntax](https://docs.github.com/en/actions/reference/workflows-and-actions/workflow-syntax),
and [native release CLI](https://cli.github.com/manual/gh_release_create).
