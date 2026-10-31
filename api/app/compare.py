"""Compare a compile, two environments, or model files. Warehouse statements stay reads."""

from __future__ import annotations

import difflib
import json
import shutil
from datetime import datetime, timezone
from pathlib import Path

from app.config import DATA_DIR, get_settings
from app.dbt_ops import delete_profiles, profile_name, run_dbt, write_profiles
from app.errors import QueryError, UserError
from app.git_ops import clone_readonly, git_diff, rev_parse
from app.identifiers import IdentifierError, quote_ident
from app.manifest_diff import diff_manifests
from app.manifest_store import get_manifest, get_node
from app.snowflake_client import fetch, resolve_relation
from app.sql_guard import guard_sql
from app.sql_templates import (
    column_metrics_sql,
    key_count_sql,
    key_match_sql,
    key_mismatch_sql,
    row_count_sql,
    schema_sql,
)

NUMERIC_TYPES = {
    "NUMBER",
    "DECIMAL",
    "NUMERIC",
    "INT",
    "INTEGER",
    "BIGINT",
    "SMALLINT",
    "TINYINT",
    "BYTEINT",
    "FLOAT",
    "FLOAT4",
    "FLOAT8",
    "DOUBLE",
    "DOUBLE PRECISION",
    "REAL",
    "FIXED",
}
LATEST_PATH = DATA_DIR / "compiles" / "latest.json"
_SKIPPED = "Schema and aggregate diffs run only when the relation already exists on both sides."


def compile_candidate(branch: str | None, sql: str | None, model_name: str | None, model_path: str | None) -> dict:
    if not branch and not sql:
        raise UserError("Provide a branch or pasted SQL to compile.", 400)
    if sql and len(sql) > 200_000:
        raise UserError("Pasted SQL is too long.", 400)
    if model_name:
        quote_ident(model_name)

    stamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%S")
    work = DATA_DIR / "compiles" / stamp
    project = work / "project"
    profiles_dir = work / "profiles"
    work.mkdir(parents=True)
    profiles_dir.mkdir()
    git_sha = None
    try:
        source, git_sha = _source_project(branch)
        if source is None:
            _minimal_project(project)
        else:
            shutil.copytree(
                source,
                project,
                ignore=shutil.ignore_patterns("target", "logs", ".git"),
                dirs_exist_ok=True,
            )
        if sql:
            if not model_name:
                raise UserError("model_name is required when SQL is pasted.", 400)
            destination = _model_destination(project, model_name, model_path)
            destination.write_text(sql)
        write_profiles(profiles_dir, profile_name(project))
        select = model_name if sql else None
        run_dbt("parse", project, profiles_dir, select=select)
        run_dbt("compile", project, profiles_dir, select=select)
    finally:
        delete_profiles(profiles_dir)

    manifest_path = project / "target" / "manifest.json"
    if not manifest_path.is_file():
        raise UserError("dbt compile did not write target/manifest.json.", 400)
    candidate = json.loads(manifest_path.read_text())
    deployed = get_manifest()
    diff = diff_manifests(deployed, candidate)
    LATEST_PATH.write_text(
        json.dumps(
            {
                "git_sha": git_sha,
                "branch": branch,
                "manifest_path": str(manifest_path),
                "project_dir": str(project),
                "created_at": datetime.now(timezone.utc).isoformat(),
            }
        )
    )
    diff["git_sha"] = git_sha
    diff["note"] = (
        "dbt compile does not build relations. Models the deploy role has not created "
        "are diffed as SQL and lineage only."
    )
    return diff


