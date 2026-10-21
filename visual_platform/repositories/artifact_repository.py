from __future__ import annotations

import hashlib
import json
from typing import Any

from visual_platform.repositories.db_support import get_connection, json_dumps, json_loads


def _stable_json_dumps(payload: dict[str, Any]) -> str:
    return json.dumps(payload, ensure_ascii=True, sort_keys=True, separators=(",", ":"))


def _build_artifact_id(
    revision_id: str,
    artifact_type: str,
    artifact_role: str,
    format_name: str,
    storage_uri: str,
    input_digest: str | None,
) -> str:
    identity_payload = {
        "revisionId": revision_id,
        "artifactType": artifact_type,
        "artifactRole": artifact_role,
        "format": format_name,
        "storageUri": storage_uri,
        "inputDigest": input_digest,
    }
    stable_suffix = hashlib.sha256(_stable_json_dumps(identity_payload).encode("utf-8")).hexdigest()[:16]
    return f"artifact:{revision_id}:{artifact_type}:{artifact_role}:{stable_suffix}"


def _row_to_artifact(row: Any) -> dict[str, Any]:
    payload = dict(row)
    metadata = json_loads(payload.pop("metadata_json", None), {})
    payload["metadata"] = metadata if isinstance(metadata, dict) else {}
    payload["error"] = payload.pop("error_message", None)
    return payload


def list_artifacts_for_revision(
    revision_id: str,
    *,
    artifact_type: str | None = None,
    artifact_role: str | None = None,
    status: str | None = None,
) -> list[dict[str, Any]]:
    query = """
        SELECT *
        FROM artifacts
        WHERE revision_id = ?
    """
    params: list[Any] = [revision_id]
    if artifact_type:
        query += " AND artifact_type = ?"
        params.append(artifact_type)
    if artifact_role:
        query += " AND artifact_role = ?"
        params.append(artifact_role)
    if status:
        query += " AND status = ?"
        params.append(status)
    query += " ORDER BY updated_at DESC, created_at DESC"
    with get_connection() as conn:
        rows = conn.execute(query, tuple(params)).fetchall()
    return [_row_to_artifact(row) for row in rows]


def get_artifact(artifact_id: str) -> dict[str, Any] | None:
    with get_connection() as conn:
        row = conn.execute(
            "SELECT * FROM artifacts WHERE artifact_id = ?",
            (artifact_id,),
        ).fetchone()
    if row is None:
        return None
    return _row_to_artifact(row)


def upsert_artifact(
    revision_id: str,
    *,
    artifact_type: str,
    artifact_role: str,
    format_name: str,
    storage_uri: str = "",
    status: str,
    metadata: dict[str, Any] | None = None,
    input_digest: str | None = None,
    content_digest: str | None = None,
    created_by_job_id: str | None = None,
    error: str | None = None,
    artifact_id: str | None = None,
) -> str:
    resolved_artifact_id = artifact_id or _build_artifact_id(
        revision_id,
        str(artifact_type or "").strip(),
        str(artifact_role or "").strip(),
        str(format_name or "").strip(),
        str(storage_uri or "").strip(),
        str(input_digest or "").strip() or None,
    )
    with get_connection() as conn:
        conn.execute(
            """
            INSERT INTO artifacts (
                artifact_id, revision_id, artifact_type, artifact_role, format, storage_uri,
                content_digest, input_digest, status, metadata_json, error_message,
                created_by_job_id, created_at, updated_at
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, CURRENT_TIMESTAMP, CURRENT_TIMESTAMP)
            ON CONFLICT(artifact_id) DO UPDATE SET
                storage_uri = excluded.storage_uri,
                content_digest = excluded.content_digest,
                input_digest = excluded.input_digest,
                status = excluded.status,
                metadata_json = excluded.metadata_json,
                error_message = excluded.error_message,
                created_by_job_id = excluded.created_by_job_id,
                updated_at = CURRENT_TIMESTAMP
            """,
            (
                resolved_artifact_id,
                revision_id,
                artifact_type,
                artifact_role,
                format_name,
                storage_uri,
                content_digest,
                input_digest,
                status,
                json_dumps(metadata or {}),
                error,
                created_by_job_id,
            ),
        )
    return resolved_artifact_id
