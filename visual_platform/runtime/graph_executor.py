from __future__ import annotations

import json
import logging
import os
import tempfile
import threading
import time
from datetime import datetime
from pathlib import Path
from typing import Any, Callable

from visual_platform.config import DEFAULT_GRAPH_NODE_LIMIT, BASE_DIR
from visual_platform.nbn.bridge import (
    build_nbn_graph,
    get_distance_metric_name,
)
from visual_platform.repositories import (
    get_job,
    get_revision_record,
    get_sample_revision,
    list_individuals_for_revision,
    upsert_graph_artifact,
    upsert_revision,
)
from visual_platform.services import job_service, workspace_service
from visual_platform.services.graph_sample_service import (
    build_small_sample_graph,
    build_summary_clusters,
    combined_graph_samples,
    hamming_distance64,
    is_history_import_run,
    normalize_graph_visual_flags,
    pick_local_cluster_samples,
    raw_score_key,
)
from visual_platform.services.graph_query_service import slim_graph_for_transport


GRAPH_BUILD_TASK_NAME = "visual_platform.celery_worker.build_graph"
GRAPH_ACTIVE_STATUSES = {"queued", "running", "stop_requested"}
_SUMMARY_GRAPH_CLUSTER_LIMIT = 128
_perf_lock = threading.Lock()
_perf_samples: dict[str, list[float]] = {}
logger = logging.getLogger(__name__)
ProgressCallback = Callable[[dict[str, Any]], None]


class GraphBuildCancelled(RuntimeError):
    pass


def now_iso() -> str:
    return datetime.now().isoformat(timespec="seconds")


def normalize_graph_limit(limit: Any) -> int:
    try:
        normalized = int(limit)
    except (TypeError, ValueError):
        return DEFAULT_GRAPH_NODE_LIMIT
    return max(1, normalized)


def graph_variant(cluster_id: str | None) -> str:
    normalized_cluster_id = str(cluster_id or "").strip() or None
    return "full" if normalized_cluster_id is None else f"cluster_{normalized_cluster_id}"


def graph_job_id(revision_id: str, cluster_id: str | None) -> str:
    variant = graph_variant(cluster_id)
    if variant == "full":
        return f"graph-build:{revision_id}"
    return f"graph-build:{revision_id}:{variant}"


def graph_distance_metric(method_config: dict[str, Any] | None) -> str:
    return str(
        get_distance_metric_name(method_config.get("distance_metric") if isinstance(method_config, dict) else None)
        or ""
    ).strip().lower()


def perf_stat_summary(metric_key: str) -> dict[str, Any]:
    with _perf_lock:
        samples = list(_perf_samples.get(metric_key, []))
    count = len(samples)
    return {
        "lastMs": samples[-1] if samples else None,
        "avgMs": (sum(samples) / count) if count else None,
        "maxMs": max(samples) if samples else None,
        "count": count,
    }


def record_perf_stat(metric_key: str, value_ms: float) -> dict[str, Any]:
    with _perf_lock:
        samples = _perf_samples.setdefault(metric_key, [])
        samples.append(float(value_ms))
        if len(samples) > 20:
            del samples[:-20]
    return perf_stat_summary(metric_key)


def update_revision_graph_state(
    revision_id: str,
    *,
    graph_status: str,
    error: str | None = None,
    cluster_id: str | None = None,
) -> None:
    if cluster_id:
        return
    update_kwargs: dict[str, Any] = {"graph_status": graph_status}
    if error is not None:
        update_kwargs["error"] = str(error)
    elif graph_status in {"building", "ready", "stale"}:
        update_kwargs["error"] = ""
    upsert_revision(revision_id, **update_kwargs)


def _source_revision_id_from_config(config: dict[str, Any] | None) -> str | None:
    if not isinstance(config, dict):
        return None
    source_revision_id = str(config.get("source_revision_id", "") or "").strip()
    return source_revision_id or None


def _read_revision_config(revision_id: str) -> dict[str, Any]:
    revision = get_revision_record(revision_id)
    config = revision.get("config", {}) if isinstance(revision, dict) else {}
    return config if isinstance(config, dict) else {}


def _resolve_revision_dir(revision_id: str | None) -> Path | None:
    requested = str(revision_id or "").strip()
    if not requested:
        return None
    revision = get_revision_record(requested)
    if not revision:
        return None
    config = revision.get("config", {})
    if not isinstance(config, dict):
        return None
    log_dir = str(config.get("log_dir", "") or "").strip()
    if not log_dir:
        return None
    return Path(log_dir).parent


def _function_preview(sample: dict[str, Any]) -> str:
    return (
        str(sample.get("function", "") or "").strip()
        or str(sample.get("program", "") or "").strip()
        or str(sample.get("algorithm", "") or "").strip()
    )


