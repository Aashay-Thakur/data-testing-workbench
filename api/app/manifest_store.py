"""Load, stitch, and cache the deployed dbt manifest."""

from __future__ import annotations

import json
import threading

from app.config import DATA_DIR, get_settings
from app.errors import QueryError, UserError
from app.identifiers import quote_ident
from app.manifest_stitch import StitchError, stitch_manifest
from app.snowflake_client import fetch_manifest_lines

_LOCK = threading.Lock()
MANIFEST_PATH = DATA_DIR / "manifest.json"


def manifest_sql() -> str:
    settings = get_settings()
    if not settings.manifest_table:
        raise UserError("SNOWFLAKE_MANIFEST_TABLE is not set.", 400)
    return (
        f"SELECT line, content FROM {_qualify(settings.manifest_table, settings)} "
        "ORDER BY line"
    )


def load_manifest() -> dict:
    settings = get_settings()
    sql = manifest_sql()
    try:
        rows = fetch_manifest_lines(sql)
    except QueryError as exc:
        if exc.status_code == 404:
            raise UserError(
                f"Manifest table {settings.manifest_table} is missing or not visible to the query role. "
                "Expected columns are line and content.",
                404,
            ) from exc
        raise
    try:
        manifest = stitch_manifest(rows)
    except StitchError as exc:
        raise UserError(str(exc), 422) from exc
    _write(manifest)
    return catalog(manifest)


def get_manifest() -> dict:
    if not MANIFEST_PATH.exists():
        raise UserError("The manifest is not loaded. Load it from the manifest table first.", 404)
    try:
        parsed = json.loads(MANIFEST_PATH.read_text())
    except json.JSONDecodeError as exc:
        raise UserError(f"The cached manifest JSON failed to parse: {exc.msg}", 422) from exc
    if not isinstance(parsed, dict):
        raise UserError("The cached manifest JSON failed to parse: the top-level value must be an object.", 422)
    return parsed


def catalog(manifest: dict | None = None) -> dict:
    document = get_manifest() if manifest is None else manifest
    models: list[dict] = []
    snapshots: list[dict] = []
    tests: list[dict] = []
    for node in (document.get("nodes") or {}).values():
        if not isinstance(node, dict):
            continue
        brief = _brief(node)
        kind = node.get("resource_type")
        if kind == "model":
            models.append(brief)
        elif kind == "snapshot":
            snapshots.append(brief)
        elif kind == "test":
            tests.append(brief)
    sources = []
    for node in (document.get("sources") or {}).values():
        if isinstance(node, dict):
            brief = _brief(node)
            brief["resource_type"] = brief.get("resource_type") or "source"
            sources.append(brief)
    for bucket in (models, sources, snapshots, tests):
        bucket.sort(key=lambda item: (item.get("name") or "", item.get("unique_id") or ""))
    return {
        "models": models,
        "sources": sources,
        "snapshots": snapshots,
        "tests": tests,
        "counts": {
            "models": len(models),
            "sources": len(sources),
            "snapshots": len(snapshots),
            "tests": len(tests),
        },
    }


def get_node(unique_id: str) -> dict:
    manifest = get_manifest()
    node = (manifest.get("nodes") or {}).get(unique_id) or (manifest.get("sources") or {}).get(unique_id)
    if not isinstance(node, dict):
        raise UserError(f"{unique_id} is not in the loaded manifest.", 404)
    return node


def relation_parts(node: dict) -> tuple[str, str, str] | None:
    database = node.get("database")
    schema_name = node.get("schema")
    relation = node.get("alias") or node.get("identifier") or node.get("name")
    if database and schema_name and relation:
        return str(database), str(schema_name), str(relation)
    return None


def _brief(node: dict) -> dict:
    return {
        "unique_id": node.get("unique_id"),
        "name": node.get("name"),
        "resource_type": node.get("resource_type"),
        "database": node.get("database"),
        "schema_name": node.get("schema"),
        "alias": node.get("alias") or node.get("identifier"),
        "original_file_path": node.get("original_file_path"),
        "description": node.get("description") or "",
    }


def _qualify(raw: str, settings) -> str:
    parts = [part.strip() for part in raw.split(".") if part.strip()]
    try:
        if len(parts) == 3:
            database, schema_name, table = parts
        elif len(parts) == 2:
            if not settings.database:
                raise UserError("SNOWFLAKE_DATABASE is required when the manifest table is schema.table.", 400)
            database, schema_name, table = settings.database, parts[0], parts[1]
        elif len(parts) == 1:
            if not settings.database or not settings.schema_name:
                raise UserError(
                    "SNOWFLAKE_DATABASE and SNOWFLAKE_SCHEMA are required when the manifest table is unqualified.",
                    400,
                )
            database, schema_name, table = settings.database, settings.schema_name, parts[0]
        else:
            raise UserError(
                "SNOWFLAKE_MANIFEST_TABLE must be table, schema.table, or database.schema.table.",
                400,
            )
        return f"{quote_ident(database.upper())}.{quote_ident(schema_name.upper())}.{quote_ident(table.upper())}"
    except UserError:
        raise
    except ValueError as exc:
        raise UserError(str(exc), 400) from exc


def _write(manifest: dict) -> None:
    DATA_DIR.mkdir(parents=True, exist_ok=True)
    payload = json.dumps(manifest)
    with _LOCK:
        temporary = MANIFEST_PATH.with_suffix(".json.tmp")
        temporary.write_text(payload)
        temporary.replace(MANIFEST_PATH)
