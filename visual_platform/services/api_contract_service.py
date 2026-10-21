from __future__ import annotations

import json
import time
from datetime import datetime
from pathlib import Path
from typing import Any

from visual_platform.repositories import (
    get_artifact,
    get_job,
    get_revision_record,
    get_workspace,
    list_artifacts_for_revision,
    list_job_events,
    list_job_events_for_revision,
    list_jobs_for_revision,
    list_revisions_for_workspace,
    list_workspaces,
    update_workspace,
    upsert_revision,
)
from visual_platform.repositories.individual_repository import get_revision_metrics, get_individuals_by_ids
from visual_platform.services.graph_query_service import sanitize_json_scalars
from visual_platform.services.artifact_content_service import (
    ArtifactContentResolutionError,
    resolve_artifact_content,
)
from visual_platform.services.job_query_service import (
    ACTIVE_JOB_STATUSES,
    STATUS_LABEL_MAP,
    build_revision_job_query,
)
from visual_platform.services import job_service, workspace_service
from visual_platform.services.revision_generation_service import revision_generation_job_id


def ok(data: dict[str, Any]) -> dict[str, Any]:
    return {"ok": True, "data": data}


def error_payload(code: str, message: str, *, details: dict[str, Any] | None = None) -> dict[str, Any]:
    return {
        "ok": False,
        "error": {
            "code": code,
            "message": message,
            "details": details or {},
        },
    }


_UNSET = object()

_WORKSPACE_CREATE_FIELDS = frozenset({"name", "description"})
_WORKSPACE_PATCH_FIELDS = frozenset({"name", "description", "selectedRevisionId", "sortIndex"})
_JOB_TOP_LEVEL_FIELDS = frozenset({"workspaceId", "jobType", "request"})
_JOB_REQUEST_FIELDS: dict[str, frozenset[str]] = {
    "revision_generation": frozenset(
        {"mode", "prompt", "selectedNodeIds", "referenceNodeIds", "initialPopulationNodeIds", "sourceRevisionIds", "llm", "method"}
    ),
    "region_search": frozenset({"region", "prompt", "llm", "method", "sourceRevisionIds"}),
    "history_import": frozenset({"source", "method"}),
    "graph_build": frozenset({"revisionId", "clusterId", "maxNodes"}),
    "expert_import": frozenset({"title", "description", "functionText", "method"}),
}


def _invalid_request(
    message: str,
    *,
    details: dict[str, Any] | None = None,
    status_code: int = 400,
) -> tuple[dict[str, Any], int]:
    return error_payload("invalid_request", message, details=details), status_code


def _reject_unknown_fields(
    payload: dict[str, Any],
    *,
    allowed_fields: frozenset[str],
    endpoint: str,
) -> tuple[dict[str, Any], int] | None:
    unsupported_fields = sorted(key for key in payload.keys() if key not in allowed_fields)
    if not unsupported_fields:
        return None
    return _invalid_request(
        f"{endpoint} 包含未支持字段。",
        details={
            "endpoint": endpoint,
            "unsupportedFields": unsupported_fields,
            "allowedFields": sorted(allowed_fields),
        },
    )


def _read_string_field(
    payload: dict[str, Any],
    field_name: str,
    *,
    allow_null: bool = False,
) -> tuple[object, tuple[dict[str, Any], int] | None]:
    if field_name not in payload:
        return _UNSET, None
    value = payload.get(field_name)
    if value is None:
        if allow_null:
            return None, None
        return _UNSET, _invalid_request(f"字段 `{field_name}` 不允许为 null。")
    if not isinstance(value, str):
        return _UNSET, _invalid_request(f"字段 `{field_name}` 必须是字符串。")
    return value, None


def _read_list_field(payload: dict[str, Any], field_name: str) -> tuple[list[Any] | object, tuple[dict[str, Any], int] | None]:
    if field_name not in payload:
        return _UNSET, None
    value = payload.get(field_name)
    if not isinstance(value, list):
        return _UNSET, _invalid_request(f"字段 `{field_name}` 必须是数组。")
    return value, None


def _read_object_field(payload: dict[str, Any], field_name: str) -> tuple[dict[str, Any] | object, tuple[dict[str, Any], int] | None]:
    if field_name not in payload:
        return _UNSET, None
    value = payload.get(field_name)
    if not isinstance(value, dict):
        return _UNSET, _invalid_request(f"字段 `{field_name}` 必须是对象。")
    return value, None


