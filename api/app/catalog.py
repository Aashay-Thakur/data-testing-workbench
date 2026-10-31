"""Plain-language labels for quick checks and business-rule templates."""

from __future__ import annotations

CHECK_KINDS = [
    {
        "kind": "row_count",
        "title": "Row count",
        "plain": "Count the rows and compare the count to a minimum and maximum.",
        "fields": ["min_rows", "max_rows"],
    },
    {
        "kind": "freshness",
        "title": "Freshness",
        "plain": "Compare the newest timestamp to now.",
        "fields": ["column", "max_age_seconds"],
    },
    {
        "kind": "null_rate",
        "title": "Null rate",
        "plain": "Fail when the share of nulls in a column is above the threshold.",
        "fields": ["column", "max_null_rate"],
    },
    {
        "kind": "duplicate_keys",
        "title": "Duplicate keys",
        "plain": "Fail when the key columns identify more than one row.",
        "fields": ["columns"],
    },
    {
        "kind": "accepted_values",
        "title": "Accepted values",
        "plain": "Fail when a column contains a value outside the accepted list.",
        "fields": ["column", "values"],
    },
    {
        "kind": "referential_integrity",
        "title": "Referential integrity",
        "plain": "Fail when a child key has no matching parent key. Null child keys are allowed.",
        "fields": ["column", "parent_database", "parent_schema", "parent_relation", "parent_column"],
    },
    {
        "kind": "min_max_mean",
        "title": "Min, max, and mean",
        "plain": "Compare the minimum, maximum, and mean of a numeric column to bounds.",
        "fields": ["column", "min_value", "max_value", "min_mean", "max_mean"],
    },
    {
        "kind": "schema",
        "title": "Schema",
        "plain": "Compare column names and Snowflake data types from information_schema.",
        "fields": ["columns"],
    },
    {
        "kind": "manifest_test",
        "title": "Manifest test",
        "plain": "Re-issue a manifest test's compiled_code as a SELECT. This does not call dbt test.",
        "fields": ["unique_id"],
    },
]

RULE_TEMPLATES = [
    {
        "kind": "not_null",
        "title": "Not null",
        "plain": "This column has no nulls.",
        "fields": ["column"],
    },
    {
        "kind": "unique",
        "title": "Unique",
        "plain": "These columns uniquely identify each row.",
        "fields": ["columns"],
    },
    {
        "kind": "accepted_set",
        "title": "Accepted set",
        "plain": "This column only contains the accepted values.",
        "fields": ["column", "values"],
    },
    {
        "kind": "relationship",
        "title": "Relationship",
        "plain": "Every child key exists on the parent relation.",
        "fields": ["column", "parent_database", "parent_schema", "parent_relation", "parent_column"],
    },
    {
        "kind": "expression",
        "title": "Expression",
        "plain": "The amount column equals quantity times price.",
        "fields": ["left", "factors"],
    },
    {
        "kind": "freshness",
        "title": "Freshness",
        "plain": "The newest timestamp is within the age limit.",
        "fields": ["column", "max_age_seconds"],
    },
    {
        "kind": "custom_sql",
        "title": "Custom SQL",
        "plain": "A single read-only SELECT that returns the rows breaking the rule. An empty result passes. Unbounded SELECT * is rejected.",
        "fields": ["sql"],
    },
]

RULE_KINDS = {item["kind"] for item in RULE_TEMPLATES}
CHECK_KIND_NAMES = {item["kind"] for item in CHECK_KINDS} | RULE_KINDS


def default_label(kind: str, params: dict) -> str:
    if kind == "not_null":
        return f"{params.get('column')} is not null"
    if kind == "null_rate":
        return f"null rate of {params.get('column')} stays within the threshold"
    if kind in {"unique", "duplicate_keys"}:
        columns = params.get("columns") or []
        return f"{', '.join(columns)} is unique"
    if kind in {"accepted_set", "accepted_values"}:
        return f"{params.get('column')} only contains the accepted values"
    if kind in {"relationship", "referential_integrity"}:
        return (
            f"every {params.get('column')} exists in "
            f"{params.get('parent_relation')}.{params.get('parent_column')}"
        )
    if kind == "expression":
        factors = " * ".join(params.get("factors") or [])
        return f"{params.get('left')} = {factors}"
    if kind == "freshness":
        return f"{params.get('column')} is fresh within {params.get('max_age_seconds')} seconds"
    if kind == "row_count":
        return "row count is within the threshold"
    if kind == "min_max_mean":
        return f"min, max, and mean of {params.get('column')} stay within bounds"
    if kind == "schema":
        return "columns match the expected schema"
    if kind == "manifest_test":
        return f"re-run {params.get('unique_id')}"
    if kind == "custom_sql":
        return "custom SQL returns no violating rows"
    return kind
