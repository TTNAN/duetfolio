"""FastAPI application entrypoint.

On startup, Alembic migrations are applied automatically (upgrade head),
so a fresh clone only needs `uvicorn app.main:app` after `pip install`.
"""
from contextlib import asynccontextmanager

from alembic import command
from alembic.config import Config as AlembicConfig
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

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
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)
app.include_router(router, prefix="/api")
