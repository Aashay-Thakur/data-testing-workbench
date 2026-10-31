"""Lineage and manifest diff without a warehouse connection."""

from app.lineage import analyze_compiled_code
from app.manifest_diff import diff_manifests
from app.scoring import score


def test_cte_breakdown_and_column_lineage():
    result = analyze_compiled_code(
        """
        WITH src AS (
          SELECT id, amount FROM orders
        ),
        calc AS (
          SELECT id, amount * 2 AS doubled FROM src
        )
        SELECT id, doubled FROM calc
        """
    )
    assert [cte["name"].lower() for cte in result["ctes"]] == ["src", "calc"]
    by_name = {column["name"].upper(): column for column in result["columns"]}
    doubled = by_name["DOUBLED"]
    assert doubled["gap"] is None
    blob = str(doubled["sources"]).upper()
    assert "ORDERS" in blob
    assert "AMOUNT" in blob


def test_jinja_is_marked_as_a_gap():
    result = analyze_compiled_code("SELECT id FROM {{ ref('orders') }}")
    assert result["columns"] == []
    assert any("jinja" in gap.lower() or "macro" in gap.lower() for gap in result["gaps"])


def test_diff_models_and_downstream():
    deployed = {
        "nodes": {
            "model.p.a": {"resource_type": "model", "name": "a", "raw_code": "select 1", "compiled_code": "select 1"},
            "model.p.b": {"resource_type": "model", "name": "b", "raw_code": "select 2", "compiled_code": "select 2"},
        },
        "child_map": {"model.p.a": ["model.p.b"], "model.p.b": []},
    }
    candidate = {
        "nodes": {
            "model.p.a": {"resource_type": "model", "name": "a", "raw_code": "select 3", "compiled_code": "select 3"},
            "model.p.b": {"resource_type": "model", "name": "b", "raw_code": "select 2", "compiled_code": "select 2"},
            "model.p.c": {"resource_type": "model", "name": "c", "raw_code": "select 4", "compiled_code": "select 4"},
        },
        "child_map": {"model.p.a": ["model.p.b"], "model.p.b": [], "model.p.c": []},
    }
    diff = diff_manifests(deployed, candidate)
    assert [item["unique_id"] for item in diff["added"]] == ["model.p.c"]
    assert diff["removed"] == []
    changed = diff["changed"][0]
    assert changed["unique_id"] == "model.p.a"
    assert changed["downstream"] == ["model.p.b"]
    assert "model.p.b" in diff["downstream"]


def test_not_null_uses_the_quick_check_scorer():
    status, _message, threshold = score("not_null", {"column": "id"}, {"row_count": 4, "null_count": 0}, [])
    assert status == "pass"
    assert threshold["max_null_rate"] == 0
    failed, _message, _threshold = score(
        "null_rate",
        {"max_null_rate": 0},
        {"row_count": 4, "null_count": 1},
        [],
    )
    assert failed == "fail"


def test_expression_fails_when_rows_mismatch():
    status, message, threshold = score("expression", {}, {"mismatch_count": 2}, [])
    assert status == "fail"
    assert threshold["max_mismatches"] == 0
    assert "2" in message
