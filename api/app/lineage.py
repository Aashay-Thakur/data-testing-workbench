"""CTE list and best-effort column lineage from compiled SQL. Gaps stay explicit."""

from __future__ import annotations

import re

import sqlglot
from sqlglot import exp
from sqlglot.lineage import lineage

from app.sql_guard import projection_is_star

_JINJA = re.compile(r"\{\{|\{%")
_DYNAMIC = re.compile(r"execute\s+immediate|\bidentifier\s*\(", re.IGNORECASE)


def analyze_compiled_code(sql: str | None) -> dict:
    """Return CTEs, column sources, and gaps. Unresolved lineage is not filled in."""
    gaps: list[str] = []
    if sql is None or not str(sql).strip():
        return {
            "ctes": [],
            "columns": [],
            "gaps": ["compiled_code is empty; column lineage was not inferred"],
        }
    text = str(sql).strip()
    if _JINJA.search(text):
        return {
            "ctes": [],
            "columns": [],
            "gaps": ["Jinja or macros remain in compiled_code; lineage is incomplete"],
        }
    if _DYNAMIC.search(text):
        gaps.append("Dynamic SQL is not expanded; lineage is incomplete.")

    try:
        statements = [stmt for stmt in sqlglot.parse(text, read="snowflake") if stmt is not None]
    except sqlglot.errors.SqlglotError as exc:
        return {
            "ctes": [],
            "columns": [],
            "gaps": gaps + [f"sqlglot could not parse compiled_code: {exc}"],
        }
    if len(statements) != 1:
        return {
            "ctes": [],
            "columns": [],
            "gaps": gaps + ["compiled_code is not a single statement; lineage was not inferred"],
        }

    parsed = statements[0]
    ctes = _ctes(parsed, gaps)
    if not isinstance(parsed, exp.Select):
        return {
            "ctes": ctes,
            "columns": [],
            "gaps": gaps + ["compiled_code is not a single SELECT; column lineage was not inferred"],
        }

    columns = _columns(parsed, text, gaps)
    return {"ctes": ctes, "columns": columns, "gaps": _dedupe(gaps)}


def _ctes(parsed: exp.Expression, gaps: list[str]) -> list[dict]:
    with_clause = parsed.args.get("with_") or parsed.args.get("with")
    if not with_clause:
        return []
    ctes: list[dict] = []
    for cte in with_clause.expressions:
        name = cte.alias
        columns: list[str] = []
        body = cte.this
        if isinstance(body, exp.Select):
            for expression in body.expressions:
                if projection_is_star(expression):
                    columns.append("*")
                    gaps.append(f"CTE {name} uses SELECT *; its column list is incomplete")
                else:
                    columns.append(expression.alias_or_name)
        else:
            gaps.append(f"CTE {name} is not a simple SELECT; its breakdown is incomplete")
        ctes.append({"name": name, "columns": columns})
    return ctes


def _columns(parsed: exp.Select, sql: str, gaps: list[str]) -> list[dict]:
    output: list[dict] = []
    star = any(projection_is_star(expression) for expression in parsed.expressions)
    if star:
        gaps.append("Outer SELECT * hides output columns; those columns were not guessed.")
        output.append({"name": "*", "sources": [], "gap": "SELECT * was not expanded"})

    names = [
        expression.alias_or_name
        for expression in parsed.expressions
        if not projection_is_star(expression)
    ]
    nodes: dict = {}
    if names:
        try:
            nodes = lineage(None, sql, schema={}, dialect="snowflake")
        except Exception as exc:
            gaps.append(f"sqlglot lineage failed: {exc}")
            return output + [
                {"name": name, "sources": [], "gap": "lineage failed; sources were not guessed"}
                for name in names
            ]
    if not isinstance(nodes, dict):
        gaps.append("sqlglot did not return column lineage; sources were not guessed")
        return output

    for name in names:
        node = nodes.get(name) or nodes.get(name.upper()) or nodes.get(name.lower())
        if node is None:
            output.append(
                {
                    "name": name,
                    "sources": [],
                    "gap": "no lineage node for this column; sources were not guessed",
                }
            )
            gaps.append(f"{name}: lineage did not resolve")
            continue
        sources, column_gaps = _leaves(node)
        column_gap = "; ".join(column_gaps) if column_gaps else None
        if column_gap:
            gaps.append(f"{name}: {column_gap}")
        output.append({"name": node.name or name, "sources": sources, "gap": column_gap})
    return output


def _leaves(node: object) -> tuple[list[dict], list[str]]:
    sources: list[dict] = []
    gaps: list[str] = []
    seen: set[int] = set()

    def walk(current: object) -> None:
        if id(current) in seen:
            return
        seen.add(id(current))
        downstream = getattr(current, "downstream", None) or []
        if not downstream:
            expression = getattr(current, "expression", None)
            leaf_name = getattr(current, "name", "")
            if isinstance(expression, exp.Table):
                sources.append({"column": leaf_name, "table": expression.sql(dialect="snowflake")})
            else:
                rendered = None if expression is None else expression.sql(dialect="snowflake")
                sources.append({"column": leaf_name, "table": None, "expression": rendered})
                gaps.append("lineage stopped before a source table")
            return
        for child in downstream:
            walk(child)

    walk(node)
    if not sources:
        gaps.append("lineage produced no sources")
    return sources, _dedupe(gaps)


def _dedupe(items: list[str]) -> list[str]:
    seen: set[str] = set()
    ordered: list[str] = []
    for item in items:
        if item not in seen:
            seen.add(item)
            ordered.append(item)
    return ordered
