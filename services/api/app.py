import time
import uuid
from contextlib import asynccontextmanager
from datetime import datetime, timezone
from fastapi import FastAPI, Request, status
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from fastapi.exceptions import RequestValidationError
from starlette.exceptions import HTTPException as StarletteHTTPException
from sqlalchemy.orm.exc import StaleDataError
from fastapi.encoders import jsonable_encoder

from services.api.config import settings
from services.api.db.session import engine
from sqlalchemy import text as sql_text
from services.api.db.session import async_session_factory
from services.api.security.tenant import get_current_user
from fastapi import Depends
from services.api.db.base import Base
from services.api.db import models  # Ensures all models are registered
from services.api.utils.logging import audit_logger

from services.api.api.auth import router as auth_router
from services.api.api.encounters import router as encounters_router
from services.api.api.documents import router as documents_router
from services.api.api.reviews import router as reviews_router
from services.api.api.references import router as references_router
from services.api.api.audit import router as audit_router
from services.api.api.exports import router as exports_router
from services.api.api.cases import router as cases_router


@asynccontextmanager
async def lifespan(app: FastAPI):
    if settings.APP_ENV == "production":
        raise RuntimeError("Production is disabled for the development catalogs and local controls. Configure and verify production policy, storage, identity, and vendor controls before enabling PHI.")
    # Initialize database tables
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    audit_logger.log(level="info", action="APPLICATION_STARTUP", status="ready")
    yield
    await engine.dispose()
    audit_logger.log(level="info", action="APPLICATION_SHUTDOWN", status="stopped")


app = FastAPI(
    title="Medical Billing & Coding Portal API",
    version="1.0.0",
    docs_url="/docs",
    redoc_url="/redoc",
    lifespan=lifespan,
)

# CORS Configuration
origins = [o.strip() for o in settings.CORS_ORIGINS.split(",") if o.strip()]
app.add_middleware(
    CORSMiddleware,
    allow_origins=origins or ["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


# Request ID and Structured Logging Middleware
@app.middleware("http")
async def request_middleware(request: Request, call_next):
    request_id = request.headers.get("X-Request-ID", str(uuid.uuid4()))
    request.state.request_id = request_id
    start_time = time.time()

    try:
        response = await call_next(request)
        duration_ms = round((time.time() - start_time) * 1000, 2)
        response.headers["X-Request-ID"] = request_id

        # Log completion
        audit_logger.log(
            level="info",
            action=f"{request.method} {request.url.path}",
            request_id=request_id,
            status=str(response.status_code),
            duration_ms=duration_ms,
        )
        return response
    except Exception as exc:
        duration_ms = round((time.time() - start_time) * 1000, 2)
        audit_logger.log(
            level="error",
            action=f"{request.method} {request.url.path}",
            request_id=request_id,
            status="500",
            duration_ms=duration_ms,
            error_code="INTERNAL_SERVER_ERROR",
        )
        return JSONResponse(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            content={
                "error": {
                    "code": "INTERNAL_SERVER_ERROR",
                    "message": "An unexpected error occurred. Please contact system administrator.",
                    "request_id": request_id,
                }
            },
            headers={"X-Request-ID": request_id},
        )


# Global Error Handlers - Never expose stack traces or secrets to browser
@app.exception_handler(StarletteHTTPException)
async def http_exception_handler(request: Request, exc: StarletteHTTPException):
    request_id = getattr(request.state, "request_id", str(uuid.uuid4()))
    return JSONResponse(
        status_code=exc.status_code,
        content={
            "error": {
                "code": f"HTTP_{exc.status_code}",
                "message": exc.detail,
                "request_id": request_id,
            }
        },
        headers={"X-Request-ID": request_id},
    )


@app.exception_handler(RequestValidationError)
async def validation_exception_handler(request: Request, exc: RequestValidationError):
    request_id = getattr(request.state, "request_id", str(uuid.uuid4()))
    return JSONResponse(
        status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
        content={
            "error": {
                "code": "VALIDATION_ERROR",
                "message": "Request validation failed.",
                "details": jsonable_encoder(exc.errors(), custom_encoder={ValueError: str}),
                "request_id": request_id,
            }
        },
        headers={"X-Request-ID": request_id},
    )


@app.exception_handler(StaleDataError)
async def stale_write_handler(request: Request, exc: StaleDataError):
    return JSONResponse(status_code=409, content={"error": {"code": "STALE_VERSION", "message": "Case changed. Reload before making a decision."}})


# Health & Readiness Endpoints (MUST NOT EXPOSE SECRETS)
@app.get("/health", tags=["system"])
async def health_check():
    return {
        "status": "healthy",
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "version": "1.0.0",
        "service": "medical-billing-coding-portal-api",
    }


@app.get("/ready", tags=["system"])
async def readiness_check():
    try:
        async with async_session_factory() as db:
            await db.execute(sql_text("SELECT 1"))
    except Exception:
        return JSONResponse(status_code=503, content={"status": "unavailable", "database": "unavailable"})
    return {
        "status": "ready",
        "database": "connected",
        "storage": settings.STORAGE_PROVIDER,
        "ocr": settings.OCR_PROVIDER,
        "timestamp": datetime.now(timezone.utc).isoformat(),
    }


@app.get("/api/system/capabilities", dependencies=[Depends(get_current_user)])
async def capabilities():
    return {"mode": "synthetic-development", "supported_domains": ["emergency_department", "professional_office"],
            "storage": settings.STORAGE_PROVIDER, "ocr": settings.OCR_PROVIDER,
            "queue": settings.QUEUE_BACKEND, "catalog": "sample-catalog-1", "ruleset": "demo-1",
            "owner_restricted": bool(settings.OWNER_EMAIL), "mfa_configured": bool(settings.OWNER_TOTP_SECRET),
            "session_minutes": settings.ACCESS_TOKEN_EXPIRE_MINUTES, "step_up_seconds": settings.STEP_UP_MAX_AGE_SECONDS,
            "production_enabled": False, "image_ocr_available": False}


# Include Routers
app.include_router(auth_router, prefix="/api")
app.include_router(encounters_router, prefix="/api")
app.include_router(documents_router, prefix="/api")
app.include_router(reviews_router, prefix="/api")
app.include_router(references_router, prefix="/api")
app.include_router(audit_router, prefix="/api")
app.include_router(exports_router, prefix="/api")
app.include_router(cases_router, prefix="/api")
