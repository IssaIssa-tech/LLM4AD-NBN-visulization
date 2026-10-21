from __future__ import annotations

import json
import math
from pathlib import Path
from typing import Any

from visual_platform.config import RUNS_DIR
from visual_platform.nbn.region_analysis import (
    MIN_EDGE_DIST,
    BOXED_IN_GAP,
    TRUE_BLANK_GAP,
    anchor_cluster_metrics,
    corridor_comparison,
    gap_status,
    min_gap_to_better,
    normalize_valid_score,
    recommend_candidates,
)
from visual_platform.repositories import get_individuals_by_ids, get_revision_record
from visual_platform.services.graph_service import get_graph_data


def _node_source(node: dict[str, Any]) -> str:
    return (
        str(node.get("function", "") or "").strip()
        or str(node.get("program", "") or "").strip()
        or str(node.get("functionPreview", "") or "").strip()
        or str(node.get("algorithm", "") or "").strip()
    )


def normalize_region_spec(region: Any) -> dict[str, Any] | None:
    """Structural normalization of a region spec: edge {a,b} or expand {a}."""
    if not isinstance(region, dict):
        return None
    region_type = str(region.get("type", "") or "").strip()
    a = str(region.get("a", "") or "").strip()
    if region_type not in {"edge", "expand"} or not a:
        return None
    b = str(region.get("b", "") or "").strip() if region_type == "edge" else None
    if region_type == "edge" and (not b or a == b):
        return None
    spec: dict[str, Any] = {"type": region_type, "a": a}
    if b:
        spec["b"] = b
    return spec


def _edge_length_from_graph(graph: dict[str, Any], a_id: str, b_id: str) -> float | None:
    nodes = graph.get("nodes") if isinstance(graph, dict) else None
    if not isinstance(nodes, list):
        return None
    node_a = None
    node_b = None
    for node in nodes:
        node_id = str(node.get("id") or "")
        if node_id == a_id:
            node_a = node
        elif node_id == b_id:
            node_b = node
    if node_a is None or node_b is None:
        return None
    # Try the direct edge list first, then the NBN parent distance.
    edges = graph.get("edges") if isinstance(graph, dict) else None
    if isinstance(edges, list):
        for edge in edges:
            source = str(edge.get("source") or "")
            target = str(edge.get("target") or "")
            if (source == a_id and target == b_id) or (source == b_id and target == a_id):
                value = edge.get("distance")
                if isinstance(value, (int, float)) and math.isfinite(float(value)):
                    return float(value)
    for node in (node_a, node_b):
        value = node.get("distanceToParent")
        if isinstance(value, (int, float)) and math.isfinite(float(value)):
            return float(value)
    return None


def validate_region_spec(region: Any, source_revision_id: str | None) -> tuple[dict[str, Any] | None, str | None]:
    """Validate a submitted region spec against the database.

    Checks structure, endpoint existence, valid scores, embeddable code, and
    (when the source graph artifact is available) the minimum edge length.
    """
    spec = normalize_region_spec(region)
    if spec is None:
        return None, "区域定义无效：需要 {type: 'edge'|'expand', a, b?}。"

    ids = [spec["a"]]
    if "b" in spec:
        ids.append(spec["b"])
    records = get_individuals_by_ids(ids)
    by_id = {str(record.get("id") or ""): record for record in records}

    a_node = by_id.get(spec["a"])
    if a_node is None:
        return None, f"区域端点 A 不存在于数据库：{spec['a']}"
    if not _node_source(a_node):
        return None, f"区域端点 A 缺少可嵌入的代码：{spec['a']}"
    if normalize_valid_score(a_node.get("score")) is None:
        return None, f"区域端点 A 无有效分数：{spec['a']}"

    if "b" in spec:
        b_node = by_id.get(spec["b"])
        if b_node is None:
            return None, f"区域端点 B 不存在于数据库：{spec['b']}"
        if not _node_source(b_node):
            return None, f"区域端点 B 缺少可嵌入的代码：{spec['b']}"
        if normalize_valid_score(b_node.get("score")) is None:
            return None, f"区域端点 B 无有效分数：{spec['b']}"

        if source_revision_id:
            graph = _load_graph_file(source_revision_id)
            distance = _edge_length_from_graph(graph, spec["a"], spec["b"]) if graph else None
            if distance is not None and distance < MIN_EDGE_DIST:
                return None, (
                    f"短边不值得填：d(A,B)={distance:.4f} < {MIN_EDGE_DIST:.2f}，"
                    "两端近乎重复，中间没有可开采空间。"
                )
    return spec, None


def _load_graph_file(revision_id: str | None) -> dict[str, Any] | None:
    if not revision_id:
        return None
    graph_path = RUNS_DIR / revision_id / "graph_full.json"
    if not graph_path.is_file():
        return None
    try:
        data = json.loads(graph_path.read_text(encoding="utf-8"))
        return data if isinstance(data, dict) else None
    except (OSError, json.JSONDecodeError):
        return None


