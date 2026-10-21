from __future__ import annotations

import hashlib
import math
import re
from pathlib import Path
from typing import Any, Callable


def is_history_import_run(
    revision_dir: Path,
    *,
    read_masked_config: Callable[[Path], dict[str, Any]],
) -> bool:
    config = read_masked_config(revision_dir)
    return str(config.get("mode", "") or "").strip() == "history_import"


def normalize_graph_visual_flags(
    revision_dir: Path,
    graph: dict[str, Any],
    *,
    is_history_import_run_fn: Callable[[Path], bool],
) -> dict[str, Any]:
    if not is_history_import_run_fn(revision_dir):
        return graph

    normalized = dict(graph)
    nodes = normalized.get("nodes", [])
    if isinstance(nodes, list):
        normalized["nodes"] = [
            {
                **node,
                "isLatestRevision": False,
                "isLatestRound": False,
            }
            if isinstance(node, dict)
            else node
            for node in nodes
        ]
    normalized["latestRevisionSampleCount"] = 0
    normalized["latestRevisionBestScore"] = None
    normalized["latestRevisionExceededHistoryBest"] = False
    normalized["latestGeneration"] = None
    normalized["latestRoundSampleCount"] = 0
    return normalized


def sanitize_graph_score(raw_score: Any) -> float | None:
    if raw_score is None:
        return None
    try:
        score = float(raw_score)
    except (TypeError, ValueError):
        return None
    if not math.isfinite(score):
        return None
    return score

def clean_sample_data(sample: dict[str, Any]) -> dict[str, Any]:
    cleaned = dict(sample)
    cleaned["score"] = sanitize_graph_score(cleaned.get("score"))
    if cleaned.get("rawScore") is not None:
        cleaned["rawScore"] = sanitize_graph_score(cleaned.get("rawScore"))
    
    # Ensure numeric fields are finite
    for field in ["x", "y", "z", "zScore", "zTree", "distanceToParent"]:
        if field in cleaned:
            val = cleaned[field]
            if val is not None:
                try:
                    val = float(val)
                    if not math.isfinite(val):
                        val = 0.0
                except (TypeError, ValueError):
                    val = 0.0
                cleaned[field] = val
                
    # Ensure int fields
    for field in ["sampleOrder", "mergedSampleOrder", "generation", "ofecIndex", "ofecParentIndex"]:
        if field in cleaned and cleaned[field] is not None:
            try:
                cleaned[field] = int(cleaned[field])
            except (TypeError, ValueError):
                cleaned[field] = None
                
    # Ensure string fields
    for field in ["id", "operator", "algorithm", "algorithmSummary", "functionPreview", "programPreview", "sourceKind", "sourceRevisionId", "sourceLabel", "originKind"]:
        if field in cleaned and cleaned[field] is not None:
            cleaned[field] = str(cleaned[field])
            
    # Ensure boolean fields
    for field in ["isLatestRevision", "isLatestRound", "hasExternalExpert"]:
        if field in cleaned and cleaned[field] is not None:
            cleaned[field] = bool(cleaned[field])
            
    return cleaned

def raw_score_key(sample: dict[str, Any]) -> float:
    score = sanitize_graph_score(sample.get("score"))
    return score if score is not None else -1e9


def simple_code_tokens(text: str) -> list[str]:
    return re.findall(r"[A-Za-z_][A-Za-z0-9_]*", str(text or "").lower())


def sample_code_text(
    sample: dict[str, Any],
    *,
    function_preview_fn: Callable[[dict[str, Any]], str],
) -> str:
    return function_preview_fn(sample).strip() or str(sample.get("algorithm", "") or "").strip()


def sample_simhash(
    sample: dict[str, Any],
    *,
    function_preview_fn: Callable[[dict[str, Any]], str],
) -> int:
    code_text = sample_code_text(sample, function_preview_fn=function_preview_fn)
    tokens = simple_code_tokens(code_text)
    if not tokens:
        tokens = [str(sample.get("operator", "") or "unknown").lower(), code_text[:32] or "empty"]
    counts: dict[str, int] = {}
    for token in tokens[:256]:
        counts[token] = counts.get(token, 0) + 1
    weights = [0] * 64
    operator = str(sample.get("operator", "") or "").strip().lower()
    if operator:
        counts[f"operator:{operator}"] = counts.get(f"operator:{operator}") or 0
        counts[f"operator:{operator}"] += 3
    for token, weight in counts.items():
        digest = hashlib.blake2b(token.encode("utf-8", errors="ignore"), digest_size=8).digest()
        token_bits = int.from_bytes(digest, "big", signed=False)
        for bit_index in range(64):
            if token_bits & (1 << bit_index):
                weights[bit_index] += weight
            else:
                weights[bit_index] -= weight
    result = 0
    for bit_index, weight in enumerate(weights):
        if weight >= 0:
            result |= 1 << bit_index
    return result


