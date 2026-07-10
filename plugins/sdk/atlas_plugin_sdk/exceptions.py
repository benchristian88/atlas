class PluginError(Exception):
    """Base class for expected plugin failures."""


class ConnectionValidationError(PluginError):
    """Raised when an integration cannot be validated."""


class DiscoveryError(PluginError):
    """Raised when raw discovery cannot complete."""


class NormalizationError(PluginError):
    """Raised when raw vendor data cannot be normalized safely."""


class SyncError(PluginError):
    """Raised when normalized results cannot be synchronized."""
