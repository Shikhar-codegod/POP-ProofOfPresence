"""Main FastAPI application entrypoint for POP (ProofOfPresence).

Serves core API routes, interactive Swagger/ReDoc documentation, and health check endpoints.
"""

import logging
from datetime import UTC, datetime
from typing import Any

from fastapi import FastAPI, HTTPException, Request, status
from fastapi.exceptions import RequestValidationError
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse

from app.api.v1.auth import router as auth_router
from app.api.v1.centres import router as centres_router
from app.api.v1.readings import router as readings_router

# Configure structured application logger
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
)
logger = logging.getLogger("pop.backend")

app = FastAPI(
    title="ProofOfPresence (POP) API",
    version="1.0.0",
    description=(
        "Edge-AI video analytics platform that verifies attendance counts and "
        "infrastructure compliance at government-funded vocational skilling centres."
    ),
    docs_url="/docs",
    redoc_url="/redoc",
    openapi_url="/openapi.json",
)

# Configure CORS
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.exception_handler(HTTPException)
async def http_exception_handler(request: Request, exc: HTTPException) -> JSONResponse:
    """Ensure HTTPException responses conform to the POP standard error format."""
    if isinstance(exc.detail, dict) and "error" in exc.detail:
        content = exc.detail
    else:
        content = {
            "error": {
                "code": f"HTTP_{exc.status_code}",
                "message": str(exc.detail),
                "details": None,
            }
        }
    return JSONResponse(status_code=exc.status_code, content=content, headers=exc.headers)


@app.exception_handler(RequestValidationError)
async def validation_exception_handler(request: Request, exc: RequestValidationError) -> JSONResponse:
    """Format Pydantic validation errors using the POP standard error envelope."""
    return JSONResponse(
        status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
        content={
            "error": {
                "code": "VALIDATION_ERROR",
                "message": "Request validation failed.",
                "details": exc.errors(),
            }
        },
    )


# Register v1 routers
app.include_router(auth_router, prefix="/api/v1")
app.include_router(centres_router, prefix="/api/v1")
app.include_router(readings_router, prefix="/api/v1")


@app.on_event("startup")
async def startup_event() -> None:
    """Execute startup routines, connection pool checks, and logger initialization."""
    logger.info("Starting POP Backend API service v1.0.0")


@app.on_event("shutdown")
async def shutdown_event() -> None:
    """Execute graceful cleanup routines on service termination."""
    logger.info("Shutting down POP Backend API service")


@app.get("/health", tags=["System"])
async def health_check() -> dict[str, Any]:
    """Health check probe for container orchestrators and edge heartbeats.

    Returns:
        Dict[str, Any]: Service health status, UTC timestamp, and service metadata.
    """
    return {
        "status": "healthy",
        "service": "pop-backend",
        "timestamp": datetime.now(UTC).isoformat(),
        "version": "1.0.0",
    }
