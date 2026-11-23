"""core-api: money, ledger, insights, collab, nudges. This service never calls an LLM."""

from __future__ import annotations

import json
import logging
import sys
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager
from typing import Any

from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse

from core_api import models as m
from core_api.api import internal, public
from core_api.config import get_settings
from core_api.db import dispose_engine, get_engine, get_sessionmaker
from core_api.seed.loader import check_ledger_source, seed_reference


class JsonFormatter(logging.Formatter):
    """Structured logs. Never log phone numbers, transcripts, SMS bodies or tokens."""

    def format(self, record: logging.LogRecord) -> str:
        out: dict[str, Any] = {"severity": record.levelname, "logger": record.name, "message": record.getMessage()}
        if record.exc_info:
            out["exception"] = self.formatException(record.exc_info)
        return json.dumps(out, ensure_ascii=False)


def setup_logging() -> None:
    handler = logging.StreamHandler(sys.stdout)
    handler.setFormatter(JsonFormatter())
    root = logging.getLogger()
    root.handlers[:] = [handler]
    root.setLevel(logging.INFO)


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncIterator[None]:
    setup_logging()
    settings = get_settings()
    if settings.env != "local" and settings.auth_mode == "dev":
        raise RuntimeError("AUTH_MODE=dev is for local only")
    check_ledger_source()
    engine = get_engine()
    if engine.url.get_backend_name() == "sqlite":
        # Zero-setup fallback: no migrations to run, so create the schema directly.
        async with engine.begin() as conn:
            await conn.run_sync(m.Base.metadata.create_all)
    async with get_sessionmaker()() as session:
        await seed_reference(session)
    yield
    await dispose_engine()


app = FastAPI(title="Pocket core-api", version="0.1.0", lifespan=lifespan)
_origins = [o.strip() for o in get_settings().cors_origins.split(",") if o.strip()]
app.add_middleware(CORSMiddleware, allow_origins=_origins, allow_methods=["*"], allow_headers=["*"])
app.include_router(public.router)
app.include_router(internal.router)


@app.get("/health")  # Cloud Run keeps /healthz for itself and answers 404 without reaching the service
@app.get("/healthz")
async def healthz() -> dict[str, str]:
    return {"status": "ok", "service": "core-api"}


@app.exception_handler(Exception)
async def unhandled(request: Request, exc: Exception) -> JSONResponse:
    logging.getLogger("core_api").exception("unhandled error on %s %s", request.method, request.url.path)
    return JSONResponse(status_code=500, content={"detail": "something went wrong"})