def hamming_distance64(lhs: int, rhs: int) -> int:
    return (lhs ^ rhs).bit_count()


def summary_cluster_count(
    total_samples: int,
    max_nodes: int,
    *,
    summary_graph_cluster_limit: int,
) -> int:
    target = max(24, int(round(math.sqrt(max(total_samples, 1)) * 1.6)))
    return max(18, min(max_nodes, summary_graph_cluster_limit, target))


def build_summary_clusters(
    samples: list[dict[str, Any]],
    max_nodes: int,
    *,
    summary_graph_cluster_limit: int,
    function_preview_fn: Callable[[dict[str, Any]], str],
) -> dict[str, Any]:
    if not samples:
        return {"nodes": [], "edges": [], "clusterMap": {}, "truncated": False}
    cluster_target = summary_cluster_count(
        len(samples),
        max_nodes,
        summary_graph_cluster_limit=summary_graph_cluster_limit,
    )
    prefix_bits = max(1, min(12, int(math.ceil(math.log2(max(cluster_target, 2))))))
    clusters: dict[str, dict[str, Any]] = {}
    for sample in samples:
        simhash = sample_simhash(sample, function_preview_fn=function_preview_fn)
        bucket = simhash >> max(0, 64 - prefix_bits)
        cluster_id = f"cluster-{prefix_bits}-{bucket:0{max(1, math.ceil(prefix_bits / 4))}x}"
        cluster = clusters.setdefault(
            cluster_id,
            {
                "id": cluster_id,
                "simhash": simhash,
                "bucket": bucket,
                "samples": [],
                "source_count": 0,
                "current_count": 0,
                "latest_revision_count": 0,
                "latest_count": 0,
                "external_expert_count": 0,
                "operator_counts": {},
            },
        )
        cluster["samples"].append(sample)
        if sample.get("source_kind") == "source":
            cluster["source_count"] += 1
        if sample.get("source_kind") == "current":
            cluster["current_count"] += 1
        if sample.get("is_latest_revision"):
            cluster["latest_revision_count"] += 1
        if sample.get("is_latest_round"):
            cluster["latest_count"] += 1
        if sample.get("origin_kind") == "external_expert":
            cluster["external_expert_count"] += 1
        operator = str(sample.get("operator", "") or "").strip() or "unknown"
        cluster["operator_counts"][operator] = cluster["operator_counts"].get(operator, 0) + 1

    cluster_items = list(clusters.values())
    cluster_items.sort(
        key=lambda item: (
            -max((raw_score_key(sample) for sample in item["samples"]), default=-1e9),
            -len(item["samples"]),
            item["id"],
        )
    )
    min_score = min((raw_score_key(sample) for sample in samples), default=0.0)
    max_score = max((raw_score_key(sample) for sample in samples), default=0.0)
    score_span = max(max_score - min_score, 1e-9)
    nodes: list[dict[str, Any]] = []
    edges: list[dict[str, Any]] = []
    for index, cluster in enumerate(cluster_items):
        members = sorted(
            cluster["samples"],
            key=lambda sample: (raw_score_key(sample), int(sample.get("sample_order", 0) or 0)),
            reverse=True,
        )
        representative = members[0]
        cluster_best_score = raw_score_key(representative)
        cluster_avg_score = sum(raw_score_key(sample) for sample in members) / max(len(members), 1)
        normalized_score = (cluster_best_score - min_score) / score_span if members else 0.0
        display_best_score = None if cluster_best_score <= -1e8 else cluster_best_score
        angle = (2.0 * math.pi * index / max(len(cluster_items), 1)) if len(cluster_items) > 1 else 0.0
        radius = 90.0 + (1.0 - normalized_score) * 90.0 + min(50.0, math.log2(len(members) + 1.0) * 10.0)
        x = math.cos(angle) * radius
        y = math.sin(angle) * radius
        z = (normalized_score - 0.5) * 120.0 + (cluster["bucket"] % 11 - 5) * 8.0
        dominant_operator = max(cluster["operator_counts"].items(), key=lambda item: (item[1], item[0]))[0]
        node = {
            "id": cluster["id"],
            "sampleOrder": representative.get("origin_sample_order", representative.get("sample_order")),
            "mergedSampleOrder": representative.get("sample_order"),
            "generation": representative.get("generation"),
            "isLatestRevision": bool(cluster["latest_revision_count"] > 0),
            "isLatestRound": bool(cluster["latest_count"] > 0),
            "score": display_best_score,
            "rawScore": display_best_score,
            "ofecFitness": None,
            "operator": dominant_operator,
            "algorithm": representative.get("algorithm", ""),
            "algorithmSummary": (
                f"区域摘要：共 {len(members)} 个解，最佳分 {display_best_score:.5f}，主操作符 {dominant_operator}"
                if display_best_score is not None
                else f"区域摘要：共 {len(members)} 个解，当前无有效分数，主操作符 {dominant_operator}"
            ),
            "functionPreview": representative.get("function", "") or representative.get("program", "") or "",
            "programPreview": representative.get("program", "") or representative.get("function", "") or "",
            "sourceKind": "cluster_summary",
            "sourceRevisionId": representative.get("source_revision_id", ""),
            "sourceLabel": (
                f"区域摘要（{len(members)} 个解，含 {cluster['external_expert_count']} 个外部专家解）"
                if cluster["external_expert_count"] > 0
                else f"区域摘要（{len(members)} 个解）"
            ),
            "originKind": "external_expert" if cluster["external_expert_count"] > 0 else representative.get("origin_kind", ""),
            "hasExternalExpert": bool(cluster["external_expert_count"] > 0),
            "x": float(x),
            "y": float(y),
            "z": float(z),
            "ofecIndex": index,
            "ofecParentIndex": None,
            "distanceToParent": None,
            "isClusterSummary": True,
            "clusterId": cluster["id"],
            "clusterSampleCount": len(members),
            "clusterSourceCount": cluster["source_count"],
            "clusterCurrentCount": cluster["current_count"],
            "clusterLatestCount": cluster["latest_count"],
            "clusterBestScore": None if cluster_best_score <= -1e8 else cluster_best_score,
            "clusterAverageScore": None if cluster_avg_score <= -1e8 else cluster_avg_score,
            "clusterRepresentativeId": representative.get("id"),
            "clusterRepresentativeSampleOrder": representative.get("origin_sample_order", representative.get("sample_order")),
            "clusterNodeKind": "summary",
        }
        nodes.append(clean_sample_data(node))
        cluster["node"] = node

    for index, cluster in enumerate(cluster_items):
        if index == 0:
            continue
        cluster_best_score = raw_score_key(max(cluster["samples"], key=raw_score_key))
        better_clusters = cluster_items[:index]
        parent = min(
            better_clusters,
            key=lambda item: (
                hamming_distance64(cluster["simhash"], item["simhash"]),
                abs(cluster_best_score - raw_score_key(max(item["samples"], key=raw_score_key))),
                -len(item["samples"]),
            ),
        )
        edges.append(
            {
                "source": cluster["id"],
                "target": parent["id"],
                "distance": float(hamming_distance64(cluster["simhash"], parent["simhash"])),
            }
        )

    return {
        "nodes": nodes,
        "edges": edges,
        "clusterMap": {
            cluster["id"]: {
                "simhash": cluster["simhash"],
                "sampleCount": len(cluster["samples"]),
                "sampleIds": [sample["id"] for sample in cluster["samples"]],
            }
            for cluster in cluster_items
        },
        "truncated": len(cluster_items) < len(samples),
    }


