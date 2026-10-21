from __future__ import annotations

from typing import Any

from flask import Blueprint, jsonify, request

from visual_platform.services.api_contract_service import (
    get_artifact_content_resource,
    get_artifact_resource,
    get_node_code_resource,
)


def create_artifact_blueprint() -> Blueprint:
    bp = Blueprint("artifact_routes", __name__)

    @bp.get("/api/artifacts/<artifact_id>")
    def api_get_artifact(artifact_id: str) -> Any:
        response_payload, status_code = get_artifact_resource(artifact_id)
        return jsonify(response_payload), status_code

    @bp.get("/api/artifacts/<artifact_id>/content")
    def api_get_artifact_content(artifact_id: str) -> Any:
        response_payload, status_code = get_artifact_content_resource(artifact_id)
        return jsonify(response_payload), status_code

    @bp.get("/api/nodes/<node_id>/code")
    def api_get_node_code(node_id: str) -> Any:
        artifact_id = request.args.get("artifactId")
        try:
            response_payload, status_code = get_node_code_resource(node_id, artifact_id)
        except Exception as exc:  # noqa: BLE001 - route must always return JSON
            response_payload = {
                "ok": False,
                "error": {"code": "node_code_error", "message": f"加载节点代码失败：{exc}"},
            }
            status_code = 500
        return jsonify(response_payload), status_code

    return bp
