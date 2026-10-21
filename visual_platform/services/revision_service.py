from __future__ import annotations

import json
import shutil
import uuid
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List, Optional

from visual_platform.config import RUNS_DIR
from visual_platform.runtime import revision_executor
from visual_platform.repositories.job_repository import (
    list_active_jobs_for_workspace,
    list_jobs_for_revision,
    upsert_job,
)
from visual_platform.services import workspace_service
from visual_platform.services.revision_generation_service import revision_generation_job_id
from visual_platform.repositories import individual_repository, revision_repository, workspace_repository
from visual_platform.importer.history import (
    history_import_job_id,
    resolve_history_source,
)
from visual_platform.llm.support import resolve_real_api_key_with_source

RUNTIME_MUTEX_JOB_TYPES = ("revision_generation", "history_import", "expert_import")

_ACTIVE_JOB_STATUSES = {"queued", "launch_requested", "running", "stop_requested"}


def _referenced_node_ids(*node_lists: Any) -> list[str]:
    """Flatten node id/objects from selected/reference/initial-population lists into
    a de-duplicated list of individual ids. Accepts both bare id strings and node
    dicts carrying an ``id`` field.
    """
    ids: list[str] = []
    seen: set[str] = set()
    for node_list in node_lists:
        if not isinstance(node_list, list):
            continue
        for node in node_list:
            node_id = str(node.get("id") or "").strip() if isinstance(node, dict) else str(node or "").strip()
            if node_id and node_id not in seen:
                seen.add(node_id)
                ids.append(node_id)
    return ids


def get_revision(revision_id: str) -> dict[str, Any] | None:
    return revision_repository.get_revision_record(revision_id)


def list_revisions_for_workspace(workspace_id: str) -> list[dict[str, Any]]:
    return revision_repository.list_revisions_for_workspace(workspace_id)


def delete_revision(revision_id: str, *, force: bool = False) -> tuple[dict[str, Any], int]:
    revision_id = str(revision_id or "").strip()
    if not revision_id:
        return {"ok": False, "error": "缺少 revisionId。"}, 400

    revision = revision_repository.get_revision_record(revision_id)
    if revision is None:
        return {"ok": False, "error": "未找到对应 revision。"}, 404

    # Refuse to delete while a job for this revision is still active, otherwise a
    # running runner/worker would keep writing rows for a revision we just removed.
    for job in list_jobs_for_revision(revision_id):
        if str(job.get("status") or "").strip().lower() in _ACTIVE_JOB_STATUSES:
            return {
                "ok": False,
                "error": "该 revision 仍有运行中的任务，请先停止或等待完成后再删除。",
            }, 409

    # Guard against silently destroying solutions. With the workspace-scoped
    # individual pool, deleting a revision only removes individuals that are unique
    # to it (not referenced by any surviving revision's graph). Count those and
    # require an explicit force flag so a routine cleanup can never wipe a solution
    # that exists only here (expert imports, one-off runs, etc.) by accident.
    if not force:
        unique_count = individual_repository.count_unique_individuals(revision_id)
        if unique_count > 0:
            return {
                "ok": False,
                "error": (
                    f"该版本独占 {unique_count} 个解（未被其它版本引用），删除后将永久丢失且无法恢复。"
                    "如果确认要删除，请再次确认（force=true）。"
                ),
                "uniqueCount": unique_count,
                "requiresForce": True,
            }, 409

    workspace_id = str(revision.get("workspace_id") or "").strip()

    # Best-effort removal of the on-disk run directory (config/logs/graph files)
    # before dropping DB rows. A missing directory is fine.
    revision_dir = RUNS_DIR / revision_id
    try:
        if revision_dir.exists():
            shutil.rmtree(revision_dir, ignore_errors=True)
    except Exception:
        pass

    deleted = revision_repository.delete_revision(revision_id)
    if not deleted:
        return {"ok": False, "error": "删除 revision 失败。"}, 500

    # Reference-counted GC: deleting the revision cascade-removed its membership rows.
    # Individuals still referenced by a surviving revision keep a membership row and
    # are preserved; only those with zero remaining references are removed.
    orphaned_removed = individual_repository.gc_orphan_individuals()

    # If the workspace was pointing at the deleted revision, repoint it at the
    # newest remaining revision (or clear it when none remain).
    next_selected_revision_id: str | None = None
    if workspace_id:
        workspace = workspace_repository.get_workspace(workspace_id)
        current_revision_id = str((workspace or {}).get("current_revision_id") or "").strip()
        if current_revision_id == revision_id or not current_revision_id:
            remaining = revision_repository.list_revisions_for_workspace(workspace_id)
            next_selected_revision_id = str(remaining[-1]["revision_id"]) if remaining else None
            workspace_repository.update_workspace(
                workspace_id,
                current_revision_id=next_selected_revision_id,
            )
        else:
            next_selected_revision_id = current_revision_id

    return {
        "ok": True,
        "revisionId": revision_id,
        "workspaceId": workspace_id or None,
        "selectedRevisionId": next_selected_revision_id,
        "removedSolutionCount": orphaned_removed,
    }, 200