def _clone_samples(samples: list[dict[str, Any]]) -> list[dict[str, Any]]:
    return [dict(sample) for sample in samples]


def _load_revision_samples(
    revision_id: str,
    *,
    source_kind: str,
    sample_order_offset: int = 0,
) -> list[dict[str, Any]]:
    records = list_individuals_for_revision(revision_id)
    normalized: list[dict[str, Any]] = []
    for index, sample in enumerate(records):
        record = dict(sample)
        sample_order = int(record.get("sample_order", index + 1) or index + 1)
        record.setdefault("id", f"{revision_id}-sample-{sample_order}")
        record.setdefault("revision_id", revision_id)
        record["sample_order"] = sample_order + sample_order_offset
        record["source_kind"] = str(record.get("source_kind", "") or source_kind)
        record["origin_kind"] = str(record.get("origin_kind", "") or record["source_kind"])
        record.setdefault("source_revision_id", revision_id)
        record.setdefault("source_label", revision_id)
        normalized.append(record)
    return normalized


def _lineage_revision_dirs(revision_dir: Path, source_revision_id: str | None) -> list[Path]:
    # Preferred path: an explicit snapshot of the revisions that made up the graph the run was
    # seeded from, recorded at creation. This is robust to later deletion of intermediate
    # revisions (unlike walking the source_revision_id chain, which breaks on the first gap).
    snapshot = _read_revision_config(revision_dir.name).get("merged_source_revision_ids")
    if isinstance(snapshot, list) and snapshot:
        lineage: list[Path] = []
        visited_revision_ids: set[str] = {revision_dir.name}
        for candidate in snapshot:
            candidate_id = str(candidate or "").strip()
            if not candidate_id or candidate_id in visited_revision_ids:
                continue
            ancestor_revision_dir = _resolve_revision_dir(candidate_id)
            if ancestor_revision_dir is None:
                continue
            visited_revision_ids.add(ancestor_revision_dir.name)
            lineage.append(ancestor_revision_dir)
        return lineage

    lineage = []
    visited_revision_ids = {revision_dir.name}
    pending_revision_id = str(source_revision_id or "").strip() or None
    while pending_revision_id:
        ancestor_revision_dir = _resolve_revision_dir(pending_revision_id)
        if ancestor_revision_dir is None:
            break
        ancestor_revision_id = ancestor_revision_dir.name
        if ancestor_revision_id in visited_revision_ids:
            break
        visited_revision_ids.add(ancestor_revision_id)
        lineage.append(ancestor_revision_dir)
        pending_revision_id = _source_revision_id_from_config(_read_revision_config(ancestor_revision_id))
    lineage.reverse()
    return lineage


def _combined_graph_samples(
    revision_dir: Path,
    source_revision_id: str | None,
) -> tuple[list[dict[str, Any]], dict[str, Any]]:
    samples, context = combined_graph_samples(
        revision_dir,
        revision_dir / "log",
        source_revision_id,
        lineage_revision_dirs_fn=_lineage_revision_dirs,
        cache_key_builder=lambda *_args, **_kwargs: "",
        cache_get=lambda _cache_key: None,
        cache_put=lambda *_args, **_kwargs: None,
        load_samples_from_log_dir=lambda _log_dir, *, revision_id, source_kind, pop_size=None, sample_order_offset=0: _load_revision_samples(
            revision_id,
            source_kind=source_kind,
            sample_order_offset=sample_order_offset,
        ),
        revision_pop_size=lambda _path: None,
        read_masked_config=lambda revision_path: _read_revision_config(revision_path.name),
        clone_samples=_clone_samples,
    )
    return _supplement_with_orphan_members(
        revision_dir,
        samples,
        context,
        source_revision_id=source_revision_id,
    )


