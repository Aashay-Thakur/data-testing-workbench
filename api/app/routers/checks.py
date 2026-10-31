"""Saved quick checks."""

from __future__ import annotations

from typing import Any

from fastapi import APIRouter
from pydantic import BaseModel, Field

from app.catalog import CHECK_KINDS
from app.db import list_checks
from app.runner import run_saved, save_check

router = APIRouter(prefix="/checks", tags=["checks"])


class TargetIn(BaseModel):
    database: str | None = None
    schema_name: str | None = None
    relation: str | None = None
    unique_id: str | None = None


class CheckIn(BaseModel):
    name: str | None = None
    kind: str
    label: str | None = None
    blocking: bool = False
    target: TargetIn = Field(default_factory=TargetIn)
    params: dict[str, Any] = Field(default_factory=dict)


@router.get("/kinds")
def kinds() -> list[dict]:
    return CHECK_KINDS


@router.get("")
def checks() -> list[dict]:
    return [item for item in list_checks() if item["origin"] == "check"]


@router.post("")
def create(body: CheckIn) -> dict:
    return save_check(body.model_dump(), origin="check")


@router.post("/{check_id}/run")
def run(check_id: int) -> dict:
    return run_saved(check_id)
