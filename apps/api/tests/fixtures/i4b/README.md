# Isolated candidate acceptance artefacts

Generated from atlas-connectors' I4B candidate by
`tools/build_acceptance_fixture.py --output <this-directory>`.

`candidate-manifest.json` records the actual unqualified candidate metadata.
`bundle.tar.gz` and `manifest.json` are the separate **i4b-fixture** harness:
candidate implementations with deterministic test-only I/O injection and a
synthetic `fixture-only` qualification marker. This does **not** qualify any
Proxmox version. Tests verify that normal installation rejects the actual
unqualified candidate and that production remains Proxmox 0.1.0 probe-only.

Only tests create an exact allowlist for this bundle in a temporary package store
and activate it inside disposable PostgreSQL transactions. It is absent from the
catalogue/bootstrap and excluded by release packaging. Production candidate
bundles contain neither this fixture transport nor the sanitized source fixtures.
Regenerate after Connector code/metadata changes; never publish these artefacts.
