"""FastAPI application factory.

Settings, db, billing, quota, and the model bundle live on app.state (not module
globals) so tests can inject a temp DB / fresh settings. The model is loaded once
at startup (cold ~5s), never per request. Routers are included BEFORE the static
mount, and a SPA catch-all serves index.html for client-side routes.
"""

from __future__ import annotations

import os
from contextlib import asynccontextmanager
from pathlib import Path

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse, JSONResponse
from fastapi.staticfiles import StaticFiles

from .billing import get_billing
from .config import Settings, get_settings
from .db import Database
from .model import load_bundle
from .security import QuotaService, RateLimiter
from .routers import analyze as analyze_router
from .routers import auth as auth_router
from .routers import billing as billing_router
from .routers import scan as scan_router

# frontend/dist relative to project root (backend/spamsms/main.py -> up 3 levels)
PROJECT_DIST = str(Path(__file__).resolve().parents[2] / "frontend" / "dist")


def create_app(settings: Settings | None = None) -> FastAPI:
    settings = settings or get_settings()

    @asynccontextmanager
    async def lifespan(app: FastAPI):
        db = Database(settings.database_path)
        app.state.db = db
        app.state.settings = settings
        app.state.billing = get_billing(settings, db)
        app.state.quota = QuotaService(db, settings)
        app.state.rate_limiter = RateLimiter(settings.rate_limit_per_minute)
        # Load the ML bundle once here (sync context). Do NOT do this in a handler.
        app.state.bundle = load_bundle()
        yield
        db.close()

    app = FastAPI(title=settings.app_name, version="1.0.0", lifespan=lifespan)

    if settings.cors_origins:
        app.add_middleware(
            CORSMiddleware,
            allow_origins=settings.cors_origins,
            allow_credentials=False,
            allow_methods=["GET", "POST", "OPTIONS"],
            allow_headers=["Authorization", "Content-Type", "X-Device-Id"],
        )

    app.include_router(auth_router.router)
    app.include_router(analyze_router.router)
    app.include_router(scan_router.router)
    app.include_router(billing_router.router)

    @app.get("/health")
    def health():
        return {"status": "ok", "provider": app.state.billing.name}

    # --- Serve built SPA same-origin (prod/demo). Registered last. ---
    dist_dir = Path(os.environ.get("SPAMSMS_FRONTEND_DIST", PROJECT_DIST))
    if dist_dir.exists() and (dist_dir / "index.html").exists():
        assets = dist_dir / "assets"
        if assets.exists():
            app.mount("/assets", StaticFiles(directory=str(assets)), name="assets")

        @app.get("/{full_path:path}", include_in_schema=False)
        def spa(full_path: str):
            candidate = dist_dir / full_path
            if full_path and candidate.is_file():
                return FileResponse(str(candidate))
            index = dist_dir / "index.html"
            if index.exists():
                return FileResponse(str(index))
            return JSONResponse({"detail": "Frontend not built. Run npm run build."}, status_code=404)

    return app


app = create_app()
