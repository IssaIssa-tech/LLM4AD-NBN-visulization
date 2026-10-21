from __future__ import annotations

import logging
import os
import signal
import subprocess
import sys
import time
from datetime import datetime
from pathlib import Path
from typing import Any

from visual_platform.config import BASE_DIR
from visual_platform.repositories import revision_repository
from visual_platform.repositories.job_repository import get_job, upsert_job
from visual_platform.services.revision_generation_service import revision_generation_job_id

logger = logging.getLogger(__name__)

REVISION_LAUNCH_TASK_NAME = "visual_platform.celery_worker.launch_revision_runner"
REVISION_STOP_TASK_NAME = "visual_platform.celery_worker.stop_revision_runner"
ACTIVE_RUNTIME_STATUSES = {"queued", "launch_requested", "running", "stop_requested"}
LAUNCH_REQUESTED_STATUSES = {"queued", "launch_requested"}


def _now() -> str:
    return datetime.now().isoformat(timespec="seconds")


def _read_revision_config(revision_id: str) -> dict[str, Any]:
    record = revision_repository.get_revision_record(revision_id)
    if not record:
        return {}
    config = record.get("config", {})
    return dict(config) if isinstance(config, dict) else {}


def _runtime_payload_for_job(revision_id: str) -> dict[str, Any]:
    job = get_job(revision_generation_job_id(revision_id))
    payload = job.get("payload", {}) if isinstance(job, dict) else {}
    return dict(payload) if isinstance(payload, dict) else {}


def _current_job_status(revision_id: str) -> str:
    job = get_job(revision_generation_job_id(revision_id))
    if not isinstance(job, dict):
        return ""
    return str(job.get("status") or "").strip().lower()


def _merge_runtime_metadata(revision_id: str, runtime_metadata: dict[str, Any]) -> dict[str, Any]:
    config = _read_revision_config(revision_id)
    existing_runtime = config.get("runtime", {})
    if not isinstance(existing_runtime, dict):
        existing_runtime = {}
    merged_runtime = {**existing_runtime, **runtime_metadata}
    config["runtime"] = merged_runtime
    revision_repository.upsert_revision(revision_id, config=config)
    return merged_runtime


def _write_runtime_state(
    revision_id: str,
    *,
    status: str,
    stage: str,
    stage_label: str,
    message: str,
    extra_payload: dict[str, Any] | None = None,
    finished_at: str | None = None,
) -> None:
    job_id = revision_generation_job_id(revision_id)
    payload = _runtime_payload_for_job(revision_id)
    payload.update(extra_payload or {})
    payload["runtimeStatus"] = status
    upsert_job(
        job_id,
        revision_id,
        "revision_generation",
        status=status,
        stage=stage,
        stage_label=stage_label,
        message=message,
        payload=payload,
        finished_at=finished_at,
    )


def submit_launch_request(revision_id: str, config_path: Path) -> dict[str, Any]:
    requested_at = _now()
    from visual_platform.celery_worker import celery_app

    async_result = celery_app.send_task(
        REVISION_LAUNCH_TASK_NAME,
        kwargs={
            "revision_id": revision_id,
            "config_path": str(config_path),
        },
    )
    runtime_metadata = _merge_runtime_metadata(
        revision_id,
        {
            "executor": "celery_worker",
            "configPath": str(config_path),
            "launchRequestedAt": requested_at,
            "launchTaskId": async_result.id,
        },
    )
    _write_runtime_state(
        revision_id,
        status="launch_requested",
        stage="launch_requested",
        stage_label="已提交到 revision worker",
        message="启动命令已提交，等待 revision executor 启动 runner",
        extra_payload={
            "phase": "launch_requested",
            "phaseLabel": "已提交到 revision worker",
            "executor": "celery_worker",
            "taskId": async_result.id,
            "requestedAt": requested_at,
            "runtime": runtime_metadata,
        },
    )
    revision_repository.upsert_revision(
        revision_id,
        lifecycle_status="launch_requested",
        latest_job_id=revision_generation_job_id(revision_id),
    )
    return {
        "revisionId": revision_id,
        "taskId": async_result.id,
        "requestedAt": requested_at,
        "executor": "celery_worker",
    }


