"""dbt parse and dbt compile only. dbt run, dbt build, and dbt test are refused."""

from __future__ import annotations

import os
import shutil
import subprocess
from pathlib import Path

import yaml

from app.config import get_settings
from app.errors import UserError
from app.redact import scrub

ALLOWED_DBT = frozenset({"parse", "compile"})
FORBIDDEN_DBT = frozenset({"run", "build", "test", "seed", "snapshot", "retry"})


def run_dbt(subcommand: str, project_dir: Path, profiles_dir: Path, select: str | None = None) -> str:
    if subcommand in FORBIDDEN_DBT or subcommand not in ALLOWED_DBT:
        raise UserError("Only dbt parse and dbt compile are allowed.", 400)
    executable = shutil.which("dbt")
    if not executable:
        raise UserError("dbt is not installed in this environment.", 400)
    command = [
        executable,
        subcommand,
        "--project-dir",
        str(project_dir),
        "--profiles-dir",
        str(profiles_dir),
        "--no-use-colors",
    ]
    if select:
        if not select.replace("_", "").replace(".", "").isalnum():
            raise UserError("The dbt --select value is not a plain model name.", 400)
        command.extend(["--select", select])
    env = os.environ.copy()
    env["DBT_SEND_ANONYMOUS_USAGE_STATS"] = "false"
    env["DO_NOT_TRACK"] = "1"
    try:
        completed = subprocess.run(
            command,
            capture_output=True,
            text=True,
            timeout=300,
            env=env,
            check=False,
        )
    except subprocess.TimeoutExpired as exc:
        raise UserError(f"dbt {subcommand} timed out.", 408) from exc
    output = scrub(f"{completed.stdout}\n{completed.stderr}")
    if completed.returncode != 0:
        raise UserError(f"dbt {subcommand} failed. {output[-2000:]}", 400)
    return output


def write_profiles(directory: Path, profile_name: str) -> None:
    """Write query-role credentials into a temp profiles.yml. Caller deletes the directory."""
    settings = get_settings()
    if not settings.snowflake_configured:
        raise UserError("Snowflake credentials are not set, so dbt compile cannot run.", 400)
    output: dict = {
        "type": "snowflake",
        "account": settings.account,
        "user": settings.user,
        "role": settings.role,
        "warehouse": settings.warehouse,
        "database": settings.database,
        "schema": settings.schema_name,
        "threads": 1,
        "client_session_keep_alive": False,
    }
    if settings.private_key:
        key_path = directory / "key.p8"
        text = settings.private_key if settings.private_key.endswith("\n") else settings.private_key + "\n"
        key_path.write_text(text)
        os.chmod(key_path, 0o600)
        output["private_key_path"] = str(key_path)
    else:
        output["password"] = settings.password
    document = {profile_name: {"target": "dev", "outputs": {"dev": output}}}
    path = directory / "profiles.yml"
    path.write_text(yaml.safe_dump(document, sort_keys=False))
    os.chmod(path, 0o600)


def profile_name(project_dir: Path) -> str:
    path = project_dir / "dbt_project.yml"
    if not path.is_file():
        raise UserError(f"dbt_project.yml was not found in {project_dir.name}.", 400)
    loaded = yaml.safe_load(path.read_text()) or {}
    name = loaded.get("profile") if isinstance(loaded, dict) else None
    if not isinstance(name, str) or not name.strip():
        raise UserError("dbt_project.yml has no profile name.", 400)
    return name.strip()


def delete_profiles(directory: Path) -> None:
    if not directory.exists():
        return
    for child in directory.iterdir():
        if child.is_file():
            child.unlink()
    directory.rmdir()
