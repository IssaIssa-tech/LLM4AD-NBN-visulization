from __future__ import annotations

import json
import os
from datetime import datetime
from pathlib import Path
from typing import Any

from visual_platform.config import DEFAULT_GRAPH_NODE_LIMIT
from visual_platform.repositories import get_graph_artifact, get_sample_revision, list_jobs_for_revision
from visual_platform.runtime.graph_executor import (
    GRAPH_ACTIVE_STATUSES,
    GRAPH_BUILD_TASK_NAME,
    complete_graph_build_cancellation,
    fail_graph_build_job,
    graph_distance_metric,
    graph_input_summary,
    graph_job_id,
    graph_variant,
    now_iso,
    normalize_graph_limit,
    perf_stat_summary,
    update_revision_graph_state,
)
from visual_platform.services import job_service


def _artifact_to_response(
    artifact_record: dict[str, Any],
    *,
    normalized_max_nodes: int,
    cluster_id: str | None,
    graph_status: str,
) -> dict[str, Any]:
    metadata = artifact_record.get("metadata", {})
    if not isinstance(metadata, dict):
        metadata = {}
    summary = artifact_record.get("summary", {})
    if isinstance(summary, dict) and isinstance(summary.get("graph"), dict):
        graph = dict(summary["graph"])
    else:
        # The graph data is stored in a file (storage_uri / path) rather
        # than inline in the metadata to keep the database small.
        graph = _load_graph_from_artifact_file(artifact_record)
    graph["graphNodeLimit"] = normalized_max_nodes
    graph["graphCachedAt"] = summary.get("savedAt")
    graph["expandedClusterId"] = str(cluster_id or "").strip() or None
    graph["graphStatus"] = graph_status
    graph["graphBuildPhase"] = "ready" if graph_status == "ready" else "failed"
    graph["artifactId"] = artifact_record.get("artifact_id")
    graph["artifactInputDigest"] = artifact_record.get("input_digest")
    graph["artifactType"] = artifact_record.get("artifact_type")
    graph["artifactRole"] = artifact_record.get("artifact_role")
    graph["artifactMetadata"] = metadata
    return graph


def _load_graph_from_artifact_file(artifact_record: dict[str, Any]) -> dict[str, Any]:
    """Load graph data from the file referenced by the artifact's storage_uri."""
    empty_graph = {
        "nodes": [],
        "edges": [],
        "truncated": False,
        "graphSource": "empty",
    }
    storage_uri = str(artifact_record.get("storage_uri") or artifact_record.get("path") or "").strip()
    if not storage_uri:
        return empty_graph
    file_path = Path(storage_uri)
    if not file_path.is_absolute():
        from visual_platform.config import BASE_DIR
        file_path = BASE_DIR / storage_uri
    if not file_path.is_file():
        return empty_graph
    try:
        data = json.loads(file_path.read_text(encoding="utf-8"))
        if isinstance(data, dict):
            return data
    except Exception:
        pass
    return empty_graph


# 构图任务的心跳：每次进度更新都会刷新 jobs.updated_at
# （job_repository.upsert_job 里 `updated_at = excluded.updated_at`）。
# 超过这个时长没有任何更新，就认为执行它的 worker 已经不在了。
# 注意：库里的时间戳是**本地无时区**的 ISO 串（datetime.now().isoformat()），
# 比较时必须用同样口径的 datetime.now()。
STALE_JOB_SECONDS = max(60, int(os.environ.get("VISUAL_PLATFORM_STALE_JOB_SECONDS", "600") or "600"))


def _heartbeat_age_seconds(job: dict[str, Any]) -> float | None:
    """距上次进度更新的秒数；取不到时间戳时返回 None（不判定为僵死）。"""
    for key in ("updated_at", "started_at", "created_at"):
        raw = str(job.get(key) or "").strip()
        if not raw:
            continue
        try:
            ts = datetime.fromisoformat(raw)
        except ValueError:
            continue
        return (datetime.now() - ts).total_seconds()
    return None


