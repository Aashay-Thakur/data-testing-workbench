"""Environment configuration. Values stay in memory and are not stored."""

from __future__ import annotations

import os
from dataclasses import dataclass
from pathlib import Path

from dotenv import load_dotenv

ROOT = Path(__file__).resolve().parents[2]
API_DIR = Path(__file__).resolve().parents[1]
DATA_DIR = API_DIR / "data"

load_dotenv(ROOT / ".env", override=False)
load_dotenv(API_DIR / ".env", override=False)

STATEMENT_TIMEOUT_SECONDS = 120
SAMPLE_CAP = 100

REQUIRED_VARS = (
    "SNOWFLAKE_ACCOUNT",
    "SNOWFLAKE_USER",
    "SNOWFLAKE_ROLE",
    "SNOWFLAKE_WAREHOUSE",
    "SNOWFLAKE_DATABASE",
    "SNOWFLAKE_SCHEMA",
    "SNOWFLAKE_MANIFEST_TABLE",
    "GITHUB_TOKEN",
    "GITHUB_REPO",
    "GITHUB_BRANCH",
    "DBT_PROJECT_DIR",
)


def _raw(name: str) -> str:
    return os.getenv(name, "").strip()


def env_set(name: str) -> bool:
    return bool(_raw(name))


def private_key_material() -> str:
    """Return PEM text from the env var or from a path it points at. Never log it."""
    raw = os.getenv("SNOWFLAKE_PRIVATE_KEY", "")
    if not raw.strip():
        return ""
    text = raw.strip()
    if "-----BEGIN" in text:
        return text.replace("\\n", "\n")
    if len(text) < 500:
        path = Path(text).expanduser()
        try:
            if path.is_file():
                return path.read_text()
        except OSError:
            return ""
    return text.replace("\\n", "\n")


@dataclass(frozen=True)
class Settings:
    account: str
    user: str
    role: str
    warehouse: str
    database: str
    schema_name: str
    manifest_table: str
    password: str
    private_key: str
    github_token: str
    github_repo: str
    github_branch: str
    dbt_project_dir: str

    @property
    def snowflake_configured(self) -> bool:
        return bool(
            self.account
            and self.user
            and self.role
            and self.warehouse
            and (self.password or self.private_key)
        )


def get_settings() -> Settings:
    return Settings(
        account=_raw("SNOWFLAKE_ACCOUNT"),
        user=_raw("SNOWFLAKE_USER"),
        role=_raw("SNOWFLAKE_ROLE"),
        warehouse=_raw("SNOWFLAKE_WAREHOUSE"),
        database=_raw("SNOWFLAKE_DATABASE"),
        schema_name=_raw("SNOWFLAKE_SCHEMA"),
        manifest_table=_raw("SNOWFLAKE_MANIFEST_TABLE"),
        password=_raw("SNOWFLAKE_PASSWORD"),
        private_key=private_key_material(),
        github_token=_raw("GITHUB_TOKEN"),
        github_repo=_raw("GITHUB_REPO"),
        github_branch=_raw("GITHUB_BRANCH"),
        dbt_project_dir=_raw("DBT_PROJECT_DIR"),
    )


def public_settings() -> dict:
    """Booleans for required variables, plus account, role, and repo."""
    settings = get_settings()
    flags = {name: env_set(name) for name in REQUIRED_VARS}
    flags["SNOWFLAKE_PASSWORD"] = env_set("SNOWFLAKE_PASSWORD")
    flags["SNOWFLAKE_PRIVATE_KEY"] = bool(settings.private_key)
    flags["SNOWFLAKE_AUTH"] = flags["SNOWFLAKE_PASSWORD"] or flags["SNOWFLAKE_PRIVATE_KEY"]
    return {
        "account": settings.account or None,
        "role": settings.role or None,
        "repo": settings.github_repo or None,
        "vars": flags,
    }


def register_loaded_secrets() -> None:
    from app.redact import register_secret

    settings = get_settings()
    register_secret(settings.password)
    register_secret(settings.private_key)
    register_secret(settings.github_token)
