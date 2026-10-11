import os
import asyncio
import uuid
from contextlib import asynccontextmanager
from urllib.parse import urlsplit

from fastapi import APIRouter, FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from fastapi.exceptions import RequestValidationError
from fastapi.exception_handlers import request_validation_exception_handler

from app.routes import (
    asset_interfaces,
    asset_relationships,
    assets,
    audit,
    auth,
    context,
    custom_fields,
    changes,
    customers,
    manual_assets,
    knowledge,
    knowledge_completeness,
    networks,
    operational_graph,
    dependency_analysis,
    protected,
    reference_data,
    asset_categories,
    topology_positions,
    roles,
    sites,
    services,
    service_reference_data,
    business_functions,
    system_settings,
    topology,
    users,
    setup,
    mfa,
    backups,
    integrations,
    integration_connections,
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


@asynccontextmanager
async def lifespan(app: FastAPI):
    from app.config import data_encryption_key
    data_encryption_key(required=False)
    from app.services.backup_runtime import cleanup_stale
    await asyncio.to_thread(cleanup_stale)
    async def clean_staging():
        while True:
            await asyncio.sleep(30)
            await asyncio.to_thread(cleanup_stale)
    cleaner = asyncio.create_task(clean_staging())
    try:
        yield
    finally:
        cleaner.cancel()
        try:
            await cleaner
        except asyncio.CancelledError:
            pass


app = FastAPI(
    title="Atlas API",
    docs_url="/api/docs",
    openapi_url="/api/openapi.json",
    redoc_url="/api/redoc",
    lifespan=lifespan,
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


@app.exception_handler(RequestValidationError)
async def safe_setup_validation(request: Request, exc: RequestValidationError):
    if request.url.path.startswith(("/api/integrations", "/api/connector-mappings", "/api/integration-forms")):
        return JSONResponse(status_code=422, content={"detail": "Invalid Integration request. Check the declared fields."}, headers={"Cache-Control": "no-store"})
    if request.url.path.startswith("/api/integration-catalogue/"):
        return JSONResponse(status_code=422, content={"detail": "Invalid Connector package selection"},
                            headers={"Cache-Control": "no-store"})
    if request.url.path.startswith(("/api/auth/", "/api/users", "/api/system-settings/backups", "/api/system-settings/restore", "/api/setup/restore")):
        return JSONResponse(status_code=422, content={"detail": "Invalid authentication request. Check the supplied fields."},
                            headers={"Cache-Control": "no-store"})
    if request.url.path.startswith("/api/setup/"):
        # FastAPI normally echoes invalid input, even with Pydantic's
        # hide_input_in_errors. Setup credentials must never be echoed.
        errors = [{key: value for key, value in error.items() if key not in {"input", "ctx"}}
                  for error in exc.errors()]
        return JSONResponse(status_code=422, content={"detail": errors}, headers={"Cache-Control": "no-store"})
    return await request_validation_exception_handler(request, exc)


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
    from app.services.backup_runtime import normal_operation
    from app.services.backup_archive import BackupError
    try:
        if request.url.path == "/api/health" or request.url.path.startswith("/api/restore-status/"):
            response = await call_next(request)
        else:
            with normal_operation():
                response = await call_next(request)
    except BackupError:
        return JSONResponse(status_code=503, content={"detail": "Atlas is in maintenance mode. A restore or local recovery is in progress."},
                            headers={"Cache-Control": "no-store", "Retry-After": "5", "X-Request-ID": request_id})
    response.headers["X-Request-ID"] = request_id
    if request.url.path.startswith(("/api/setup/", "/api/auth/", "/api/users", "/api/system-settings", "/api/restore-status/", "/api/integration-runtime", "/api/integration-catalogue", "/api/installed-connectors", "/api/integrations", "/api/integration-forms", "/api/connector-mappings")):
        response.headers["Cache-Control"] = "no-store"
    return response


api_router = APIRouter()
api_router.include_router(auth.router)
api_router.include_router(mfa.router)
api_router.include_router(backups.router)
api_router.include_router(backups.setup_router)
api_router.include_router(backups.status_router)
api_router.include_router(setup.router)
api_router.include_router(context.router)
api_router.include_router(users.router)
api_router.include_router(roles.router)
api_router.include_router(roles.permissions_router)
api_router.include_router(customers.router)
api_router.include_router(sites.router)
api_router.include_router(service_reference_data.service_types_router)
api_router.include_router(service_reference_data.criticality_router)
api_router.include_router(services.router)
api_router.include_router(business_functions.router)
api_router.include_router(operational_graph.router)
api_router.include_router(dependency_analysis.router)
api_router.include_router(asset_categories.router)
api_router.include_router(topology_positions.router)
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
api_router.include_router(knowledge_completeness.router)
api_router.include_router(changes.router)
api_router.include_router(protected.router)
api_router.include_router(integrations.router)
api_router.include_router(integration_connections.router)


@api_router.get("/health", tags=["health"])
async def health() -> dict[str, str]:
    """Report whether the API process is available."""
    from app.services.backup_runtime import maintenance
    return {"status": "maintenance" if maintenance() else "ok"}


app.include_router(api_router, prefix="/api")
