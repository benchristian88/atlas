import os
import uuid
from urllib.parse import urlsplit

from fastapi import APIRouter, FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse

from app.routes import (
    asset_interfaces,
    asset_relationships,
    assets,
    audit,
    auth,
    context,
    custom_fields,
    customers,
    manual_assets,
    knowledge,
    networks,
    protected,
    reference_data,
    roles,
    sites,
    system_settings,
    topology,
    users,
)


def allowed_origins() -> list[str]:
    origins = []
    for raw_origin in os.getenv("CORS_ORIGINS", "").split(","):
        origin = raw_origin.strip().rstrip("/")
        parsed = urlsplit(origin)
        if origin and parsed.scheme in {"http", "https"} and parsed.netloc and parsed.path in {"", "/"}:
            origins.append(origin)
    return origins


def request_origin_is_allowed(request: Request, origin: str) -> bool:
    normalized_origin = origin.rstrip("/")
    if normalized_origin in allowed_origins():
        return True
    parsed = urlsplit(normalized_origin)
    request_host = request.headers.get("host", "").lower()
    return parsed.scheme in {"http", "https"} and parsed.netloc.lower() == request_host


app = FastAPI(
    title="Atlas API",
    docs_url="/api/docs",
    openapi_url="/api/openapi.json",
    redoc_url="/api/redoc",
)
app.add_middleware(
    CORSMiddleware,
    allow_origins=allowed_origins(),
    allow_credentials=True,
    allow_methods=["GET", "POST", "PUT", "PATCH", "DELETE", "OPTIONS"],
    allow_headers=[
        "Authorization",
        "Content-Type",
        "X-Atlas-Customer-ID",
        "X-Atlas-Site-ID",
        "X-Request-ID",
    ],
    expose_headers=["X-Request-ID"],
)


@app.middleware("http")
async def request_security(request: Request, call_next):
    request_id = request.headers.get("x-request-id", "")
    if not request_id or len(request_id) > 100:
        request_id = str(uuid.uuid4())
    request.state.request_id = request_id
    origin = request.headers.get("origin")
    if (
        request.method in {"POST", "PUT", "PATCH", "DELETE"}
        and origin is not None
        and not request_origin_is_allowed(request, origin)
    ):
        return JSONResponse(
            status_code=403,
            content={"detail": "Request origin is not allowed"},
            headers={"X-Request-ID": request_id},
        )
    response = await call_next(request)
    response.headers["X-Request-ID"] = request_id
    return response


api_router = APIRouter()
api_router.include_router(auth.router)
api_router.include_router(context.router)
api_router.include_router(users.router)
api_router.include_router(roles.router)
api_router.include_router(roles.permissions_router)
api_router.include_router(customers.router)
api_router.include_router(sites.router)
api_router.include_router(reference_data.asset_types_router)
api_router.include_router(reference_data.relationship_types_router)
api_router.include_router(custom_fields.router)
api_router.include_router(assets.router)
api_router.include_router(custom_fields.asset_values_router)
api_router.include_router(asset_relationships.router)
api_router.include_router(networks.router)
api_router.include_router(asset_interfaces.router)
api_router.include_router(topology.router)
api_router.include_router(audit.router)
api_router.include_router(system_settings.router)
api_router.include_router(manual_assets.router)
api_router.include_router(knowledge.router)
api_router.include_router(protected.router)


@api_router.get("/health", tags=["health"])
async def health() -> dict[str, str]:
    """Report whether the API process is available."""
    return {"status": "ok"}


app.include_router(api_router, prefix="/api")
