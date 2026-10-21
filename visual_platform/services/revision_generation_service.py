from __future__ import annotations

from datetime import datetime
from pathlib import Path
from typing import Any

from visual_platform.config import DEFAULT_GRAPH_NODE_LIMIT
from visual_platform.repositories import get_revision_record, upsert_revision
from visual_platform.repositories.individual_repository import get_revision_metrics
from visual_platform.services import job_service

# Drop this marker file to pause the automatic graph build after each run
# (e.g. during batch experiments where full rebuilds only cause SQLite lock
# contention). Delete the file to restore the default behaviour.
AUTO_GRAPH_BUILD_OFF_MARKER = Path(__file__).resolve().parent.parent / ".local" / "AUTO_GRAPH_BUILD_OFF"


def revision_generation_job_id(revision_id: str) -> str:
    return f"revision-generation:{revision_id}"


def read_run_meta(log_dir: Path) -> dict[str, Any]:
    revision_id = log_dir.parent.name
    row = get_revision_record(revision_id)
    if row is None:
        return {}
    config = row.get("config", {})
    return dict(config) if isinstance(config, dict) else {}


def write_run_meta(log_dir: Path, payload: dict[str, Any]) -> None:
    revision_id = log_dir.parent.name
    progress = payload.get("progress", {})
    config = {key: value for key, value in payload.items() if key != "progress"}
    phase = str(progress.get("phase", "") or "").strip().lower() if isinstance(progress, dict) else ""
    lifecycle_status = "running"
    if phase in {"finished", "completed"}:
        lifecycle_status = "completed"
    elif phase in {"failed", "error"}:
        lifecycle_status = "failed"
    elif phase in {"stopped", "cancelled"}:
        lifecycle_status = "stopped"
    upsert_revision(
        revision_id,
        config=config,
        lifecycle_status=lifecycle_status,
        graph_status=(
            "stale"
            if lifecycle_status == "completed"
            else str(config.get("graph_status", "") or "").strip() or None
        ),
        error=str(progress.get("error", "") or config.get("error", "") or "").strip() or None,
        started_at=str(config.get("started_at", "") or "").strip() or None,
        finished_at=str(config.get("finishedAt", "") or "").strip() or None,
    )


def merge_run_meta(log_dir: Path, payload: dict[str, Any]) -> dict[str, Any]:
    meta = read_run_meta(log_dir)
    meta.update(payload)
    meta["updatedAt"] = datetime.now().isoformat(timespec="seconds")
    write_run_meta(log_dir, meta)
    return meta


def _effective_sample_budget(method: dict[str, Any], meta: dict[str, Any]) -> int | None:
    """Mirror the sample budget the runner actually uses for seeded EoH.

    ``run_seeded_eoh_mode`` overrides the configured ``max_sample_nums`` with
    ``max(max_sample_nums, pop_size * max_generations)`` and also bumps
    ``pop_size`` up to the seed count when more seeds are supplied than the
    configured population size. The raw config value alone underestimates the
    denominator, which made the progress bar overshoot 100% (e.g. 200%)."""
    def _as_int(value: Any) -> int:
        return int(value or 0) if isinstance(value, (int, float)) else 0

    budget = _as_int(method.get("max_sample_nums"))
    pop_size = _as_int(method.get("pop_size"))
    seeds = meta.get("initial_population_nodes")
    if isinstance(seeds, list):
        pop_size = max(pop_size, len(seeds))
    derived = pop_size * _as_int(method.get("max_generations"))
    budget = max(budget, derived)
    return budget if budget > 0 else None


def _progress_counters(
    method: dict[str, Any], progress: dict[str, Any], meta: dict[str, Any] | None = None
) -> tuple[int | None, int | None]:
    current: int | None = None
    total: int | None = None
    if isinstance(progress.get("sampleCount"), (int, float)):
        current = int(progress.get("sampleCount") or 0)
        total = _effective_sample_budget(method, meta or {})
    elif isinstance(progress.get("currentGeneration"), (int, float)):
        current = int(progress.get("currentGeneration") or 0)
        if isinstance(method.get("max_generations"), (int, float)):
            total = int(method.get("max_generations") or 0)
    return current, total