def _append_missing_members(
    samples: list[dict[str, Any]],
    context: dict[str, Any],
    members: list[dict[str, Any]],
) -> tuple[list[dict[str, Any]], dict[str, Any]]:
    """Append member records (already loaded from the DB) that are missing from
    the current sample set, keeping the merged graph complete even when a node's
    origin revision is absent from the lineage snapshot."""
    if not members:
        return samples, context

    existing_ids = {str(sample.get("id")) for sample in samples if sample.get("id")}
    missing = [m for m in members if str(m.get("id")) not in existing_ids]
    if not missing:
        return samples, context

    max_order = max((int(sample.get("sample_order") or 0) for sample in samples), default=0)
    recovered_scores: list[float] = []
    recovered_origins: set[str] = set()
    for offset, payload in enumerate(missing, start=1):
        sample = dict(payload)
        origin = str(sample.get("revision_id") or "").strip()
        sample["source_kind"] = "source"
        sample["origin_kind"] = str(sample.get("origin_kind", "") or "source")
        sample["source_revision_id"] = origin or sample.get("source_revision_id") or "deleted"
        sample.setdefault("source_label", sample["source_revision_id"])
        sample["sample_order"] = max_order + offset
        sample["is_latest_round"] = False
        sample["is_latest_revision"] = False
        samples.append(sample)
        if sample.get("score") is not None:
            recovered_scores.append(sample["score"])
        if origin:
            recovered_origins.add(origin)

    # Reflect the recovered ancestors in the merge context (UI badges/best scores).
    context = dict(context)
    context["sourceSampleCount"] = int(context.get("sourceSampleCount") or 0) + len(missing)
    existing_ancestors = list(context.get("ancestorRevisionIds") or [])
    for origin in recovered_origins:
        if origin not in existing_ancestors:
            existing_ancestors.append(origin)
    context["ancestorRevisionIds"] = existing_ancestors
    context["mergedRevisionCount"] = len(existing_ancestors) + 1
    if recovered_scores:
        historical = context.get("historicalBestScore")
        best_recovered = max(recovered_scores)
        context["historicalBestScore"] = best_recovered if historical is None else max(historical, best_recovered)
    context["recoveredOrphanMemberCount"] = int(context.get("recoveredOrphanMemberCount") or 0) + len(missing)
    return samples, context


def _supplement_with_orphan_members(
    revision_dir: Path,
    samples: list[dict[str, Any]],
    context: dict[str, Any],
    *,
    source_revision_id: str | None = None,
) -> tuple[list[dict[str, Any]], dict[str, Any]]:
    """Keep a derived revision's merged graph complete beyond the lineage
    snapshot: add back (a) members recorded for this revision whose origin was
    deleted, and (b) every member of the source revision's graph that the
    lineage walk missed (e.g. expert-import revisions not present in the
    ``merged_source_revision_ids`` snapshot). Both ensure region endpoints and
    other source nodes remain locatable in the rebuilt graph.
    """
    try:
        from visual_platform.repositories.individual_repository import list_member_individuals

        members = list_member_individuals(revision_dir.name)
        samples, context = _append_missing_members(samples, context, members)
    except Exception:
        pass

    if source_revision_id:
        try:
            source_members = list_member_individuals(source_revision_id)
            samples, context = _append_missing_members(samples, context, source_members)
        except Exception:
            pass
    return samples, context


def _normalize_graph_visual_flags_for_revision(revision_dir: Path, graph: dict[str, Any]) -> dict[str, Any]:
    return normalize_graph_visual_flags(
        revision_dir,
        graph,
        is_history_import_run_fn=lambda path: is_history_import_run(
            path,
            read_masked_config=lambda inner_path: _read_revision_config(inner_path.name),
        ),
    )


def _build_summary_graph(samples: list[dict[str, Any]], max_nodes: int, distance_metric: str) -> dict[str, Any]:
    summary = build_summary_clusters(
        samples,
        max_nodes,
        summary_graph_cluster_limit=_SUMMARY_GRAPH_CLUSTER_LIMIT,
        function_preview_fn=_function_preview,
    )
    summary["graphSource"] = "summary_clusters"
    summary["distanceMetric"] = distance_metric
    summary["distanceMetricRequested"] = distance_metric
    return summary


def _run_ofec_graph(
    samples: list[dict[str, Any]],
    revision_id: str,
    variant: str,
    *,
    distance_metric: str,
    progress_callback: ProgressCallback | None = None,
) -> dict[str, Any]:
    with tempfile.TemporaryDirectory(prefix=f"vp_graph_{revision_id}_{variant}_") as temp_dir:
        return build_nbn_graph(
            samples,
            Path(temp_dir),
            distance_metric=distance_metric,
            progress_callback=progress_callback,
        )


def _build_full_graph(
    samples: list[dict[str, Any]],
    revision_dir: Path,
    variant: str,
    *,
    distance_metric: str,
    progress_callback: ProgressCallback | None = None,
) -> dict[str, Any]:
    """Build the full-graph payload with a full OFEC NBN recompute over all nodes."""
    return _run_ofec_graph(
        samples,
        revision_dir.name,
        variant,
        distance_metric=distance_metric,
        progress_callback=progress_callback,
    )