def normalize_code_for_match(code: str) -> str:
    text = str(code or "")
    text = re.sub(r"#.*", "", text)
    text = text.replace("\r\n", "\n").replace("\r", "\n")
    text = re.sub(r"\s+", "", text)
    return text.strip()


def build_lineage_edges(samples: list[dict[str, Any]]) -> list[dict[str, Any]]:
    active_node_ids = {
        str(sample.get("id"))
        for sample in samples
        if isinstance(sample, dict) and sample.get("id") is not None
    }
    code_to_id: dict[str, Any] = {}
    for sample in samples:
        function_code = sample.get("function")
        if function_code:
            code_to_id[normalize_code_for_match(str(function_code))] = sample["id"]

    lineage_edges: list[dict[str, Any]] = []
    for sample in samples:
        child_id = sample["id"]
        if child_id not in active_node_ids:
            continue
        for parent_code in sample.get("parents", []):
            parent_id = code_to_id.get(normalize_code_for_match(str(parent_code)))
            if parent_id and parent_id in active_node_ids:
                lineage_edges.append({"source": parent_id, "target": child_id})
    return lineage_edges


def build_small_sample_graph(
    samples: list[dict[str, Any]],
    *,
    distance_metric: str | None = None,
    function_preview_fn: Callable[[dict[str, Any]], str],
) -> dict[str, Any]:
    requested_metric = str(distance_metric or "").strip() or "codet5p_embedding_cosine"
    nodes: list[dict[str, Any]] = []
    for index, sample in enumerate(samples):
        raw_score = sanitize_graph_score(sample.get("score"))
        node = {
            "id": sample["id"],
            "sampleOrder": sample.get("origin_sample_order", sample["sample_order"]),
            "mergedSampleOrder": sample["sample_order"],
            "generation": sample.get("generation"),
            "isLatestRevision": bool(sample.get("is_latest_revision")),
            "isLatestRound": bool(sample.get("is_latest_round")),
            "score": raw_score,
            "rawScore": raw_score,
            "ofecFitness": None,
            "operator": sample.get("operator", ""),
            "algorithm": sample.get("algorithm", ""),
            "algorithmSummary": (sample.get("algorithm", "") or "No algorithm summary")[:160],
            "functionPreview": function_preview_fn(sample),
            "programPreview": str(sample.get("program", "") or "").strip() or function_preview_fn(sample),
            "sourceKind": sample.get("source_kind", ""),
            "sourceRevisionId": sample.get("source_revision_id", ""),
            "sourceLabel": sample.get("source_label", ""),
            "originKind": sample.get("origin_kind", sample.get("source_kind", "")),
            "hasExternalExpert": sample.get("origin_kind") == "external_expert",
            "x": 0.0,
            "y": 0.0,
            "z": 0.0,
            "ofecIndex": index,
            "ofecParentIndex": index,
            "distanceToParent": 0.0,
        }
        nodes.append(clean_sample_data(node))

    return {
        "nodes": nodes,
        "edges": [],
        "lineageEdges": build_lineage_edges(samples),
        "truncated": False,
        "graphSource": "empty",
        "distanceMetric": requested_metric,
        "distanceMetricRequested": requested_metric,
        "distanceMetricFallbackReason": "仅有 1 个样本，退化为单根节点图。",
    }


