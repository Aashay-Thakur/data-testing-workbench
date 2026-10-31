"""Run a saved check or business rule and store the score."""

from __future__ import annotations

import hashlib
import time

from app.catalog import CHECK_KIND_NAMES, default_label
from app.db import create_check, create_run, find_check_by_kind_param, get_check
from app.errors import QueryError, UserError
from app.identifiers import IdentifierError, quote_ident, quote_literal
from app.manifest_store import get_node, relation_parts
from app.redact import scrub
from app.scoring import canonical_kind, score
from app.sql_guard import SqlRejected, guard_sql
from app.sql_templates import (
    accepted_values_sql,
    duplicate_keys_sql,
    expression_sql,
    failing_rows_sql,
    freshness_sql,
    min_max_mean_sql,
    null_rate_sql,
    referential_sql,
    row_count_sql,
    schema_sql,
)
from app.snowflake_client import fetch, resolve_relation

_COLUMN_KINDS = {"null_rate", "freshness", "min_max_mean", "accepted_values"}


def validate_definition(kind: str, target: dict, params: dict) -> dict:
    if kind not in CHECK_KIND_NAMES:
        raise UserError(f"Unknown check kind {kind}.", 400)
    cleaned = dict(params or {})
    canonical = canonical_kind(kind)
    if canonical in _COLUMN_KINDS or kind == "not_null":
        cleaned["column"] = _require_ident(cleaned.get("column"), "column")
    if canonical == "duplicate_keys":
        cleaned["columns"] = _ident_list(cleaned.get("columns"), "columns")
    if canonical == "accepted_values":
        cleaned["column"] = _require_ident(cleaned.get("column"), "column")
        values = cleaned.get("values") or []
        if not isinstance(values, list) or not values:
            raise UserError("Accepted values need at least one value.", 400)
        if len(values) > 100:
            raise UserError("Accepted values are capped at 100.", 400)
        cleaned["values"] = [str(value) for value in values]
    if canonical == "referential_integrity":
        for field in ("column", "parent_column"):
            cleaned[field] = _require_ident(cleaned.get(field), field)
        for field in ("parent_database", "parent_schema", "parent_relation"):
            cleaned[field] = _require_ident(cleaned.get(field), field)
    if canonical == "expression":
        cleaned["left"] = _require_ident(cleaned.get("left"), "left")
        cleaned["factors"] = _ident_list(cleaned.get("factors"), "factors")
        if len(cleaned["factors"]) < 2:
            raise UserError("An expression needs at least two factor columns, such as qty and price.", 400)
    if canonical == "freshness":
        if cleaned.get("max_age_seconds") is None:
            raise UserError("Freshness needs max_age_seconds.", 400)
        cleaned["max_age_seconds"] = float(cleaned["max_age_seconds"])
    if canonical == "schema":
        columns = cleaned.get("columns") or []
        normalized = []
        if not isinstance(columns, list):
            raise UserError("Schema columns must be a list.", 400)
        for column in columns:
            if not isinstance(column, dict):
                raise UserError("Each expected column needs a name.", 400)
            normalized.append(
                {
                    "name": _require_ident(column.get("name"), "column name"),
                    "type": column.get("type") or None,
                }
            )
        cleaned["columns"] = normalized
    if canonical == "custom_sql":
        sql = str(cleaned.get("sql") or "").strip()
        if not sql:
            raise UserError("Custom SQL is empty.", 400)
        if len(sql) > 200_000:
            raise UserError("Custom SQL is too long.", 400)
        try:
            guard_sql(sql)
        except SqlRejected as exc:
            raise UserError(str(exc), 400) from exc
        cleaned["sql"] = sql
    if canonical == "manifest_test":
        unique_id = str(cleaned.get("unique_id") or "").strip()
        if not unique_id:
            raise UserError("A manifest test needs a unique_id.", 400)
        cleaned["unique_id"] = unique_id
    else:
        _require_target(target)
    if kind == "not_null" and cleaned.get("max_null_rate") is None:
        cleaned["max_null_rate"] = 0
    return cleaned


def save_check(body: dict, origin: str) -> dict:
    kind = str(body.get("kind") or "")
    target = body.get("target") or {}
    params = validate_definition(kind, target, body.get("params") or {})
    name = str(body.get("name") or "").strip() or default_label(kind, params)
    label = str(body.get("label") or "").strip() or default_label(kind, params)
    return create_check(
        name=name,
        kind=kind,
        label=label,
        origin=origin,
        target=target,
        params=params,
        blocking=bool(body.get("blocking")),
    )