def _build_graph_payload(
    revision_dir: Path,
    *,
    method_config: dict[str, Any] | None,
    max_nodes: int,
    source_revision_id: str | None,
    cluster_id: str | None,
    progress_callback: ProgressCallback | None = None,
) -> dict[str, Any]:
    samples, context = _combined_graph_samples(revision_dir, source_revision_id)
    # Fix the merged node set as members of this revision so it survives deletion of
    # any source/ancestor revision (reference-counted deletion keeps referenced nodes).
    try:
        from visual_platform.repositories.individual_repository import add_revision_members

        add_revision_members(
            revision_dir.name,
            [str(sample.get("id")) for sample in samples if sample.get("id")],
        )
    except Exception:
        pass
    distance_metric = get_distance_metric_name(
        method_config.get("distance_metric") if isinstance(method_config, dict) else None
    )
    variant = graph_variant(cluster_id)
    graph: dict[str, Any]
    extra_meta: dict[str, Any] = {}

    if cluster_id:
        local_cluster = pick_local_cluster_samples(
            samples,
            cluster_id,
            normalize_graph_limit(max_nodes),
            build_summary_clusters=lambda local_samples, local_limit: build_summary_clusters(
                local_samples,
                local_limit,
                summary_graph_cluster_limit=_SUMMARY_GRAPH_CLUSTER_LIMIT,
                function_preview_fn=_function_preview,
            ),
            summary_graph_cluster_limit=_SUMMARY_GRAPH_CLUSTER_LIMIT,
            hamming_distance64=hamming_distance64,
            raw_score_key=raw_score_key,
        )
        if local_cluster is None:
            graph = {
                "nodes": [],
                "edges": [],
                "truncated": False,
                "graphSource": "empty",
                "distanceMetric": distance_metric,
                "distanceMetricRequested": distance_metric,
                "error": f"未找到区域 {cluster_id}。",
            }
        else:
            selected_samples, extra_meta = local_cluster
            if len(selected_samples) <= 1:
                graph = build_small_sample_graph(
                    selected_samples,
                    distance_metric=distance_metric,
                    function_preview_fn=_function_preview,
                )
            else:
                graph = _run_ofec_graph(
                    selected_samples,
                    revision_dir.name,
                    variant,
                    distance_metric=distance_metric,
                    progress_callback=progress_callback,
                )
    elif not samples:
        graph = {
            "nodes": [],
            "edges": [],
            "truncated": False,
            "graphSource": "empty",
            "distanceMetric": distance_metric,
            "distanceMetricRequested": distance_metric,
        }
    elif len(samples) <= 1:
        graph = build_small_sample_graph(
            samples,
            distance_metric=distance_metric,
            function_preview_fn=_function_preview,
        )
    elif len(samples) > normalize_graph_limit(max_nodes):
        graph = _build_summary_graph(samples, normalize_graph_limit(max_nodes), distance_metric)
    else:
        graph = _build_full_graph(
            samples,
            revision_dir,
            variant,
            distance_metric=distance_metric,
            progress_callback=progress_callback,
        )

    graph.update(context)
    graph.update(extra_meta)
    if cluster_id:
        graph.setdefault("expandedClusterId", cluster_id)
    return graph


def graph_input_summary(
    revision_id: str,
    *,
    distance_metric: str,
    max_nodes: int,
    variant: str,
    sample_revision: int,
    source_revision_id: str | None,
    cluster_id: str | None,
) -> dict[str, Any]:
    return {
        "revisionId": revision_id,
        "distanceMetric": distance_metric,
        "graphOptions": {
            "maxNodes": int(max_nodes),
            "variant": variant,
            "clusterId": str(cluster_id or "").strip() or None,
            "summaryClusterLimit": _SUMMARY_GRAPH_CLUSTER_LIMIT,
        },
        "sampleRevision": int(sample_revision),
        "sourceRevisionId": str(source_revision_id or "").strip() or None,
    }


MAX_GRAPH_BACKUPS = 3


def _prune_graph_backups(revision_dir: Path, variant: str) -> None:
    """只保留最近若干个图备份。

    每次重建都会把上一份重命名成 backup；单份图可达上百 MB，不清理会无限堆积。
    """
    try:
        backups = sorted(
            revision_dir.glob(f"graph_{variant}.backup_*.json"),
            key=lambda path: path.name,
            reverse=True,
        )
    except OSError:
        return
    for stale in backups[MAX_GRAPH_BACKUPS:]:
        try:
            stale.unlink()
            logger.info("Pruned stale graph backup %s", stale)
        except OSError as prune_error:
            logger.warning("Failed to prune graph backup %s: %s", stale, prune_error)


