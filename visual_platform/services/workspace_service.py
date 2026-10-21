from __future__ import annotations

from pathlib import Path
from typing import Any

from visual_platform.repositories import revision_repository, workspace_repository


def get_revision_dir(revision_id: str | None) -> Path | None:
    requested_revision_id = str(revision_id or "").strip()
    if not requested_revision_id:
        return None
    revision = revision_repository.get_revision_record(requested_revision_id)
    if not revision:
        return None
    config = revision.get("config", {})
    if not isinstance(config, dict):
        return None
    log_dir = str(config.get("log_dir", "") or "").strip()
    if not log_dir:
        return None
    return Path(log_dir).parent


def get_active_workspace() -> dict[str, Any] | None:
    return workspace_repository.get_active_workspace()


def list_workspaces() -> list[dict[str, Any]]:
    return workspace_repository.list_workspaces()


def create_workspace(name: str, *, description: str | None = None) -> str:
    return workspace_repository.create_workspace(name, description=description)


def activate_workspace(workspace_id: str) -> None:
    workspace_repository.activate_workspace(workspace_id)


def delete_workspace(workspace_id: str) -> None:
    workspace_repository.delete_workspace(workspace_id)


def update_workspace_revision(workspace_id: str, revision_id: str) -> None:
    workspace_repository.update_workspace_revision(workspace_id, revision_id)


def set_workspace_revision(workspace_id: str, revision_id: str) -> None:
    revision = revision_repository.get_revision_record(revision_id)
    if not revision:
        raise ValueError("未找到对应 revision。")
    if str(revision.get("workspace_id") or "") != str(workspace_id or ""):
        raise ValueError("该 revision 不属于当前工作台。")
    workspace_repository.update_workspace_revision(workspace_id, revision_id)


def ensure_default_workspace() -> None:
    active_workspace = workspace_repository.get_active_workspace()
    if active_workspace:
        return

    workspaces = workspace_repository.list_workspaces()
    if workspaces:
        workspace_repository.activate_workspace(workspaces[0]["workspace_id"])
        return

    workspace_id = workspace_repository.create_workspace("Default Workspace")
    workspace_repository.activate_workspace(workspace_id)


def get_active_workspace_context() -> dict[str, Any] | None:
    ensure_default_workspace()
    workspace = get_active_workspace()
    if not workspace:
        return None

    from visual_platform.services import job_service, revision_service

    revisions = revision_service.list_revisions_for_workspace(workspace["workspace_id"])
    workspace["revisions"] = revisions

    current_revision = None
    latest_job = None
    current_revision_id = workspace.get("current_revision_id")
    if current_revision_id:
        current_revision = revision_service.get_revision(current_revision_id)
        latest_job_id = current_revision.get("latest_job_id") if current_revision else None
        if latest_job_id:
            latest_job = job_service.get_job(latest_job_id)

    return {
        "workspace": workspace,
        "currentRevision": current_revision,
        "latestJob": latest_job,
    }