def run_saved(check_id: int) -> dict:
    check = get_check(check_id)
    return _execute_and_store(check)


def rerun_manifest_test(unique_id: str) -> dict:
    existing = find_check_by_kind_param("manifest_test", "unique_id", unique_id)
    if existing is None:
        existing = save_check(
            {
                "name": unique_id,
                "kind": "manifest_test",
                "target": {"unique_id": unique_id},
                "params": {"unique_id": unique_id},
                "blocking": False,
            },
            origin="check",
        )
    return run_saved(existing["id"])


def _execute_and_store(check: dict) -> dict:
    started = time.perf_counter()
    try:
        outcome = _execute(check)
    except (QueryError, SqlRejected, IdentifierError) as exc:
        outcome = {
            "status": "error",
            "message": scrub(str(exc)),
            "threshold": {},
            "sample": [],
            "metrics": {},
            "sql_hash": None,
            "target": _target_label(check["target"]),
            "git_sha": None,
        }
    outcome["runtime_ms"] = int((time.perf_counter() - started) * 1000)
    outcome["check_id"] = check["id"]
    outcome["name"] = check["label"] or check["name"]
    outcome["kind"] = check["kind"]
    outcome["blocking"] = check["blocking"]
    outcome.setdefault("git_sha", None)
    return create_run(outcome)


def _execute(check: dict) -> dict:
    kind = check["kind"]
    canonical = canonical_kind(kind)
    params = check["params"]
    if canonical == "manifest_test":
        statements, metrics, sample, target = _manifest_test(params["unique_id"])
    elif canonical == "custom_sql":
        statements = [guard_sql(params["sql"])]
        sample = fetch(statements[0])
        metrics = {"failing_rows": len(sample)}
        target = _target_label(check["target"])
    else:
        resolved = _resolve_target(check["target"])
        target = resolved["label"]
        statements = _statements(canonical, resolved, params)
        for statement in statements:
            guard_sql(statement)
        if canonical == "schema":
            sample = fetch(statements[0])
            metrics = {"column_count": len(sample)}
        else:
            metrics_rows = fetch(statements[0])
            if not metrics_rows:
                raise QueryError("The check query returned no aggregate row.")
            metrics = dict(metrics_rows[0])
            sample = fetch(statements[1]) if len(statements) > 1 else []
    status, message, threshold = score(kind, params, metrics, sample)
    return {
        "status": status,
        "message": message,
        "threshold": threshold,
        "sample": _shrink(sample),
        "metrics": metrics,
        "sql_hash": _hash(statements),
        "target": target,
        "git_sha": None,
    }


def _statements(kind: str, resolved: dict, params: dict) -> list[str]:
    relation = resolved["qualified"]
    if kind == "row_count":
        return row_count_sql(relation)
    if kind == "freshness":
        return freshness_sql(relation, _qualified_column(resolved, params["column"]))
    if kind == "null_rate":
        return null_rate_sql(relation, _qualified_column(resolved, params["column"]))
    if kind == "duplicate_keys":
        columns = [_qualified_column(resolved, column) for column in params["columns"]]
        return duplicate_keys_sql(relation, columns)
    if kind == "accepted_values":
        column = _qualified_column(resolved, params["column"])
        literals = [quote_literal(value) for value in params["values"]]
        return accepted_values_sql(relation, column, literals)
    if kind == "referential_integrity":
        parent = resolve_relation(
            params["parent_database"], params["parent_schema"], params["parent_relation"]
        )
        return referential_sql(
            relation,
            parent["qualified"],
            _qualified_column(resolved, params["column"]),
            quote_ident(parent_column_name(parent, params["parent_column"])),
        )
    if kind == "min_max_mean":
        return min_max_mean_sql(relation, _qualified_column(resolved, params["column"]))
    if kind == "schema":
        return schema_sql(
            quote_ident(resolved["database"]),
            quote_literal(resolved["schema_name"]),
            quote_literal(resolved["relation"]),
        )
    if kind == "expression":
        left = _qualified_column(resolved, params["left"])
        factors = [_qualified_column(resolved, column) for column in params["factors"]]
        return expression_sql(relation, left, factors)
    raise UserError(f"Unknown check kind {kind}.", 400)


