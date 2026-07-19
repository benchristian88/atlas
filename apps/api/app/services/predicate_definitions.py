"""Central knowledge-predicate cardinality and display rules."""

from __future__ import annotations

from typing import Literal

PredicateCardinality = Literal["single", "multi"]

SINGLE_VALUE_PREDICATES = frozenset(
    {
        "name",
        "hostname",
        "asset_type",
        "status",
        "operational_state",
        "observation_state",
        "platform",
        "lifecycle_state",
    }
)

MULTI_VALUE_PREDICATES = frozenset(
    {
        "interface_ip",
        "interface",
        "network_membership",
        "relationship",
        "owner",
        "dependency",
    }
)

ASSET_FIELD_PREDICATES = frozenset({"name", "hostname", "asset_type", "status"})


def predicate_cardinality(
    predicate: str, *, object_type: str | None = None
) -> PredicateCardinality:
    """Return the canonical cardinality for a predicate.

    Relationship assertions use their taxonomy key as the predicate, so an
    assertion with an object identity is always multi-valued. Interface facts
    are also namespaced (for example ``interface.eth0.ip_address``).
    Unknown scalar predicates default to single-valued so accidental duplicate
    accepted values fail closed at the service boundary.
    """

    if object_type is not None:
        return "multi"
    if predicate in MULTI_VALUE_PREDICATES or predicate.startswith("interface."):
        return "multi"
    return "single"


def predicate_label(predicate: str) -> str:
    return predicate.replace(".", " · ").replace("_", " ").strip().title()
