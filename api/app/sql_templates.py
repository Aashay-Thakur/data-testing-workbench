"""SELECT templates. Callers pass already-quoted identifiers and literals."""

from __future__ import annotations


def row_count_sql(relation: str) -> list[str]:
    return [f"SELECT COUNT(*) AS row_count FROM {relation}"]


def freshness_sql(relation: str, column: str) -> list[str]:
    return [
        f"SELECT MAX({column}) AS max_ts, "
        f"DATEDIFF('second', MAX({column}), CURRENT_TIMESTAMP()) AS age_seconds "
        f"FROM {relation}"
    ]


def null_rate_sql(relation: str, column: str) -> list[str]:
    return [
        f"SELECT COUNT(*) AS row_count, SUM(IFF({column} IS NULL, 1, 0)) AS null_count "
        f"FROM {relation}"
    ]


def duplicate_keys_sql(relation: str, columns: list[str]) -> list[str]:
    cols = ", ".join(columns)
    count = (
        f"SELECT COUNT(*) AS duplicate_key_count FROM ("
        f"SELECT 1 AS _one FROM {relation} GROUP BY {cols} HAVING COUNT(*) > 1"
        f") AS _dupes"
    )
    sample = (
        f"SELECT {cols}, COUNT(*) AS copies FROM {relation} "
        f"GROUP BY {cols} HAVING COUNT(*) > 1 LIMIT 100"
    )
    return [count, sample]


def accepted_values_sql(relation: str, column: str, literals: list[str]) -> list[str]:
    listed = ", ".join(literals)
    count = (
        f"SELECT COUNT(*) AS unexpected_count FROM {relation} "
        f"WHERE {column} IS NOT NULL AND {column} NOT IN ({listed})"
    )
    sample = (
        f"SELECT {column} AS value, COUNT(*) AS copies FROM {relation} "
        f"WHERE {column} IS NOT NULL AND {column} NOT IN ({listed}) "
        f"GROUP BY {column} LIMIT 100"
    )
    return [count, sample]


def referential_sql(child: str, parent: str, child_column: str, parent_column: str) -> list[str]:
    count = (
        f"SELECT COUNT(*) AS orphan_count FROM {child} AS c "
        f"LEFT JOIN {parent} AS p ON c.{child_column} = p.{parent_column} "
        f"WHERE c.{child_column} IS NOT NULL AND p.{parent_column} IS NULL"
    )
    sample = (
        f"SELECT c.{child_column} AS key FROM {child} AS c "
        f"LEFT JOIN {parent} AS p ON c.{child_column} = p.{parent_column} "
        f"WHERE c.{child_column} IS NOT NULL AND p.{parent_column} IS NULL LIMIT 100"
    )
    return [count, sample]


def min_max_mean_sql(relation: str, column: str) -> list[str]:
    return [
        f"SELECT MIN({column}) AS min_v, MAX({column}) AS max_v, AVG({column}) AS mean_v "
        f"FROM {relation}"
    ]


def schema_sql(database: str, schema_literal: str, relation_literal: str) -> list[str]:
    return [
        "SELECT column_name, data_type, is_nullable, ordinal_position "
        f"FROM {database}.information_schema.columns "
        f"WHERE UPPER(table_schema) = UPPER({schema_literal}) "
        f"AND UPPER(table_name) = UPPER({relation_literal}) "
        "ORDER BY ordinal_position LIMIT 100"
    ]


def exists_sql(database: str, schema_literal: str, relation_literal: str) -> str:
    return (
        "SELECT table_schema, table_name, table_type "
        f"FROM {database}.information_schema.tables "
        f"WHERE UPPER(table_schema) = UPPER({schema_literal}) "
        f"AND UPPER(table_name) = UPPER({relation_literal}) "
        "LIMIT 5"
    )


def expression_sql(relation: str, left: str, factors: list[str]) -> list[str]:
    product = " * ".join(factors)
    count = (
        f"SELECT COUNT(*) AS mismatch_count FROM {relation} "
        f"WHERE {left} IS DISTINCT FROM ({product})"
    )
    sample = (
        f"SELECT {left} AS left_value, {product} AS right_value FROM {relation} "
        f"WHERE {left} IS DISTINCT FROM ({product}) LIMIT 100"
    )
    return [count, sample]


def failing_rows_sql(inner: str) -> tuple[str, str]:
    body = inner.strip()
    if body.endswith(";"):
        body = body[:-1].rstrip()
    count = f"SELECT COUNT(*) AS failing_rows FROM (\n{body}\n) AS _failing_rows"
    sample = f"SELECT * FROM (\n{body}\n) AS _failing_rows LIMIT 100"
    return count, sample


def column_metrics_sql(relation: str, columns: list[str], numeric: list[str]) -> str:
    pieces = ["COUNT(*) AS row_count"]
    for index, column in enumerate(columns):
        pieces.append(f"SUM(IFF({column} IS NULL, 1, 0)) AS n_{index}")
    for index, column in enumerate(numeric):
        pieces.append(f"MIN({column}) AS min_{index}")
        pieces.append(f"MAX({column}) AS max_{index}")
        pieces.append(f"AVG({column}) AS avg_{index}")
    return f"SELECT {', '.join(pieces)} FROM {relation}"


def key_count_sql(relation: str, columns: list[str], alias: str) -> str:
    cols = ", ".join(columns)
    return (
        f"SELECT COUNT(*) AS {alias} FROM (SELECT DISTINCT {cols} FROM {relation}) AS _keys"
    )


def key_match_sql(left: str, right: str, columns: list[str]) -> str:
    cols = ", ".join(columns)
    return (
        "SELECT COUNT(*) AS matched FROM ("
        f"SELECT {cols} FROM {left} INTERSECT SELECT {cols} FROM {right}"
        ") AS _matched"
    )


def key_mismatch_sql(left: str, right: str, columns: list[str], side: str, limit: int) -> str:
    cols = ", ".join(columns)
    side_literal = "'" + side.replace("'", "''") + "'"
    return (
        f"SELECT {cols}, {side_literal} AS side FROM ("
        f"SELECT {cols} FROM {left} EXCEPT SELECT {cols} FROM {right}"
        f") AS _mismatch LIMIT {limit}"
    )