def _read_int_field(
    payload: dict[str, Any],
    field_name: str,
    *,
    minimum: int | None = None,
) -> tuple[int | object, tuple[dict[str, Any], int] | None]:
    if field_name not in payload:
        return _UNSET, None
    value = payload.get(field_name)
    if isinstance(value, bool) or not isinstance(value, int):
        return _UNSET, _invalid_request(f"字段 `{field_name}` 必须是整数。")
    if minimum is not None and value < minimum:
        return _UNSET, _invalid_request(f"字段 `{field_name}` 不能小于 {minimum}。")
    return value, None


def _normalize_revision_status(revision: dict[str, Any], jobs: list[dict[str, Any]]) -> str:
    for job in jobs:
        job_status = str(job.get("status") or "").strip().lower()
        if job_status in ACTIVE_JOB_STATUSES:
            return job_status
    if str(revision.get("error") or "").strip():
        return "failed"
    metrics = get_revision_metrics(str(revision.get("revision_id") or ""))
    if int(metrics.get("sample_count", 0) or 0) > 0:
        return "ready"
    return "idle"


def _serialize_artifact(artifact: dict[str, Any]) -> dict[str, Any]:
    metadata = artifact.get("metadata", {})
    if not isinstance(metadata, dict):
        metadata = {}
    return {
        "artifactId": artifact.get("artifact_id"),
        "revisionId": artifact.get("revision_id"),
        "artifactType": artifact.get("artifact_type"),
        "artifactRole": artifact.get("artifact_role"),
        "format": artifact.get("format"),
        "status": artifact.get("status"),
        "storageUri": artifact.get("storage_uri"),
        "inputDigest": artifact.get("input_digest"),
        "contentDigest": artifact.get("content_digest"),
        "metadata": metadata,
        "createdByJobId": artifact.get("created_by_job_id"),
        "createdAt": artifact.get("created_at"),
        "updatedAt": artifact.get("updated_at"),
        "error": artifact.get("error"),
    }


def _serialize_job(job: dict[str, Any]) -> dict[str, Any]:
    revision = get_revision_record(str(job.get("revision_id") or ""))
    config = revision.get("config", {}) if isinstance(revision, dict) else {}
    if not isinstance(config, dict):
        config = {}
    payload = job.get("payload", {})
    result = job.get("result", {})
    if not isinstance(payload, dict):
        payload = {}
    if not isinstance(result, dict):
        result = {}
    job_status = job.get("status")
    return {
        "jobId": job.get("job_id"),
        "workspaceId": revision.get("workspace_id") if isinstance(revision, dict) else None,
        "jobType": job.get("job_type"),
        "sourceRevisionId": config.get("source_revision_id"),
        "resultRevisionId": job.get("revision_id"),
        "status": job_status,
        "statusLabel": STATUS_LABEL_MAP.get(str(job_status or ""), str(job_status or "")),
        "stage": job.get("stage"),
        "stageLabel": job.get("stage_label"),
        "current": job.get("current"),
        "total": job.get("total"),
        "percent": job.get("percent"),
        "message": job.get("message"),
        "error": job.get("error"),
        "request": payload,
        "result": result,
        "queuedAt": job.get("created_at"),
        "startedAt": job.get("started_at"),
        "finishedAt": job.get("finished_at"),
        "updatedAt": job.get("updated_at"),
    }


def _serialize_job_event(event: dict[str, Any]) -> dict[str, Any]:
    payload = event.get("payload", {})
    if not isinstance(payload, dict):
        payload = {}
    status = event.get("status")
    return {
        "seq": event.get("seq"),
        "jobId": event.get("job_id"),
        "jobType": event.get("job_type"),
        "status": status,
        "statusLabel": STATUS_LABEL_MAP.get(str(status or ""), str(status or "")),
        "stage": event.get("stage"),
        "stageLabel": event.get("stage_label"),
        "current": event.get("current"),
        "total": event.get("total"),
        "percent": event.get("percent"),
        "message": event.get("message"),
        "error": event.get("error"),
        "level": event.get("level"),
        "payload": payload,
        "createdAt": event.get("created_at"),
    }