def _preflight_llm_config(llm_payload: Any) -> tuple[dict[str, Any], str | None]:
    llm_config = dict(llm_payload) if isinstance(llm_payload, dict) else {}
    base_url = str(llm_config.get("host", "") or llm_config.get("base_url", "")).strip()
    model_name = str(llm_config.get("model", "")).strip()
    api_key, key_source = resolve_real_api_key_with_source(llm_config.get("key", ""))
    if not base_url:
        return llm_config, "未提供 API Base URL。请在左侧填写形如 https://api.openai.com/v1 的 OpenAI 兼容接口地址。"
    if not model_name:
        return llm_config, "未提供模型名称。请在左侧填写模型名，如 gpt-4o-mini、deepseek-chat、glm-4。"
    if not api_key:
        return llm_config, "未提供可用的 API Key。请在左侧填写 API Key，或在环境变量中设置 OPENAI_API_KEY / API_KEY。"
    llm_config["resolvedKeySource"] = key_source
    return llm_config, None

def _active_runtime_job_for_workspace(
    workspace_id: str,
    *,
    exclude_revision_id: str | None = None,
) -> dict[str, Any] | None:
    for job in list_active_jobs_for_workspace(
        workspace_id,
        job_types=RUNTIME_MUTEX_JOB_TYPES,
    ):
        job_revision_id = str(job.get("revision_id") or "").strip()
        if exclude_revision_id and job_revision_id == str(exclude_revision_id).strip():
            continue
        return job
    return None

def _flatten_source_lineage(source_revision_id: str | None) -> list[str]:
    """Return the full flattened ancestry of ``source_revision_id`` (inclusive).

    A seeded revision's graph is rebuilt by loading, for every revision in its
    ``merged_source_revision_ids`` snapshot, that revision's own individuals (see
    ``graph_sample_service.combined_graph_samples``). The source revision only *owns* the
    nodes it directly produced; the rest of its graph came from its own ancestors (recorded
    in the source's ``merged_source_revision_ids``). If we snapshot only the direct source,
    those deeper ancestors -- e.g. a large imported-history revision with thousands of
    nodes -- silently drop out and the merged graph collapses to "seed + newly generated"
    instead of "base graph + new nodes". Walking both the recorded snapshot and the
    ``source_revision_id`` chain here flattens the entire lineage, and also repairs partial
    snapshots written by older code that stored only the direct parent.
    """
    root = str(source_revision_id or "").strip()
    if not root:
        return []
    ordered: list[str] = []
    seen: set[str] = set()
    queue: list[str] = [root]
    while queue:
        current = queue.pop(0)
        if current in seen:
            continue
        seen.add(current)
        ordered.append(current)
        record = revision_repository.get_revision_record(current)
        config = record.get("config", {}) if isinstance(record, dict) else {}
        if not isinstance(config, dict):
            continue
        parent = str(config.get("source_revision_id", "") or "").strip()
        if parent and parent not in seen:
            queue.append(parent)
        snapshot = config.get("merged_source_revision_ids")
        if isinstance(snapshot, list):
            for candidate in snapshot:
                candidate_id = str(candidate or "").strip()
                if candidate_id and candidate_id not in seen:
                    queue.append(candidate_id)
    return ordered

