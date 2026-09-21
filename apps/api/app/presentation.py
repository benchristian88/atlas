"""Bounded presentation write contract; never used for domain semantics.

Mirrored by web/lib/presentation-registry.json. The contract test compares every
key so changes must be deliberately applied to both API and UI.
Responses allow historical strings; renderers supply safe fallbacks.
"""
from typing import Literal

PresentationIcon = Literal[
    "infrastructure", "server", "cube", "database", "archive", "network",
    "switch", "router", "shield", "bridge", "cloud", "device", "home", "application",
]
PresentationAccent = Literal[
    "blue", "green", "purple", "orange", "red", "teal", "cyan", "amber", "slate", "rose",
]
