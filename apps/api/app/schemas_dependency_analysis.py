"""Versioned, structured hypothetical dependency-analysis contracts."""

import uuid
from datetime import datetime
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field

from app.schemas import OperationalGraphEdge

AnalysisState = Literal["unavailable", "degraded", "unknown", "unaffected"]


class DependencyAnalysisRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    focus_type: Literal["asset", "service"]
    focus_id: uuid.UUID
    state: Literal["unavailable"] = "unavailable"
    max_depth: int = Field(default=8, ge=1, le=20)
    max_results: int = Field(default=100, ge=1, le=500)
    max_paths_per_result: int = Field(default=3, ge=1, le=20)


class AnalysisEntity(BaseModel):
    key: str
    entity_id: uuid.UUID
    name: str
    href: str


class AnalysisMember(BaseModel):
    entity: AnalysisEntity
    state: AnalysisState
    edge: OperationalGraphEdge


class AnalysisReason(BaseModel):
    key: str
    dependency_group_id: uuid.UUID | None
    dependency_group_name: str | None
    dependency_strategy: Literal["all", "any"] | None
    dependency_requirement: Literal["required", "optional"] | None
    failure_effect: Literal["unavailable", "degraded", "unknown"]
    satisfaction: Literal["satisfied", "unsatisfied", "unknown"]
    consequence: AnalysisState
    code: Literal["set_satisfied", "set_unsatisfied", "member_state_unresolved", "dependency_set_unresolved", "ungrouped_consequence_unknown"]
    members: list[AnalysisMember]
    triggering_edge_keys: list[str]
    summary: str


class AnalysisPath(BaseModel):
    # Nodes run from scenario to consequence; edges retain dependent -> provider.
    nodes: list[AnalysisEntity]
    edges: list[OperationalGraphEdge]


class ServiceAnalysisResult(BaseModel):
    service: AnalysisEntity
    state: AnalysisState
    classification: Literal["direct", "downstream"]
    distance: int
    reasons: list[AnalysisReason]
    paths: list[AnalysisPath]


class DependencyAnalysisResponse(BaseModel):
    schema_version: Literal["1"] = "1"
    engine_version: Literal["c2.3-v1"] = "c2.3-v1"
    focus_key: str
    focus: AnalysisEntity
    analysis_time: datetime
    scenario_state: Literal["unavailable"] = "unavailable"
    assumption: str = (
        "Hypothetical consequences within your authorized current knowledge. "
        "Other members are assumed available unless this scenario derives a consequence; "
        "unaffected means unaffected by this scenario, not verified live health."
    )
    truncated: bool = False
    warnings: list[str] = Field(default_factory=list)
    results: list[ServiceAnalysisResult] = Field(default_factory=list)