def launch_revision_runner(revision_id: str, config_path: Path) -> dict[str, Any]:
    revision_dir = config_path.parent
    stdout_log_path = revision_dir / "runner_stdout.log"
    stderr_log_path = revision_dir / "runner_stderr.log"
    stdout_log = stdout_log_path.open("w", encoding="utf-8")
    stderr_log = stderr_log_path.open("w", encoding="utf-8")

    creation_flags = subprocess.CREATE_NEW_PROCESS_GROUP if os.name == "nt" else 0
    try:
        process = subprocess.Popen(
            [sys.executable, "-m", "visual_platform.runtime.runner_cli", "--config", str(config_path)],
            cwd=str(BASE_DIR.parent),
            stdin=subprocess.DEVNULL,
            stdout=stdout_log,
            stderr=stderr_log,
            creationflags=creation_flags,
        )
    except Exception:
        stdout_log.close()
        stderr_log.close()
        raise
    stdout_log.close()
    stderr_log.close()

    runner_metadata = {
        "pid": int(process.pid),
        "command": [sys.executable, "-m", "visual_platform.runtime.runner_cli", "--config", str(config_path)],
        "cwd": str(BASE_DIR.parent),
        "stdoutLog": str(stdout_log_path),
        "stderrLog": str(stderr_log_path),
        "launchedAt": _now(),
    }
    # Once the runner process exists, bookkeeping failures (e.g. transient
    # SQLite locks) must not propagate: the celery-level autoretry would
    # launch a duplicate runner against the same revision directory.
    runtime_metadata = runner_metadata
    try:
        runtime_metadata = _merge_runtime_metadata(revision_id, runner_metadata)
        _write_runtime_state(
            revision_id,
            status="queued",
            stage="queued",
            stage_label="等待运行进程启动",
            message="运行任务已提交给 revision executor",
            extra_payload={
                "runtime": runtime_metadata,
                "phase": "queued",
                "phaseLabel": "等待运行进程启动",
            },
        )
        revision_repository.upsert_revision(
            revision_id,
            lifecycle_status="queued",
            latest_job_id=revision_generation_job_id(revision_id),
        )
    except Exception:
        logger.exception("Runner %s started (pid=%s) but state persistence failed", revision_id, process.pid)
    return runtime_metadata


def run_revision_launch_task(
    revision_id: str,
    config_path: str,
    *,
    task_id: str | None = None,
) -> dict[str, Any]:
    current_status = _current_job_status(revision_id)
    if current_status == "stop_requested":
        result = apply_stop_request(revision_id)
        result.update({"ok": True, "skippedLaunch": True, "taskId": task_id})
        return result
    # "failed" is retryable: the celery task auto-retries transient SQLite
    # lock errors, and by then the failure handler has already stamped the
    # job as failed. A relaunch from failed is exactly what we want.
    if current_status not in LAUNCH_REQUESTED_STATUSES and current_status != "failed":
        return {
            "ok": False,
            "skipped": True,
            "reason": f"revision status is {current_status or 'unknown'}",
            "revisionId": revision_id,
            "taskId": task_id,
        }

    try:
        runtime_metadata = launch_revision_runner(revision_id, Path(config_path))
    except Exception as error:
        error_text = str(error)
        # The failure handler itself must never raise: it used to re-read the
        # revision config from SQLite here, and when the launch failed because
        # of "database is locked" that read crashed too, leaving the job stuck
        # in launch_requested forever. Keep every step best-effort.
        try:
            runtime_payload = _read_revision_config(revision_id).get("runtime", {})
        except Exception:
            runtime_payload = {}
        try:
            _write_runtime_state(
                revision_id,
                status="failed",
                stage="failed",
                stage_label="运行启动失败",
                message=error_text,
                extra_payload={
                    "phase": "failed",
                    "phaseLabel": "运行启动失败",
                    "runtime": runtime_payload,
                    "taskId": task_id,
                },
                finished_at=_now(),
            )
            revision_repository.upsert_revision(
                revision_id,
                lifecycle_status="failed",
                graph_status="failed",
                error=error_text,
                latest_job_id=revision_generation_job_id(revision_id),
            )
        except Exception:
            logger.exception("Unable to persist failed launch state for %s", revision_id)
        raise

    return {
        "ok": True,
        "revisionId": revision_id,
        "taskId": task_id,
        "runtime": runtime_metadata,
    }


