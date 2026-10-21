from __future__ import annotations

import json
import logging
from datetime import datetime
from pathlib import Path
from typing import Any
import uuid
import zipfile

from visual_platform.repositories import insert_individuals_bulk

logger = logging.getLogger(__name__)


BASE_DIR = Path(__file__).resolve().parent.parent  # visual_platform/（本级是 importer/）

HISTORY_SAMPLE_SOURCES: dict[str, dict[str, Any]] = {
    "circle_packing_history": {
        "label": "Circle Packing 历史样本",
        "archive_path": BASE_DIR.parent / "example" / "tasks" / "circle_packing" / "EoH_settings_logs" / "EoH_sample_history.zip",
        "entry_root": "samples",
    }
}


def history_import_job_id(revision_id: str) -> str:
    return f"history-import:{revision_id}"


def resolve_history_source(source_key: str) -> dict[str, Any]:
    normalized_source_key = str(source_key or "").strip()
    source = HISTORY_SAMPLE_SOURCES.get(normalized_source_key)
    if source is None:
        available = ", ".join(sorted(HISTORY_SAMPLE_SOURCES))
        raise ValueError(f"Unknown history source '{normalized_source_key}'. Available sources: {available}")

    archive_path = Path(source["archive_path"])
    return {
        "key": normalized_source_key,
        "label": str(source.get("label", normalized_source_key)),
        "archive_path": archive_path,
        "entry_root": str(source.get("entry_root", "") or "").strip(),
        "path": str(archive_path),
    }


def _history_entry_sort_key(entry_name: str) -> tuple[int, str]:
    entry_path = Path(entry_name)
    stem = entry_path.stem
    prefix, _, range_part = stem.partition("_")
    if prefix != "samples" or "~" not in range_part:
        return (10**9, entry_name)
    start_text, _, _ = range_part.partition("~")
    if start_text.isdigit():
        return (int(start_text), entry_name)
    return (10**9, entry_name)


def _iter_history_archive_entries(source: dict[str, Any]) -> list[str]:
    archive_path = Path(source["archive_path"])
    entry_root = str(source.get("entry_root", "") or "").strip().strip("/\\")
    if not archive_path.exists():
        raise FileNotFoundError(f"History samples archive not found: {archive_path}")

    with zipfile.ZipFile(archive_path) as archive:
        entries = sorted(
            (
                entry_name
                for entry_name in archive.namelist()
                if Path(entry_name).parent.as_posix() == entry_root
                and Path(entry_name).suffix.lower() == ".json"
                and Path(entry_name).stem.partition("_")[0] == "samples"
                and "~" in Path(entry_name).stem.partition("_")[2]
            ),
            key=_history_entry_sort_key,
        )
    if not entries:
        raise FileNotFoundError(f"No declared history sample entries found in archive: {archive_path}")
    return entries


def list_history_sources() -> list[dict[str, str]]:
    items: list[dict[str, str]] = []
    for key in HISTORY_SAMPLE_SOURCES:
        source = resolve_history_source(key)
        items.append(
            {
                "key": source["key"],
                "label": source["label"],
                "path": source["path"],
            }
        )
    return items


