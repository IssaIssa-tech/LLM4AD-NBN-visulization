from __future__ import annotations

import json
from pathlib import Path
from typing import Any, Callable
from urllib.parse import urlparse

from visual_platform.config import BASE_DIR


class ArtifactContentResolutionError(Exception):
    def __init__(
        self,
        message: str,
        *,
        status_code: int = 422,
        code: str = "precondition_failed",
        details: dict[str, Any] | None = None,
    ) -> None:
        super().__init__(message)
        self.message = message
        self.status_code = status_code
        self.code = code
        self.details = details or {}


def _artifact_metadata(artifact: dict[str, Any]) -> dict[str, Any]:
    metadata = artifact.get("metadata", {})
    return metadata if isinstance(metadata, dict) else {}


def _artifact_type_key(artifact: dict[str, Any]) -> tuple[str, str]:
    return (
        str(artifact.get("artifact_type") or "").strip().lower(),
        str(artifact.get("format") or "").strip().lower(),
    )


def _is_remote_uri(storage_uri: str) -> bool:
    if Path(storage_uri).drive:
        return False
    parsed = urlparse(storage_uri)
    return bool(parsed.scheme and parsed.scheme != "file")


def _resolve_storage_path(storage_uri: str) -> Path | None:
    normalized = str(storage_uri or "").strip()
    if not normalized or _is_remote_uri(normalized):
        return None
    parsed = urlparse(normalized)
    if parsed.scheme == "file":
        return Path(parsed.path)
    path = Path(normalized)
    if path.is_absolute():
        return path
    # Handle Windows drive-letter paths when running under WSL:
    # In WSL, Path("D:\\foo") is NOT absolute, so we need to convert
    # it to /mnt/d/foo.
    if path.drive and len(path.drive) == 2 and path.drive[1] == ":":
        drive_letter = path.drive[0].lower()
        wsl_path = Path(f"/mnt/{drive_letter}") / path.relative_to(path.anchor)
        if wsl_path.exists():
            return wsl_path
    return BASE_DIR / path


def _load_json_file(storage_uri: str) -> tuple[Any, str] | None:
    path = _resolve_storage_path(storage_uri)
    if path is None or not path.exists() or not path.is_file():
        return None
    return json.loads(path.read_text(encoding="utf-8")), str(path)


def _load_text_file(storage_uri: str) -> tuple[str, str] | None:
    path = _resolve_storage_path(storage_uri)
    if path is None or not path.exists() or not path.is_file():
        return None
    return path.read_text(encoding="utf-8"), str(path)


def _build_content_payload(
    artifact: dict[str, Any],
    *,
    content_mode: str,
    content_type: str,
    renderable: bool,
    content: Any = None,
    location: str | None = None,
) -> dict[str, Any]:
    return {
        "artifact": artifact,
        "contentMode": content_mode,
        "contentType": content_type,
        "format": artifact.get("format"),
        "renderable": renderable,
        "location": location,
        "content": content,
    }


def _resolve_graph_json_content(artifact: dict[str, Any]) -> dict[str, Any]:
    from visual_platform.services.graph_query_service import slim_graph_for_transport
    storage_uri = str(artifact.get("storage_uri") or "").strip()
    file_payload = _load_json_file(storage_uri)
    if file_payload is not None:
        content, resolved_path = file_payload
        # Strip heavy per-node code so legacy artifacts (built before build-time
        # slimming) also load fast; the full code is fetched on demand per node.
        content = slim_graph_for_transport(content) if isinstance(content, dict) else content
        return _build_content_payload(
            artifact,
            content_mode="file_json",
            content_type="application/vnd.llm4ad.graph+json",
            renderable=True,
            content=content,
            location=resolved_path,
        )

    metadata = _artifact_metadata(artifact)
    summary = metadata.get("summary", {})
    if isinstance(summary, dict) and summary.get("graph") is not None:
        return _build_content_payload(
            artifact,
            content_mode="inline_json",
            content_type="application/vnd.llm4ad.graph+json",
            renderable=True,
            content=slim_graph_for_transport(summary.get("graph")),
        )

    raise ArtifactContentResolutionError(
        "graph artifact 缺少可读取的内容来源。",
        details={
            "artifactType": artifact.get("artifact_type"),
            "format": artifact.get("format"),
            "storageUri": storage_uri or None,
        },
    )


