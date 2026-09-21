"""Bounded Connectivity presentation layers; no domain relationship semantics.

Mirrored by web/lib/topology-layers.json and checked by a registry contract test.
"""
from typing import Literal, get_args

TopologyLayer = Literal["platform", "physical_network", "data_resilience", "logical_operational", "other"]
TOPOLOGY_LAYERS = frozenset(get_args(TopologyLayer))
DEFAULT_TOPOLOGY_LAYERS = frozenset({"platform", "physical_network"})
