"""Recent runs and one result."""

from __future__ import annotations

from fastapi import APIRouter

from app.db import get_run, home_summary

router = APIRouter(tags=["runs"])


@router.get("/home")
def home() -> dict:
    return home_summary()


@router.get("/runs/{run_id}")
def run(run_id: int) -> dict:
    return get_run(run_id)
