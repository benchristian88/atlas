"""Read-only hypothetical analysis; POST carries a bounded scenario input."""

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from app.authorization import ActiveContext, Principal, RequestContext, require_any_permission
from app.database import get_db
from app.schemas_dependency_analysis import DependencyAnalysisRequest, DependencyAnalysisResponse
from app.services.dependency_analysis import DependencyAnalysisEngine
from app.services.operational_graph import GraphFocusNotFound, OperationalGraphBuilder

router = APIRouter(prefix="/dependency-analysis", tags=["dependency analysis"])


@router.post("", response_model=DependencyAnalysisResponse)
def analyze_dependencies(
    payload: DependencyAnalysisRequest,
    context: RequestContext,
    site_viewpoint: bool = False,
    principal: Principal = Depends(require_any_permission("assets.view", "services.view")),
    db: Session = Depends(get_db),
):
    if site_viewpoint and context.customer_id is None:
        raise HTTPException(status_code=404, detail="Record not found")
    try:
        analysis_context = ActiveContext(context.customer_id, None) if site_viewpoint and context.customer_id else context
        return DependencyAnalysisEngine(OperationalGraphBuilder(db, principal)).analyze(payload, analysis_context)
    except GraphFocusNotFound as exc:
        raise HTTPException(status_code=404, detail="Record not found") from exc
