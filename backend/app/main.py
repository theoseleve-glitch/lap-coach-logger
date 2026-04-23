"""FastAPI application factory.

Includes CORS, structured JSON error handler, and the three routers
(ingest, auth, read).
"""

from __future__ import annotations

import logging
from contextlib import asynccontextmanager

from fastapi import FastAPI, Request
from fastapi.exceptions import RequestValidationError
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from starlette.exceptions import HTTPException as StarletteHTTPException

from app.config import get_settings
from app.database import dispose_engine
from app.routers import admin, auth_routes, bundles, ingest, read, registry

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s | %(levelname)-8s | %(name)s | %(message)s",
)
log = logging.getLogger(__name__)


@asynccontextmanager
async def lifespan(app: FastAPI):
    # Initialize object storage (MinIO) on startup.
    try:
        from app.storage import ObjectStore
        store = ObjectStore(get_settings())
        store.ensure_bucket()
        bundles.set_store(store)
        log.info("Object storage ready (bucket=%s)", get_settings().s3_bucket)
    except Exception:
        log.warning("Object storage unavailable — bundle uploads disabled", exc_info=True)
    yield
    await dispose_engine()


def create_app() -> FastAPI:
    settings = get_settings()
    app = FastAPI(
        title="Lap Coach Logger API",
        version="0.1.0",
        description="Connected v1 ingestion + read API.",
        lifespan=lifespan,
    )

    if settings.cors_origins:
        app.add_middleware(
            CORSMiddleware,
            allow_origins=settings.cors_origins,
            allow_credentials=True,     # cookies must cross origins for auth
            allow_methods=["GET", "POST", "OPTIONS"],
            allow_headers=["Authorization", "Content-Type", "Idempotency-Key"],
        )

    # -------- error handlers: always return the { ok, code, message } shape --
    @app.exception_handler(StarletteHTTPException)
    async def http_exception_handler(_: Request, exc: StarletteHTTPException):
        detail = exc.detail
        if isinstance(detail, dict) and "ok" in detail:
            return JSONResponse(status_code=exc.status_code, content=detail)
        return JSONResponse(
            status_code=exc.status_code,
            content={"ok": False, "code": f"http_{exc.status_code}", "message": str(detail)},
        )

    @app.exception_handler(RequestValidationError)
    async def validation_exception_handler(_: Request, exc: RequestValidationError):
        # Surface only the first field error to the desktop — matches the
        # typed error envelope the desktop's transport expects.
        errors = exc.errors()
        first = errors[0] if errors else {"loc": ["_root"], "msg": "invalid body"}
        field = ".".join(str(p) for p in first.get("loc", []) if p != "body")
        return JSONResponse(
            status_code=400,
            content={
                "ok": False,
                "code": "invalid_payload",
                "message": str(first.get("msg", "invalid")),
                "field": field or None,
            },
        )

    # Routers — all under /v1 prefix for API versioning
    app.include_router(ingest.router, prefix="/v1")
    app.include_router(auth_routes.router, prefix="/v1")
    app.include_router(read.router, prefix="/v1")
    app.include_router(registry.router, prefix="/v1")
    app.include_router(bundles.router, prefix="/v1")
    app.include_router(admin.router, prefix="/v1")

    @app.get("/health")
    async def health():
        return {"ok": True}

    log.info("Lap Coach backend ready (cors_origins=%s)", settings.cors_origins or "same-origin")
    return app


app = create_app()
