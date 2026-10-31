"""Shared pass/fail scoring for quick checks and business rules."""

from __future__ import annotations

CANONICAL = {
    "not_null": "null_rate",
    "unique": "duplicate_keys",
    "accepted_set": "accepted_values",
    "relationship": "referential_integrity",
}


def canonical_kind(kind: str) -> str:
    return CANONICAL.get(kind, kind)


def score(kind: str, params: dict, metrics: dict, sample: list) -> tuple[str, str, dict]:
    """Return status, message, and the threshold that was applied."""
    if kind == "not_null":
        params = {**params, "max_null_rate": params.get("max_null_rate", 0)}
        kind = "null_rate"
    elif kind in CANONICAL:
        kind = CANONICAL[kind]

    if kind == "row_count":
        return _row_count(metrics, params)
    if kind == "freshness":
        return _freshness(metrics, params)
    if kind == "null_rate":
        return _null_rate(metrics, params)
    if kind == "duplicate_keys":
        return _zero_count(metrics, "duplicate_key_count", "duplicate key groups", "max_duplicate_keys")
    if kind == "accepted_values":
        return _zero_count(metrics, "unexpected_count", "values outside the accepted set", "max_unexpected")
    if kind == "referential_integrity":
        return _zero_count(metrics, "orphan_count", "orphan keys", "max_orphans")
    if kind == "min_max_mean":
        return _min_max_mean(metrics, params)
    if kind == "schema":
        return _schema(metrics, params, sample)
    if kind == "expression":
        return _zero_count(metrics, "mismatch_count", "rows where the expression is false", "max_mismatches")
    if kind in {"manifest_test", "custom_sql"}:
        return _failing_rows(metrics, sample, kind)
    return "error", f"unknown check kind {kind}", {}


def _row_count(metrics: dict, params: dict) -> tuple[str, str, dict]:
    count = int(metrics.get("row_count") or 0)
    minimum = params.get("min_rows")
    maximum = params.get("max_rows")
    threshold = {"min_rows": minimum, "max_rows": maximum}
    if minimum is None and maximum is None:
        return "pass", f"row count is {count}; no threshold was set", threshold
    problems: list[str] = []
    if minimum is not None and count < int(minimum):
        problems.append(f"row count {count} is below {int(minimum)}")
    if maximum is not None and count > int(maximum):
        problems.append(f"row count {count} is above {int(maximum)}")
    if problems:
        return "fail", "; ".join(problems), threshold
    return "pass", f"row count {count} is within the threshold", threshold


def _freshness(metrics: dict, params: dict) -> tuple[str, str, dict]:
    max_age = float(params["max_age_seconds"])
    threshold = {"max_age_seconds": max_age}
    if metrics.get("max_ts") is None:
        return "fail", "the timestamp column has no values", threshold
    age = metrics.get("age_seconds")
    if age is None:
        return "error", "Snowflake did not return an age in seconds", threshold
    if float(age) <= max_age:
        return "pass", f"newest row is {age} seconds old (limit {max_age})", threshold
    return "fail", f"newest row is {age} seconds old, past the limit of {max_age}", threshold


def _null_rate(metrics: dict, params: dict) -> tuple[str, str, dict]:
    rows = int(metrics.get("row_count") or 0)
    nulls = int(metrics.get("null_count") or 0)
    rate = (nulls / rows) if rows else 0.0
    metrics["null_rate"] = rate
    maximum = params.get("max_null_rate")
    threshold = {"max_null_rate": maximum}
    if maximum is None:
        return "pass", f"null rate is {rate:.4f}; no threshold was set", threshold
    maximum_f = float(maximum)
    if rate <= maximum_f:
        return "pass", f"null rate {rate:.4f} is within {maximum_f}", threshold
    return "fail", f"null rate {rate:.4f} is above {maximum_f}", threshold


def _zero_count(metrics: dict, key: str, noun: str, threshold_key: str) -> tuple[str, str, dict]:
    count = int(metrics.get(key) or 0)
    threshold = {threshold_key: 0}
    if count == 0:
        return "pass", f"no {noun}", threshold
    return "fail", f"{count} {noun}", threshold


def _min_max_mean(metrics: dict, params: dict) -> tuple[str, str, dict]:
    threshold = {
        "min_value": params.get("min_value"),
        "max_value": params.get("max_value"),
        "min_mean": params.get("min_mean"),
        "max_mean": params.get("max_mean"),
    }
    if all(value is None for value in threshold.values()):
        return "pass", "min, max, and mean were recorded; no threshold was set", threshold
    if metrics.get("min_v") is None and metrics.get("max_v") is None and metrics.get("mean_v") is None:
        return "fail", "the column has no numeric values", threshold
    problems: list[str] = []
    _bound(problems, metrics.get("min_v"), params.get("min_value"), "min", lower=True)
    _bound(problems, metrics.get("max_v"), params.get("max_value"), "max", lower=False)
    _bound(problems, metrics.get("mean_v"), params.get("min_mean"), "mean", lower=True)
    _bound(problems, metrics.get("mean_v"), params.get("max_mean"), "mean", lower=False)
    if problems:
        return "fail", "; ".join(problems), threshold
    return "pass", "min, max, and mean are within the threshold", threshold


def _bound(problems: list[str], actual: object, expected: object, label: str, *, lower: bool) -> None:
    if expected is None or actual is None:
        return
    if lower and float(actual) < float(expected):
        problems.append(f"{label} {actual} is below {expected}")
    if not lower and float(actual) > float(expected):
        problems.append(f"{label} {actual} is above {expected}")


def _schema(metrics: dict, params: dict, sample: list) -> tuple[str, str, dict]:
    expected = params.get("columns") or []
    threshold = {"columns": expected}
    if not sample:
        return "fail", "information_schema returned no columns; the relation may be missing", threshold
    if not expected:
        return "pass", f"{len(sample)} columns recorded; no expected schema was set", threshold
    actual = {str(row.get("column_name", "")).upper(): row for row in sample}
    missing: list[str] = []
    mismatched: list[dict] = []
    for column in expected:
        name = str(column.get("name", ""))
        found = actual.get(name.upper())
        if found is None:
            missing.append(name)
            continue
        expected_type = column.get("type")
        if expected_type and str(found.get("data_type", "")).upper() != str(expected_type).upper():
            mismatched.append(
                {"name": name, "expected": expected_type, "actual": found.get("data_type")}
            )
    metrics["missing"] = missing
    metrics["mismatched"] = mismatched
    if missing or mismatched:
        return "fail", "schema does not match the expected columns", threshold
    return "pass", "expected columns are present with the expected types", threshold


def _failing_rows(metrics: dict, sample: list, kind: str) -> tuple[str, str, dict]:
    failing = metrics.get("failing_rows")
    if failing is None:
        failing = len(sample)
    failing = int(failing)
    threshold = {"max_failing_rows": 0}
    subject = "compiled test" if kind == "manifest_test" else "custom SQL"
    if failing == 0:
        return "pass", f"{subject} returned no failing rows", threshold
    capped = " Sample is capped at 100 rows." if failing > len(sample) else ""
    return "fail", f"{subject} returned {failing} failing rows.{capped}", threshold