def import_history_samples(source_key: str, target_log_dir: Path) -> dict[str, Any]:
    source = resolve_history_source(source_key)
    archive_path = Path(source["archive_path"])
    archive_entries = _iter_history_archive_entries(source)

    sample_count = 0
    imported_entries = 0
    skipped_entries: list[str] = []
    best_score: float | None = None
    best_sample_order: int | None = None
    revision_id = target_log_dir.parent.name
    
    all_individuals = []
    
    with zipfile.ZipFile(archive_path) as archive:
        for entry_name in archive_entries:
            imported_entries += 1
            try:
                raw_bytes = archive.read(entry_name)
                content = json.loads(raw_bytes.decode("utf-8"))
            except (KeyError, OSError, UnicodeDecodeError, json.JSONDecodeError) as parse_error:
                # 不要静默丢数据：损坏/截断的样本文件以前会被无声跳过，导入看起来成功，
                # 实际却少了一批样本。这里记录下来并告警，随返回值一起上报给前端。
                skipped_entries.append(entry_name)
                logger.warning("history import: 跳过无法解析的条目 %s（%s）", entry_name, parse_error)
                continue
            if not isinstance(content, list):
                skipped_entries.append(entry_name)
                logger.warning("history import: 跳过非数组条目 %s", entry_name)
                continue
            for item in content:
                if not isinstance(item, dict):
                    continue
                sample_count += 1
                item["revision_id"] = revision_id

                if "id" not in item:
                    item["id"] = f"history-{revision_id}-{uuid.uuid4().hex[:8]}"

                all_individuals.append(item)

                raw_score = item.get("score")
                if isinstance(raw_score, (int, float)):
                    score = float(raw_score)
                    if best_score is None or score > best_score:
                        best_score = score
                        sample_order = item.get("sample_order")
                        best_sample_order = int(sample_order) if isinstance(sample_order, int) else best_sample_order
    
    # insert all into db
    if all_individuals:
        insert_individuals_bulk(all_individuals)

    # Runtime state is written back through the database model; history import no longer
    # needs to materialize compatibility directories under the run tree.

    return {
        "sourceKey": source_key,
        "sourceLabel": source.get("label", source_key),
        "sourcePath": str(archive_path),
        "importedEntries": imported_entries,
        "sampleCount": sample_count,
        "skippedEntries": skipped_entries,
        "skippedEntryCount": len(skipped_entries),
        "bestScore": best_score,
        "bestSampleOrder": best_sample_order,
    }


def _write_json_file(path: Path, payload: dict[str, Any]) -> None:
    with path.open("w", encoding="utf-8") as handle:
        json.dump(payload, handle, indent=2, ensure_ascii=True)


def _merge_job_payload(job_id: str, updates: dict[str, Any]) -> dict[str, Any]:
    from visual_platform.repositories.job_repository import get_job

    job = get_job(job_id)
    payload = job.get("payload", {}) if isinstance(job, dict) else {}
    if not isinstance(payload, dict):
        payload = {}
    merged = dict(payload)
    merged.update(updates)
    return merged


def _task_matches(job_id: str, task_id: str | None) -> bool:
    from visual_platform.repositories.job_repository import get_job

    job = get_job(job_id)
    if not isinstance(job, dict):
        return True
    payload = job.get("payload", {})
    if not isinstance(payload, dict):
        payload = {}
    current_task_id = str(payload.get("taskId", "") or "").strip() or None
    normalized_task_id = str(task_id or "").strip() or None
    if current_task_id is None or normalized_task_id is None:
        return True
    return current_task_id == normalized_task_id