def _serialize_revision(revision: dict[str, Any]) -> dict[str, Any]:
    revision_id = str(revision.get("revision_id") or "")
    config = revision.get("config", {})
    if not isinstance(config, dict):
        config = {}
    metrics = get_revision_metrics(revision_id)
    job_query = build_revision_job_query(revision_id)
    jobs = job_query["latest_jobs"]
    revision_creation_job = job_query["revision_creation_job"]
    return {
        "revisionId": revision_id,
        "displayName": (str(revision.get("display_name")).strip() or None) if revision.get("display_name") else None,
        "workspaceId": revision.get("workspace_id"),
        "parentRevisionId": config.get("source_revision_id"),
        "createdByJobId": revision_creation_job.get("job_id") if isinstance(revision_creation_job, dict) else None,
        "mode": revision.get("mode"),
        "status": _normalize_revision_status(revision, jobs),
        "sampleCount": metrics.get("sample_count", 0),
        "bestScore": metrics.get("best_score"),
        "summary": {
            "sampleCount": metrics.get("sample_count", 0),
            "bestScore": metrics.get("best_score"),
            "bestSampleOrder": metrics.get("best_sample_order"),
        },
        "createdAt": revision.get("created_at"),
        "readyAt": revision.get("finished_at"),
        "updatedAt": revision.get("updated_at"),
    }


def _workspace_latest_revision(workspace_id: str) -> dict[str, Any] | None:
    revisions = list_revisions_for_workspace(workspace_id)
    if not revisions:
        return None
    return revisions[-1]


def _serialize_workspace(workspace: dict[str, Any]) -> dict[str, Any]:
    workspace_id = str(workspace.get("workspace_id") or "")
    latest_revision = _workspace_latest_revision(workspace_id)
    selected_revision_id = workspace.get("current_revision_id")
    return {
        "workspaceId": workspace_id,
        "name": workspace.get("name"),
        "description": workspace.get("description"),
        "latestRevisionId": latest_revision.get("revision_id") if latest_revision else None,
        "selectedRevisionId": selected_revision_id,
        "sortIndex": workspace.get("sort_index"),
        "createdAt": workspace.get("created_at"),
        "updatedAt": workspace.get("updated_at"),
    }


def list_workspaces_resource() -> dict[str, Any]:
    items = [_serialize_workspace(workspace) for workspace in list_workspaces()]
    return ok({"items": items})


def create_workspace_resource(payload: dict[str, Any]) -> tuple[dict[str, Any], int]:
    validation_error = _reject_unknown_fields(
        payload,
        allowed_fields=_WORKSPACE_CREATE_FIELDS,
        endpoint="POST /api/workspaces",
    )
    if validation_error is not None:
        return validation_error

    description_value, description_error = _read_string_field(payload, "description", allow_null=True)
    if description_error is not None:
        return description_error

    name_value, name_error = _read_string_field(payload, "name")
    if name_error is not None:
        return name_error

    name = "New Workspace"
    if name_value is not _UNSET:
        normalized_name = str(name_value).strip()
        if normalized_name:
            name = normalized_name
    description = None if description_value is _UNSET else description_value

    workspace_id = workspace_service.create_workspace(name, description=description)
    workspace = get_workspace(workspace_id)
    return ok({"workspace": _serialize_workspace(workspace or {"workspace_id": workspace_id, "name": name})}), 201


def get_workspace_resource(workspace_id: str) -> tuple[dict[str, Any], int]:
    workspace = get_workspace(workspace_id)
    if workspace is None:
        return error_payload("workspace_not_found", "未找到对应工作台。"), 404
    revisions = list_revisions_for_workspace(workspace_id)
    selected_revision_id = str(workspace.get("current_revision_id") or "").strip() or None
    selected_revision = get_revision_record(selected_revision_id) if selected_revision_id else None
    latest_revision = revisions[-1] if revisions else None
    running_jobs: list[dict[str, Any]] = []
    for revision in revisions:
        for job in list_jobs_for_revision(str(revision.get("revision_id") or "")):
            if str(job.get("status") or "").strip().lower() in ACTIVE_JOB_STATUSES:
                running_jobs.append(_serialize_job(job))
    return (
        ok(
            {
                "workspace": _serialize_workspace(workspace),
                "selectedRevision": _serialize_revision(selected_revision) if selected_revision else None,
                "latestRevision": _serialize_revision(latest_revision) if latest_revision else None,
                "runningJobs": running_jobs,
            }
        ),
        200,
    )


