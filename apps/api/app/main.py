import os
import uuid

from fastapi import FastAPI, Request
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
    return [
        origin.strip()
        for origin in os.getenv("CORS_ORIGINS", "http://localhost:3000").split(",")
        if origin.strip()
    ]


app = FastAPI(title="Atlas API")
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
        and origin not in allowed_origins()
    ):
        return JSONResponse(
            status_code=403,
            content={"detail": "Request origin is not allowed"},
            headers={"X-Request-ID": request_id},
        )
    response = await call_next(request)
    response.headers["X-Request-ID"] = request_id
    return response


app.include_router(auth.router)
app.include_router(context.router)
app.include_router(users.router)
app.include_router(roles.router)
app.include_router(roles.permissions_router)
app.include_router(customers.router)
app.include_router(sites.router)
app.include_router(reference_data.asset_types_router)
app.include_router(reference_data.relationship_types_router)
app.include_router(custom_fields.router)
app.include_router(assets.router)
app.include_router(custom_fields.asset_values_router)
app.include_router(asset_relationships.router)
app.include_router(networks.router)
app.include_router(asset_interfaces.router)
app.include_router(topology.router)
app.include_router(audit.router)
app.include_router(system_settings.router)
app.include_router(manual_assets.router)
app.include_router(protected.router)


@app.get("/health", tags=["health"])
async def health() -> dict[str, str]:
    """Report whether the API process is available."""
    return {"status": "ok"}