def execute_history_import_job(
    *,
    revision_id: str,
    source_key: str,
    source_revision_id: str | None,
    method_config: dict[str, Any] | None,
    task_id: str | None = None,
) -> dict[str, Any]:
    from visual_platform.config import DEFAULT_GRAPH_NODE_LIMIT
    from visual_platform.repositories.revision_repository import get_revision_record, upsert_revision
    from visual_platform.services import job_service, workspace_service
    from visual_platform.services.graph_service import ensure_graph_build_task

    normalized_method_config = method_config if isinstance(method_config, dict) else {}
    job_id = history_import_job_id(revision_id)
    task_token = str(task_id or "").strip() or None
    if not _task_matches(job_id, task_token):
        return {"ok": True, "ignored": True, "reason": "stale_task", "jobId": job_id}

    revision_dir = workspace_service.get_revision_dir(revision_id)
    if revision_dir is None:
        error_text = "未找到对应 revision 目录。"
        finished_at = datetime.now().isoformat(timespec="seconds")
        upsert_revision(
            revision_id,
            lifecycle_status="failed",
            graph_status="failed",
            error=error_text,
            finished_at=finished_at,
            latest_job_id=job_id,
        )
        job_service.update_job(
            job_id,
            revision_id,
            "history_import",
            status="failed",
            stage="failed",
            stage_label="历史样本导入失败",
            message=error_text,
            error=error_text,
            payload=_merge_job_payload(
                job_id,
                {
                    "phase": "failed",
                    "phaseLabel": "历史样本导入失败",
                    "taskId": task_token,
                    "failedAt": finished_at,
                },
            ),
            finished_at=finished_at,
        )
        return {"ok": False, "jobId": job_id, "revisionId": revision_id, "error": error_text}

    log_dir = revision_dir / "log"
    config_path = revision_dir / "config.json"
    revision = get_revision_record(revision_id)
    config = revision.get("config", {}) if isinstance(revision, dict) else {}
    if not isinstance(config, dict):
        config = {}

    source = resolve_history_source(source_key)
    running_payload = _merge_job_payload(
        job_id,
        {
            "phase": "loading",
            "phaseLabel": "导入历史样本中",
            "taskId": task_token,
            "executor": "celery_worker",
            "sourceKey": source["key"],
            "sourceLabel": source["label"],
            "sourcePath": source["path"],
            "sourceRevisionId": source_revision_id,
            "startedByWorkerAt": datetime.now().isoformat(timespec="seconds"),
        },
    )
    job_service.update_job(
        job_id,
        revision_id,
        "history_import",
        status="running",
        stage="loading",
        stage_label="导入历史样本中",
        current=0,
        total=None,
        percent=None,
        message="worker 正在读取 ZIP 并批量导入历史样本",
        payload=running_payload,
    )

    try:
        import_meta = import_history_samples(source_key, log_dir)
        finished_at = datetime.now().isoformat(timespec="seconds")
        sample_revision = int(import_meta.get("sampleCount", 0) or 0)
        config["historyImport"] = {
            **import_meta,
            "status": "completed",
            "finishedAt": finished_at,
        }
        _write_json_file(config_path, config)
        upsert_revision(
            revision_id,
            lifecycle_status="completed",
            graph_status="stale",
            config=config,
            error="",
            finished_at=finished_at,
            latest_job_id=job_id,
            sample_revision=sample_revision,
        )
        job_service.update_job(
            job_id,
            revision_id,
            "history_import",
            status="succeeded",
            stage="completed",
            stage_label="历史样本导入完成",
            current=sample_revision,
            total=sample_revision,
            percent=100.0,
            message=f"已导入 {sample_revision} 个历史样本",
            payload=_merge_job_payload(
                job_id,
                {
                    "phase": "completed",
                    "phaseLabel": "历史样本导入完成",
                    "taskId": task_token,
                    "finishedAt": finished_at,
                    **import_meta,
                },
            ),
            result=import_meta,
            finished_at=finished_at,
        )
        graph_task = ensure_graph_build_task(
            revision_dir,
            log_dir,
            method_config=normalized_method_config,
            max_nodes=DEFAULT_GRAPH_NODE_LIMIT,
            source_revision_id=source_revision_id,
            cluster_id=None,
        )
        return {
            "ok": True,
            "jobId": job_id,
            "revisionId": revision_id,
            "imported": import_meta,
            "graphBuild": graph_task,
        }
    except Exception as error:
        error_text = str(error)
        finished_at = datetime.now().isoformat(timespec="seconds")
        config["historyImport"] = {
            "sourceKey": source["key"],
            "sourceLabel": source["label"],
            "sourcePath": source["path"],
            "status": "failed",
            "error": error_text,
            "finishedAt": finished_at,
        }
        _write_json_file(config_path, config)
        upsert_revision(
            revision_id,
            lifecycle_status="failed",
            graph_status="failed",
            config=config,
            error=error_text,
            finished_at=finished_at,
            latest_job_id=job_id,
        )
        job_service.update_job(
            job_id,
            revision_id,
            "history_import",
            status="failed",
            stage="failed",
            stage_label="历史样本导入失败",
            message=error_text,
            error=error_text,
            payload=_merge_job_payload(
                job_id,
                {
                    "phase": "failed",
                    "phaseLabel": "历史样本导入失败",
                    "taskId": task_token,
                    "finishedAt": finished_at,
                    "errorSource": "history_import_worker",
                    "sourceKey": source["key"],
                    "sourceLabel": source["label"],
                    "sourcePath": source["path"],
                },
            ),
            result={"errorSource": "history_import_worker"},
            finished_at=finished_at,
        )
        return {
            "ok": False,
            "jobId": job_id,
            "revisionId": revision_id,
            "error": error_text,
        }