def start_revision(payload: dict[str, Any]) -> tuple[dict[str, Any], int]:
    mode = str(payload.get("mode", "prompt_gen") or "prompt_gen").strip()
    if mode not in {"prompt_gen", "seeded_eoh", "region_search"}:
        return {"ok": False, "error": f"不支持的运行模式: {mode}"}, 400
    prompt = str(payload.get("prompt", "")).strip()
    region = payload.get("region", {})
    if not isinstance(region, dict):
        region = {}
    selected_nodes = payload.get("selected_nodes", [])
    if not isinstance(selected_nodes, list):
        selected_nodes = []
    reference_nodes = payload.get("reference_nodes", [])
    if not isinstance(reference_nodes, list):
        reference_nodes = []
    initial_population_nodes = payload.get("initial_population_nodes", [])
    if not isinstance(initial_population_nodes, list):
        initial_population_nodes = []
    if mode == "prompt_gen" and not reference_nodes:
        reference_nodes = selected_nodes
    if mode == "seeded_eoh" and not initial_population_nodes:
        initial_population_nodes = selected_nodes
    requested_workspace_id = str(payload.get("workspace_id", "") or "").strip()
    llm_config, llm_error = _preflight_llm_config(payload.get("llm", {}))
    if llm_error is not None:
        return {"ok": False, "error": llm_error}, 400

    if requested_workspace_id:
        workspace_service.activate_workspace(requested_workspace_id)

    active_workspace = workspace_service.get_active_workspace()
    if active_workspace is None:
        return {"ok": False, "error": "未找到对应工作台。"}, 404

    blocking_job = _active_runtime_job_for_workspace(active_workspace["workspace_id"])
    if blocking_job is not None:
        return {
            "ok": False,
            "error": "当前工作台已有运行中的版本任务，请先停止或等待完成后再启动新任务。",
        }, 409

    source_revision_id = str(active_workspace.get("current_revision_id", "") or "").strip() or None

    normalized_region: dict[str, Any] | None = None
    if mode == "region_search":
        from visual_platform.services.region_service import validate_region_spec

        normalized_region, region_error = validate_region_spec(region, source_revision_id)
        if region_error is not None:
            return {"ok": False, "error": region_error}, 400
        if normalized_region is None:
            return {"ok": False, "error": "区域定义无效。"}, 400

    # Snapshot of every revision that made up the graph the user evolved from. Recorded at
    # creation so the merged graph is reproducible even if intermediate revisions are later
    # deleted (walking the source_revision_id chain silently loses upstream nodes otherwise).
    raw_source_revision_ids = payload.get("source_revision_ids", [])
    if not isinstance(raw_source_revision_ids, list):
        raw_source_revision_ids = []
    merged_source_revision_ids: list[str] = []
    for candidate in raw_source_revision_ids:
        candidate_id = str(candidate or "").strip()
        if candidate_id and candidate_id not in merged_source_revision_ids:
            merged_source_revision_ids.append(candidate_id)
    # Inherit the source revision's *full* flattened ancestry (inclusive of the source
    # itself), so deep ancestors are not lost when the frontend sends only the direct
    # parent (or nothing). Without this the seeded graph collapses to seed + new nodes.
    for ancestor_id in _flatten_source_lineage(source_revision_id):
        if ancestor_id not in merged_source_revision_ids:
            merged_source_revision_ids.append(ancestor_id)

    revision_id = datetime.now().strftime("%Y%m%d_%H%M%S") + "_" + uuid.uuid4().hex[:8]
    revision_dir = RUNS_DIR / revision_id
    log_dir = revision_dir / "log"
    revision_dir.mkdir(parents=True, exist_ok=True)
    log_dir.mkdir(parents=True, exist_ok=True)

    started_at = datetime.now().isoformat(timespec="seconds")
    config = {
        "revision_id": revision_id,
        "started_at": started_at,
        "mode": mode,
        "prompt": prompt,
        "region": normalized_region if mode == "region_search" else None,
        "selected_nodes": selected_nodes,
        "reference_nodes": reference_nodes,
        "initial_population_nodes": initial_population_nodes,
        "workspace_id": active_workspace["workspace_id"],
        "source_revision_id": source_revision_id,
        "merged_source_revision_ids": merged_source_revision_ids,
        "log_dir": str(log_dir),
        "llm": llm_config,
        "method": payload.get("method", {}),
    }
    config_path = revision_dir / "config.json"
    with config_path.open("w", encoding="utf-8") as handle:
        json.dump(config, handle, indent=2, ensure_ascii=True)

    revision_repository.insert_revision(revision_id, active_workspace["workspace_id"], mode, config)

    # Record the nodes this revision was seeded/derived from as members immediately.
    # Merged members are normally recorded only when this revision's graph is first
    # built; until then a source revision that uniquely owns these seed nodes could
    # be force-deleted out from under us and GC the seeds we still depend on. Pinning
    # membership at creation closes that window (missing/synthetic ids are ignored).
    seed_member_ids = _referenced_node_ids(selected_nodes, reference_nodes, initial_population_nodes)
    if mode == "region_search" and isinstance(normalized_region, dict):
        # Region endpoints must survive in the new revision's graph even when
        # their origin revision is not part of the lineage snapshot (e.g. an
        # expert-import revision). Pin them as members so the merged graph
        # rebuild keeps the corridor (anchor/direction) visible for comparison.
        seed_member_ids.extend(
            [normalized_region["a"]]
            + ([normalized_region["b"]] if "b" in normalized_region else [])
        )
    if seed_member_ids:
        try:
            individual_repository.add_revision_members(revision_id, seed_member_ids)
        except Exception:
            pass

    total_hint = None
    if isinstance(config.get("method"), dict):
        method = config["method"]
        if isinstance(method.get("max_sample_nums"), (int, float)):
            total_hint = int(method.get("max_sample_nums") or 0)
        elif isinstance(method.get("max_generations"), (int, float)):
            total_hint = int(method.get("max_generations") or 0)

    revision_job_id = revision_generation_job_id(revision_id)
    upsert_job(
        revision_job_id,
        revision_id,
        "revision_generation",
        status="queued",
        stage="queued",
        stage_label="等待运行进程启动",
        current=0,
        total=total_hint,
        percent=0.0 if total_hint else None,
        message="运行任务已创建，等待采样开始",
        payload={"phase": "queued", "phaseLabel": "等待运行进程启动"},
        started_at=started_at,
    )
    workspace_service.update_workspace_revision(active_workspace["workspace_id"], revision_id)
    revision_repository.upsert_revision(
        revision_id,
        latest_job_id=revision_job_id,
        graph_status="none",
        lifecycle_status="queued",
        started_at=started_at,
    )
    try:
        revision_executor.submit_launch_request(revision_id, config_path)
    except Exception as error:
        error_text = str(error)
        upsert_job(
            revision_job_id,
            revision_id,
            "revision_generation",
            status="failed",
            stage="failed",
            stage_label="运行启动失败",
            message=error_text,
            error=error_text,
            finished_at=datetime.now().isoformat(timespec="seconds"),
        )
        revision_repository.upsert_revision(
            revision_id,
            lifecycle_status="failed",
            graph_status="failed",
            error=error_text,
            latest_job_id=revision_job_id,
        )
        return {"ok": False, "error": f"revision executor 启动失败：{error_text}"}, 500

    return {"ok": True, "revisionId": revision_id, "workspaceId": active_workspace["workspace_id"]}, 200

