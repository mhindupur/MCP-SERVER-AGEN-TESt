from __future__ import annotations

import uvicorn
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from ide_platform_api.auth_oidc import router as auth_router
from ide_platform_api.config import settings
from ide_platform_api.db import Base, engine
from ide_platform_api.routes import router as api_router


def create_app() -> FastAPI:
    app = FastAPI(title="IDE Platform API", version="0.1.0")

    app.add_middleware(
        CORSMiddleware,
        allow_origins=settings.cors_origins,
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )

    app.include_router(auth_router)
    app.include_router(api_router)

    @app.on_event("startup")
    def _startup():
        # Dev convenience. In production, use Alembic migrations.
        Base.metadata.create_all(bind=engine)

    return app


app = create_app()


def run():
    uvicorn.run("ide_platform_api.main:app", host="0.0.0.0", port=8000, reload=False)
