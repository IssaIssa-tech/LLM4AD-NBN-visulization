from __future__ import annotations

from datetime import datetime
from pathlib import Path
from typing import Any

from visual_platform.services import revision_generation_service


def write_real_run_meta(log_dir: Path, payload: dict[str, Any]) -> None:
    revision_generation_service.write_run_meta(log_dir, payload)


def read_real_run_meta(log_dir: Path) -> dict[str, Any]:
    return revision_generation_service.read_run_meta(log_dir)


def merge_real_run_meta(log_dir: Path, payload: dict[str, Any]) -> dict[str, Any]:
    return revision_generation_service.merge_run_meta(log_dir, payload)


def recent_records(records: Any, limit: int = 24) -> list[dict[str, Any]]:
    if not isinstance(records, list):
        return []
    normalized = [item for item in records if isinstance(item, dict)]
    return normalized[-limit:]


def record_run_timing(
    log_dir: Path,
    metric_name: str,
    elapsed_ms: float,
    *,
    extra: dict[str, Any] | None = None,
) -> dict[str, Any]:
    meta = read_real_run_meta(log_dir)
    timings = meta.get("timings", {})
    if not isinstance(timings, dict):
        timings = {}

    metric = timings.get(metric_name, {})
    if not isinstance(metric, dict):
        metric = {}

    count = int(metric.get("count", 0) or 0) + 1
    total_ms = float(metric.get("totalMs", 0.0) or 0.0) + float(elapsed_ms)
    record = {"ms": round(float(elapsed_ms), 3), **(extra or {})}
    records = recent_records(metric.get("recent"))
    records.append(record)

    metric.update(
        {
            "count": count,
            "totalMs": round(total_ms, 3),
            "avgMs": round(total_ms / count, 3),
            "maxMs": round(max(float(metric.get("maxMs", 0.0) or 0.0), float(elapsed_ms)), 3),
            "lastMs": round(float(elapsed_ms), 3),
            "recent": records[-24:],
        }
    )
    timings[metric_name] = metric
    meta["timings"] = timings
    meta["updatedAt"] = datetime.now().isoformat(timespec="seconds")
    write_real_run_meta(log_dir, meta)
    return metric


def update_run_progress(log_dir: Path, **payload: Any) -> dict[str, Any]:
    return revision_generation_service.update_run_progress(log_dir, **payload)


def has_generated_samples(log_dir: Path) -> bool:
    return revision_generation_service.has_generated_samples(log_dir)
