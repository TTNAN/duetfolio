"""FastAPI application entrypoint.

On startup, Alembic migrations are applied automatically (upgrade head),
so a fresh clone only needs `uvicorn app.main:app` after `pip install`.
"""
from contextlib import asynccontextmanager
import secrets

from alembic import command
from alembic.config import Config as AlembicConfig
from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse

from app import config
from app.api.routes import router


def run_migrations() -> None:
    cfg = AlembicConfig("alembic.ini")
    command.upgrade(cfg, "head")


@asynccontextmanager
async def lifespan(app: FastAPI):
    run_migrations()
    yield


app = FastAPI(title="duetfolio", version="0.1.0",
              description="Dual-market (US+HK) portfolio tracker API",
              lifespan=lifespan)
app.add_middleware(
    CORSMiddleware,
    allow_origins=config.CORS_ORIGINS,
    # browsers forbid allow_credentials with a wildcard origin; only send
    # credentials when specific origins are configured
    allow_credentials=config.CORS_ORIGINS != ["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)
app.include_router(router, prefix="/api")


@app.middleware("http")
async def optional_basic_auth(request: Request, call_next):
    """Gate /api/* behind HTTP Basic auth when BASIC_AUTH_USER+PASS are set.

    Disabled entirely when unset (local dev). /api/health stays public so
    uptime checks keep working.
    """
    if (config.BASIC_AUTH_USER and config.BASIC_AUTH_PASS
            and request.url.path.startswith("/api/")
            and request.url.path != "/api/health"):
        import base64
        expected = "Basic " + base64.b64encode(
            f"{config.BASIC_AUTH_USER}:{config.BASIC_AUTH_PASS}".encode()
        ).decode()
        got = request.headers.get("authorization", "")
        if not secrets.compare_digest(got, expected):
            return JSONResponse(
                {"detail": "Unauthorized"},
                status_code=401,
                headers={"WWW-Authenticate": "Basic"},
            )
    return await call_next(request)