def request_revision_stop(revision_id: str) -> dict[str, Any]:
    requested_at = _now()
    runtime_metadata = _merge_runtime_metadata(
        revision_id,
        {
            "stopRequestedAt": requested_at,
        },
    )
    _write_runtime_state(
        revision_id,
        status="stop_requested",
        stage="stop_requested",
        stage_label="已请求停止",
        message="已记录停止请求，等待 revision executor 终止运行进程",
        extra_payload={
            "phase": "stop_requested",
            "phaseLabel": "已请求停止",
            "runtime": runtime_metadata,
            "stopRequestedAt": requested_at,
        },
    )
    revision_repository.upsert_revision(
        revision_id,
        lifecycle_status="stop_requested",
        latest_job_id=revision_generation_job_id(revision_id),
    )

    try:
        from visual_platform.celery_worker import celery_app

        async_result = celery_app.send_task(
            REVISION_STOP_TASK_NAME,
            kwargs={"revision_id": revision_id},
        )
    except Exception as error:
        error_text = str(error)
        failed_runtime_metadata = _merge_runtime_metadata(
            revision_id,
            {"stopSubmitError": error_text},
        )
        _write_runtime_state(
            revision_id,
            status="stop_requested",
            stage="stop_requested",
            stage_label="停止请求待重试",
            message="已记录停止请求，但提交 revision executor 失败",
            extra_payload={
                "phase": "stop_requested",
                "phaseLabel": "停止请求待重试",
                "runtime": failed_runtime_metadata,
                "stopRequestedAt": requested_at,
                "stopSubmitError": error_text,
            },
        )
        raise

    runtime_metadata = _merge_runtime_metadata(
        revision_id,
        {
            "executor": "celery_worker",
            "stopTaskId": async_result.id,
        },
    )
    _write_runtime_state(
        revision_id,
        status="stop_requested",
        stage="stop_requested",
        stage_label="已提交停止命令",
        message="停止命令已提交，等待 revision executor 消费",
        extra_payload={
            "phase": "stop_requested",
            "phaseLabel": "已提交停止命令",
            "runtime": runtime_metadata,
            "stopRequestedAt": requested_at,
            "taskId": async_result.id,
            "executor": "celery_worker",
        },
    )
    return {
        "revisionId": revision_id,
        "taskId": async_result.id,
        "requestedAt": requested_at,
        "executor": "celery_worker",
    }


def run_revision_stop_task(
    revision_id: str,
    *,
    task_id: str | None = None,
) -> dict[str, Any]:
    current_status = _current_job_status(revision_id)
    if current_status != "stop_requested":
        return {
            "ok": False,
            "skipped": True,
            "reason": f"revision status is {current_status or 'unknown'}",
            "revisionId": revision_id,
            "taskId": task_id,
        }
    result = apply_stop_request(revision_id)
    result.update({"ok": True, "taskId": task_id})
    return result


def apply_stop_request(revision_id: str) -> dict[str, Any]:
    config = _read_revision_config(revision_id)
    runtime_metadata = config.get("runtime", {})
    if not isinstance(runtime_metadata, dict):
        runtime_metadata = {}

    pid_value = runtime_metadata.get("pid")
    terminated = False
    if isinstance(pid_value, int) and pid_value > 0:
        terminated = terminate_process_tree(pid_value)

    finished_at = _now()
    runtime_metadata.update(
        {
            "terminatedAt": finished_at,
            "terminated": terminated,
            "pid": None,
        }
    )
    runtime_metadata = _merge_runtime_metadata(revision_id, runtime_metadata)
    _write_runtime_state(
        revision_id,
        status="cancelled",
        stage="cancelled",
        stage_label="已停止",
        message="revision executor 已完成停止请求",
        extra_payload={
            "phase": "cancelled",
            "phaseLabel": "已停止",
            "runtime": runtime_metadata,
            "terminated": terminated,
        },
        finished_at=finished_at,
    )
    revision_repository.upsert_revision(
        revision_id,
        lifecycle_status="stopped",
        finished_at=finished_at,
        latest_job_id=revision_generation_job_id(revision_id),
    )
    return {
        "revisionId": revision_id,
        "terminated": terminated,
        "finishedAt": finished_at,
    }