def update_run_progress(log_dir: Path, **payload: Any) -> dict[str, Any]:
    meta = read_run_meta(log_dir)
    progress: dict[str, Any] = dict(payload)
    progress["updatedAt"] = datetime.now().isoformat(timespec="seconds")
    meta["updatedAt"] = progress["updatedAt"]
    write_run_meta(log_dir, meta)

    revision_id = log_dir.parent.name
    method = meta.get("method", {})
    if not isinstance(method, dict):
        method = {}
    phase = str(progress.get("phase", "") or "").strip().lower() or None
    phase_label = str(progress.get("phaseLabel", "") or "").strip() or None
    status = "running"
    if phase in {"boot", "queued"}:
        status = "queued"
    elif phase in {"finished", "completed"}:
        status = "succeeded"
    elif phase in {"failed", "error"}:
        status = "failed"
    elif phase in {"stopped", "cancelled"}:
        status = "cancelled"

    current, total = _progress_counters(method, progress, meta)
    percent = None
    if isinstance(current, int) and isinstance(total, int) and total > 0:
        percent = round((current / total) * 100.0, 3)

    job_id = revision_generation_job_id(revision_id)
    job_service.upsert_job(
        job_id,
        revision_id,
        "revision_generation",
        status=status,
        stage=phase,
        stage_label=phase_label,
        current=current,
        total=total,
        percent=percent,
        message=str(progress.get("message", "") or phase_label or "").strip() or None,
        error=str(progress.get("error", "") or "").strip() or None,
        payload=progress,
        started_at=str(meta.get("started_at", "") or "").strip() or None,
        finished_at=str(progress.get("updatedAt", "") or "").strip() or None if status in {"succeeded", "failed", "cancelled"} else None,
    )

    update_kwargs: dict[str, Any] = {
        "lifecycle_status": "running",
        "latest_job_id": job_id,
    }
    if status == "failed":
        update_kwargs["lifecycle_status"] = "failed"
        update_kwargs["graph_status"] = "failed"
        update_kwargs["error"] = str(progress.get("error", "") or "").strip() or None
    elif status == "succeeded":
        update_kwargs["lifecycle_status"] = "completed"
        update_kwargs["graph_status"] = "stale"
        update_kwargs["error"] = ""
    elif status == "cancelled":
        update_kwargs["lifecycle_status"] = "stopped"
    upsert_revision(revision_id, **update_kwargs)
    return progress


def has_generated_samples(log_dir: Path) -> bool:
    metrics = get_revision_metrics(log_dir.parent.name)
    return int(metrics.get("sample_count", 0) or 0) > 0


def complete_run(
    log_dir: Path,
    *,
    phase: str = "completed",
    phase_label: str = "运行完成",
    message: str | None = None,
    result: dict[str, Any] | None = None,
    trigger_graph_build: bool = True,
    max_nodes: int = DEFAULT_GRAPH_NODE_LIMIT,
) -> dict[str, Any]:
    revision_id = log_dir.parent.name
    finished_at = datetime.now().isoformat(timespec="seconds")
    meta = read_run_meta(log_dir)
    method = meta.get("method", {})
    if not isinstance(method, dict):
        method = {}
    metrics = get_revision_metrics(revision_id)
    sample_count = int(metrics.get("sample_count", 0) or 0)
    total = _effective_sample_budget(method, meta)
    payload = {
        "phase": phase,
        "phaseLabel": phase_label,
        "sampleCount": sample_count,
        "bestScore": metrics.get("best_score"),
        "bestSampleOrder": metrics.get("best_sample_order"),
        "finishedAt": finished_at,
    }
    if isinstance(result, dict):
        payload.update(result)

    job_id = revision_generation_job_id(revision_id)
    job_service.update_job(
        job_id,
        revision_id,
        "revision_generation",
        status="succeeded",
        stage=phase,
        stage_label=phase_label,
        current=sample_count,
        total=total or sample_count,
        percent=100.0,
        message=message or phase_label,
        payload=payload,
        result=result,
        started_at=str(meta.get("started_at", "") or "").strip() or None,
        finished_at=finished_at,
    )
    upsert_revision(
        revision_id,
        lifecycle_status="completed",
        graph_status="stale",
        error="",
        finished_at=finished_at,
        latest_job_id=job_id,
    )

    graph_state: dict[str, Any] | None = None
    if trigger_graph_build and AUTO_GRAPH_BUILD_OFF_MARKER.exists():
        trigger_graph_build = False
    if trigger_graph_build:
        from visual_platform.services.graph_service import ensure_graph_build_task

        graph_state = ensure_graph_build_task(
            log_dir.parent,
            log_dir,
            method_config=method,
            max_nodes=max_nodes,
            source_revision_id=str(meta.get("source_revision_id", "") or "").strip() or None,
            cluster_id=None,
        )
    return {
        "finishedAt": finished_at,
        "sampleCount": sample_count,
        "bestScore": metrics.get("best_score"),
        "graphBuild": graph_state,
    }


def fail_run(
    log_dir: Path,
    error: BaseException | str,
    *,
    phase: str = "failed",
    phase_label: str = "运行失败",
) -> dict[str, Any]:
    revision_id = log_dir.parent.name
    finished_at = datetime.now().isoformat(timespec="seconds")
    meta = read_run_meta(log_dir)
    metrics = get_revision_metrics(revision_id)
    error_text = str(error)
    job_id = revision_generation_job_id(revision_id)
    job_service.update_job(
        job_id,
        revision_id,
        "revision_generation",
        status="failed",
        stage=phase,
        stage_label=phase_label,
        current=int(metrics.get("sample_count", 0) or 0),
        total=None,
        percent=None,
        message=error_text,
        error=error_text,
        payload={
            "phase": phase,
            "phaseLabel": phase_label,
            "sampleCount": int(metrics.get("sample_count", 0) or 0),
            "finishedAt": finished_at,
        },
        started_at=str(meta.get("started_at", "") or "").strip() or None,
        finished_at=finished_at,
    )
    upsert_revision(
        revision_id,
        lifecycle_status="failed",
        graph_status="failed",
        error=error_text,
        finished_at=finished_at,
        latest_job_id=job_id,
    )
    return {"finishedAt": finished_at, "sampleCount": int(metrics.get("sample_count", 0) or 0)}
