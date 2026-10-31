"""Compile diff, environment diff, and file diff."""

from __future__ import annotations

from fastapi import APIRouter
from pydantic import BaseModel, Field

from app.compare import compare_environments, compare_files, compile_candidate

router = APIRouter(prefix="/compare", tags=["compare"])


class CompileIn(BaseModel):
    branch: str | None = None
    sql: str | None = None
    model_name: str | None = None
    model_path: str | None = None


class SideIn(BaseModel):
    database: str
    schema_name: str


class EnvironmentIn(BaseModel):
    relation: str
    left: SideIn
    right: SideIn
    key_columns: list[str] = Field(default_factory=list)


class FileIn(BaseModel):
    unique_id: str


@router.post("/compile")
def compile_change(body: CompileIn) -> dict:
    return compile_candidate(body.branch, body.sql, body.model_name, body.model_path)


@router.post("/environments")
def environments(body: EnvironmentIn) -> dict:
    return compare_environments(
        body.relation,
        body.left.model_dump(),
        body.right.model_dump(),
        body.key_columns,
    )


@router.post("/files")
def files(body: FileIn) -> dict:
    return compare_files(body.unique_id.strip())