def _persist_graph_artifact(
    revision_dir: Path,
    *,
    job_id: str,
    method_config: dict[str, Any] | None,
    max_nodes: int,
    source_revision_id: str | None,
    cluster_id: str | None,
    progress_callback: ProgressCallback | None = None,
) -> dict[str, Any]:
    normalized_max_nodes = normalize_graph_limit(max_nodes)
    normalized_cluster_id = str(cluster_id or "").strip() or None
    revision_id = revision_dir.name
    variant = graph_variant(normalized_cluster_id)
    sample_revision = int(get_sample_revision(revision_id))
    built_at = now_iso()
    distance_metric = graph_distance_metric(method_config)
    input_summary = graph_input_summary(
        revision_id,
        distance_metric=distance_metric,
        max_nodes=normalized_max_nodes,
        variant=variant,
        sample_revision=sample_revision,
        source_revision_id=source_revision_id,
        cluster_id=normalized_cluster_id,
    )

    # 构图在纯 numpy 中完成（bridge.build_nbn_graph）；异常一律向上抛，
    # 由 job 层统一记为失败（原先只兜 OFEC 扩展报错，该分支已随扩展一并移除）。
    graph = _build_graph_payload(
        revision_dir,
        method_config=method_config,
        max_nodes=normalized_max_nodes,
        source_revision_id=source_revision_id,
        cluster_id=normalized_cluster_id,
        progress_callback=progress_callback,
    )

    graph["graphNodeLimit"] = normalized_max_nodes
    graph["graphCachedAt"] = built_at
    graph["expandedClusterId"] = normalized_cluster_id
    graph["sampleRevision"] = sample_revision
    graph["graphStatus"] = "ready" if not graph.get("error") else "failed"
    graph["graphBuildPhase"] = "ready" if not graph.get("error") else "failed"

    # Drop the heavy per-node code fields before persisting/serving. The full
    # code/algorithm text is fetched on demand per node (node id ==
    # individuals.id), so the transported graph only carries lightweight
    # rendering fields. This keeps the artifact from ballooning to ~100MB.
    graph = slim_graph_for_transport(graph)

    # Write graph data to a JSON file so the artifact can load it from disk
    # instead of embedding the full graph inside the database metadata (which
    # can be 50-100+ MB for large revisions).
    graph_file_path = revision_dir / f"graph_{variant}.json"
    graph_file_rel = ""  # relative path from BASE_DIR (platform-independent)
    try:
        graph_file_path.parent.mkdir(parents=True, exist_ok=True)
        # Keep the previous build instead of silently overwriting it: the NBN/HNSW
        # layout is stochastic, so a rebuild can never reproduce the old picture.
        if graph_file_path.exists():
            backup_stamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            backup_path = revision_dir / f"graph_{variant}.backup_{backup_stamp}.json"
            try:
                graph_file_path.rename(backup_path)
                logger.info("Previous graph backed up to %s", backup_path)
            except OSError as backup_error:
                logger.warning("Failed to back up previous graph: %s", backup_error)
        # 原子写入：先落临时文件再 os.replace。直接原地 write_text 时，进程若在
        # 写入途中崩溃/被杀，会留下截断的 JSON，而读取方会直接拒绝它——
        # 等于整张图作废。fsync 后再改名，保证读者永远看到完整文件。
        payload = json.dumps(graph, ensure_ascii=False)
        tmp_fd, tmp_name = tempfile.mkstemp(
            dir=str(graph_file_path.parent),
            prefix=f".graph_{variant}.",
            suffix=".tmp",
        )
        try:
            with os.fdopen(tmp_fd, "w", encoding="utf-8") as handle:
                handle.write(payload)
                handle.flush()
                os.fsync(handle.fileno())
            os.replace(tmp_name, graph_file_path)
        except BaseException:
            try:
                os.unlink(tmp_name)
            except OSError:
                pass
            raise
        _prune_graph_backups(revision_dir, variant)
        try:
            graph_file_rel = str(graph_file_path.relative_to(BASE_DIR)).replace("\\", "/")
        except (ValueError, TypeError):
            graph_file_rel = str(graph_file_path).replace("\\", "/")
        logger.info(
            "Graph data written to %s (%.1f MB)",
            graph_file_path,
            graph_file_path.stat().st_size / (1024 * 1024),
        )
    except Exception as write_error:
        logger.warning("Failed to write graph file %s: %s", graph_file_path, write_error)
        graph_file_rel = ""

    if progress_callback is not None:
        progress_callback(
            {
                "stage": "persist_artifact",
                "stageLabel": "Persist Graph Artifact",
                "current": 1,
                "total": 1,
                "message": "Persisting completed graph artifact.",
            }
        )

    upsert_graph_artifact(
        revision_id,
        variant=variant,
        metric=distance_metric,
        max_nodes=normalized_max_nodes,
        sample_revision=sample_revision,
        source_revision_id=source_revision_id,
        path=graph_file_rel,
        status=graph["graphStatus"],
        created_by_job_id=job_id,
        error=str(graph.get("error", "") or "").strip() or None,
        # Keep metadata small: do NOT embed the full graph here.
        summary={"savedAt": built_at},
        metadata={
            "inputSummary": input_summary,
            "nodeCount": len(graph.get("nodes", [])),
            "edgeCount": len(graph.get("edges", [])),
            "graphSource": graph.get("graphSource"),
            "distanceMetricRequested": graph.get("distanceMetricRequested"),
        },
    )
    update_revision_graph_state(
        revision_id,
        graph_status=graph["graphStatus"],
        error=str(graph.get("error", "") or "").strip() or None,
        cluster_id=normalized_cluster_id,
    )
    return _normalize_graph_visual_flags_for_revision(revision_dir, graph)