def load_raw_graph_content(artifact: dict[str, Any]) -> dict[str, Any] | None:
    """Load the un-slimmed graph JSON for an artifact (embedded code intact).

    The transported payload is slimmed (heavy per-node code stripped), but the
    on-disk artifact still carries the embedded ``functionPreview``/
    ``programPreview`` for legacy nodes that no longer have an ``individuals``
    row. This lets the node-code endpoint fall back to the file when the DB has
    no record.
    """
    storage_uri = str(artifact.get("storage_uri") or "").strip()
    file_payload = _load_json_file(storage_uri)
    if file_payload is not None:
        content, _ = file_payload
        return content if isinstance(content, dict) else None
    metadata = _artifact_metadata(artifact)
    summary = metadata.get("summary", {})
    if isinstance(summary, dict) and isinstance(summary.get("graph"), dict):
        return summary.get("graph")
    return None


def _resolve_inline_or_file_json_content(
    artifact: dict[str, Any],
    *,
    content_type: str = "application/json",
) -> dict[str, Any]:
    storage_uri = str(artifact.get("storage_uri") or "").strip()
    file_payload = _load_json_file(storage_uri)
    if file_payload is not None:
        content, resolved_path = file_payload
        return _build_content_payload(
            artifact,
            content_mode="file_json",
            content_type=content_type,
            renderable=True,
            content=content,
            location=resolved_path,
        )

    metadata = _artifact_metadata(artifact)
    for key in ("content", "inlineContent"):
        if key in metadata:
            return _build_content_payload(
                artifact,
                content_mode="inline_json",
                content_type=content_type,
                renderable=True,
                content=metadata.get(key),
            )

    raise ArtifactContentResolutionError(
        "artifact 缺少可读取的 JSON 内容来源。",
        details={
            "artifactType": artifact.get("artifact_type"),
            "format": artifact.get("format"),
            "storageUri": storage_uri or None,
        },
    )


def _resolve_text_content(
    artifact: dict[str, Any],
    *,
    content_type: str,
) -> dict[str, Any]:
    storage_uri = str(artifact.get("storage_uri") or "").strip()
    file_payload = _load_text_file(storage_uri)
    if file_payload is not None:
        content, resolved_path = file_payload
        return _build_content_payload(
            artifact,
            content_mode="file_text",
            content_type=content_type,
            renderable=True,
            content=content,
            location=resolved_path,
        )

    metadata = _artifact_metadata(artifact)
    for key in ("content", "inlineContent"):
        if isinstance(metadata.get(key), str):
            return _build_content_payload(
                artifact,
                content_mode="inline_text",
                content_type=content_type,
                renderable=True,
                content=metadata.get(key),
            )

    raise ArtifactContentResolutionError(
        "artifact 缺少可读取的文本内容来源。",
        details={
            "artifactType": artifact.get("artifact_type"),
            "format": artifact.get("format"),
            "storageUri": storage_uri or None,
        },
    )


_RESOLVERS: dict[tuple[str, str], Callable[[dict[str, Any]], dict[str, Any]]] = {
    ("graph", "json"): _resolve_graph_json_content,
    ("config_snapshot", "json"): lambda artifact: _resolve_inline_or_file_json_content(
        artifact,
        content_type="application/json",
    ),
    ("sample_set", "json"): lambda artifact: _resolve_inline_or_file_json_content(
        artifact,
        content_type="application/json",
    ),
    ("report", "txt"): lambda artifact: _resolve_text_content(
        artifact,
        content_type="text/plain; charset=utf-8",
    ),
    ("log", "txt"): lambda artifact: _resolve_text_content(
        artifact,
        content_type="text/plain; charset=utf-8",
    ),
    ("log", "jsonl"): lambda artifact: _resolve_text_content(
        artifact,
        content_type="application/x-ndjson",
    ),
}


def resolve_artifact_content(artifact: dict[str, Any]) -> dict[str, Any]:
    artifact_status = str(artifact.get("status") or "").strip().lower()
    if artifact_status != "ready":
        raise ArtifactContentResolutionError(
            f"artifact 当前状态为 {artifact.get('status')}，内容尚不可读取。",
            details={
                "artifactType": artifact.get("artifact_type"),
                "format": artifact.get("format"),
                "status": artifact.get("status"),
            },
        )

    artifact_key = _artifact_type_key(artifact)
    resolver = _RESOLVERS.get(artifact_key)
    if resolver is None:
        raise ArtifactContentResolutionError(
            "当前 artifact 类型或格式尚未定义内容读取协议。",
            details={
                "artifactType": artifact.get("artifact_type"),
                "format": artifact.get("format"),
            },
        )
    return resolver(artifact)
