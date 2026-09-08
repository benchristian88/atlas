"""Read-only hypothetical analysis; POST carries a bounded scenario input."""

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from app.authorization import Principal, RequestContext, require_any_permission
from app.database import get_db
from app.schemas_dependency_analysis import DependencyAnalysisRequest, DependencyAnalysisResponse
from app.services.dependency_analysis import DependencyAnalysisEngine
from app.services.operational_graph import GraphFocusNotFound, OperationalGraphBuilder

router = APIRouter(prefix="/dependency-analysis", tags=["dependency analysis"])


@router.post("", response_model=DependencyAnalysisResponse)
def analyze_dependencies(
    payload: DependencyAnalysisRequest,
    context: RequestContext,
    principal: Principal = Depends(require_any_permission("assets.view", "services.view")),
    db: Session = Depends(get_db),
):
    try:
        return DependencyAnalysisEngine(OperationalGraphBuilder(db, principal)).analyze(payload, context)
    except GraphFocusNotFound as exc:
        raise HTTPException(status_code=404, detail="Record not found") from exc