def import_history_revision(payload: dict[str, Any]) -> tuple[dict[str, Any], int]:
    source_key = str(payload.get("source", "circle_packing_history") or "circle_packing_history").strip()
    requested_workspace_id = str(payload.get("workspace_id", "") or "").strip()
    method_config = payload.get("method", {})
    if not isinstance(method_config, dict):
        method_config = {}
    try:
        history_source = resolve_history_source(source_key)
    except ValueError as error:
        return {"ok": False, "error": str(error)}, 400

    if requested_workspace_id:
        workspace_service.activate_workspace(requested_workspace_id)

    active_workspace = workspace_service.get_active_workspace()
    if active_workspace is None:
        return {"ok": False, "error": "未找到对应工作台。"}, 404

    blocking_job = _active_runtime_job_for_workspace(active_workspace["workspace_id"])
    if blocking_job is not None:
        return {
            "ok": False,
            "error": "当前工作台已有运行中的版本任务，请先停止或等待完成后再导入历史样本。",
        }, 409

    source_revision_id = str(active_workspace.get("current_revision_id", "") or "").strip() or None

    revision_id = datetime.now().strftime("%Y%m%d_%H%M%S") + "_" + uuid.uuid4().hex[:8]
    revision_dir = RUNS_DIR / revision_id
    log_dir = revision_dir / "log"
    revision_dir.mkdir(parents=True, exist_ok=True)
    log_dir.mkdir(parents=True, exist_ok=True)
    started_at = datetime.now().isoformat(timespec="seconds")
    config = {
        "revision_id": revision_id,
        "started_at": started_at,
        "mode": "history_import",
        "prompt": "",
        "selected_nodes": [],
        "workspace_id": active_workspace["workspace_id"],
        "source_revision_id": source_revision_id,
        "log_dir": str(log_dir),
        "llm": {},
        "method": method_config,
        "historyImport": None,
    }
    config_path = revision_dir / "config.json"
    with config_path.open("w", encoding="utf-8") as handle:
        json.dump(config, handle, indent=2, ensure_ascii=True)

    revision_repository.insert_revision(revision_id, active_workspace["workspace_id"], "history_import", config)

    job_id = history_import_job_id(revision_id)
    upsert_job(
        job_id,
        revision_id,
        "history_import",
        status="queued",
        stage="queued",
        stage_label="等待 history import worker 启动",
        current=0,
        total=None,
        message="历史样本导入任务已创建，等待 worker 接手",
        payload={
            "phase": "queued",
            "phaseLabel": "等待 history import worker 启动",
            "sourceKey": history_source["key"],
            "sourceLabel": history_source["label"],
            "sourcePath": history_source["path"],
            "sourceRevisionId": source_revision_id,
            "executor": "celery_worker",
        },
        started_at=started_at,
    )

    workspace_service.update_workspace_revision(active_workspace["workspace_id"], revision_id)
    revision_repository.upsert_revision(
        revision_id,
        workspace_id=active_workspace["workspace_id"],
        lifecycle_status="queued",
        graph_status="none",
        latest_job_id=job_id,
        config=config,
    )

    try:
        from visual_platform.celery_worker import celery_app

        async_result = celery_app.send_task(
            "visual_platform.celery_worker.import_history_samples",
            kwargs={
                "revision_id": revision_id,
                "source_key": source_key,
                "source_revision_id": source_revision_id,
                "method_config": method_config,
            },
        )
    except Exception as error:
        error_text = str(error)
        upsert_job(
            job_id,
            revision_id,
            "history_import",
            status="failed",
            stage="failed",
            stage_label="Worker 提交失败",
            message=error_text,
            error=error_text,
            finished_at=datetime.now().isoformat(timespec="seconds"),
        )
        revision_repository.upsert_revision(
            revision_id,
            lifecycle_status="failed",
            graph_status="failed",
            error=error_text,
            latest_job_id=job_id,
        )
        return {"ok": False, "error": f"Worker 任务提交失败：{error_text}"}, 503

    upsert_job(
        job_id,
        revision_id,
        "history_import",
        status="queued",
        stage="queued",
        stage_label="已提交到 history import worker",
        payload={
            "phase": "queued",
            "phaseLabel": "已提交到 history import worker",
            "taskId": async_result.id,
            "sourceKey": history_source["key"],
            "sourceLabel": history_source["label"],
            "sourcePath": history_source["path"],
            "sourceRevisionId": source_revision_id,
            "executor": "celery_worker",
        },
    )

    return {
        "ok": True,
        "revisionId": revision_id,
        "workspaceId": active_workspace["workspace_id"],
        "queued": True,
    }, 200