def pick_local_cluster_samples(
    samples: list[dict[str, Any]],
    cluster_id: str,
    max_nodes: int,
    *,
    build_summary_clusters: Callable[[list[dict[str, Any]], int], dict[str, Any]],
    summary_graph_cluster_limit: int,
    hamming_distance64: Callable[[int, int], int],
    raw_score_key: Callable[[dict[str, Any]], float],
) -> tuple[list[dict[str, Any]], dict[str, Any]] | None:
    summary = build_summary_clusters(samples, max(max_nodes, summary_graph_cluster_limit))
    cluster_map = summary.get("clusterMap", {})
    target_cluster = cluster_map.get(cluster_id)
    if not isinstance(target_cluster, dict):
        return None
    sample_lookup = {sample["id"]: sample for sample in samples}
    selected_ids: list[str] = list(target_cluster.get("sampleIds", []))
    selected_set = set(selected_ids)
    if len(selected_ids) < max_nodes:
        other_clusters = []
        for other_id, other in cluster_map.items():
            if other_id == cluster_id:
                continue
            other_clusters.append(
                (
                    hamming_distance64(int(target_cluster.get("simhash", 0)), int(other.get("simhash", 0))),
                    -int(other.get("sampleCount", 0)),
                    other_id,
                    other,
                )
            )
        other_clusters.sort()
        for _, _, _, other in other_clusters:
            for sample_id in other.get("sampleIds", []):
                if sample_id in selected_set:
                    continue
                selected_ids.append(sample_id)
                selected_set.add(sample_id)
                if len(selected_ids) >= max_nodes:
                    break
            if len(selected_ids) >= max_nodes:
                break
    local_samples = [sample_lookup[sample_id] for sample_id in selected_ids if sample_id in sample_lookup]
    local_samples.sort(key=lambda sample: int(sample.get("sample_order", 0) or 0))
    local_samples = local_samples[:max_nodes]
    selected_best = max((raw_score_key(sample) for sample in local_samples), default=-1e9)
    return local_samples, {
        "graphView": "local_cluster",
        "expandedClusterId": cluster_id,
        "expandedClusterSampleCount": int(target_cluster.get("sampleCount", 0)),
        "expandedBestScore": None if selected_best <= -1e8 else selected_best,
    }


