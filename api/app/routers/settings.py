"""Settings: which variables are set, plus non-secret connection tests."""

from __future__ import annotations

from fastapi import APIRouter

from app.config import get_settings, public_settings
from app.errors import QueryError, UserError
from app.snowflake_client import test_connection

router = APIRouter(tags=["settings"])


@router.get("/settings")
def read_settings() -> dict:
    return public_settings()


@router.post("/settings/test-snowflake")
def snowflake_test() -> dict:
    try:
        return test_connection()
    except (UserError, QueryError) as exc:
        return {
            "ok": False,
            "detail": exc.message,
            "account": get_settings().account or None,
            "role": get_settings().role or None,
        }


@router.post("/settings/test-token")
def token_test() -> dict:
    token_set = bool(get_settings().github_token)
    return {
        "ok": token_set,
        "token_set": token_set,
        "detail": None if token_set else "GITHUB_TOKEN is not set.",
    }