def _pid_alive(pid: int) -> bool:
    try:
        os.kill(int(pid), 0)
    except ProcessLookupError:
        return False
    except OSError:
        # e.g. EPERM: the process exists but we may not own it. Treat as alive.
        return True
    return True


def _parse_pid_ppid(stat_text: str) -> tuple[int | None, int | None]:
    """Extract ``(pid, ppid)`` from the contents of ``/proc/<pid>/stat``.

    Field 2 (``comm``) is wrapped in parentheses and may itself contain spaces
    or parentheses, so the parse is anchored on the final ``)`` rather than on
    whitespace splitting.
    """
    lparen = stat_text.find("(")
    rparen = stat_text.rfind(")")
    if lparen == -1 or rparen == -1 or rparen < lparen:
        return None, None
    try:
        pid = int(stat_text[:lparen].strip())
    except ValueError:
        return None, None
    rest = stat_text[rparen + 1 :].split()
    # rest[0] = state char, rest[1] = ppid
    if len(rest) < 2:
        return pid, None
    try:
        return pid, int(rest[1])
    except ValueError:
        return pid, None


def _read_process_parentage() -> dict[int, list[int]]:
    """Map each pid to its direct child pids.

    Reads ``/proc`` on Linux (the runner deployment target, incl. WSL) and
    falls back to ``ps`` elsewhere (e.g. macOS, which has no ``/proc``).
    """
    mapping: dict[int, list[int]] = {}
    proc_root = Path("/proc")
    if proc_root.is_dir():
        for entry in proc_root.iterdir():
            if not entry.name.isdigit():
                continue
            try:
                stat_text = (entry / "stat").read_text(encoding="utf-8", errors="replace")
            except OSError:
                continue
            child_pid, ppid = _parse_pid_ppid(stat_text)
            if child_pid is None or ppid is None:
                continue
            mapping.setdefault(ppid, []).append(child_pid)
        return mapping

    try:
        output = subprocess.run(
            ["ps", "-eo", "pid=,ppid="],
            stdout=subprocess.PIPE,
            stderr=subprocess.DEVNULL,
            check=False,
            text=True,
        ).stdout
    except OSError:
        return mapping
    for line in output.splitlines():
        parts = line.split()
        if len(parts) < 2:
            continue
        try:
            child_pid = int(parts[0])
            ppid = int(parts[1])
        except ValueError:
            continue
        mapping.setdefault(ppid, []).append(child_pid)
    return mapping


def _collect_process_tree_pids(pid: int) -> list[int]:
    """Return ``pid`` plus all its descendants, ordered parents-before-children.

    Reverse the result to signal leaves first so a parent cannot reap/mask a
    child's exit (or, worse, leave it orphaned and hanging) before we reach it.
    """
    parent_to_children = _read_process_parentage()
    ordered: list[int] = []
    seen: set[int] = set()
    stack = [int(pid)]
    while stack:
        current = stack.pop()
        if current in seen:
            continue
        seen.add(current)
        ordered.append(current)
        stack.extend(parent_to_children.get(current, ()))
    return ordered


def terminate_process_tree(pid: int) -> bool:
    if int(pid or 0) <= 0:
        return False
    if os.name == "nt":
        completed = subprocess.run(
            ["taskkill", "/PID", str(int(pid)), "/T", "/F"],
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
            check=False,
        )
        return completed.returncode == 0

    # POSIX: the runner spawns child workers (e.g. llm_call_worker) that are not
    # placed in a dedicated process group, so a bare os.kill(pid) leaves them
    # orphaned and hanging (reparented to init). Walk the whole tree and signal
    # every descendant, leaves first, escalating to SIGKILL for anything that
    # ignores SIGTERM within the grace period.
    root_alive = _pid_alive(pid)
    ordered = list(reversed(_collect_process_tree_pids(pid)))

    for target in ordered:
        try:
            os.kill(target, signal.SIGTERM)
        except OSError:
            continue

    deadline = time.monotonic() + 3.0
    while time.monotonic() < deadline:
        if not any(_pid_alive(target) for target in ordered):
            break
        time.sleep(0.1)

    for target in ordered:
        if _pid_alive(target):
            try:
                os.kill(target, signal.SIGKILL)
            except OSError:
                continue

    return root_alive
