from __future__ import annotations

from typing import Any

from visual_platform.repositories.job_repository import list_jobs_for_revision
from visual_platform.services import job_service

ACTIVE_JOB_STATUSES = frozenset({"queued", "launch_requested", "running", "stop_requested"})

JOB_LABEL_MAP = {
    "history_import": "历史样本导入",
    "expert_import": "外部专家解导入",
    "revision_generation": "版本生成",
    "graph_build": "NBN 图构建",
}

STATUS_LABEL_MAP = {
    "queued": "排队中",
    "launch_requested": "已提交启动命令",
    "running": "运行中",
    "stop_requested": "停止请求中",
    "succeeded": "已完成",
    "completed": "已完成",
    "failed": "失败",
    "cancelled": "已取消",
}

_REVISION_CREATION_JOB_TYPES = ("revision_generation", "history_import", "expert_import")


def _job_sort_key(job: dict[str, Any]) -> tuple[str, str, str]:
    return (
        str(job.get("updated_at") or ""),
        str(job.get("created_at") or ""),
        str(job.get("job_id") or ""),
    )


def list_recent_jobs_for_revision(revision_id: str) -> list[dict[str, Any]]:
    jobs = list_jobs_for_revision(revision_id)
    # 读的时候顺手把心跳停了的任务标记失败，否则 worker 没起/中途死掉时前端会一直转圈。
    jobs = [job_service.reconcile_stale_job(job) or job for job in jobs]
    return sorted(jobs, key=_job_sort_key, reverse=True)


def select_current_job(jobs: list[dict[str, Any]]) -> dict[str, Any] | None:
    if not jobs:
        return None
    for job in jobs:
        if str(job.get("status") or "").strip().lower() in ACTIVE_JOB_STATUSES:
            return job
    return jobs[0]


def summarize_latest_jobs_by_type(jobs: list[dict[str, Any]]) -> list[dict[str, Any]]:
    items: list[dict[str, Any]] = []
    seen_types: set[str] = set()
    for job in jobs:
        job_type = str(job.get("job_type") or "")
        if job_type in seen_types:
            continue
        seen_types.add(job_type)
        items.append(job)
    return items


def find_revision_creation_job(jobs: list[dict[str, Any]]) -> dict[str, Any] | None:
    creation_jobs = [job for job in jobs if str(job.get("job_type") or "") in _REVISION_CREATION_JOB_TYPES]
    if not creation_jobs:
        return min(jobs, key=lambda job: (str(job.get("created_at") or ""), str(job.get("job_id") or "")), default=None)
    return min(creation_jobs, key=lambda job: (str(job.get("created_at") or ""), str(job.get("job_id") or "")))


def timeline_item_from_job(job: dict[str, Any], *, index: int | None = None) -> dict[str, Any]:
    job_type = str(job.get("job_type") or "")
    status = str(job.get("status") or "")
    return {
        "index": index,
        "jobId": str(job.get("job_id") or ""),
        "jobType": job_type,
        "jobLabel": JOB_LABEL_MAP.get(job_type, job_type),
        "status": status,
        "statusLabel": STATUS_LABEL_MAP.get(status, status),
        "stage": str(job.get("stage") or ""),
        "stageLabel": str(job.get("stage_label") or ""),
        "current": job.get("current"),
        "total": job.get("total"),
        "percent": job.get("percent"),
        "message": str(job.get("message") or ""),
        "error": str(job.get("error") or ""),
        "queuedAt": str(job.get("created_at") or ""),
        "startedAt": str(job.get("started_at") or ""),
        "finishedAt": str(job.get("finished_at") or ""),
        "updatedAt": str(job.get("updated_at") or ""),
    }


def build_job_timeline(jobs: list[dict[str, Any]]) -> list[dict[str, Any]]:
    return [timeline_item_from_job(job, index=index) for index, job in enumerate(jobs, start=1)]


def build_revision_job_query(revision_id: str) -> dict[str, Any]:
    latest_jobs = list_recent_jobs_for_revision(revision_id)
    current_job = select_current_job(latest_jobs)
    latest_jobs_by_type = summarize_latest_jobs_by_type(latest_jobs)
    timeline = build_job_timeline(latest_jobs)
    return {
        "latest_jobs": latest_jobs,
        "latest_jobs_by_type": latest_jobs_by_type,
        "current_job": current_job,
        "timeline": timeline,
        "revision_creation_job": find_revision_creation_job(latest_jobs),
    }
