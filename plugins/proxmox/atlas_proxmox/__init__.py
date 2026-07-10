"""Proxmox discovery plugin for Atlas."""

from .connection import ProxmoxConnectionValidator, validate_connection
from .plugin import ProxmoxPlugin

PLUGIN_ID = "proxmox"

__all__ = [
    "PLUGIN_ID",
    "ProxmoxConnectionValidator",
    "ProxmoxPlugin",
    "validate_connection",
]
