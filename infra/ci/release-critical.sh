#!/usr/bin/env bash
# Shared release/runtime selector. Run from apps/api with SDK/Proxmox source PYTHONPATH.
set -euo pipefail
python -m pytest tests/test_release_foundation.py tests/test_docker_ingress.py \
  tests/test_native_install.py tests/test_backups.py tests/test_mfa.py \
  tests/test_release_distribution.py tests/test_updates.py \
  tests/test_integration_runtime.py tests/test_runtime_packaging.py \
  tests/test_official_provenance.py tests/test_attestation_distribution.py \
  tests/test_official_catalogue_selection.py tests/test_official_selection_provenance.py \
  tests/test_catalogue_trust.py tests/test_catalogue_publication_evidence.py \
  tests/test_catalogue_bootstrap_authorization.py \
  tests/test_catalogue_source.py \
  tests/test_connector_packages.py tests/test_integration_catalogue_api.py \
  tests/test_i2_runtime.py tests/test_i3_runtime.py tests/test_i4a_runtime.py tests/test_connector_bootstrap.py \
  tests/test_capability_diagnostics.py tests/test_source_identity.py tests/test_i4b_runtime.py \
  tests/test_discovery_diagnostics.py tests/test_discovery_diagnostics_runtime.py \
  tests/test_discovery_diagnostics_concurrency_postgres.py \
  tests/test_i4c_diagnostics_runtime.py \
  tests/test_reconciliation_listing.py \
  tests/test_connector_qualification.py tests/test_connector_qualification_postgres.py \
  ../../plugins/sdk/tests ../../plugins/proxmox/tests -q
