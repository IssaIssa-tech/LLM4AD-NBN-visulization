from __future__ import annotations

from typing import Any
from flask import Blueprint, jsonify, request
from visual_platform.services.api_contract_service import (
    delete_revision_resource,
    get_revision_events_resource,
    get_revision_resource,
    list_revision_artifacts_resource,
    rename_revision_resource,
)
from visual_platform.services.region_service import get_region_report

def create_revision_blueprint() -> Blueprint:
    bp = Blueprint("revision_routes", __name__)

    @bp.get("/api/revisions/<revision_id>")
    def api_get_revision(revision_id: str) -> Any:
        response_payload, status_code = get_revision_resource(revision_id)
        return jsonify(response_payload), status_code

    @bp.delete("/api/revisions/<revision_id>")
    def api_delete_revision(revision_id: str) -> Any:
        force_raw = str(request.args.get("force", "") or "").strip().lower()
        force = force_raw in {"1", "true", "yes", "on"}
        response_payload, status_code = delete_revision_resource(revision_id, force=force)
        return jsonify(response_payload), status_code

    @bp.patch("/api/revisions/<revision_id>")
    def api_rename_revision(revision_id: str) -> Any:
        body = request.get_json(silent=True) or {}
        display_name = body.get("displayName", body.get("display_name", ""))
        response_payload, status_code = rename_revision_resource(revision_id, display_name)
        return jsonify(response_payload), status_code

    @bp.get("/api/revisions/<revision_id>/artifacts")
    def api_list_revision_artifacts(revision_id: str) -> Any:
        response_payload, status_code = list_revision_artifacts_resource(
            revision_id,
            artifact_type=str(request.args.get("artifactType", "") or "").strip() or None,
            artifact_role=str(request.args.get("artifactRole", "") or "").strip() or None,
            status=str(request.args.get("status", "") or "").strip() or None,
        )
        return jsonify(response_payload), status_code

    @bp.get("/api/revisions/<revision_id>/events")
    def api_get_revision_events(revision_id: str) -> Any:
        limit_raw = request.args.get("limit", "100")
        try:
            limit = max(1, min(500, int(limit_raw)))
        except (TypeError, ValueError):
            limit = 100
        response_payload, status_code = get_revision_events_resource(revision_id, limit=limit)
        return jsonify(response_payload), status_code

    @bp.get("/api/revisions/<revision_id>/region")
    def api_get_revision_region(revision_id: str) -> Any:
        result, error = get_region_report(revision_id)
        if error is not None:
            return jsonify({"ok": False, "error": error}), 404
        return jsonify({"ok": True, "data": result})

    return bp
