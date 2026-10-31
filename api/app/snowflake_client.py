"""Snowflake reads with the query role. Every statement passes the SQL guard."""

from __future__ import annotations

from datetime import date, datetime
from decimal import Decimal

import sqlglot

from app.config import STATEMENT_TIMEOUT_SECONDS, get_settings
from app.errors import QueryError, UserError
from app.identifiers import quote_ident, quote_literal, quote_relation
from app.redact import scrub
from app.sql_guard import MAX_SAMPLE_ROWS, guard_sql
from app.sql_templates import exists_sql, schema_sql


def connect():
    settings = get_settings()
    if not settings.snowflake_configured:
        raise UserError(
            "Snowflake is not configured. Set the account, user, role, warehouse, and a password or private key.",
            400,
        )
    import snowflake.connector

    kwargs = {
        "account": settings.account,
        "user": settings.user,
        "role": settings.role,
        "warehouse": settings.warehouse,
        "database": settings.database or None,
        "schema": settings.schema_name or None,
        "session_parameters": {"STATEMENT_TIMEOUT_IN_SECONDS": STATEMENT_TIMEOUT_SECONDS},
        "login_timeout": 20,
        "network_timeout": STATEMENT_TIMEOUT_SECONDS,
        "client_session_keep_alive": False,
    }
    if settings.private_key:
        kwargs["private_key"] = _private_key_der(settings.private_key)
    else:
        kwargs["password"] = settings.password
    try:
        return snowflake.connector.connect(**kwargs)
    except Exception as exc:
        _raise_snowflake(exc)


def fetch(sql: str, cap: int = MAX_SAMPLE_ROWS) -> list[dict]:
    """Run one guarded read and return at most ``cap`` rows (never above the sample cap)."""
    if cap < 1 or cap > MAX_SAMPLE_ROWS:
        cap = MAX_SAMPLE_ROWS
    return _execute(guard_sql(sql), cap)


def fetch_manifest_lines(sql: str) -> list[dict]:
    """Read the manifest table. The statement must be exactly line, content."""
    guarded = guard_sql(sql)
    parsed = sqlglot.parse_one(guarded, read="snowflake")
    names = [expression.alias_or_name.lower() for expression in parsed.expressions]
    if names != ["line", "content"]:
        raise UserError("The manifest read must select line and content only.", 500)
    return _execute(guarded, cap=None)


def test_connection() -> dict:
    rows = fetch("SELECT 1 AS ok")
    settings = get_settings()
    return {
        "ok": bool(rows and rows[0].get("ok") == 1),
        "account": settings.account,
        "role": settings.role,
    }


def list_databases() -> dict:
    rows = fetch("SHOW DATABASES")
    names = [_cell(row, "name") for row in rows if _cell(row, "name")]
    return {"databases": names, "truncated": len(rows) >= MAX_SAMPLE_ROWS}


def list_schemas(database: str) -> dict:
    rows = fetch(f"SHOW SCHEMAS IN DATABASE {quote_ident(database)}")
    names = [_cell(row, "name") for row in rows if _cell(row, "name")]
    return {"database": database, "schemas": names, "truncated": len(rows) >= MAX_SAMPLE_ROWS}


def list_tables(database: str, schema_name: str) -> dict:
    sql = f"SHOW TABLES IN SCHEMA {quote_ident(database)}.{quote_ident(schema_name)}"
    rows = fetch(sql)
    tables = []
    for row in rows:
        name = _cell(row, "name")
        if name:
            tables.append({"name": name, "kind": _cell(row, "kind") or _cell(row, "table_type")})
    return {
        "database": database,
        "schema_name": schema_name,
        "tables": tables,
        "truncated": len(rows) >= MAX_SAMPLE_ROWS,
    }


def count_relation(database: str, schema_name: str, relation: str) -> dict:
    resolved = resolve_relation(database, schema_name, relation)
    sql = f"SELECT COUNT(*) AS row_count FROM {resolved['qualified']}"
    rows = fetch(sql)
    if not rows:
        raise QueryError(f"{resolved['label']} did not return a row count.")
    return {
        "database": resolved["database"],
        "schema_name": resolved["schema_name"],
        "relation": resolved["relation"],
        "row_count": rows[0].get("row_count"),
        "target": resolved["label"],
    }