def _manifest_test(unique_id: str) -> tuple[list[str], dict, list, str]:
    node = get_node(unique_id)
    if node.get("resource_type") != "test":
        raise UserError(f"{unique_id} is not a test in the loaded manifest.", 400)
    compiled = node.get("compiled_code") or node.get("compiled_sql") or ""
    if not str(compiled).strip():
        raise QueryError(f"{unique_id} has no compiled_code in the stitched manifest.")
    count_sql, sample_sql = failing_rows_sql(str(compiled))
    statements = [guard_sql(count_sql), guard_sql(sample_sql)]
    metrics_rows = fetch(statements[0])
    sample = fetch(statements[1])
    metrics = dict(metrics_rows[0]) if metrics_rows else {"failing_rows": len(sample)}
    return statements, metrics, sample, unique_id


def _resolve_target(target: dict) -> dict:
    if target.get("unique_id") and not (target.get("database") and target.get("relation")):
        node = get_node(str(target["unique_id"]))
        parts = relation_parts(node)
        if parts is None:
            raise QueryError(f"{target['unique_id']} has no database, schema, and alias in the manifest.")
        database, schema_name, relation = parts
    else:
        database = target.get("database")
        schema_name = target.get("schema_name")
        relation = target.get("relation")
        if not (database and schema_name and relation):
            raise UserError("Choose a model or a database, schema, and relation.", 400)
    return resolve_relation(str(database), str(schema_name), str(relation))


def _qualified_column(resolved: dict, column: str) -> str:
    from app.snowflake_client import fetch_columns

    rows = fetch_columns(resolved["database"], resolved["schema_name"], resolved["relation"])
    match = [row for row in rows if str(row.get("column_name", "")).upper() == column.upper()]
    if not match:
        raise QueryError(
            f"Column {column} is not in information_schema for {resolved['label']}, so it was not queried."
        )
    if len(match) > 1:
        raise QueryError(f"Column {column} is ambiguous on {resolved['label']}.")
    return quote_ident(str(match[0]["column_name"]))


def parent_column_name(parent: dict, column: str) -> str:
    from app.snowflake_client import fetch_columns

    rows = fetch_columns(parent["database"], parent["schema_name"], parent["relation"])
    match = [row for row in rows if str(row.get("column_name", "")).upper() == column.upper()]
    if not match:
        raise QueryError(
            f"Parent column {column} is not in information_schema for {parent['label']}."
        )
    return str(match[0]["column_name"])


def _require_target(target: dict) -> None:
    if target.get("unique_id"):
        return
    if target.get("database") and target.get("schema_name") and target.get("relation"):
        quote_ident(str(target["database"]))
        quote_ident(str(target["schema_name"]))
        quote_ident(str(target["relation"]))
        return
    raise UserError("Choose a model or a database, schema, and relation.", 400)


def _require_ident(value: object, field: str) -> str:
    if value is None or not str(value).strip():
        raise UserError(f"{field} is required.", 400)
    text = str(value).strip()
    quote_ident(text)
    return text


def _ident_list(value: object, field: str) -> list[str]:
    if isinstance(value, str):
        items = [part.strip() for part in value.split(",") if part.strip()]
    elif isinstance(value, list):
        items = [str(part).strip() for part in value if str(part).strip()]
    else:
        items = []
    if not items:
        raise UserError(f"{field} is required.", 400)
    if len(items) > 8:
        raise UserError(f"{field} accepts at most 8 columns.", 400)
    for item in items:
        quote_ident(item)
    return items


def _target_label(target: dict) -> str:
    if target.get("database") and target.get("schema_name") and target.get("relation"):
        return f"{target['database']}.{target['schema_name']}.{target['relation']}"
    if target.get("unique_id"):
        return str(target["unique_id"])
    return "unset"


def _hash(statements: list[str]) -> str:
    return hashlib.sha256("\n---\n".join(statements).encode()).hexdigest()


def _shrink(rows: list[dict]) -> list[dict]:
    shrunk = []
    for row in rows[:100]:
        item = {}
        for key, value in row.items():
            if isinstance(value, str) and len(value) > 500:
                value = value[:500] + "…"
            item[str(key)] = value
        shrunk.append(item)
    return shrunk
