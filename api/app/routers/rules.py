"""Business-rule templates. They use the same scorer as quick checks."""

from __future__ import annotations

from typing import Any

from fastapi import APIRouter
from pydantic import BaseModel, Field

from app.catalog import RULE_TEMPLATES
from app.db import list_checks
from app.runner import run_saved, save_check

router = APIRouter(prefix="/rules", tags=["rules"])


class TargetIn(BaseModel):
    database: str | None = None
    schema_name: str | None = None
    relation: str | None = None
    unique_id: str | None = None


class RuleIn(BaseModel):
    name: str | None = None
    kind: str
    label: str | None = None
    blocking: bool = False
    target: TargetIn = Field(default_factory=TargetIn)
    params: dict[str, Any] = Field(default_factory=dict)


@router.get("/templates")
def templates() -> list[dict]:
    return RULE_TEMPLATES


@router.get("")
def rules() -> list[dict]:
    return [item for item in list_checks() if item["origin"] == "rule"]


@router.post("")
def create(body: RuleIn) -> dict:
    if body.kind not in {item["kind"] for item in RULE_TEMPLATES}:
        from app.errors import UserError

        raise UserError("That is not a business-rule template.", 400)
    return save_check(body.model_dump(), origin="rule")


@router.post("/{rule_id}/run")
def run(rule_id: int) -> dict:
    return run_saved(rule_id)
