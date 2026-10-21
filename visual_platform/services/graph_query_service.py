from __future__ import annotations

import math
from typing import Any


def sanitize_json_scalars(value: Any) -> Any:
    """Recursively replace non-finite floats (inf/-inf/nan) with ``None``.

    Python's ``json`` module emits ``Infinity``/``-Infinity``/``NaN`` by
    default, which are valid for ``json.loads`` but rejected by the browser's
    ``JSON.parse`` (it fails with e.g. "No number after minus sign"). A single
    non-finite node score (e.g. an invalid expert solution scored ``-inf``) is
    enough to break the whole graph load, so we scrub them before transport.
    """
    if isinstance(value, float):
        return value if math.isfinite(value) else None
    if isinstance(value, dict):
        return {key: sanitize_json_scalars(item) for key, item in value.items()}
    if isinstance(value, list):
        return [sanitize_json_scalars(item) for item in value]
    if isinstance(value, tuple):
        return [sanitize_json_scalars(item) for item in value]
    return value


_GRAPH_NODE_OMIT_FIELDS = {
    "algorithm",
    "algorithmSummary",
    "functionPreview",
    "sourceRevisionId",
}

_GRAPH_NODE_COORD_FIELDS = {"x", "y", "z"}


def _compact_float(value: Any, digits: int = 3) -> float | Any:
    if not isinstance(value, (int, float)):
        return value
    return round(float(value), digits)


def compact_graph_node(node: dict[str, Any]) -> dict[str, Any]:
    compact: dict[str, Any] = {}
    for key, value in node.items():
        if key in _GRAPH_NODE_OMIT_FIELDS or value is None:
            continue
        if key in _GRAPH_NODE_COORD_FIELDS:
            compact[key] = _compact_float(value)
            continue
        compact[key] = value
    compact["hasDetailPayload"] = True
    return compact


def compact_graph_payload(graph: dict[str, Any]) -> dict[str, Any]:
    payload = dict(graph)
    nodes = payload.get("nodes", [])
    if isinstance(nodes, list):
        payload["nodes"] = [compact_graph_node(node) if isinstance(node, dict) else node for node in nodes]
    payload.pop("clusterMap", None)
    return payload


def find_graph_node(graph: dict[str, Any], node_id: str) -> dict[str, Any] | None:
    for node in graph.get("nodes", []):
        if isinstance(node, dict) and str(node.get("id")) == node_id:
            return node
    return None


# Heavy per-node fields that must never be embedded in the transported graph
# payload. For ~14k-node graphs each of these carries ~2.4KB of source code, so
# leaving them in bloats the artifact to ~100MB and stalls the browser on load.
# The full code/algorithm text is fetched on demand per node (node id ==
# individuals.id), so stripping here is lossless for rendering.
GRAPH_NODE_HEAVY_FIELDS = (
    "functionPreview",
    "programPreview",
    "function",
    "program",
    "code",
    "programSource",
    "algorithm",
    "rawPayload",
    "raw_payload",
)


def slim_graph_node(node: dict[str, Any]) -> dict[str, Any]:
    slimmed = {key: value for key, value in node.items() if key not in GRAPH_NODE_HEAVY_FIELDS}
    slimmed["hasDetailPayload"] = True
    return slimmed


def slim_graph_for_transport(graph: dict[str, Any]) -> dict[str, Any]:
    """Return a copy of ``graph`` with heavy per-node code fields removed.

    Keeps every lightweight field the renderer needs (id/coords/score/source/
    short labels/flags) and drops the large embedded code so the payload stays
    small. Also scrubs non-finite floats so the result is valid for the
    browser's ``JSON.parse``. Idempotent and safe to call on already-slim
    graphs.
    """
    if not isinstance(graph, dict):
        return sanitize_json_scalars(graph)
    nodes = graph.get("nodes")
    if not isinstance(nodes, list):
        return sanitize_json_scalars(graph)
    payload = dict(graph)
    payload["nodes"] = [
        slim_graph_node(node) if isinstance(node, dict) else node for node in nodes
    ]
    return sanitize_json_scalars(payload)