def patch_workspace_resource(workspace_id: str, payload: dict[str, Any]) -> tuple[dict[str, Any], int]:
    workspace = get_workspace(workspace_id)
    if workspace is None:
        return error_payload("workspace_not_found", "未找到对应工作台。"), 404

    validation_error = _reject_unknown_fields(
        payload,
        allowed_fields=_WORKSPACE_PATCH_FIELDS,
        endpoint="PATCH /api/workspaces/{workspace_id}",
    )
    if validation_error is not None:
        return validation_error
    if not payload:
        return _invalid_request(
            "PATCH /api/workspaces/{workspace_id} 至少需要一个可更新字段。",
            details={"allowedFields": sorted(_WORKSPACE_PATCH_FIELDS)},
        )

    next_name, name_error = _read_string_field(payload, "name")
    if name_error is not None:
        return name_error
    next_description, description_error = _read_string_field(payload, "description", allow_null=True)
    if description_error is not None:
        return description_error
    next_revision_id, revision_error = _read_string_field(payload, "selectedRevisionId", allow_null=True)
    if revision_error is not None:
        return revision_error
    next_sort_index, sort_index_error = _read_int_field(payload, "sortIndex")
    if sort_index_error is not None:
        return sort_index_error

    if next_name is not _UNSET and not str(next_name).strip():
        return _invalid_request("字段 `name` 不能为空字符串。")

    if next_revision_id not in {_UNSET, None, ""}:
        revision = get_revision_record(str(next_revision_id))
        if revision is None or str(revision.get("workspace_id") or "") != workspace_id:
            return error_payload("revision_not_found", "未找到属于该工作台的 revision。"), 404

    update_kwargs: dict[str, Any] = {}
    if next_name is not _UNSET:
        update_kwargs["name"] = str(next_name).strip()
    if next_description is not _UNSET:
        update_kwargs["description"] = next_description
    if next_revision_id is not _UNSET:
        update_kwargs["current_revision_id"] = None if next_revision_id in {None, ""} else str(next_revision_id)
    if next_sort_index is not _UNSET:
        update_kwargs["sort_index"] = next_sort_index

    update_workspace(
        workspace_id,
        **update_kwargs,
    )
    return get_workspace_resource(workspace_id)


def list_workspace_revisions_resource(workspace_id: str) -> tuple[dict[str, Any], int]:
    workspace = get_workspace(workspace_id)
    if workspace is None:
        return error_payload("workspace_not_found", "未找到对应工作台。"), 404
    items = [_serialize_revision(revision) for revision in list_revisions_for_workspace(workspace_id)]
    return ok({"items": items}), 200


def _job_from_service_result(job_id: str) -> tuple[dict[str, Any], int]:
    job = get_job(job_id)
    if job is None:
        return error_payload("job_not_found", "未找到对应 job。"), 404
    # 刚提交完就探测一下有没有在线 worker：没有的话把警告写进 message，
    # 用户不用等十分钟才发现"任务根本没人在跑"。
    job = job_service.annotate_worker_availability(job) or job
    return ok({"job": _serialize_job(job)}), 200


