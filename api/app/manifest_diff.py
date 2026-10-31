"""Diff two dbt manifests. Uses child_map only; it does not infer extra edges."""

from __future__ import annotations


def diff_manifests(deployed: dict, candidate: dict) -> dict:
    """Models added, removed, or changed, plus downstream unique ids from child_map."""
    left = _models(deployed)
    right = _models(candidate)
    added_ids = sorted(set(right) - set(left))
    removed_ids = sorted(set(left) - set(right))
    changed_ids = [
        uid
        for uid in sorted(set(left) & set(right))
        if _signature(left[uid]) != _signature(right[uid])
    ]
    left_children = deployed.get("child_map") or {}
    right_children = candidate.get("child_map") or {}

    def pack(uid: str, change: str, node: dict, graphs: list[dict]) -> dict:
        downstream: list[str] = []
        seen: set[str] = set()
        for graph in graphs:
            for item in _reachable(graph, uid):
                if item not in seen:
                    seen.add(item)
                    downstream.append(item)
        return {
            "unique_id": uid,
            "name": node.get("name"),
            "change": change,
            "downstream": downstream,
        }

    added = [pack(uid, "added", right[uid], [right_children]) for uid in added_ids]
    removed = [pack(uid, "removed", left[uid], [left_children]) for uid in removed_ids]
    changed = [
        pack(uid, "changed", left[uid], [left_children, right_children]) for uid in changed_ids
    ]
    downstream: list[str] = []
    seen_down: set[str] = set()
    for item in added + removed + changed:
        for uid in item["downstream"]:
            if uid not in seen_down:
                seen_down.add(uid)
                downstream.append(uid)
    return {
        "added": added,
        "removed": removed,
        "changed": changed,
        "downstream": downstream,
    }


def _models(manifest: dict) -> dict[str, dict]:
    nodes = manifest.get("nodes") or {}
    return {
        uid: node
        for uid, node in nodes.items()
        if isinstance(node, dict) and node.get("resource_type") == "model"
    }


def _signature(node: dict) -> tuple[str, str, str]:
    checksum = node.get("checksum") or {}
    checksum_text = checksum.get("checksum") if isinstance(checksum, dict) else ""
    return (
        node.get("raw_code") or node.get("raw_sql") or "",
        node.get("compiled_code") or node.get("compiled_sql") or "",
        checksum_text or "",
    )


def _reachable(graph: dict, start: str, limit: int = 200) -> list[str]:
    seen: set[str] = set()
    ordered: list[str] = []
    queue = [item for item in graph.get(start) or [] if isinstance(item, str)]
    while queue and len(ordered) < limit:
        item = queue.pop(0)
        if item in seen or item == start:
            continue
        seen.add(item)
        ordered.append(item)
        queue.extend(child for child in graph.get(item) or [] if isinstance(child, str))
    return ordered