def _mark_stale_graph_job(job: dict[str, Any], *, revision_id: str, age_seconds: float) -> None:
    """把心跳停止的构图任务标记为失败，从而允许重新提交。"""
    from visual_platform.services.job_service import update_job

    minutes = int(age_seconds // 60)
    message = (
        f"构图任务已中断：{minutes} 分钟没有任何进度更新，"
        "执行它的 worker 可能已退出。已自动标记失败，可重新提交构图。"
    )
    update_job(
        str(job.get("job_id") or ""),
        revision_id,
        "graph_build",
        status="failed",
        stage="failed",
        stage_label="构图任务中断",
        message=message,
        error=message,
        finished_at=now_iso(),
    )


def _job_to_state(job: dict[str, Any] | None) -> dict[str, Any] | None:
    if not isinstance(job, dict):
        return None
    payload = job.get("payload", {})
    if not isinstance(payload, dict):
        payload = {}
    status = str(job.get("status", "") or "").strip().lower()
    phase = str(payload.get("phase", "") or job.get("stage", "") or "").strip()
    if not phase:
        phase = "failed" if status == "failed" else "ready" if status == "succeeded" else "queued"
    return {
        "jobId": job.get("job_id"),
        "active": status in GRAPH_ACTIVE_STATUSES,
        "phase": phase,
        "phaseLabel": payload.get("phaseLabel") or job.get("stage_label"),
        "message": job.get("message"),
        "error": job.get("error"),
        "errorSource": payload.get("errorSource"),
        "retryable": payload.get("retryable"),
        "variant": payload.get("variant"),
        "taskId": payload.get("taskId"),
    }


def _matches_graph_variant(job: dict[str, Any], *, cluster_id: str | None) -> bool:
    if str(job.get("job_type") or "").strip() != "graph_build":
        return False
    payload = job.get("payload", {})
    if not isinstance(payload, dict):
        payload = {}
    job_cluster_id = str(payload.get("clusterId", "") or "").strip() or None
    job_variant = str(payload.get("variant", "") or "").strip() or graph_variant(job_cluster_id)
    return job_variant == graph_variant(cluster_id)


def _latest_graph_job(revision_id: str, *, cluster_id: str | None, active_only: bool = False) -> dict[str, Any] | None:
    for job in list_jobs_for_revision(revision_id):
        if not _matches_graph_variant(job, cluster_id=cluster_id):
            continue
        if active_only and str(job.get("status") or "").strip().lower() not in GRAPH_ACTIVE_STATUSES:
            continue
        return job
    return None


def _queued_graph_payload(
    revision_id: str,
    *,
    method_config: dict[str, Any] | None,
    normalized_max_nodes: int,
    source_revision_id: str | None,
    normalized_cluster_id: str | None,
) -> dict[str, Any]:
    variant = graph_variant(normalized_cluster_id)
    return {
        "phase": "queued",
        "phaseLabel": "等待 graph worker 启动",
        "submittedAt": now_iso(),
        "revisionId": revision_id,
        "variant": variant,
        "clusterId": normalized_cluster_id,
        "maxNodes": normalized_max_nodes,
        "distanceMetric": graph_distance_metric(method_config),
        "sourceRevisionId": source_revision_id,
        "inputSummary": graph_input_summary(
            revision_id,
            distance_metric=graph_distance_metric(method_config),
            max_nodes=normalized_max_nodes,
            variant=variant,
            sample_revision=int(get_sample_revision(revision_id)),
            source_revision_id=source_revision_id,
            cluster_id=normalized_cluster_id,
        ),
        "executor": "celery_worker",
        "retryable": True,
    }


def ensure_graph_build_task(
    revision_dir: Path,
    log_dir: Path,
    *,
    method_config: dict[str, Any] | None = None,
    max_nodes: int = DEFAULT_GRAPH_NODE_LIMIT,
    source_revision_id: str | None = None,
    cluster_id: str | None = None,
) -> dict[str, Any]:
    del log_dir
    revision_id = revision_dir.name
    normalized_cluster_id = str(cluster_id or "").strip() or None
    normalized_max_nodes = normalize_graph_limit(max_nodes)
    variant = graph_variant(normalized_cluster_id)

    latest_active_job = _latest_graph_job(revision_id, cluster_id=normalized_cluster_id, active_only=True)
    if latest_active_job is not None:
        latest_status = str(latest_active_job.get("status") or "").strip().lower()
        if latest_status == "stop_requested":
            # The previous build was interrupted but cancellation was never
            # finalised (e.g. the process was killed).  Complete the
            # cancellation now so a fresh job can be submitted.
            latest_payload = latest_active_job.get("payload") if isinstance(latest_active_job.get("payload"), dict) else {}
            complete_graph_build_cancellation(
                revision_id,
                job_id=str(latest_active_job.get("job_id") or ""),
                cluster_id=normalized_cluster_id,
                task_id=str(latest_payload.get("taskId") or "").strip() or None,
                message="Stale stop_request finalised on resubmission.",
            )
        else:
            current_state = _job_to_state(latest_active_job)
            if current_state and current_state.get("active"):
                age = _heartbeat_age_seconds(latest_active_job)
                if age is not None and age > STALE_JOB_SECONDS:
                    # 心跳停了：执行它的 worker 已经不在了（被 kill / OOM / 重启）。
                    # 标记失败后继续往下走，本次提交会生成一个新任务；否则该任务会
                    # 永远停在 running，前端一直"加载中"，重新提交也只会拿回旧状态。
                    _mark_stale_graph_job(latest_active_job, revision_id=revision_id, age_seconds=age)
                else:
                    return current_state

    update_revision_graph_state(revision_id, graph_status="building", cluster_id=normalized_cluster_id)
    queued_payload = _queued_graph_payload(
        revision_id,
        method_config=method_config,
        normalized_max_nodes=normalized_max_nodes,
        source_revision_id=source_revision_id,
        normalized_cluster_id=normalized_cluster_id,
    )
    job_id = graph_job_id(revision_id, normalized_cluster_id)
    job_service.update_job(
        job_id,
        revision_id,
        "graph_build",
        status="queued",
        stage="queued",
        stage_label="等待 graph worker 启动",
        message="图构建任务已提交，等待 graph worker 接手",
        payload=queued_payload,
        started_at=queued_payload.get("submittedAt"),
    )

    try:
        from visual_platform.celery_worker import celery_app

        async_result = celery_app.send_task(
            GRAPH_BUILD_TASK_NAME,
            kwargs={
                "job_id": job_id,
                "revision_id": revision_id,
                "method_config": method_config or {},
                "max_nodes": normalized_max_nodes,
                "source_revision_id": source_revision_id,
                "cluster_id": normalized_cluster_id,
            },
        )
    except Exception as error:
        return fail_graph_build_job(
            revision_id,
            job_id=job_id,
            method_config=method_config,
            max_nodes=normalized_max_nodes,
            source_revision_id=source_revision_id,
            cluster_id=normalized_cluster_id,
            error=error,
            error_source="graph_worker_submit",
            retryable=True,
        )

    payload = dict(queued_payload)
    payload["taskId"] = async_result.id
    job_service.update_job(
        job_id,
        revision_id,
        "graph_build",
        status="queued",
        stage="queued",
        stage_label="已提交到 graph worker",
        message="图构建任务已提交到 graph worker",
        payload=payload,
    )
    return {
        "jobId": job_id,
        "active": True,
        "phase": "queued",
        "phaseLabel": "已提交到 graph worker",
        "message": "图构建任务已提交到 graph worker",
        "variant": variant,
        "taskId": async_result.id,
    }


def get_graph_data(
    revision_dir: Path,
    log_dir: Path,
    *,
    method_config: dict[str, Any] | None = None,
    max_nodes: int = DEFAULT_GRAPH_NODE_LIMIT,
    source_revision_id: str | None = None,
    cluster_id: str | None = None,
    allow_async_build: bool = False,
) -> dict[str, Any]:
    del log_dir
    revision_id = revision_dir.name
    normalized_max_nodes = normalize_graph_limit(max_nodes)
    normalized_cluster_id = str(cluster_id or "").strip() or None
    variant = graph_variant(normalized_cluster_id)
    current_sample_revision = int(get_sample_revision(revision_id))
    distance_metric = graph_distance_metric(method_config)
    artifact_record = get_graph_artifact(
        revision_id,
        variant=variant,
        metric=distance_metric,
        max_nodes=normalized_max_nodes,
        sample_revision=current_sample_revision,
        source_revision_id=source_revision_id,
    )

    if isinstance(artifact_record, dict):
        record_status = str(artifact_record.get("status", "") or "").strip().lower()
        if record_status in {"ready", "failed"}:
            return _artifact_to_response(
                artifact_record,
                normalized_max_nodes=normalized_max_nodes,
                cluster_id=normalized_cluster_id,
                graph_status=record_status,
            )

    job_state = _job_to_state(_latest_graph_job(revision_id, cluster_id=normalized_cluster_id, active_only=True))
    if job_state and job_state.get("active"):
        return {
            "nodes": [],
            "edges": [],
            "truncated": False,
            "graphSource": "empty",
            "graphNodeLimit": normalized_max_nodes,
            "expandedClusterId": normalized_cluster_id,
            "graphStatus": "building",
            "graphBuildPhase": job_state.get("phase", "queued"),
            "sampleRevision": current_sample_revision,
            "error": job_state.get("error"),
            "errorSource": job_state.get("errorSource"),
            "retryable": job_state.get("retryable"),
        }

    if allow_async_build:
        task = ensure_graph_build_task(
            revision_dir,
            revision_dir / "log",
            method_config=method_config,
            max_nodes=normalized_max_nodes,
            source_revision_id=source_revision_id,
            cluster_id=normalized_cluster_id,
        )
        graph_status = "building" if task.get("active") else "failed" if task.get("phase") == "failed" else "stale"
        return {
            "nodes": [],
            "edges": [],
            "truncated": False,
            "graphSource": "empty",
            "graphNodeLimit": normalized_max_nodes,
            "expandedClusterId": normalized_cluster_id,
            "graphStatus": graph_status,
            "graphBuildPhase": task.get("phase", "queued"),
            "sampleRevision": current_sample_revision,
            "error": task.get("error"),
            "errorSource": task.get("errorSource"),
            "retryable": task.get("retryable"),
        }

    return {
        "nodes": [],
        "edges": [],
        "truncated": False,
        "graphSource": "empty",
        "graphNodeLimit": normalized_max_nodes,
        "expandedClusterId": normalized_cluster_id,
        "graphStatus": "stale",
        "graphBuildPhase": "stale",
        "sampleRevision": current_sample_revision,
        "error": None,
    }
