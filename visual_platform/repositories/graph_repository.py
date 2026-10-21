from __future__ import annotations

import hashlib
import json
from typing import Any

from visual_platform.repositories.db_support import get_connection, json_dumps, json_loads


def _stable_json_dumps(payload: dict[str, Any]) -> str:
    return json.dumps(payload, ensure_ascii=True, sort_keys=True, separators=(",", ":"))


def build_graph_artifact_input_digest(
    revision_id: str,
    *,
    variant: str,
    metric: str,
    max_nodes: int,
    sample_revision: int,
    source_revision_id: str | None = None,
    graph_options: dict[str, Any] | None = None,
) -> str:
    payload = {
        "artifactType": "graph",
        "artifactRole": str(variant or "full"),
        "distanceMetric": str(metric or "").strip().lower(),
        "graphOptions": {
            "maxNodes": int(max_nodes),
            "variant": str(variant or "full"),
            **(graph_options or {}),
        },
        "revisionId": str(revision_id),
        "sampleRevision": int(sample_revision),
        "sourceRevisionId": str(source_revision_id or "").strip() or None,
        "schemaVersion": 1,
    }
    return hashlib.sha256(_stable_json_dumps(payload).encode("utf-8")).hexdigest()


def _artifact_role(variant: str) -> str:
    normalized = str(variant or "").strip()
    return normalized or "full"


def _row_to_graph_artifact(row: Any) -> dict[str, Any]:
    payload = dict(row)
    metadata = json_loads(payload.pop("metadata_json", None), {})
    payload["metadata"] = metadata
    payload["artifact_type"] = str(payload.get("artifact_type") or "graph")
    payload["artifact_role"] = str(payload.get("artifact_role") or "full")
    payload["variant"] = payload["artifact_role"]
    payload["path"] = payload.get("storage_uri", "")
    payload["error"] = payload.get("error_message")
    payload["summary"] = metadata.get("summary", {}) if isinstance(metadata, dict) else {}
    payload["metric"] = payload.get("metric") or metadata.get("metric")
    payload["max_nodes"] = payload.get("max_nodes") or metadata.get("maxNodes")
    payload["sample_revision"] = payload.get("sample_revision") or metadata.get("sampleRevision")
    payload["built_at"] = (
        metadata.get("legacyBuiltAt")
        or payload["summary"].get("savedAt")
        or payload.get("created_at")
    )
    return payload


def upsert_graph_artifact(
    revision_id: str,
    *,
    variant: str,
    metric: str,
    max_nodes: int,
    sample_revision: int,
    source_revision_id: str | None,
    path: str,
    status: str,
    input_digest: str | None = None,
    content_digest: str | None = None,
    created_by_job_id: str | None = None,
    error: str | None = None,
    summary: dict[str, Any] | None = None,
    metadata: dict[str, Any] | None = None,
) -> None:
    artifact_role = _artifact_role(variant)
    resolved_input_digest = input_digest or build_graph_artifact_input_digest(
        revision_id,
        variant=artifact_role,
        metric=metric,
        max_nodes=max_nodes,
        sample_revision=sample_revision,
        source_revision_id=source_revision_id,
    )
    artifact_id = f"artifact:{revision_id}:graph:{artifact_role}:{resolved_input_digest[:16]}"
    metadata_payload = {
        "metric": str(metric or "").strip().lower(),
        "maxNodes": int(max_nodes),
        "sampleRevision": int(sample_revision),
        "variant": artifact_role,
        "sourceRevisionId": str(source_revision_id or "").strip() or None,
        "summary": summary or {},
    }
    if metadata:
        metadata_payload.update(metadata)
    metadata_json = json_dumps(metadata_payload)

    with get_connection() as conn:
        conn.execute(
            """
            INSERT INTO artifacts (
                artifact_id, revision_id, artifact_type, artifact_role, format, storage_uri,
                content_digest, input_digest, status, metadata_json, error_message,
                created_by_job_id, created_at, updated_at
            ) VALUES (?, ?, 'graph', ?, 'json', ?, ?, ?, ?, ?, ?, ?, CURRENT_TIMESTAMP, CURRENT_TIMESTAMP)
            ON CONFLICT(revision_id, artifact_type, artifact_role, input_digest) DO UPDATE SET
                storage_uri = excluded.storage_uri,
                content_digest = excluded.content_digest,
                status = excluded.status,
                metadata_json = excluded.metadata_json,
                error_message = excluded.error_message,
                created_by_job_id = COALESCE(excluded.created_by_job_id, artifacts.created_by_job_id),
                updated_at = CURRENT_TIMESTAMP
            """,
            (
                artifact_id,
                revision_id,
                artifact_role,
                path,
                content_digest,
                resolved_input_digest,
                status,
                metadata_json,
                error,
                created_by_job_id,
            ),
        )


def get_graph_artifact(
    revision_id: str,
    *,
    variant: str,
    metric: str,
    max_nodes: int,
    sample_revision: int,
    source_revision_id: str | None = None,
) -> dict[str, Any] | None:
    artifact_role = _artifact_role(variant)
    input_digest = build_graph_artifact_input_digest(
        revision_id,
        variant=artifact_role,
        metric=metric,
        max_nodes=max_nodes,
        sample_revision=sample_revision,
        source_revision_id=source_revision_id,
    )
    with get_connection() as conn:
        row = conn.execute(
            """
            SELECT *
            FROM artifacts
            WHERE revision_id = ?
              AND artifact_type = 'graph'
              AND artifact_role = ?
              AND input_digest = ?
            ORDER BY updated_at DESC
            LIMIT 1
            """,
            (revision_id, artifact_role, input_digest),
        ).fetchone()
        if row is None:
            return None
        return _row_to_graph_artifact(row)


def get_latest_graph_artifact(
    revision_id: str,
    *,
    variant: str = "full",
    status: str | None = None,
) -> dict[str, Any] | None:
    artifact_role = _artifact_role(variant)
    query = """
        SELECT *
        FROM artifacts
        WHERE revision_id = ?
          AND artifact_type = 'graph'
          AND artifact_role = ?
    """
    params: list[Any] = [revision_id, artifact_role]
    if status:
        query += " AND status = ?"
        params.append(status)
    query += " ORDER BY updated_at DESC LIMIT 1"
    with get_connection() as conn:
        row = conn.execute(query, tuple(params)).fetchone()
        if row is None:
            return None
        return _row_to_graph_artifact(row)


def count_graph_artifacts(revision_id: str, *, status: str | None = None) -> int:
    query = "SELECT COUNT(*) as count FROM artifacts WHERE revision_id = ? AND artifact_type = 'graph'"
    params: list[Any] = [revision_id]
    if status:
        query += " AND status = ?"
        params.append(status)
    with get_connection() as conn:
        row = conn.execute(query, tuple(params)).fetchone()
        return int(row["count"]) if row else 0