def submit_job_resource(payload: dict[str, Any]) -> tuple[dict[str, Any], int]:
    validation_error = _reject_unknown_fields(
        payload,
        allowed_fields=_JOB_TOP_LEVEL_FIELDS,
        endpoint="POST /api/jobs",
    )
    if validation_error is not None:
        return validation_error

    workspace_id = str(payload.get("workspaceId", "") or "").strip()
    job_type = str(payload.get("jobType", "") or "").strip()
    request_payload = payload.get("request", {})
    if not isinstance(request_payload, dict):
        return _invalid_request("字段 `request` 必须是对象。")
    if not workspace_id:
        return error_payload("invalid_request", "缺少 workspaceId。"), 400
    if not job_type:
        return error_payload("invalid_request", "缺少 jobType。"), 400
    allowed_request_fields = _JOB_REQUEST_FIELDS.get(job_type)
    if allowed_request_fields is None:
        return error_payload("unsupported_job_type", f"不支持的 jobType: {job_type}"), 422

    request_validation_error = _reject_unknown_fields(
        request_payload,
        allowed_fields=allowed_request_fields,
        endpoint=f"POST /api/jobs request<{job_type}>",
    )
    if request_validation_error is not None:
        return request_validation_error

    if job_type == "revision_generation":
        for field_name in ("mode", "prompt"):
            _, field_error = _read_string_field(request_payload, field_name)
            if field_error is not None:
                return field_error
        for field_name in ("selectedNodeIds", "referenceNodeIds", "initialPopulationNodeIds", "sourceRevisionIds"):
            _, field_error = _read_list_field(request_payload, field_name)
            if field_error is not None:
                return field_error
        for field_name in ("llm", "method"):
            _, field_error = _read_object_field(request_payload, field_name)
            if field_error is not None:
                return field_error

        from visual_platform.services.revision_service import start_revision

        response_payload, status_code = start_revision(
            {
                "workspace_id": workspace_id,
                "mode": request_payload.get("mode", "prompt_gen"),
                "prompt": request_payload.get("prompt", ""),
                "selected_nodes": request_payload.get("selectedNodeIds", []),
                "reference_nodes": request_payload.get("referenceNodeIds", []),
                "initial_population_nodes": request_payload.get("initialPopulationNodeIds", []),
                "source_revision_ids": request_payload.get("sourceRevisionIds", []),
                "llm": request_payload.get("llm", {}),
                "method": request_payload.get("method", {}),
            }
        )
        if status_code >= 400:
            return error_payload("invalid_request", str(response_payload.get("error") or "提交任务失败。")), status_code
        return _job_from_service_result(revision_generation_job_id(str(response_payload.get("revisionId") or "")))

    if job_type == "region_search":
        _, region_error = _read_object_field(request_payload, "region")
        if region_error is not None:
            return region_error
        _, prompt_error = _read_string_field(request_payload, "prompt", allow_null=True)
        if prompt_error is not None:
            return prompt_error
        _, source_error = _read_list_field(request_payload, "sourceRevisionIds")
        if source_error is not None:
            return source_error
        _, llm_error = _read_object_field(request_payload, "llm")
        if llm_error is not None:
            return llm_error
        _, method_error = _read_object_field(request_payload, "method")
        if method_error is not None:
            return method_error

        from visual_platform.services.revision_service import start_revision

        response_payload, status_code = start_revision(
            {
                "workspace_id": workspace_id,
                "mode": "region_search",
                "region": request_payload.get("region", {}),
                "prompt": request_payload.get("prompt", ""),
                "source_revision_ids": request_payload.get("sourceRevisionIds", []),
                "llm": request_payload.get("llm", {}),
                "method": request_payload.get("method", {}),
            }
        )
        if status_code >= 400:
            return error_payload("invalid_request", str(response_payload.get("error") or "提交任务失败。")), status_code
        return _job_from_service_result(revision_generation_job_id(str(response_payload.get("revisionId") or "")))

    if job_type == "history_import":
        _, source_error = _read_string_field(request_payload, "source")
        if source_error is not None:
            return source_error
        _, method_error = _read_object_field(request_payload, "method")
        if method_error is not None:
            return method_error

        from visual_platform.services.revision_service import import_history_revision

        response_payload, status_code = import_history_revision(
            {
                "workspace_id": workspace_id,
                "source": request_payload.get("source", "circle_packing_history"),
                "method": request_payload.get("method", {}),
            }
        )
        if status_code >= 400:
            return error_payload("invalid_request", str(response_payload.get("error") or "导入历史失败。")), status_code
        return _job_from_service_result(f"history-import:{response_payload.get('revisionId')}")

    if job_type == "graph_build":
        _, revision_id_error = _read_string_field(request_payload, "revisionId")
        if revision_id_error is not None:
            return revision_id_error
        _, cluster_error = _read_string_field(request_payload, "clusterId", allow_null=True)
        if cluster_error is not None:
            return cluster_error
        _, max_nodes_error = _read_int_field(request_payload, "maxNodes", minimum=1)
        if max_nodes_error is not None:
            return max_nodes_error

        from visual_platform.services.graph_service import ensure_graph_build_task

        revision_id = str(request_payload.get("revisionId", "") or "").strip()
        revision = get_revision_record(revision_id)
        if revision is None:
            return error_payload("revision_not_found", "未找到对应 revision。"), 404
        revision_dir = workspace_service.get_revision_dir(revision_id)
        if revision_dir is None:
            return error_payload("revision_not_found", "未找到对应 revision 目录。"), 404
        config = revision.get("config", {})
        if not isinstance(config, dict):
            config = {}
        method_config = config.get("method", {})
        if not isinstance(method_config, dict):
            method_config = {}
        cluster_id = str(request_payload.get("clusterId", "") or "").strip() or None
        task_state = ensure_graph_build_task(
            revision_dir,
            revision_dir / "log",
            method_config=method_config,
            max_nodes=int(request_payload.get("maxNodes", 50000) or 50000),
            source_revision_id=str(config.get("source_revision_id", "") or "").strip() or None,
            cluster_id=cluster_id,
        )
        if task_state.get("phase") == "failed" and not task_state.get("active"):
            return (
                error_payload(
                    "graph_worker_submit_failed",
                    str(task_state.get("message") or "图构建任务提交失败。"),
                    details={
                        "error": task_state.get("error"),
                        "errorSource": task_state.get("errorSource"),
                        "retryable": task_state.get("retryable"),
                    },
                ),
                503,
            )
        variant = "full" if cluster_id is None else f"cluster_{cluster_id}"
        job_id = f"graph-build:{revision_id}" if variant == "full" else f"graph-build:{revision_id}:{variant}"
        return _job_from_service_result(job_id)

    if job_type == "expert_import":
        for field_name in ("title", "description", "functionText"):
            _, field_error = _read_string_field(request_payload, field_name)
            if field_error is not None:
                return field_error
        _, method_error = _read_object_field(request_payload, "method")
        if method_error is not None:
            return method_error

        from visual_platform.services.expert_service import submit_expert_solution

        response_payload, status_code = submit_expert_solution(
            {
                "workspace_id": workspace_id,
                "title": request_payload.get("title", ""),
                "description": request_payload.get("description", ""),
                "function_text": request_payload.get("functionText", ""),
                "method": request_payload.get("method", {}),
            }
        )
        if status_code >= 400:
            return error_payload("invalid_request", str(response_payload.get("error") or "专家解导入失败。")), status_code
        return _job_from_service_result(f"expert-import:{response_payload.get('revisionId')}")


