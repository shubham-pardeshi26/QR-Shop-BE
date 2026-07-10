"""FastAPI application factory."""
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from slowapi import _rate_limit_exceeded_handler
from slowapi.errors import RateLimitExceeded

from app.api import admin, auth, health, platform, public, staff
from app.core.config import settings
from app.core.rate_limit import limiter


def create_app() -> FastAPI:
    app = FastAPI(
        title=settings.app_name,
        version="0.1.0",
        description="Gamified queue-engagement + coupon platform (multi-tenant).",
    )

    # Rate limiting (slowapi) — used via @limiter.limit on hot public routes.
    app.state.limiter = limiter
    app.add_exception_handler(RateLimitExceeded, _rate_limit_exceeded_handler)

    app.add_middleware(
        CORSMiddleware,
        allow_origins=settings.cors_origins_list,
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )

    # Routers
    app.include_router(health.router, prefix=settings.api_v1_prefix)
    app.include_router(auth.router, prefix=settings.api_v1_prefix)
    app.include_router(platform.router, prefix=settings.api_v1_prefix)
    app.include_router(admin.router, prefix=settings.api_v1_prefix)
    app.include_router(public.router, prefix=settings.api_v1_prefix)
    app.include_router(staff.router, prefix=settings.api_v1_prefix)

    @app.get("/", tags=["root"])
    def root() -> dict:
        return {"service": settings.app_name, "docs": "/docs"}

    return app


app = create_app()
