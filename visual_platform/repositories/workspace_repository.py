from __future__ import annotations

import uuid
from typing import Any

from visual_platform.repositories.db_support import get_connection, json_loads

_UNSET = object()

def create_workspace(
    name: str,
    *,
    description: str | None = None,
    sort_index: int = 0,
) -> str:
    workspace_id = str(uuid.uuid4())
    with get_connection() as conn:
        conn.execute(
            """
            INSERT INTO workspaces (workspace_id, name, description, sort_index, is_active)
            VALUES (?, ?, ?, ?, 0)
            """,
            (workspace_id, name, description, sort_index),
        )
        conn.commit()
    return workspace_id


def list_workspaces() -> list[dict[str, Any]]:
    with get_connection() as conn:
        rows = conn.execute(
            "SELECT * FROM workspaces ORDER BY sort_index ASC, created_at ASC"
        ).fetchall()
        workspaces = [dict(row) for row in rows]
        for workspace in workspaces:
            revision_rows = conn.execute(
                "SELECT * FROM revisions WHERE workspace_id = ? ORDER BY created_at ASC",
                (workspace["workspace_id"],),
            ).fetchall()
            workspace["revisions"] = [dict(row) for row in revision_rows]
        return workspaces


def list_workspace_overview() -> dict[str, Any]:
    with get_connection() as conn:
        workspace_rows = conn.execute(
            """
            SELECT workspace_id, name, description, current_revision_id, sort_index, is_active, created_at, updated_at
            FROM workspaces
            ORDER BY sort_index ASC, created_at ASC
            """
        ).fetchall()
        workspaces = [dict(row) for row in workspace_rows]
        current_revision_ids = [
            str(workspace.get("current_revision_id") or "")
            for workspace in workspaces
            if workspace.get("current_revision_id")
        ]

        revision_rows = conn.execute(
            """
            SELECT revision_id, workspace_id, mode, lifecycle_status, graph_status, config,
                   sample_revision, created_at, started_at
            FROM revisions
            ORDER BY created_at ASC
            """
        ).fetchall()
        revisions_by_workspace: dict[str, list[dict[str, Any]]] = {}
        revisions_by_id: dict[str, dict[str, Any]] = {}
        for row in revision_rows:
            revision = dict(row)
            revision["config"] = json_loads(revision.get("config"), {})
            revisions_by_id[revision["revision_id"]] = revision
            revisions_by_workspace.setdefault(revision["workspace_id"], []).append(revision)

        graph_counts_by_revision: dict[str, int] = {}
        if current_revision_ids:
            placeholders = ",".join("?" for _ in current_revision_ids)
            graph_rows = conn.execute(
                f"""
                SELECT revision_id, COUNT(*) AS cnt
                FROM artifacts
                WHERE revision_id IN ({placeholders})
                  AND artifact_type = 'graph'
                GROUP BY revision_id
                """,
                current_revision_ids,
            ).fetchall()
            graph_counts_by_revision = {
                str(row["revision_id"]): int(row["cnt"] or 0) for row in graph_rows
            }

        best_scores_by_revision: dict[str, float | None] = {}
        if current_revision_ids:
            placeholders = ",".join("?" for _ in current_revision_ids)
            best_rows = conn.execute(
                f"""
                SELECT revision_id, MAX(score) AS best_score
                FROM individuals
                WHERE revision_id IN ({placeholders})
                GROUP BY revision_id
                """,
                current_revision_ids,
            ).fetchall()
            best_scores_by_revision = {
                str(row["revision_id"]): row["best_score"] for row in best_rows
            }

    active_workspace_id = next(
        (
            workspace["workspace_id"]
            for workspace in workspaces
            if int(workspace.get("is_active") or 0) == 1
        ),
        None,
    )
    return {
        "active_workspace_id": active_workspace_id,
        "workspaces": workspaces,
        "revisions_by_workspace": revisions_by_workspace,
        "revisions_by_id": revisions_by_id,
        "graph_counts_by_revision": graph_counts_by_revision,
        "best_scores_by_revision": best_scores_by_revision,
    }


def get_workspace(workspace_id: str) -> dict[str, Any] | None:
    with get_connection() as conn:
        row = conn.execute(
            "SELECT * FROM workspaces WHERE workspace_id = ?",
            (workspace_id,),
        ).fetchone()
        return dict(row) if row else None


def update_workspace(
    workspace_id: str,
    *,
    name: str | object = _UNSET,
    description: str | None | object = _UNSET,
    current_revision_id: str | None | object = _UNSET,
    sort_index: int | object = _UNSET,
    is_active: bool | object = _UNSET,
) -> None:
    updates: list[str] = []
    params: list[Any] = []
    if name is not _UNSET:
        updates.append("name = ?")
        params.append(name)
    if description is not _UNSET:
        updates.append("description = ?")
        params.append(description)
    if current_revision_id is not _UNSET:
        updates.append("current_revision_id = ?")
        params.append(current_revision_id)
    if sort_index is not _UNSET:
        updates.append("sort_index = ?")
        params.append(sort_index)
    if is_active is not _UNSET:
        updates.append("is_active = ?")
        params.append(1 if is_active else 0)
    if not updates:
        return
    updates.append("updated_at = CURRENT_TIMESTAMP")
    params.append(workspace_id)
    with get_connection() as conn:
        conn.execute(
            f"UPDATE workspaces SET {', '.join(updates)} WHERE workspace_id = ?",
            tuple(params),
        )
        conn.commit()


def activate_workspace(workspace_id: str) -> None:
    with get_connection() as conn:
        conn.execute("UPDATE workspaces SET is_active = 0")
        conn.execute(
            "UPDATE workspaces SET is_active = 1 WHERE workspace_id = ?",
            (workspace_id,),
        )
        conn.commit()


def delete_workspace(workspace_id: str) -> None:
    with get_connection() as conn:
        conn.execute("DELETE FROM workspaces WHERE workspace_id = ?", (workspace_id,))
        conn.commit()


def get_active_workspace() -> dict[str, Any] | None:
    with get_connection() as conn:
        row = conn.execute(
            "SELECT * FROM workspaces WHERE is_active = 1 LIMIT 1"
        ).fetchone()
        return dict(row) if row else None


def update_workspace_revision(workspace_id: str, revision_id: str) -> None:
    with get_connection() as conn:
        conn.execute(
            "UPDATE workspaces SET current_revision_id = ?, updated_at = CURRENT_TIMESTAMP WHERE workspace_id = ?",
            (revision_id, workspace_id),
        )
        conn.commit()
