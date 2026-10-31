"""FastAPI entrypoint. The browser never receives credentials."""

from __future__ import annotations

import logging
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse

from app.config import register_loaded_secrets
from app.db import init_db
from app.errors import AppError
from app.identifiers import IdentifierError
from app.redact import install_redaction, scrub
from app.routers import checks, compare, explore, manifest, rules, runs, settings, snowflake
from app.sql_guard import SqlRejected


@asynccontextmanager
async def lifespan(_app: FastAPI):
    install_redaction()
    register_loaded_secrets()
    init_db()
    yield


app = FastAPI(title="Data testing workbench", lifespan=lifespan)
app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://127.0.0.1:5173", "http://localhost:5173"],
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(settings.router, prefix="/api")
app.include_router(snowflake.router, prefix="/api")
app.include_router(manifest.router, prefix="/api")
app.include_router(explore.router, prefix="/api")
app.include_router(checks.router, prefix="/api")
app.include_router(rules.router, prefix="/api")
app.include_router(compare.router, prefix="/api")
app.include_router(runs.router, prefix="/api")


@app.get("/api/health")
def health() -> dict:
    return {"status": "ok"}


@app.exception_handler(AppError)
async def app_error(_request, exc: AppError):
    return JSONResponse(status_code=exc.status_code, content={"detail": scrub(exc.message)})


@app.exception_handler(SqlRejected)
async def sql_rejected(_request, exc: SqlRejected):
    return JSONResponse(status_code=400, content={"detail": str(exc)})


@app.exception_handler(IdentifierError)
async def bad_identifier(_request, exc: IdentifierError):
    return JSONResponse(status_code=400, content={"detail": str(exc)})


@app.exception_handler(Exception)
async def unexpected(_request, exc: Exception):
    logging.getLogger("workbench").exception("request failed: %s", exc)
    return JSONResponse(status_code=500, content={"detail": "The request failed."})