def _merge_job_payload(job_id: str, updates: dict[str, Any]) -> dict[str, Any]:
    job = get_job(job_id)
    payload = job.get("payload", {}) if isinstance(job, dict) else {}
    if not isinstance(payload, dict):
        payload = {}
    merged = dict(payload)
    merged.update(updates)
    return merged


def _task_matches(job: dict[str, Any] | None, task_id: str | None) -> bool:
    if not isinstance(job, dict):
        return True
    payload = job.get("payload", {})
    if not isinstance(payload, dict):
        payload = {}
    current_task_id = str(payload.get("taskId", "") or "").strip() or None
    normalized_task_id = str(task_id or "").strip() or None
    if normalized_task_id is None or current_task_id is None:
        return True
    return current_task_id == normalized_task_id


def _classify_graph_error(error: Exception) -> tuple[str, bool]:
    if isinstance(error, (FileNotFoundError, ValueError)):
        return "graph_input", False
    return "graph_executor", False


def _graph_cancel_payload(
    *,
    job_id: str,
    revision_id: str,
    cluster_id: str | None,
    task_id: str | None,
) -> dict[str, Any]:
    return _merge_job_payload(
        job_id,
        {
            "phase": "cancelled",
            "phaseLabel": "Cancelled",
            "revisionId": revision_id,
            "variant": graph_variant(cluster_id),
            "clusterId": cluster_id,
            "taskId": task_id,
            "retryable": True,
            "finishedAt": now_iso(),
        },
    )


def complete_graph_build_cancellation(
    revision_id: str,
    *,
    job_id: str,
    cluster_id: str | None,
    task_id: str | None = None,
    message: str = "Graph build cancelled.",
) -> dict[str, Any]:
    normalized_cluster_id = str(cluster_id or "").strip() or None
    update_revision_graph_state(revision_id, graph_status="stale", cluster_id=normalized_cluster_id)
    job_service.update_job(
        job_id,
        revision_id,
        "graph_build",
        status="cancelled",
        stage="cancelled",
        stage_label="Cancelled",
        message=message,
        payload=_graph_cancel_payload(
            job_id=job_id,
            revision_id=revision_id,
            cluster_id=normalized_cluster_id,
            task_id=str(task_id or "").strip() or None,
        ),
        result={"cancelled": True, "executor": "celery_worker"},
        finished_at=now_iso(),
    )
    return {
        "active": False,
        "phase": "cancelled",
        "phaseLabel": "Cancelled",
        "message": message,
        "variant": graph_variant(normalized_cluster_id),
        "cancelled": True,
    }


def _raise_if_graph_build_cancelled(
    revision_id: str,
    *,
    job_id: str,
    cluster_id: str | None,
    task_id: str | None,
    message: str,
) -> None:
    current_job = get_job(job_id)
    if not _task_matches(current_job, task_id):
        raise GraphBuildCancelled("Graph build superseded by a newer task.")
    current_status = str(current_job.get("status") or "").strip().lower() if isinstance(current_job, dict) else ""
    if current_status in {"stop_requested", "cancelled"}:
        raise GraphBuildCancelled(message)


def request_graph_build_stop(job: dict[str, Any]) -> None:
    revision_id = str(job.get("revision_id") or "").strip()
    job_id = str(job.get("job_id") or "").strip()
    status = str(job.get("status") or "").strip().lower()
    payload = job.get("payload", {})
    if not isinstance(payload, dict):
        payload = {}
    cluster_id = str(payload.get("clusterId", "") or "").strip() or None
    task_id = str(payload.get("taskId", "") or "").strip() or None

    if task_id:
        try:
            from visual_platform.celery_worker import celery_app

            celery_app.control.revoke(task_id, terminate=False)
        except Exception as error:
            logger.warning("Unable to revoke graph build task %s: %s", task_id, error)

    if status in {"queued", "launch_requested"}:
        complete_graph_build_cancellation(
            revision_id,
            job_id=job_id,
            cluster_id=cluster_id,
            task_id=task_id,
            message="Graph build cancelled before execution.",
        )
        return

    job_service.update_job(
        job_id,
        revision_id,
        "graph_build",
        status="stop_requested",
        stage="stop_requested",
        stage_label="Stop Requested",
        message="Cancellation requested. Waiting for the current graph compute step to finish.",
        payload=_merge_job_payload(
            job_id,
            {
                "phase": "stop_requested",
                "phaseLabel": "Stop Requested",
                "taskId": task_id,
                "stopRequestedAt": now_iso(),
            },
        ),
    )