def get_job_resource(job_id: str) -> tuple[dict[str, Any], int]:
    job = job_service.reconcile_stale_job(get_job(job_id))
    if job is None:
        return error_payload("job_not_found", "未找到对应 job。"), 404
    return ok({"job": _serialize_job(job)}), 200


def get_job_events_resource(job_id: str, *, limit: int = 50, after_seq: int | None = None) -> tuple[dict[str, Any], int]:
    # 先把僵死任务判失败，这样下面列事件时能带上"为什么失败"那条。
    job = job_service.reconcile_stale_job(get_job(job_id))
    if job is None:
        return error_payload("job_not_found", "未找到对应 job。"), 404
    items = [_serialize_job_event(event) for event in list_job_events(job_id, limit=limit, after_seq=after_seq)]
    return ok({"jobId": job_id, "items": items}), 200


# 任务进入这些状态后不会再有新事件，SSE 应当收尾退出。
_TERMINAL_JOB_STATUSES = frozenset({"succeeded", "failed", "cancelled"})
# 兜底上限：即使状态一直异常，也不让一个客户端永久占住一个 Flask 线程。
_STREAM_MAX_SECONDS = 30 * 60.0


def iter_job_events_stream_resource(job_id: str) -> Any:
    def _payload_builder() -> dict[str, Any]:
        payload, _ = get_job_events_resource(job_id, limit=200)
        return payload

    def _should_stop() -> bool:
        job = get_job(job_id)
        # job 不存在（错误的 id）同样视为终止，否则会一直挂着。
        if job is None:
            return True
        return str(job.get("status") or "") in _TERMINAL_JOB_STATUSES

    last_payload_key: str | None = None
    heartbeat_started_at = time.monotonic()
    started_at = time.monotonic()
    while True:
        try:
            payload = _payload_builder()
            payload_key = json.dumps(
                sanitize_json_scalars(payload),
                ensure_ascii=False,
                sort_keys=True,
                separators=(",", ":"),
            )
            if payload_key != last_payload_key:
                last_payload_key = payload_key
                heartbeat_started_at = time.monotonic()
                yield f"event: job_event\ndata: {payload_key}\n\n"
            elif (time.monotonic() - heartbeat_started_at) >= 10.0:
                heartbeat_started_at = time.monotonic()
                yield "event: heartbeat\ndata: {}\n\n"
            # 任务结束就收尾退出。原先这里是无条件 while True，每个客户端会永久
            # 占住一个请求线程（并在轮询数据库），连接只增不减。
            if _should_stop() or (time.monotonic() - started_at) >= _STREAM_MAX_SECONDS:
                yield "event: done\ndata: {}\n\n"
                return
            time.sleep(1.0)
        except GeneratorExit:
            return
        except Exception as error:
            payload = json.dumps(error_payload("internal_error", str(error)), ensure_ascii=False)
            yield f"event: error\ndata: {payload}\n\n"
            if (time.monotonic() - started_at) >= _STREAM_MAX_SECONDS:
                return
            time.sleep(2.0)


def cancel_job_resource(job_id: str) -> tuple[dict[str, Any], int]:
    job = get_job(job_id)
    if job is None:
        return error_payload("job_not_found", "未找到对应 job。"), 404
    status = str(job.get("status") or "").strip().lower()
    if status in {"stop_requested", "cancelled"}:
        return get_job_resource(job_id)
    if status not in {"queued", "launch_requested", "running"}:
        return error_payload("job_not_cancellable", "当前 job 不可取消。"), 409
    job_type = str(job.get("job_type") or "")
    revision_id = str(job.get("revision_id") or "")
    if job_type == "revision_generation":
        from visual_platform.services.revision_service import stop_revision

        response_payload, status_code = stop_revision({"revision_id": revision_id})
        if status_code >= 400:
            return error_payload("job_not_cancellable", str(response_payload.get("error") or "取消失败。")), status_code
    elif job_type == "graph_build":
        from visual_platform.runtime.graph_executor import request_graph_build_stop

        request_graph_build_stop(job)
    else:
        job_service.update_job(
            job_id,
            revision_id,
            job_type,
            status="cancelled",
            stage="cancelled",
            stage_label="已取消",
            message="任务已取消",
            finished_at=datetime.now().isoformat(timespec="seconds"),
        )
    return get_job_resource(job_id)


