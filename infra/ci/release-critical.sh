#!/usr/bin/env bash
# Shared release/runtime selector. Run from apps/api with SDK/Proxmox source PYTHONPATH.
set -euo pipefail
python -m pytest tests/test_release_foundation.py tests/test_docker_ingress.py \
  tests/test_native_install.py tests/test_backups.py tests/test_mfa.py \
  tests/test_release_distribution.py tests/test_updates.py \
  tests/test_integration_runtime.py tests/test_runtime_packaging.py \
  tests/test_connector_packages.py tests/test_integration_catalogue_api.py \
  tests/test_i2_runtime.py tests/test_i3_runtime.py tests/test_i4a_runtime.py tests/test_connector_bootstrap.py \
  tests/test_capability_diagnostics.py tests/test_source_identity.py tests/test_i4b_runtime.py \
  ../../plugins/sdk/tests ../../plugins/proxmox/tests -q