def fail_graph_build_job(
    revision_id: str,
    *,
    job_id: str | None = None,
    method_config: dict[str, Any] | None,
    max_nodes: int,
    source_revision_id: str | None,
    cluster_id: str | None,
    error: Exception | str,
    error_source: str,
    retryable: bool,
    task_id: str | None = None,
) -> dict[str, Any]:
    error_text = str(error)
    normalized_cluster_id = str(cluster_id or "").strip() or None
    normalized_max_nodes = normalize_graph_limit(max_nodes)
    resolved_job_id = str(job_id or "").strip() or graph_job_id(revision_id, normalized_cluster_id)
    payload = _merge_job_payload(
        resolved_job_id,
        {
            "phase": "failed",
            "phaseLabel": "图构建失败",
            "revisionId": revision_id,
            "variant": graph_variant(normalized_cluster_id),
            "clusterId": normalized_cluster_id,
            "maxNodes": normalized_max_nodes,
            "distanceMetric": graph_distance_metric(method_config),
            "sourceRevisionId": source_revision_id,
            "taskId": str(task_id or "").strip() or None,
            "errorSource": error_source,
            "retryable": retryable,
            "failedAt": now_iso(),
        },
    )
    update_revision_graph_state(
        revision_id,
        graph_status="failed",
        error=error_text,
        cluster_id=normalized_cluster_id,
    )
    job_service.update_job(
        resolved_job_id,
        revision_id,
        "graph_build",
        status="failed",
        stage="failed",
        stage_label="图构建失败",
        message=f"构建失败: {error_text}",
        error=error_text,
        payload=payload,
        result={"errorSource": error_source, "retryable": retryable},
        finished_at=now_iso(),
    )
    return {
        "active": False,
        "phase": "failed",
        "phaseLabel": "图构建失败",
        "message": f"构建失败: {error_text}",
        "error": error_text,
        "errorSource": error_source,
        "retryable": retryable,
        "variant": graph_variant(normalized_cluster_id),
    }


