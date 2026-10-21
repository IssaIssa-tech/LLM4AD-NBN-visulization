from __future__ import annotations

from typing import Any, Dict, List, Optional

from visual_platform.repositories.db_support import get_connection, json_dumps, json_loads

def upsert_revision(
    revision_id: str,
    *,
    workspace_id: Optional[str] = None,
    mode: Optional[str] = None,
    lifecycle_status: Optional[str] = None,
    graph_status: Optional[str] = None,
    config: Optional[dict[str, Any]] = None,
    error: Optional[str] = None,
    started_at: Optional[str] = None,
    finished_at: Optional[str] = None,
    latest_job_id: Optional[str] = None,
    sample_revision: Optional[int] = None,
    display_name: Optional[str] = None,
) -> None:
    with get_connection() as conn:
        row = conn.execute("SELECT 1 FROM revisions WHERE revision_id = ?", (revision_id,)).fetchone()
        if row:
            updates = []
            params = []
            if workspace_id is not None:
                updates.append("workspace_id = ?")
                params.append(workspace_id)
            if mode is not None:
                updates.append("mode = ?")
                params.append(mode)
            if lifecycle_status is not None:
                updates.append("lifecycle_status = ?")
                params.append(lifecycle_status)
            if graph_status is not None:
                updates.append("graph_status = ?")
                params.append(graph_status)
            if config is not None:
                updates.append("config = ?")
                params.append(json_dumps(config))
            if error is not None:
                updates.append("error = ?")
                params.append(error)
            if started_at is not None:
                updates.append("started_at = ?")
                params.append(started_at)
            if finished_at is not None:
                updates.append("finished_at = ?")
                params.append(finished_at)
            if latest_job_id is not None:
                updates.append("latest_job_id = ?")
                params.append(latest_job_id)
            if sample_revision is not None:
                updates.append("sample_revision = ?")
                params.append(sample_revision)
            if display_name is not None:
                # Empty string intentionally clears a previously set name.
                updates.append("display_name = ?")
                params.append(display_name or None)
            
            if updates:
                updates.append("updated_at = CURRENT_TIMESTAMP")
                params.append(revision_id)
                query = f"UPDATE revisions SET {', '.join(updates)} WHERE revision_id = ?"
                conn.execute(query, tuple(params))
        else:
            conn.execute(
                """
                INSERT INTO revisions (
                    revision_id, workspace_id, mode, lifecycle_status, graph_status,
                    config, error, started_at, finished_at, latest_job_id, sample_revision
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    revision_id,
                    workspace_id or "",
                    mode or "",
                    lifecycle_status or "idle",
                    graph_status or "none",
                    json_dumps(config) if config else None,
                    error,
                    started_at,
                    finished_at,
                    latest_job_id,
                    sample_revision or 0,
                )
            )

def insert_revision(revision_id: str, workspace_id: str, mode: str, config: dict) -> None:
    upsert_revision(revision_id, workspace_id=workspace_id, mode=mode, config=config)

def get_revision_record(revision_id: str) -> Optional[Dict[str, Any]]:
    with get_connection() as conn:
        row = conn.execute("SELECT * FROM revisions WHERE revision_id = ?", (revision_id,)).fetchone()
        if not row:
            return None
        res = dict(row)
        res["config"] = json_loads(res.get("config"), {})
        return res

def delete_revision(revision_id: str) -> bool:
    # Child rows (individuals / jobs / job_events / artifacts / graph_artifacts) are
    # removed automatically via ON DELETE CASCADE, which relies on the
    # `PRAGMA foreign_keys = ON` set on every connection.
    with get_connection() as conn:
        cursor = conn.execute("DELETE FROM revisions WHERE revision_id = ?", (revision_id,))
        return cursor.rowcount > 0

def get_sample_revision(revision_id: str) -> int:
    with get_connection() as conn:
        row = conn.execute("SELECT sample_revision FROM revisions WHERE revision_id = ?", (revision_id,)).fetchone()
        return int(row["sample_revision"]) if row else 0

def list_revisions_for_workspace(workspace_id: str) -> List[Dict[str, Any]]:
    with get_connection() as conn:
        rows = conn.execute("SELECT * FROM revisions WHERE workspace_id = ? ORDER BY created_at ASC", (workspace_id,)).fetchall()
        result = []
        for row in rows:
            res = dict(row)
            res["config"] = json_loads(res.get("config"), {})
            result.append(res)
        return result