def compare_environments(relation: str, left: dict, right: dict, key_columns: list[str]) -> dict:
    quote_ident(relation)
    keys = []
    for column in key_columns:
        quote_ident(column)
        keys.append(column)
    if not keys:
        raise UserError("Key columns are required for a key match. No key was guessed.", 400)

    left_resolved, left_error = _try_resolve(left["database"], left["schema_name"], relation)
    right_resolved, right_error = _try_resolve(right["database"], right["schema_name"], relation)
    result = {
        "relation": relation,
        "left_exists": left_resolved is not None,
        "right_exists": right_resolved is not None,
        "left_error": left_error,
        "right_error": right_error,
    }
    if left_resolved is None or right_resolved is None:
        result["skipped"] = _SKIPPED
        return result

    left_columns = _columns(left_resolved)
    right_columns = _columns(right_resolved)
    result["schema"] = _schema_diff(left_columns, right_columns)
    result["columns_truncated"] = len(left_columns) >= 100 or len(right_columns) >= 100
    shared = _shared_columns(left_columns, right_columns)
    numeric = [
        column
        for column in shared
        if _is_numeric(left_columns, column) and _is_numeric(right_columns, column)
    ]
    result["row_count"] = {
        "left": _scalar(row_count_sql(left_resolved["qualified"])[0], "row_count"),
        "right": _scalar(row_count_sql(right_resolved["qualified"])[0], "row_count"),
    }
    result["nulls"] = _nulls(left_resolved, right_resolved, shared)
    result["aggregates"] = _aggregates(left_resolved, right_resolved, numeric)
    result["keys"] = _keys(left_resolved, right_resolved, keys, left_columns, right_columns)
    return result


def compare_files(unique_id: str) -> dict:
    node = get_node(unique_id)
    raw = node.get("raw_code") or node.get("raw_sql") or ""
    compiled = node.get("compiled_code") or node.get("compiled_sql") or ""
    relative = node.get("original_file_path") or ""
    meta = _latest()
    candidate_node = None
    if meta:
        candidate = json.loads(Path(meta["manifest_path"]).read_text())
        candidate_node = (candidate.get("nodes") or {}).get(unique_id)
    payload = {
        "unique_id": unique_id,
        "path": relative,
        "source": None,
        "raw_diff": "",
        "compiled_diff": "",
        "git_diff": None,
        "git_sha": meta.get("git_sha") if meta else None,
        "gaps": [],
    }
    if isinstance(candidate_node, dict):
        payload["source"] = "local compile"
        payload["raw_diff"] = _unified(raw, candidate_node.get("raw_code") or "", "raw_code")
        payload["compiled_diff"] = _unified(
            compiled, candidate_node.get("compiled_code") or "", "compiled_code"
        )
        return payload

    project = _project_dir(meta)
    file_text = _read_project_file(project, relative) if project and relative else None
    if file_text is not None:
        payload["source"] = "project file"
        payload["raw_diff"] = _unified(raw, file_text, "model.sql")
        payload["gaps"].append("compiled_code was not diffed because there is no local dbt compile for this model.")
        return payload
    if project and relative and (project / ".git").exists():
        payload["source"] = "git diff"
        payload["git_diff"] = git_diff(project, relative)
        payload["gaps"].append("The model file was not read from the project, so this is a read-only git diff.")
        return payload
    payload["gaps"].append("No local compile, project file, or git checkout was available to diff.")
    return payload


def _source_project(branch: str | None) -> tuple[Path | None, str | None]:
    settings = get_settings()
    if branch:
        if not settings.github_token or not settings.github_repo:
            raise UserError("GITHUB_TOKEN and GITHUB_REPO must be set to clone a branch.", 400)
        cloned = clone_readonly(settings.github_repo, branch, settings.github_token)
        return cloned, rev_parse(cloned)
    if settings.dbt_project_dir:
        path = Path(settings.dbt_project_dir)
        if not path.is_dir():
            raise UserError("DBT_PROJECT_DIR is not a directory.", 400)
        return path, rev_parse(path)
    return None, None


def _minimal_project(project: Path) -> None:
    project.mkdir(parents=True, exist_ok=True)
    (project / "models").mkdir()
    (project / "dbt_project.yml").write_text(
        'name: workbench_paste\nversion: "1.0.0"\nprofile: workbench\nmodel-paths: ["models"]\n'
    )


