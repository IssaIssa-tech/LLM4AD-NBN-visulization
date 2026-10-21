from __future__ import annotations

import os
import uuid
from datetime import datetime
from typing import Any

from visual_platform.repositories import job_repository


def create_job(
    revision_id: str,
    job_type: str,
    *,
    status: str = "queued",
    stage: str | None = None,
    stage_label: str | None = None,
    payload: dict[str, Any] | None = None,
) -> str:
    job_id = str(uuid.uuid4())
    job_repository.upsert_job(
        job_id,
        revision_id,
        job_type,
        status=status,
        stage=stage,
        stage_label=stage_label,
        payload=payload,
    )
    return job_id


def upsert_job(
    job_id: str,
    revision_id: str,
    job_type: str,
    *,
    status: str,
    stage: str | None = None,
    stage_label: str | None = None,
    current: int | None = None,
    total: int | None = None,
    percent: float | None = None,
    message: str | None = None,
    error: str | None = None,
    payload: dict[str, Any] | None = None,
    result: dict[str, Any] | None = None,
    started_at: str | None = None,
    finished_at: str | None = None,
) -> None:
    job_repository.upsert_job(
        job_id,
        revision_id,
        job_type,
        status=status,
        stage=stage,
        stage_label=stage_label,
        current=current,
        total=total,
        percent=percent,
        message=message,
        error=error,
        payload=payload,
        result=result,
        started_at=started_at,
        finished_at=finished_at,
    )


def update_job(
    job_id: str,
    revision_id: str,
    job_type: str,
    *,
    status: str,
    stage: str | None = None,
    stage_label: str | None = None,
    current: int | None = None,
    total: int | None = None,
    percent: float | None = None,
    message: str | None = None,
    error: str | None = None,
    payload: dict[str, Any] | None = None,
    result: dict[str, Any] | None = None,
    started_at: str | None = None,
    finished_at: str | None = None,
) -> None:
    upsert_job(
        job_id,
        revision_id,
        job_type,
        status=status,
        stage=stage,
        stage_label=stage_label,
        current=current,
        total=total,
        percent=percent,
        message=message,
        error=error,
        payload=payload,
        result=result,
        started_at=started_at,
        finished_at=finished_at,
    )


def get_job(job_id: str) -> dict[str, Any] | None:
    return job_repository.get_job(job_id)


def list_jobs_for_revision(revision_id: str) -> list[dict[str, Any]]:
    return job_repository.list_jobs_for_revision(revision_id)


def get_latest_job(revision_id: str, job_type: str | None = None) -> dict[str, Any] | None:
    return job_repository.get_latest_job(revision_id, job_type)


def list_job_events_for_revision(revision_id: str, limit: int = 20) -> list[dict[str, Any]]:
    return job_repository.list_job_events_for_revision(revision_id, limit)


# ---------------------------------------------------------------------------
# worker 侧失败的可视化兜底
#
# 背景：任务由 Celery worker 执行。worker 没启动（任务一直 queued）、worker 被
# kill/OOM（任务一直 running）、或任务被别的 checkout 的 worker 抢走后失败时，
# 原来 job 记录不会再被更新，前端就一直显示「排队中 / 运行中」，用户完全不知道
# 出了什么事。这里做两件事：
#   1. 读路径上按心跳把僵死的活动任务标记为失败（和 graph_service 对构图任务的
#      处理口径一致）；
#   2. 提交任务后立刻探测有没有在线 worker，没有就把警告写进 message。
# ---------------------------------------------------------------------------

#: 仍然"活着"（在等 worker 或正在跑）的状态；不在这些状态里的任务不会被兜底改写。
ACTIVE_JOB_STATUSES = frozenset({"queued", "launch_requested", "running", "stop_requested"})

#: 超过这个时长没有任何更新，就认为执行它的 worker 已经不在了。
#: 与 graph_service.STALE_JOB_SECONDS 读同一个环境变量。
STALE_JOB_SECONDS = max(60, int(os.environ.get("VISUAL_PLATFORM_STALE_JOB_SECONDS", "600") or "600"))

#: 提交后探测不到在线 worker 时追加到 message 的警告。
NO_WORKER_HINT = (
    "当前没有检测到在线的 Celery worker，任务会一直排队直到 worker 启动"
    "（见 README「常见问题」）。"
)


def _heartbeat_age_seconds(job: dict[str, Any]) -> float | None:
    """距上次进度更新的秒数；取不到时间戳时返回 None（不判定为僵死）。

    库里的时间戳是本地无时区 ISO 串（datetime.now().isoformat()），比较时必须
    用同样口径的 datetime.now()。
    """
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


def _runtime_pid(job: dict[str, Any]) -> int | None:
    """从 job payload 里取 runner 进程号（派发 runner 时会写进 payload.runtime.pid）。"""
    payload = job.get("payload")
    if not isinstance(payload, dict):
        return None
    runtime = payload.get("runtime")
    if not isinstance(runtime, dict):
        return None
    try:
        pid = int(runtime.get("pid") or 0)
    except (TypeError, ValueError):
        return None
    return pid if pid > 0 else None


