"""Reject anything that is not one capped read before it can reach Snowflake."""

from __future__ import annotations

import sqlglot
from sqlglot import exp

MAX_SAMPLE_ROWS = 100

_WRITE_NAMES = (
    "Insert",
    "Update",
    "Delete",
    "Merge",
    "Create",
    "Drop",
    "Alter",
    "Copy",
    "Grant",
    "Revoke",
    "Use",
    "TruncateTable",
    "Commit",
    "Rollback",
    "Transaction",
    "Command",
    "Kill",
    "Into",
)

_AGGREGATES = (exp.Count, exp.Sum, exp.Avg, exp.Min, exp.Max)


class SqlRejected(ValueError):
    """The statement is not a single SELECT, SHOW, DESCRIBE, or information_schema read."""


def _write_types() -> tuple[type, ...]:
    found: list[type] = []
    for name in _WRITE_NAMES:
        kind = getattr(exp, name, None)
        if isinstance(kind, type):
            found.append(kind)
    return tuple(found)


WRITE_TYPES = _write_types()

_READ_ROOTS = (exp.Select, exp.Union, exp.Intersect, exp.Except, exp.Show, exp.Describe)
_LIMIT_NODES = (exp.Select, exp.Union, exp.Intersect, exp.Except, exp.Subquery)


def guard_sql(sql: str) -> str:
    """Return stripped SQL when it is one allowed read. Raise SqlRejected otherwise."""
    if sql is None or not str(sql).strip():
        raise SqlRejected("Only a single SELECT, SHOW, DESCRIBE, or information_schema read is allowed.")
    text = str(sql).strip()
    if text.endswith(";"):
        text = text[:-1].rstrip()
    if not text or "\x00" in text:
        raise SqlRejected("Only a single SELECT, SHOW, DESCRIBE, or information_schema read is allowed.")

    try:
        statements = [stmt for stmt in sqlglot.parse(text, read="snowflake") if stmt is not None]
    except sqlglot.errors.SqlglotError as exc:
        raise SqlRejected(
            "Only a single SELECT, SHOW, DESCRIBE, or information_schema read is allowed."
        ) from exc

    if len(statements) != 1:
        raise SqlRejected("Only a single SELECT, SHOW, DESCRIBE, or information_schema read is allowed.")

    stmt = statements[0]
    if isinstance(stmt, exp.Command):
        head = str(stmt.this or "").strip().split()
        word = head[0].upper() if head else ""
        if word not in {"SHOW", "DESCRIBE", "DESC"}:
            raise SqlRejected("Only a single SELECT, SHOW, DESCRIBE, or information_schema read is allowed.")
        return text

    if not isinstance(stmt, _READ_ROOTS):
        raise SqlRejected("Only a single SELECT, SHOW, DESCRIBE, or information_schema read is allowed.")

    for node in stmt.walk():
        if isinstance(node, WRITE_TYPES):
            raise SqlRejected("Only a single SELECT, SHOW, DESCRIBE, or information_schema read is allowed.")
        limit_value = _limit_value(node)
        if limit_value is not None and limit_value > MAX_SAMPLE_ROWS:
            raise SqlRejected(f"Sample cap is {MAX_SAMPLE_ROWS} rows.")

    if isinstance(stmt, (exp.Select, exp.Union, exp.Intersect, exp.Except)):
        _reject_unbounded_stars(stmt)
    return text


def _limit_value(node: exp.Expression) -> int | None:
    if not isinstance(node, _LIMIT_NODES):
        return None
    limit = node.args.get("limit")
    if limit is None:
        return None
    literal = limit.expression
    if isinstance(literal, exp.Literal) and not literal.is_string:
        try:
            value = int(literal.this)
        except (TypeError, ValueError) as exc:
            raise SqlRejected("LIMIT must be an integer constant.") from exc
        if value < 0:
            raise SqlRejected("LIMIT must be a non-negative integer.")
        return value
    raise SqlRejected("LIMIT must be an integer constant.")


def projection_is_star(projection: exp.Expression) -> bool:
    node = projection.this if isinstance(projection, exp.Alias) else projection
    while isinstance(node, exp.Paren):
        node = node.this
    if isinstance(node, exp.Star):
        return True
    return isinstance(node, exp.Column) and isinstance(node.this, exp.Star)


def _is_aggregate(expression: exp.Expression) -> bool:
    node = expression.this if isinstance(expression, exp.Alias) else expression
    while isinstance(node, exp.Paren):
        node = node.this
    return isinstance(node, _AGGREGATES)


def _scalar_aggregate(statement: exp.Expression) -> bool:
    if not isinstance(statement, exp.Select):
        return False
    if statement.args.get("group") or not statement.expressions:
        return False
    return all(_is_aggregate(expression) for expression in statement.expressions)


def _enclosing_limit(select_node: exp.Select) -> int | None:
    current: exp.Expression | None = select_node
    while current is not None:
        if isinstance(current, (exp.Select, exp.Union, exp.Intersect, exp.Except)):
            value = _limit_value(current)
            if value is not None:
                return value
        current = current.parent
    return None


def _reject_unbounded_stars(statement: exp.Expression) -> None:
    scalar_root = _scalar_aggregate(statement)
    for select in statement.find_all(exp.Select):
        if not any(projection_is_star(projection) for projection in select.expressions):
            continue
        limit = _enclosing_limit(select)
        if limit is not None and limit <= MAX_SAMPLE_ROWS:
            continue
        if select is not statement and scalar_root:
            continue
        raise SqlRejected(f"Unbounded SELECT * is blocked. Add LIMIT {MAX_SAMPLE_ROWS} or less.")
