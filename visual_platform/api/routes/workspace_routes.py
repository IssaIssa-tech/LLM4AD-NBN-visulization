from __future__ import annotations

from typing import Any

from flask import Blueprint, jsonify, request

from visual_platform.services.api_contract_service import (
    create_workspace_resource,
    get_workspace_resource,
    list_workspace_revisions_resource,
    list_workspaces_resource,
    patch_workspace_resource,
)


def create_workspace_blueprint() -> Blueprint:
    bp = Blueprint("workspace_routes", __name__)

    @bp.get("/api/workspaces")
    def api_list_workspaces() -> Any:
        return jsonify(list_workspaces_resource())

    @bp.post("/api/workspaces")
    def api_create_workspace() -> Any:
        payload = request.get_json(silent=True) or {}
        response_payload, status_code = create_workspace_resource(payload)
        return jsonify(response_payload), status_code

    @bp.get("/api/workspaces/<workspace_id>")
    def api_get_workspace(workspace_id: str) -> Any:
        response_payload, status_code = get_workspace_resource(workspace_id)
        return jsonify(response_payload), status_code

    @bp.patch("/api/workspaces/<workspace_id>")
    def api_patch_workspace(workspace_id: str) -> Any:
        response_payload, status_code = patch_workspace_resource(
            workspace_id,
            request.get_json(silent=True) or {},
        )
        return jsonify(response_payload), status_code

    @bp.get("/api/workspaces/<workspace_id>/revisions")
    def api_list_workspace_revisions(workspace_id: str) -> Any:
        response_payload, status_code = list_workspace_revisions_resource(workspace_id)
        return jsonify(response_payload), status_code

    return bp