def resolve_relation(database: str, schema_name: str, relation: str) -> dict:
    """Confirm the relation exists and return the catalog's exact identifiers."""
    quote_ident(database)
    quote_ident(schema_name)
    quote_ident(relation)
    qualifier = database.strip().upper()
    rows = fetch(exists_sql(quote_ident(qualifier), quote_literal(schema_name), quote_literal(relation)))
    if not rows:
        raise QueryError(
            f"Relation {database}.{schema_name}.{relation} does not exist "
            f"in {qualifier}.information_schema, so it was not queried."
        )
    if len(rows) > 1:
        raise QueryError(
            f"Relation {database}.{schema_name}.{relation} matched more than one table. "
            "The name was not guessed."
        )
    exact_schema = rows[0]["table_schema"]
    exact_table = rows[0]["table_name"]
    return {
        "database": qualifier,
        "schema_name": exact_schema,
        "relation": exact_table,
        "qualified": quote_relation(qualifier, exact_schema, exact_table),
        "label": f"{qualifier}.{exact_schema}.{exact_table}",
    }


def fetch_columns(database: str, schema_name: str, relation: str) -> list[dict]:
    qualifier = database.strip().upper()
    quote_ident(qualifier)
    rows = fetch(
        schema_sql(quote_ident(qualifier), quote_literal(schema_name), quote_literal(relation))[0]
    )
    return [
        {
            "column_name": row.get("column_name"),
            "data_type": row.get("data_type"),
            "is_nullable": row.get("is_nullable"),
            "ordinal_position": row.get("ordinal_position"),
        }
        for row in rows
    ]


def _execute(sql: str, cap: int | None) -> list[dict]:
    try:
        connection = connect()
    except UserError:
        raise
    except QueryError:
        raise
    try:
        cursor = connection.cursor()
        try:
            cursor.execute(sql)
            if cursor.description is None:
                return []
            columns = [item[0].lower() for item in cursor.description]
            if cap is None:
                raw_rows: list = []
                while True:
                    batch = cursor.fetchmany(1000)
                    if not batch:
                        break
                    raw_rows.extend(batch)
                    if len(raw_rows) > 250_000:
                        raise QueryError("The manifest table has more than 250000 lines, so it was not stitched.")
            else:
                raw_rows = cursor.fetchmany(cap)
        finally:
            cursor.close()
    except (UserError, QueryError):
        raise
    except Exception as exc:
        _raise_snowflake(exc)
    finally:
        connection.close()
    return [_row(columns, row) for row in raw_rows]


def _row(columns: list[str], values: tuple) -> dict:
    return {column: _jsonable(value) for column, value in zip(columns, values)}


def _jsonable(value):
    if isinstance(value, Decimal):
        if value == int(value):
            return int(value)
        return float(value)
    if isinstance(value, datetime):
        return value.isoformat()
    if isinstance(value, date):
        return value.isoformat()
    if isinstance(value, bytes):
        return value.decode("utf-8", errors="replace")
    return value


def _cell(row: dict, name: str):
    if name in row:
        return row[name]
    lowered = {str(key).lower(): value for key, value in row.items()}
    return lowered.get(name)


def _private_key_der(pem: str) -> bytes:
    from cryptography.hazmat.primitives import serialization

    text = pem.strip().replace("\\n", "\n")
    try:
        key = serialization.load_pem_private_key(text.encode(), password=None)
    except Exception as exc:
        raise UserError("SNOWFLAKE_PRIVATE_KEY could not be read as an unencrypted PEM key.", 400) from exc
    return key.private_bytes(
        encoding=serialization.Encoding.DER,
        format=serialization.PrivateFormat.PKCS8,
        encryption_algorithm=serialization.NoEncryption(),
    )


def _raise_snowflake(exc: Exception) -> None:
    text = scrub(str(exc))
    lowered = text.lower()
    if "timeout" in lowered or "57014" in lowered:
        raise QueryError(
            "Snowflake canceled the statement because it exceeded the session timeout.",
            408,
        ) from exc
    if "does not exist" in lowered or "not authorized" in lowered:
        raise QueryError(text, 404) from exc
    raise QueryError(text, 400) from exc