def _process_alive(pid: int) -> bool:
    try:
        os.kill(pid, 0)
    except ProcessLookupError:
        return False
    except PermissionError:
        # 进程存在但当前用户没权限发信号；按"活着"处理，宁可漏判也不误杀。
        return True
    except OSError:
        return False
    return True


def reconcile_stale_job(job: dict[str, Any] | None) -> dict[str, Any] | None:
    """读路径兜底：把心跳停了的活动任务标记为 failed，并写明原因。

    worker 没起 → 一直 queued；worker 中途死了 → 一直 running。两种情况原来都
    会让前端无限转圈。标记失败后用户可以重新提交，和构图任务的既有行为一致。

    注意 revision_generation（EoH / 提示词生成 / 区域搜索）这类任务：runner 进程
    在运行期间**不会**持续写 job 行（进度写在 `.local/runs/<rev>/` 里，job 只在开始
    和结束各写一次），所以时间戳不足以判定它死了——必须再看 runner 进程是否还在。
    实测一个跑了 610 秒的提示词生成任务，job 事件只有开始那 6 条，中间一片空白；
    只按 600 秒阈值判就会在它还差 10 秒跑完时把它误标成失败。
    """
    if not job:
        return job
    status = str(job.get("status") or "").strip().lower()
    if status not in ACTIVE_JOB_STATUSES:
        return job
    age = _heartbeat_age_seconds(job)
    if age is None or age <= STALE_JOB_SECONDS:
        return job

    pid = _runtime_pid(job)
    if pid is not None and _process_alive(pid):
        return job

    minutes = max(1, int(age // 60))
    if status == "queued":
        reason = (
            f"任务已排队 {minutes} 分钟仍没有 worker 接手：请确认 Redis 与 Celery worker 正在运行，"
            "并且没有别的 worker 抢走了同一个 Redis DB（见 README「常见问题」）。已自动标记失败，可重新提交。"
        )
    else:
        reason = (
            f"任务已 {minutes} 分钟没有任何进度更新，执行它的 worker 可能已退出（被 kill / OOM / 重启）。"
            "已自动标记失败，可重新提交。"
        )

    job_id = str(job.get("job_id") or "")
    if not job_id:
        return job
    update_job(
        job_id,
        str(job.get("revision_id") or ""),
        str(job.get("job_type") or ""),
        status="failed",
        stage="failed",
        stage_label="任务中断",
        message=reason,
        error=reason,
        finished_at=datetime.now().isoformat(timespec="seconds"),
    )
    return get_job(job_id)


def celery_worker_online(timeout: float = 1.0) -> bool:
    """探测是否有在线的 Celery worker。

    探测本身出问题（没装 celery、broker 不可达等）时返回 True——宁可漏报，
    也不要因为探测失败就吓唬用户。
    """
    try:
        from visual_platform.celery_worker import celery_app

        replies = celery_app.control.inspect(timeout=timeout).ping()
        return bool(replies)
    except Exception:
        return True


def annotate_worker_availability(job: dict[str, Any] | None) -> dict[str, Any] | None:
    """提交任务后调用：没有在线 worker 时把警告写进 job.message（不改状态）。"""
    if not job:
        return job
    status = str(job.get("status") or "").strip().lower()
    if status not in ACTIVE_JOB_STATUSES:
        return job
    existing_message = str(job.get("message") or "")
    if NO_WORKER_HINT in existing_message:
        return job
    if celery_worker_online():
        return job

    merged = f"{existing_message.rstrip('。')}；{NO_WORKER_HINT}" if existing_message else NO_WORKER_HINT
    update_job(
        str(job.get("job_id") or ""),
        str(job.get("revision_id") or ""),
        str(job.get("job_type") or ""),
        status=str(job.get("status") or "queued"),
        message=merged,
    )
    return get_job(str(job.get("job_id") or "")) or job


def mark_job_failed_by_task_id(task_id: str, exception: BaseException | None = None) -> bool:
    """Celery task_failure 信号的兜底写回：按 task id 找到 job 并标记失败。

    服务层自己的 try/except 通常会先写好失败原因（此时 job 已不是活动状态，
    这里直接跳过，不覆盖更具体的错误信息）。这里是最后一道网：任何逃过服务层
    保护的异常，也不会让任务永远停在「运行中」。
    """
    job = job_repository.find_job_by_task_id(task_id)
    if job is None:
        return False
    status = str(job.get("status") or "").strip().lower()
    if status not in ACTIVE_JOB_STATUSES:
        return False
    detail = (
        f"worker 中的任务执行失败：{type(exception).__name__}: {exception}"
        if exception is not None
        else "worker 中的任务执行失败（未拿到异常信息）。"
    )
    update_job(
        str(job.get("job_id") or ""),
        str(job.get("revision_id") or ""),
        str(job.get("job_type") or ""),
        status="failed",
        stage="failed",
        stage_label="Worker 任务失败",
        message="worker 中的任务执行失败，详见错误信息；可重新提交。",
        error=detail,
        finished_at=datetime.now().isoformat(timespec="seconds"),
    )
    return True
