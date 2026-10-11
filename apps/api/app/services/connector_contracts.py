"""Atlas policy adapter over the sole canonical, pinned Apache SDK."""
from pathlib import Path
from atlas_connector_sdk import __version__ as SDK_VERSION
from atlas_connector_sdk.contracts import ContractError, strict_json as sdk_json, validate_manifest as sdk_manifest, validator, version_in_range

MAX_MANIFEST_BYTES = 256 * 1024

class ConnectorPackageError(ValueError):
    def __init__(self, code):
        self.code = code
        super().__init__(code)

class ManifestValidationError(ConnectorPackageError):
    pass

def strict_json(raw, *, maximum=MAX_MANIFEST_BYTES):
    try:
        return sdk_json(raw, maximum=maximum)
    except ContractError as error:
        raise ManifestValidationError(error.code) from None

def bootstrap_manifest_root():
    return Path(__file__).resolve().parents[1] / "integration_bootstrap"

def manifest_validator():
    return validator("connector-manifest-v1")

def validate_manifest(manifest, *, activation=False):
    try:
        sdk_manifest(manifest)
        if activation:
            qualification = manifest["source_versions"]["qualification"]
            probe_only = manifest["manifest_version"] == "1.1" and manifest["capabilities"]["discover"] is False
            if qualification == "example" or not probe_only and qualification != "qualified":
                raise ContractError("package_not_qualified")
    except ContractError as error:
        raise ManifestValidationError(error.code) from None
    return manifest