def _model_destination(project: Path, model_name: str, model_path: str | None) -> Path:
    models = project / "models"
    models.mkdir(exist_ok=True)
    if model_path:
        relative = Path(model_path)
        if relative.is_absolute() or ".." in relative.parts or relative.suffix != ".sql":
            raise UserError("model_path must be a relative .sql path under models/.", 400)
        destination = (project / relative).resolve()
        if not str(destination).startswith(str(models.resolve())):
            raise UserError("model_path must stay under models/.", 400)
        destination.parent.mkdir(parents=True, exist_ok=True)
        return destination
    matches = list(models.rglob(f"{model_name}.sql"))
    if len(matches) > 1:
        raise UserError("Multiple model files match that name. Set model_path.", 400)
    if len(matches) == 1:
        return matches[0]
    return models / f"{model_name}.sql"


def _try_resolve(database: str, schema_name: str, relation: str) -> tuple[dict | None, str | None]:
    try:
        return resolve_relation(database, schema_name, relation), None
    except IdentifierError as exc:
        raise UserError(str(exc), 400) from exc
    except QueryError as exc:
        if exc.status_code == 408:
            raise
        text = exc.message.lower()
        if exc.status_code == 404 or "does not exist" in text:
            return None, exc.message
        raise


def _columns(resolved: dict) -> list[dict]:
    from app.snowflake_client import fetch_columns

    return fetch_columns(resolved["database"], resolved["schema_name"], resolved["relation"])


def _schema_diff(left: list[dict], right: list[dict]) -> dict:
    left_index = {str(row["column_name"]).upper(): row for row in left}
    right_index = {str(row["column_name"]).upper(): row for row in right}
    only_left = [row["column_name"] for key, row in left_index.items() if key not in right_index]
    only_right = [row["column_name"] for key, row in right_index.items() if key not in left_index]
    type_mismatches = []
    nullable_mismatches = []
    for key, row in left_index.items():
        other = right_index.get(key)
        if other is None:
            continue
        if str(row.get("data_type", "")).upper() != str(other.get("data_type", "")).upper():
            type_mismatches.append(
                {
                    "column": row["column_name"],
                    "left_type": row.get("data_type"),
                    "right_type": other.get("data_type"),
                }
            )
        if str(row.get("is_nullable", "")).upper() != str(other.get("is_nullable", "")).upper():
            nullable_mismatches.append(
                {
                    "column": row["column_name"],
                    "left_nullable": row.get("is_nullable"),
                    "right_nullable": other.get("is_nullable"),
                }
            )
    return {
        "only_left": only_left,
        "only_right": only_right,
        "type_mismatches": type_mismatches,
        "nullable_mismatches": nullable_mismatches,
    }


def _shared_columns(left: list[dict], right: list[dict]) -> list[str]:
    right_names = {str(row["column_name"]).upper() for row in right}
    shared = []
    for row in left:
        if str(row["column_name"]).upper() in right_names:
            try:
                quote_ident(str(row["column_name"]))
            except IdentifierError:
                continue
            shared.append(str(row["column_name"]))
        if len(shared) >= 80:
            break
    return shared


def _is_numeric(columns: list[dict], name: str) -> bool:
    for row in columns:
        if str(row["column_name"]).upper() == name.upper():
            return str(row.get("data_type", "")).upper() in NUMERIC_TYPES
    return False


def _nulls(left: dict, right: dict, columns: list[str]) -> list[dict]:
    if not columns:
        return []
    quoted = [quote_ident(column) for column in columns]
    left_metrics = fetch(guard_sql(column_metrics_sql(left["qualified"], quoted, [])))
    right_metrics = fetch(guard_sql(column_metrics_sql(right["qualified"], quoted, [])))
    left_row = left_metrics[0] if left_metrics else {}
    right_row = right_metrics[0] if right_metrics else {}
    left_count = int(left_row.get("row_count") or 0)
    right_count = int(right_row.get("row_count") or 0)
    compared = []
    for index, column in enumerate(columns):
        left_nulls = int(left_row.get(f"n_{index}") or 0)
        right_nulls = int(right_row.get(f"n_{index}") or 0)
        compared.append(
            {
                "column": column,
                "left_null_rate": (left_nulls / left_count) if left_count else None,
                "right_null_rate": (right_nulls / right_count) if right_count else None,
            }
        )
    return compared


