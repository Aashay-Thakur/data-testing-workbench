"""One model page: lineage maps, information_schema columns, and sqlglot gaps."""

from __future__ import annotations

from app.errors import QueryError
from app.lineage import analyze_compiled_code
from app.manifest_diff import _reachable
from app.manifest_store import get_manifest, get_node, relation_parts
from app.snowflake_client import fetch_columns


def explore_node(unique_id: str) -> dict:
    manifest = get_manifest()
    node = get_node(unique_id)
    parents = [item for item in (manifest.get("parent_map") or {}).get(unique_id) or [] if isinstance(item, str)]
    children = [item for item in (manifest.get("child_map") or {}).get(unique_id) or [] if isinstance(item, str)]
    compiled = node.get("compiled_code") or node.get("compiled_sql") or ""
    analysis = analyze_compiled_code(compiled if isinstance(compiled, str) else "")
    if node.get("resource_type") == "source" and not str(compiled).strip():
        analysis["gaps"].append("Sources have no compiled_code; column lineage is not available.")

    columns: list[dict] = []
    column_error = None
    parts = relation_parts(node)
    if parts is None:
        analysis["gaps"].append("This node has no database, schema, and relation, so information_schema was not queried.")
    else:
        try:
            columns = fetch_columns(*parts)
            if not columns:
                column_error = (
                    f"information_schema returned no columns for {parts[0]}.{parts[1]}.{parts[2]}."
                )
                analysis["gaps"].append(column_error)
        except QueryError as exc:
            column_error = exc.message
            analysis["gaps"].append(f"Columns were not read from information_schema: {exc.message}")

    gaps = []
    seen: set[str] = set()
    for gap in analysis["gaps"]:
        if gap not in seen:
            seen.add(gap)
            gaps.append(gap)

    return {
        "node": {
            "unique_id": node.get("unique_id"),
            "name": node.get("name"),
            "resource_type": node.get("resource_type"),
            "database": node.get("database"),
            "schema_name": node.get("schema"),
            "alias": node.get("alias") or node.get("identifier") or node.get("name"),
            "original_file_path": node.get("original_file_path"),
            "description": node.get("description") or "",
            "compiled_code_present": bool(str(compiled).strip()),
        },
        "upstream": parents,
        "downstream": children,
        "upstream_all": _reachable(manifest.get("parent_map") or {}, unique_id),
        "downstream_all": _reachable(manifest.get("child_map") or {}, unique_id),
        "columns": columns,
        "column_error": column_error,
        "ctes": analysis["ctes"],
        "lineage": analysis["columns"],
        "gaps": gaps,
    }
