"""Stitch the manifest table and list models, sources, snapshots, and tests."""

from __future__ import annotations

from fastapi import APIRouter
from pydantic import BaseModel

from app.manifest_store import catalog, load_manifest
from app.runner import rerun_manifest_test

router = APIRouter(prefix="/manifest", tags=["manifest"])


class RerunIn(BaseModel):
    unique_id: str


@router.post("/load")
def load() -> dict:
    return load_manifest()


@router.get("")
def current() -> dict:
    return catalog()


@router.post("/tests/rerun")
def rerun(body: RerunIn) -> dict:
    return rerun_manifest_test(body.unique_id.strip())