def _aggregates(left: dict, right: dict, columns: list[str]) -> list[dict]:
    if not columns:
        return []
    quoted = [quote_ident(column) for column in columns]
    left_row = _one(column_metrics_sql(left["qualified"], [], quoted))
    right_row = _one(column_metrics_sql(right["qualified"], [], quoted))
    compared = []
    for index, column in enumerate(columns):
        compared.append(
            {
                "column": column,
                "left": _stats(left_row, index),
                "right": _stats(right_row, index),
            }
        )
    return compared


def _keys(left: dict, right: dict, keys: list[str], left_columns: list[dict], right_columns: list[dict]) -> dict:
    missing = []
    for key in keys:
        if not any(str(row["column_name"]).upper() == key.upper() for row in left_columns):
            missing.append(f"{key} is missing on the left")
        if not any(str(row["column_name"]).upper() == key.upper() for row in right_columns):
            missing.append(f"{key} is missing on the right")
    if missing:
        return {
            "skipped": True,
            "gap": "; ".join(missing) + ". Key match was not run.",
            "mismatch_sample": [],
        }
    quoted = [quote_ident(key) for key in keys]
    left_keys = _scalar(key_count_sql(left["qualified"], quoted, "left_keys"), "left_keys")
    right_keys = _scalar(key_count_sql(right["qualified"], quoted, "right_keys"), "right_keys")
    matched = _scalar(key_match_sql(left["qualified"], right["qualified"], quoted), "matched")
    denominator = max(int(left_keys or 0), int(right_keys or 0))
    match_rate = (int(matched) / denominator) if denominator else None
    left_only = fetch(guard_sql(key_mismatch_sql(left["qualified"], right["qualified"], quoted, "left_only", 50)))
    right_only = fetch(guard_sql(key_mismatch_sql(right["qualified"], left["qualified"], quoted, "right_only", 50)))
    return {
        "skipped": False,
        "key_columns": keys,
        "left_keys": left_keys,
        "right_keys": right_keys,
        "matched": matched,
        "match_rate": match_rate,
        "match_rate_definition": "matched / max(left_keys, right_keys)",
        "mismatch_sample": (left_only + right_only)[:100],
    }


def _scalar(sql: str, key: str):
    rows = fetch(guard_sql(sql))
    if not rows:
        return None
    return rows[0].get(key)


def _one(sql: str) -> dict:
    rows = fetch(guard_sql(sql))
    return rows[0] if rows else {}


def _stats(row: dict, index: int) -> dict:
    return {"min": row.get(f"min_{index}"), "max": row.get(f"max_{index}"), "mean": row.get(f"avg_{index}")}


def _latest() -> dict | None:
    if not LATEST_PATH.is_file():
        return None
    meta = json.loads(LATEST_PATH.read_text())
    path = Path(meta.get("manifest_path", ""))
    if not path.is_file():
        return None
    return meta


def _project_dir(meta: dict | None) -> Path | None:
    if meta and meta.get("project_dir"):
        path = Path(meta["project_dir"])
        if path.is_dir():
            return path
    settings = get_settings()
    if settings.dbt_project_dir:
        path = Path(settings.dbt_project_dir)
        if path.is_dir():
            return path
    return None


def _read_project_file(project: Path | None, relative: str) -> str | None:
    if project is None or not relative:
        return None
    path = Path(relative)
    if path.is_absolute() or ".." in path.parts:
        raise UserError("The model path is not inside the project.", 400)
    file_path = (project / path).resolve()
    if not str(file_path).startswith(str(project.resolve())):
        raise UserError("The model path is not inside the project.", 400)
    if not file_path.is_file():
        return None
    return file_path.read_text()


def _unified(left: str, right: str, name: str) -> str:
    diff = difflib.unified_diff(
        (left or "").splitlines(),
        (right or "").splitlines(),
        fromfile=f"manifest/{name}",
        tofile=f"candidate/{name}",
        lineterm="",
    )
    return "\n".join(diff)
