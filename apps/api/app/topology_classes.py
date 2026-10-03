"""Bounded Connectivity presentation classes; no domain relationship semantics.

Mirrored by web/lib/topology-classes.json and checked by a registry contract test.
"""
from typing import Literal, get_args

TopologyClass = Literal["platform", "physical_network", "data_resilience", "logical_operational", "other"]
TOPOLOGY_CLASSES = frozenset(get_args(TopologyClass))
DEFAULT_TOPOLOGY_CLASSES = frozenset({"platform", "physical_network"})