def execute_graph_build_job(
    revision_id: str,
    *,
    job_id: str | None = None,
    method_config: dict[str, Any] | None,
    max_nodes: int,
    source_revision_id: str | None,
    cluster_id: str | None,
    task_id: str | None = None,
) -> dict[str, Any]:
    normalized_cluster_id = str(cluster_id or "").strip() or None
    normalized_max_nodes = normalize_graph_limit(max_nodes)
    variant = graph_variant(normalized_cluster_id)
    resolved_job_id = str(job_id or "").strip() or graph_job_id(revision_id, normalized_cluster_id)
    task_token = str(task_id or "").strip() or None
    current_job = get_job(resolved_job_id)
    if not _task_matches(current_job, task_token):
        return {"ok": True, "ignored": True, "reason": "stale_task", "jobId": resolved_job_id}
    current_status = str(current_job.get("status") or "").strip().lower() if isinstance(current_job, dict) else ""
    if current_status in {"stop_requested", "cancelled"}:
        return complete_graph_build_cancellation(
            revision_id,
            job_id=resolved_job_id,
            cluster_id=normalized_cluster_id,
            task_id=task_token,
            message="Graph build cancelled before execution.",
        )

    revision_dir = workspace_service.get_revision_dir(revision_id)
    if revision_dir is None:
        return fail_graph_build_job(
            revision_id,
            job_id=resolved_job_id,
            method_config=method_config,
            max_nodes=normalized_max_nodes,
            source_revision_id=source_revision_id,
            cluster_id=normalized_cluster_id,
            error="未找到对应 revision 目录。",
            error_source="graph_input",
            retryable=False,
            task_id=task_token,
        )

    started_at = time.perf_counter()
    job_service.update_job(
        resolved_job_id,
        revision_id,
        "graph_build",
        status="running",
        stage="building",
        stage_label="构建 NBN 图",
        message="graph worker 正在计算图结构",
        payload=_merge_job_payload(
            resolved_job_id,
            {
                "phase": "building",
                "phaseLabel": "构建 NBN 图",
                "revisionId": revision_id,
                "variant": variant,
                "clusterId": normalized_cluster_id,
                "maxNodes": normalized_max_nodes,
                "distanceMetric": graph_distance_metric(method_config),
                "sourceRevisionId": source_revision_id,
                "taskId": task_token,
                "executor": "celery_worker",
                "startedByWorkerAt": now_iso(),
            },
        ),
    )

    stage_ranges: dict[str, tuple[float, float]] = {
        "prepare_samples": (5.0, 10.0),
        "loading_model": (10.0, 15.0),
        "cache_lookup": (15.0, 25.0),
        "embedding": (25.0, 65.0),
        "distance_matrix": (65.0, 78.0),
        "nbn_compute": (78.0, 92.0),
        "parse_outputs": (92.0, 98.0),
        "persist_artifact": (98.0, 99.0),
        "completed": (99.0, 99.0),
    }

    def report_progress(event: dict[str, Any]) -> None:
        _raise_if_graph_build_cancelled(
            revision_id,
            job_id=resolved_job_id,
            cluster_id=normalized_cluster_id,
            task_id=task_token,
            message="Graph build cancelled during processing.",
        )
        stage = str(event.get("stage", "") or "building").strip() or "building"
        stage_label = str(event.get("stageLabel", "") or stage).strip() or stage
        current = event.get("current")
        total = event.get("total")
        message = str(event.get("message", "") or stage_label).strip() or stage_label

        percent: float | None = None
        stage_range = stage_ranges.get(stage)
        if stage_range is not None:
            start_percent, end_percent = stage_range
            if isinstance(current, (int, float)) and isinstance(total, (int, float)) and float(total) > 0:
                ratio = min(max(float(current) / float(total), 0.0), 1.0)
                percent = start_percent + (end_percent - start_percent) * ratio
            else:
                percent = start_percent

        logger.info(
            "graph build progress revision=%s stage=%s current=%s total=%s percent=%s message=%s",
            revision_id,
            stage,
            current,
            total,
            percent,
            message,
        )
        job_service.update_job(
            resolved_job_id,
            revision_id,
            "graph_build",
            status="running",
            stage=stage,
            stage_label=stage_label,
            current=int(current) if isinstance(current, (int, float)) else None,
            total=int(total) if isinstance(total, (int, float)) else None,
            percent=percent,
            message=message,
            payload=_merge_job_payload(
                resolved_job_id,
                {
                    "phase": "building",
                    "phaseLabel": stage_label,
                    "taskId": task_token,
                    "progressStage": stage,
                    "progressMessage": message,
                },
            ),
        )

    try:
        _raise_if_graph_build_cancelled(
            revision_id,
            job_id=resolved_job_id,
            cluster_id=normalized_cluster_id,
            task_id=task_token,
            message="Graph build cancelled before execution.",
        )
        graph = _persist_graph_artifact(
            revision_dir,
            job_id=resolved_job_id,
            method_config=method_config,
            max_nodes=normalized_max_nodes,
            source_revision_id=source_revision_id,
            cluster_id=normalized_cluster_id,
            progress_callback=report_progress,
        )
        build_duration_ms = (time.perf_counter() - started_at) * 1000.0
        graph_build_rollup = record_perf_stat("graphBuildMs", build_duration_ms)
        current_job = get_job(resolved_job_id)
        if not _task_matches(current_job, task_token):
            return {"ok": True, "ignored": True, "reason": "stale_task", "jobId": resolved_job_id}
        _raise_if_graph_build_cancelled(
            revision_id,
            job_id=resolved_job_id,
            cluster_id=normalized_cluster_id,
            task_id=task_token,
            message="Graph build cancelled after computation completed.",
        )
        job_service.update_job(
            resolved_job_id,
            revision_id,
            "graph_build",
            status="succeeded",
            stage="completed",
            stage_label="图构建完成",
            current=100,
            total=100,
            percent=100.0,
            message="NBN 图已由 graph worker 生成",
            payload=_merge_job_payload(
                resolved_job_id,
                {
                    "phase": "ready",
                    "phaseLabel": "图构建完成",
                    "taskId": task_token,
                    "retryable": False,
                    "finishedAt": now_iso(),
                },
            ),
            result={
                "graphStatus": graph.get("graphStatus"),
                "sampleRevision": graph.get("sampleRevision"),
                "rolling": {"graphBuildMs": graph_build_rollup},
                "executor": "celery_worker",
            },
            finished_at=now_iso(),
        )
        return {
            "ok": True,
            "jobId": resolved_job_id,
            "revisionId": revision_id,
            "graphStatus": graph.get("graphStatus"),
            "variant": variant,
        }
    except GraphBuildCancelled as error:
        return complete_graph_build_cancellation(
            revision_id,
            job_id=resolved_job_id,
            cluster_id=normalized_cluster_id,
            task_id=task_token,
            message=str(error),
        )
    except Exception as error:  # pragma: no cover
        error_source, retryable = _classify_graph_error(error)
        return fail_graph_build_job(
            revision_id,
            job_id=resolved_job_id,
            method_config=method_config,
            max_nodes=normalized_max_nodes,
            source_revision_id=source_revision_id,
            cluster_id=normalized_cluster_id,
            error=error,
            error_source=error_source,
            retryable=retryable,
            task_id=task_token,
        )