def lineage_revision_dirs(
    revision_dir: Path,
    source_revision_id: str | None,
    *,
    resolve_revision_dir: Callable[[str | None], Path | None],
    read_masked_config: Callable[[Path], dict[str, Any]],
) -> list[Path]:
    lineage: list[Path] = []
    visited_revision_ids: set[str] = {revision_dir.name}
    pending_revision_id = str(source_revision_id or "").strip() or None

    while pending_revision_id:
        ancestor_revision_dir = resolve_revision_dir(pending_revision_id)
        if ancestor_revision_dir is None:
            break
        ancestor_revision_id = ancestor_revision_dir.name
        if ancestor_revision_id in visited_revision_ids:
            break
        visited_revision_ids.add(ancestor_revision_id)
        lineage.append(ancestor_revision_dir)
        ancestor_config = read_masked_config(ancestor_revision_dir)
        if isinstance(ancestor_config, dict):
            pending_revision_id = str(ancestor_config.get("source_revision_id", "") or "").strip() or None
        else:
            pending_revision_id = None

    lineage.reverse()
    return lineage


def combined_graph_samples(
    revision_dir: Path,
    log_dir: Path,
    source_revision_id: str | None,
    *,
    lineage_revision_dirs_fn: Callable[[Path, str | None], list[Path]],
    cache_key_builder: Callable[[Path, str | None, list[Path]], str],
    cache_get: Callable[[str], tuple[list[dict[str, Any]], dict[str, Any]] | None],
    cache_put: Callable[[str, list[dict[str, Any]], dict[str, Any]], None],
    load_samples_from_log_dir: Callable[..., list[dict[str, Any]]],
    revision_pop_size: Callable[[Path], int | None],
    read_masked_config: Callable[[Path], dict[str, Any]],
    clone_samples: Callable[[list[dict[str, Any]]], list[dict[str, Any]]],
) -> tuple[list[dict[str, Any]], dict[str, Any]]:
    samples: list[dict[str, Any]] = []
    source_count = 0
    current_count = 0
    normalized_source = str(source_revision_id or "").strip()
    ancestor_revision_dirs = lineage_revision_dirs_fn(revision_dir, normalized_source)
    cache_key = cache_key_builder(revision_dir, normalized_source, ancestor_revision_dirs)
    cached = cache_get(cache_key)
    if cached is not None:
        return cached
    ancestor_revision_ids = [path.name for path in ancestor_revision_dirs]
    for source_revision_dir in ancestor_revision_dirs:
        source_samples = load_samples_from_log_dir(
            source_revision_dir / "log",
            revision_id=source_revision_dir.name,
            source_kind="source",
            pop_size=revision_pop_size(source_revision_dir),
            sample_order_offset=len(samples),
        )
        samples.extend(source_samples)
        source_count += len(source_samples)

    current_samples = load_samples_from_log_dir(
        log_dir,
        revision_id=revision_dir.name,
        source_kind="current",
        pop_size=revision_pop_size(revision_dir),
        sample_order_offset=len(samples),
    )
    source_best_score = max((sample["score"] for sample in samples if sample.get("score") is not None), default=None)
    current_best_score = max((sample["score"] for sample in current_samples if sample.get("score") is not None), default=None)
    run_config = read_masked_config(revision_dir)
    is_history_import_run = str(run_config.get("mode", "") or "").strip() == "history_import"
    latest_generation = max(
        (int(sample["generation"]) for sample in current_samples if sample.get("generation") is not None),
        default=None,
    )
    for sample in samples:
        sample["is_latest_round"] = False
        sample["is_latest_revision"] = False
    if is_history_import_run:
        for sample in current_samples:
            sample["is_latest_round"] = False
            sample["is_latest_revision"] = False
    elif latest_generation is not None:
        for sample in current_samples:
            sample["is_latest_round"] = sample.get("generation") == latest_generation
    else:
        for sample in current_samples:
            sample["is_latest_round"] = False
    if not is_history_import_run:
        for sample in current_samples:
            sample["is_latest_revision"] = True
    samples.extend(current_samples)
    current_count = len(current_samples)
    latest_revision_sample_count = 0 if is_history_import_run else current_count
    latest_round_sample_count = 0 if is_history_import_run else sum(1 for sample in current_samples if sample.get("is_latest_round"))
    context = {
        "sourceRevisionId": normalized_source or None,
        "ancestorRevisionIds": ancestor_revision_ids,
        "mergedRevisionCount": len(ancestor_revision_ids) + 1,
        "sourceSampleCount": source_count,
        "currentSampleCount": current_count,
        "latestRevisionSampleCount": latest_revision_sample_count,
        "latestRevisionBestScore": None if is_history_import_run else current_best_score,
        "historicalBestScore": source_best_score,
        "latestRevisionExceededHistoryBest": bool(
            not is_history_import_run
            and current_best_score is not None
            and source_best_score is not None
            and current_best_score > source_best_score
        ),
        "latestGeneration": None if is_history_import_run else latest_generation,
        "latestRoundSampleCount": latest_round_sample_count,
    }
    cache_put(cache_key, samples, context)
    return clone_samples(samples), dict(context)
