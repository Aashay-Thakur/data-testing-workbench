"""Model page."""

from __future__ import annotations

from fastapi import APIRouter

from app.explore import explore_node

router = APIRouter(prefix="/explore", tags=["explore"])


@router.get("/node")
def node(unique_id: str) -> dict:
    return explore_node(unique_id)