def get_revision_events_resource(revision_id: str, *, limit: int = 100) -> tuple[dict[str, Any], int]:
    revision = get_revision_record(revision_id)
    if revision is None:
        return error_payload("revision_not_found", "未找到对应 revision。"), 404
    raw_events = list_job_events_for_revision(revision_id, limit=max(1, min(500, limit)))
    items = [_serialize_job_event(event) for event in reversed(raw_events)]
    return ok({"revisionId": revision_id, "items": items}), 200


def get_revision_resource(revision_id: str) -> tuple[dict[str, Any], int]:
    revision = get_revision_record(revision_id)
    if revision is None:
        return error_payload("revision_not_found", "未找到对应 revision。"), 404
    workspace = get_workspace(str(revision.get("workspace_id") or ""))
    job_query = build_revision_job_query(revision_id)
    latest_jobs = [_serialize_job(job) for job in job_query["latest_jobs"]]
    latest_jobs_by_type = [_serialize_job(job) for job in job_query["latest_jobs_by_type"]]
    current_job_raw = job_query["current_job"]
    artifacts = [_serialize_artifact(artifact) for artifact in list_artifacts_for_revision(revision_id)]
    return (
        ok(
            {
                "revision": _serialize_revision(revision),
                "workspace": _serialize_workspace(workspace) if workspace else None,
                "artifacts": artifacts,
                "latestJobs": latest_jobs,
                "latestJobsByType": latest_jobs_by_type,
                "currentJob": _serialize_job(current_job_raw) if isinstance(current_job_raw, dict) else None,
                "timeline": job_query["timeline"],
            }
        ),
        200,
    )


def delete_revision_resource(revision_id: str, *, force: bool = False) -> tuple[dict[str, Any], int]:
    from visual_platform.services.revision_service import delete_revision

    response_payload, status_code = delete_revision(revision_id, force=force)
    if status_code >= 400:
        if status_code == 404:
            code = "revision_not_found"
        elif status_code == 409:
            code = "revision_deletes_unique_solutions" if response_payload.get("requiresForce") else "revision_delete_conflict"
        else:
            code = "invalid_request"
        details = None
        if response_payload.get("requiresForce"):
            details = {
                "requiresForce": True,
                "uniqueCount": response_payload.get("uniqueCount"),
            }
        return error_payload(code, str(response_payload.get("error") or "删除 revision 失败。"), details=details), status_code
    return (
        ok(
            {
                "revisionId": response_payload.get("revisionId"),
                "workspaceId": response_payload.get("workspaceId"),
                "selectedRevisionId": response_payload.get("selectedRevisionId"),
            }
        ),
        status_code,
    )


_MAX_REVISION_NAME_LEN = 200


def rename_revision_resource(revision_id: str, display_name: Any) -> tuple[dict[str, Any], int]:
    revision = get_revision_record(revision_id)
    if revision is None:
        return error_payload("revision_not_found", "未找到对应 revision。"), 404
    normalized = str(display_name or "").strip()
    if len(normalized) > _MAX_REVISION_NAME_LEN:
        return (
            error_payload(
                "invalid_request",
                f"名称过长，请限制在 {_MAX_REVISION_NAME_LEN} 个字符以内。",
            ),
            400,
        )
    # Empty string clears the custom name and reverts the UI to the raw revision_id.
    upsert_revision(revision_id, display_name=normalized)
    updated = get_revision_record(revision_id)
    return ok({"revision": _serialize_revision(updated)}), 200


def list_revision_artifacts_resource(
    revision_id: str,
    *,
    artifact_type: str | None = None,
    artifact_role: str | None = None,
    status: str | None = None,
) -> tuple[dict[str, Any], int]:
    revision = get_revision_record(revision_id)
    if revision is None:
        return error_payload("revision_not_found", "未找到对应 revision。"), 404
    items = [
        _serialize_artifact(artifact)
        for artifact in list_artifacts_for_revision(
            revision_id,
            artifact_type=artifact_type,
            artifact_role=artifact_role,
            status=status,
        )
    ]
    return ok({"items": items}), 200


