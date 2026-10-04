#!/usr/bin/env bash
# Shared H4 selector. Run from apps/api with SDK/Proxmox source PYTHONPATH.
set -euo pipefail
python -m pytest tests/test_release_foundation.py tests/test_docker_ingress.py \
  tests/test_native_install.py tests/test_backups.py tests/test_mfa.py \
  tests/test_release_distribution.py tests/test_updates.py \
  ../../plugins/sdk/tests ../../plugins/proxmox/tests -q
