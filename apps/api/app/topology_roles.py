"""Bounded Asset Type presentation roles; never domain or traversal semantics."""
from typing import Literal, get_args

TopologyRole = Literal["external", "security_edge", "routing", "aggregation_network", "access_network", "platform", "infrastructure", "workload", "endpoint", "automatic"]
TOPOLOGY_ROLES = frozenset(get_args(TopologyRole))
