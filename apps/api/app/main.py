import os

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.routes import auth, customers, manual_assets, protected, sites

app = FastAPI(title="Atlas API")
app.add_middleware(
    CORSMiddleware,
    allow_origins=[
        origin.strip()
        for origin in os.getenv("CORS_ORIGINS", "http://localhost:3000").split(",")
        if origin.strip()
    ],
    allow_credentials=True,
    allow_methods=["GET", "POST", "PATCH", "DELETE", "OPTIONS"],
    allow_headers=["Authorization", "Content-Type"],
)
app.include_router(auth.router)
app.include_router(customers.router)
app.include_router(sites.router)
app.include_router(manual_assets.router)
app.include_router(protected.router)


@app.get("/health", tags=["health"])
async def health() -> dict[str, str]:
    """Report whether the API process is available."""
    return {"status": "ok"}
