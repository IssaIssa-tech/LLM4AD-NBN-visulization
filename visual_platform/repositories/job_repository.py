from __future__ import annotations

from datetime import datetime
from typing import Any

from visual_platform.repositories.db_support import get_connection, json_dumps, json_loads


def _now_iso() -> str:
    """Return current local time as ISO string (consistent across all timestamps)."""
    return datetime.now().isoformat(timespec="seconds")


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
    with get_connection() as conn:
        if revision_id:
            # ensure_run_row is removed since runs table is deleted
            pass
        existing_row = conn.execute("SELECT * FROM jobs WHERE job_id = ?", (job_id,)).fetchone()
        existing = dict(existing_row) if existing_row else None
        resolved_stage = stage if stage is not None else (str(existing["stage"]) if existing and existing["stage"] else None)
        resolved_stage_label = stage_label if stage_label is not None else (str(existing["stage_label"]) if existing and existing["stage_label"] else None)
        resolved_current = current if current is not None else (int(existing["current"]) if existing and existing["current"] is not None else None)
        resolved_total = total if total is not None else (int(existing["total"]) if existing and existing["total"] is not None else None)
        resolved_percent = percent if percent is not None else (float(existing["percent"]) if existing and existing["percent"] is not None else None)
        resolved_message = message if message is not None else (str(existing["message"]) if existing and existing["message"] else None)
        resolved_error = error if error is not None else (str(existing["error"]) if existing and existing["error"] else None)
        resolved_payload_json = json_dumps(payload) if payload is not None else (str(existing["payload_json"]) if existing and existing["payload_json"] else None)
        resolved_result_json = json_dumps(result) if result is not None else (str(existing["result_json"]) if existing and existing["result_json"] else None)
        resolved_started_at = started_at if started_at is not None else (str(existing["started_at"]) if existing and existing["started_at"] else None)
        resolved_finished_at = finished_at if finished_at is not None else (str(existing["finished_at"]) if existing and existing["finished_at"] else None)
        now_ts = _now_iso()
        conn.execute(
            """
            INSERT INTO jobs (
                job_id, revision_id, job_type, status, stage, stage_label, current, total,
                percent, message, error, payload_json, result_json, started_at,
                finished_at, created_at, updated_at
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            ON CONFLICT(job_id) DO UPDATE SET
                revision_id = excluded.revision_id,
                status = excluded.status,
                stage = excluded.stage,
                stage_label = excluded.stage_label,
                current = excluded.current,
                total = excluded.total,
                percent = excluded.percent,
                message = excluded.message,
                error = excluded.error,
                payload_json = excluded.payload_json,
                result_json = excluded.result_json,
                started_at = COALESCE(excluded.started_at, jobs.started_at),
                finished_at = COALESCE(excluded.finished_at, jobs.finished_at),
                updated_at = excluded.updated_at
            """,
            (
                job_id,
                revision_id,
                job_type,
                status,
                resolved_stage,
                resolved_stage_label,
                resolved_current,
                resolved_total,
                resolved_percent,
                resolved_message,
                resolved_error,
                resolved_payload_json,
                resolved_result_json,
                resolved_started_at,
                resolved_finished_at,
                now_ts,
                now_ts,
            ),
        )
        existing_payload = None if existing is None else (
            str(existing["status"] or ""),
            str(existing["stage"] or "") or None,
            str(existing["stage_label"] or "") or None,
            int(existing["current"]) if existing["current"] is not None else None,
            int(existing["total"]) if existing["total"] is not None else None,
            float(existing["percent"]) if existing["percent"] is not None else None,
            str(existing["message"] or "") or None,
            str(existing["error"] or "") or None,
        )
        new_payload = (
            str(status or ""),
            resolved_stage,
            resolved_stage_label,
            resolved_current,
            resolved_total,
            resolved_percent,
            resolved_message,
            resolved_error,
        )
        if existing is None or existing_payload != new_payload:
            next_seq_row = conn.execute(
                "SELECT COALESCE(MAX(seq), 0) + 1 AS next_seq FROM job_events WHERE job_id = ?",
                (job_id,),
            ).fetchone()
            next_seq = int(next_seq_row["next_seq"]) if next_seq_row is not None else 1
            conn.execute(
                """
                INSERT INTO job_events (
                    job_id, revision_id, seq, level, status, stage, stage_label, current,
                    total, percent, message, error, payload_json, created_at
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    job_id,
                    revision_id,
                    next_seq,
                    "error" if resolved_error else "info",
                    status,
                    resolved_stage,
                    resolved_stage_label,
                    resolved_current,
                    resolved_total,
                    resolved_percent,
                    resolved_message,
                    resolved_error,
                    resolved_payload_json,
                    _now_iso(),
                ),
            )


def get_job(job_id: str) -> dict[str, Any] | None:
    with get_connection() as conn:
        row = conn.execute("SELECT * FROM jobs WHERE job_id = ?", (job_id,)).fetchone()
        if row is None:
            return None
        payload = dict(row)
        payload["payload"] = json_loads(payload.pop("payload_json", None), {})
        payload["result"] = json_loads(payload.pop("result_json", None), {})
        return payload


def find_job_by_task_id(task_id: str) -> dict[str, Any] | None:
    """按 Celery task id 找回对应的 job。

    派发任务时各 service 会把 ``async_result.id`` 写进 job 的 payload
    （键名 ``taskId``），这里用一次 LIKE 反查。task id 是 UUID，不会误命中。
    """
    normalized = str(task_id or "").strip()
    if not normalized:
        return None
    with get_connection() as conn:
        row = conn.execute(
            """
            SELECT *
            FROM jobs
            WHERE payload_json LIKE ?
            ORDER BY updated_at DESC, created_at DESC
            LIMIT 1
            """,
            (f'%"{normalized}"%',),
        ).fetchone()
        if row is None:
            return None
        payload = dict(row)
        payload["payload"] = json_loads(payload.pop("payload_json", None), {})
        payload["result"] = json_loads(payload.pop("result_json", None), {})
        return payload


def get_latest_job(revision_id: str, job_type: str | None = None) -> dict[str, Any] | None:
    query = "SELECT * FROM jobs WHERE revision_id = ?"
    params: list[Any] = [revision_id]
    if job_type:
        query += " AND job_type = ?"
        params.append(job_type)
    query += " ORDER BY updated_at DESC, created_at DESC LIMIT 1"
    with get_connection() as conn:
        row = conn.execute(query, tuple(params)).fetchone()
        if row is None:
            return None
        payload = dict(row)
        payload["payload"] = json_loads(payload.pop("payload_json", None), {})
        payload["result"] = json_loads(payload.pop("result_json", None), {})
        return payload


def list_jobs_for_revision(revision_id: str) -> list[dict[str, Any]]:
    with get_connection() as conn:
        rows = conn.execute(
            """
            SELECT *
            FROM jobs
            WHERE revision_id = ?
            ORDER BY updated_at DESC, created_at DESC, job_id DESC
            """,
            (revision_id,),
        ).fetchall()
    items: list[dict[str, Any]] = []
    for row in rows:
        payload = dict(row)
        payload["payload"] = json_loads(payload.pop("payload_json", None), {})
        payload["result"] = json_loads(payload.pop("result_json", None), {})
        items.append(payload)
    return items


def list_active_jobs_for_workspace(
    workspace_id: str,
    *,
    statuses: tuple[str, ...] = ("queued", "launch_requested", "running", "stop_requested"),
    job_types: tuple[str, ...] | None = None,
) -> list[dict[str, Any]]:
    normalized_workspace_id = str(workspace_id or "").strip()
    normalized_statuses = tuple(
        str(status or "").strip().lower()
        for status in statuses
        if str(status or "").strip()
    )
    if not normalized_workspace_id or not normalized_statuses:
        return []

    params: list[Any] = [normalized_workspace_id, *normalized_statuses]
    status_placeholders = ", ".join("?" for _ in normalized_statuses)
    query = f"""
        SELECT
            j.*
        FROM jobs j
        JOIN revisions r ON r.revision_id = j.revision_id
        WHERE r.workspace_id = ?
          AND LOWER(j.status) IN ({status_placeholders})
    """
    normalized_job_types: tuple[str, ...] = ()
    if job_types:
        normalized_job_types = tuple(
            str(job_type or "").strip()
            for job_type in job_types
            if str(job_type or "").strip()
        )
        if normalized_job_types:
            query += f" AND j.job_type IN ({', '.join('?' for _ in normalized_job_types)})"
            params.extend(normalized_job_types)
    query += " ORDER BY j.updated_at DESC, j.created_at DESC"

    with get_connection() as conn:
        rows = conn.execute(query, tuple(params)).fetchall()

    items: list[dict[str, Any]] = []
    for row in rows:
        payload = dict(row)
        payload["payload"] = json_loads(payload.pop("payload_json", None), {})
        payload["result"] = json_loads(payload.pop("result_json", None), {})
        items.append(payload)
    return items


def list_job_events_for_revision(revision_id: str, limit: int = 20) -> list[dict[str, Any]]:
    with get_connection() as conn:
        rows = conn.execute(
            """
            SELECT
                e.*,
                j.job_type
            FROM job_events e
            JOIN jobs j ON j.job_id = e.job_id
            WHERE e.revision_id = ?
            ORDER BY e.created_at DESC, e.event_id DESC
            LIMIT ?
            """,
            (revision_id, int(max(1, limit))),
        ).fetchall()
    items: list[dict[str, Any]] = []
    for row in rows:
        payload = dict(row)
        payload["payload"] = json_loads(payload.pop("payload_json", None), {})
        items.append(payload)
    return items


def list_job_events(
    job_id: str,
    *,
    limit: int = 50,
    after_seq: int | None = None,
) -> list[dict[str, Any]]:
    if after_seq is not None:
        # Incremental fetch: return events after the given seq, in ascending order.
        query = """
            SELECT
                e.*,
                j.job_type
            FROM job_events e
            JOIN jobs j ON j.job_id = e.job_id
            WHERE e.job_id = ? AND e.seq > ?
            ORDER BY e.seq ASC LIMIT ?
        """
        params: list[Any] = [job_id, int(after_seq), int(max(1, limit))]
    else:
        # Full fetch: return the LATEST N events (not the earliest), in ascending order.
        query = """
            SELECT
                e.*,
                j.job_type
            FROM job_events e
            JOIN jobs j ON j.job_id = e.job_id
            WHERE e.job_id = ?
            ORDER BY e.seq DESC LIMIT ?
        """
        params = [job_id, int(max(1, limit))]
    with get_connection() as conn:
        rows = conn.execute(query, tuple(params)).fetchall()
    items: list[dict[str, Any]] = []
    for row in rows:
        payload = dict(row)
        payload["payload"] = json_loads(payload.pop("payload_json", None), {})
        items.append(payload)
    # When fetching latest N, rows come back in DESC order; reverse to ASC for display.
    if after_seq is None:
        items.reverse()
    return items