def stop_revision(payload: dict[str, Any]) -> tuple[dict[str, Any], int]:
    revision_id = str(payload.get("revision_id", "") or "").strip()
    if not revision_id:
        active_workspace = workspace_service.get_active_workspace()
        if active_workspace and active_workspace.get("current_revision_id"):
            revision_id = str(active_workspace["current_revision_id"])

    if not revision_id:
        return {"ok": False, "error": "未找到可停止的 revision。"}, 404

    revision_job_id = revision_generation_job_id(revision_id)
    job = revision_repository.get_revision_record(revision_id)
    if job is None:
        return {"ok": False, "error": "未找到对应 revision。"}, 404

    current_job = None
    from visual_platform.repositories.job_repository import get_job

    current_job = get_job(revision_job_id)
    current_status = str(current_job.get("status") or "").strip().lower() if isinstance(current_job, dict) else ""
    if current_status not in revision_executor.ACTIVE_RUNTIME_STATUSES:
        return {"ok": False, "error": "当前 revision 没有可停止的运行任务。"}, 409

    try:
        stop_state = revision_executor.request_revision_stop(revision_id)
    except Exception as error:
        return {"ok": False, "error": f"revision executor 停止命令提交失败: {error}"}, 503
    return {"ok": True, "data": stop_state}, 200