def get_artifact_resource(artifact_id: str) -> tuple[dict[str, Any], int]:
    artifact = get_artifact(artifact_id)
    if artifact is None:
        return error_payload("artifact_not_found", "未找到对应 artifact。"), 404
    return ok({"artifact": _serialize_artifact(artifact)}), 200


def get_artifact_content_resource(artifact_id: str) -> tuple[dict[str, Any], int]:
    artifact = get_artifact(artifact_id)
    if artifact is None:
        return error_payload("artifact_not_found", "未找到对应 artifact。"), 404
    serialized_artifact = _serialize_artifact(artifact)
    try:
        resolved_payload = resolve_artifact_content(artifact)
    except ArtifactContentResolutionError as error:
        return error_payload(error.code, error.message, details=error.details), error.status_code
    resolved_payload["artifact"] = serialized_artifact
    return ok(resolved_payload), 200


def get_node_code_resource(node_id: str, artifact_id: str | None = None) -> tuple[dict[str, Any], int]:
    """Return the full code/algorithm for a single graph node on demand.

    Graph node id equals ``individuals.id`` (global primary key), so the heavy
    code fields stripped from the transported graph payload are normally fetched
    here lazily when a node is inspected.

    Legacy/merged nodes (e.g. expert solutions pulled in from earlier revisions)
    may have no ``individuals`` row while their code is still embedded in the
    graph artifact on disk. When ``artifact_id`` is supplied we fall back to that
    file so those nodes keep showing their code.
    """
    normalized_id = str(node_id or "").strip()
    if not normalized_id:
        return error_payload("node_not_found", "缺少节点 ID。"), 404
    try:
        return _resolve_node_code_resource(normalized_id, artifact_id)
    except Exception as exc:  # noqa: BLE001 - endpoint must always emit JSON
        # Never let an unexpected error bubble up as a Flask HTML 500 page: the
        # frontend does JSON.parse on every response and would otherwise report
        # "接口未返回 JSON". Degrade to a structured JSON error instead.
        return error_payload("node_code_error", f"加载节点代码失败：{exc}"), 500


def _resolve_node_code_resource(normalized_id: str, artifact_id: str | None = None) -> tuple[dict[str, Any], int]:
    from visual_platform.services.graph_query_service import sanitize_json_scalars

    records = get_individuals_by_ids([normalized_id])
    if records:
        payload = records[0] if isinstance(records[0], dict) else {}
        function_text = str(
            payload.get("function") or payload.get("code") or ""
        ).strip()
        program_text = str(
            payload.get("program") or payload.get("function") or payload.get("code") or ""
        ).strip()
        algorithm_text = str(
            payload.get("algorithm") or payload.get("algorithm_summary") or ""
        ).strip()
        # Non-finite scores (e.g. an infeasible sample scored -inf) serialize as
        # `-Infinity`, which the browser's JSON.parse rejects -> scrub to None.
        return ok(sanitize_json_scalars({
            "nodeId": normalized_id,
            "function": function_text,
            "program": program_text,
            "algorithm": algorithm_text,
            "score": payload.get("score"),
            "source": "db",
        })), 200

    # DB miss: fall back to the embedded code in the graph artifact file.
    normalized_artifact_id = str(artifact_id or "").strip()
    if normalized_artifact_id:
        artifact = get_artifact(normalized_artifact_id)
        if artifact is not None:
            from visual_platform.services.artifact_content_service import load_raw_graph_content
            from visual_platform.services.graph_query_service import find_graph_node

            raw_graph = load_raw_graph_content(artifact)
            node = find_graph_node(raw_graph, normalized_id) if isinstance(raw_graph, dict) else None
            if isinstance(node, dict):
                function_text = str(
                    node.get("functionPreview")
                    or node.get("function")
                    or node.get("programPreview")
                    or node.get("program")
                    or node.get("code")
                    or ""
                ).strip()
                program_text = str(
                    node.get("programPreview")
                    or node.get("program")
                    or node.get("functionPreview")
                    or node.get("function")
                    or node.get("code")
                    or ""
                ).strip()
                algorithm_text = str(
                    node.get("algorithm") or node.get("algorithmSummary") or ""
                ).strip()
                if function_text or program_text or algorithm_text:
                    return ok(sanitize_json_scalars({
                        "nodeId": normalized_id,
                        "function": function_text,
                        "program": program_text,
                        "algorithm": algorithm_text,
                        "score": node.get("rawScore") if node.get("rawScore") is not None else node.get("score"),
                        "source": "artifact",
                    })), 200

    return error_payload("node_not_found", "未找到对应节点的解记录。"), 404