def recommend_regions(revision_id: str) -> tuple[dict[str, Any] | None, str | None]:
    """Return the system-recommended search regions for a revision's graph."""
    revision = get_revision_record(revision_id)
    if revision is None:
        return None, "未找到对应 revision。"
    config = revision.get("config", {})
    if not isinstance(config, dict):
        config = {}
    method_config = config.get("method", {})
    if not isinstance(method_config, dict):
        method_config = {}
    graph = get_graph_data(
        RUNS_DIR / revision_id,
        RUNS_DIR / revision_id / "log",
        method_config=method_config,
        max_nodes=50000,
        source_revision_id=str(config.get("source_revision_id", "") or "").strip() or None,
        cluster_id=None,
        allow_async_build=False,
    )
    nodes = graph.get("nodes", []) if isinstance(graph, dict) else []
    if not isinstance(nodes, list) or len(nodes) < 2:
        return None, "图数据不足（<2 个节点）。请先完成构图。"
    if str(graph.get("graphSource") or "") == "summary_clusters":
        return None, "当前展示的是摘要聚类图，请先构建全量 NBN 图后再获取区域推荐。"
    if graph.get("error"):
        return None, f"图数据不可用：{graph.get('error')}"
    result = recommend_candidates(graph)
    _attach_gap_scores(result, graph)
    return result, None


def _attach_gap_scores(result: dict[str, Any], graph: dict[str, Any]) -> None:
    """Compute each high-score candidate's gap to the nearest better solution
    (semantic distance, via the embedding cache) and re-rank true blanks first.
    """
    high_score = result.get("highScoreList") or []
    if not high_score:
        return
    top_k = int(result.get("_highScoreTopK") or 20)
    nodes = graph.get("nodes") if isinstance(graph, dict) else []
    if not isinstance(nodes, list):
        return
    valid_nodes = [
        node
        for node in nodes
        if normalize_valid_score(node.get("rawScore", node.get("score"))) is not None
    ]
    if len(valid_nodes) < 2:
        return
    try:
        from visual_platform.nbn.bridge import get_codet5_embedding_matrix
        from visual_platform.repositories import get_individuals_by_ids

        records = get_individuals_by_ids([str(node.get("id") or "") for node in valid_nodes])
        by_id = {str(record.get("id") or ""): record for record in records}
        code_of = {
            node_id: str(
                record.get("function")
                or record.get("program")
                or record.get("code")
                or ""
            ).strip()
            for node_id, record in by_id.items()
        }
        node_ids = [str(node.get("id") or "") for node in valid_nodes]
        vectors, _ = get_codet5_embedding_matrix(
            [{"function": code_of[node_id]} for node_id in node_ids],
            progress_callback=lambda payload: None,
        )
        index_of = {node_id: index for index, node_id in enumerate(node_ids)}
        scores = {
            node_id: float(normalize_valid_score(node.get("rawScore", node.get("score"))))
            for node, node_id in zip(valid_nodes, node_ids, strict=False)
        }
    except Exception:
        return

    import numpy as np

    for item in high_score:
        anchor_id = str(item.get("anchor") or "")
        anchor_score = float(item.get("repScore") or 0.0)
        anchor_index = index_of.get(anchor_id)
        if anchor_index is None:
            item["gapToNearestBetter"] = None
            item["gapStatus"] = "unknown"
            continue
        anchor_vec = vectors[anchor_index]
        distances = 1.0 - np.clip(vectors @ anchor_vec, -1.0, 1.0)
        gap = min_gap_to_better(
            anchor_score,
            [scores.get(node_id, 0.0) for node_id in node_ids],
            distances,
        )
        if gap is None:
            item["gapToNearestBetter"] = None
            item["gapStatus"] = "unknown"
            continue
        item["gapToNearestBetter"] = round(gap, 4)
        item["gapStatus"] = gap_status(gap)

    # Rank true blanks first, then by score, and trim back to the leaderboard size.
    high_score.sort(
        key=lambda item: (
            -(float(item.get("gapToNearestBetter") or -1.0)),
            -float(item.get("repScore") or 0.0),
            str(item.get("anchor") or ""),
        )
    )
    result["highScoreList"] = high_score[:top_k]


def get_region_report(revision_id: str) -> tuple[dict[str, Any] | None, str | None]:
    """Region summary + ledger + markdown report for a region_search revision."""
    revision = get_revision_record(revision_id)
    if revision is None:
        return None, "未找到对应 revision。"
    config = revision.get("config", {})
    if not isinstance(config, dict):
        config = {}
    region = config.get("region")
    if not isinstance(region, dict):
        return None, "该 revision 不是区域搜索任务。"

    revision_dir = RUNS_DIR / revision_id
    ledger_records: list[dict[str, Any]] = []
    ledger_path = revision_dir / "region_ledger.jsonl"
    if ledger_path.is_file():
        try:
            for line in ledger_path.read_text(encoding="utf-8").splitlines():
                line = line.strip()
                if line:
                    ledger_records.append(json.loads(line))
        except (OSError, json.JSONDecodeError):
            ledger_records = []

    report_text = ""
    report_path = revision_dir / "region_report.md"
    if report_path.is_file():
        try:
            report_text = report_path.read_text(encoding="utf-8")
        except OSError:
            report_text = ""

    neighborhood: list[dict[str, Any]] = []
    if ledger_records:
        final_record = ledger_records[-1]
        if isinstance(final_record.get("neighborhood"), list):
            neighborhood = final_record["neighborhood"]

    source_revision_id = str(config.get("source_revision_id", "") or "").strip() or None
    corridor = None
    if source_revision_id:
        source_graph = _load_graph_file(source_revision_id)
        new_graph = _load_graph_file(revision_id)
        if str(region.get("type") or "") == "expand":
            corridor = anchor_cluster_metrics(source_graph, new_graph, str(region.get("a") or ""))
        else:
            corridor = corridor_comparison(source_graph, new_graph, region)

    return {
        "revisionId": revision_id,
        "region": region,
        "summary": config.get("regionSummary"),
        "ledger": ledger_records,
        "neighborhood": neighborhood,
        "reportMarkdown": report_text,
        "corridor": corridor,
    }, None
