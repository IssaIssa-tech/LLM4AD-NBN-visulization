from __future__ import annotations

from typing import Any

from flask import Blueprint, Response, jsonify, request
from visual_platform.services.api_contract_service import (
    cancel_job_resource,
    get_job_events_resource,
    get_job_resource,
    iter_job_events_stream_resource,
    submit_job_resource,
)

def create_job_blueprint() -> Blueprint:
    bp = Blueprint("job_routes", __name__)

    @bp.post("/api/jobs")
    def api_submit_job() -> Any:
        response_payload, status_code = submit_job_resource(request.get_json(silent=True) or {})
        return jsonify(response_payload), status_code

    @bp.get("/api/jobs/<job_id>")
    def api_get_job(job_id: str) -> Any:
        response_payload, status_code = get_job_resource(job_id)
        return jsonify(response_payload), status_code

    @bp.get("/api/jobs/<job_id>/events")
    def api_job_events(job_id: str) -> Any:
        limit_raw = request.args.get("limit", 50)
        after_seq_raw = request.args.get("afterSeq")
        try:
            limit = max(1, min(200, int(limit_raw)))
        except (TypeError, ValueError):
            limit = 50
        try:
            after_seq = int(after_seq_raw) if after_seq_raw is not None else None
        except (TypeError, ValueError):
            after_seq = None
        response_payload, status_code = get_job_events_resource(job_id, limit=limit, after_seq=after_seq)
        return jsonify(response_payload), status_code

    @bp.get("/api/jobs/<job_id>/events/stream")
    def api_job_events_stream(job_id: str) -> Any:
        return Response(
            iter_job_events_stream_resource(job_id),
            mimetype="text/event-stream",
            headers={
                "Cache-Control": "no-cache",
                "Connection": "keep-alive",
                "X-Accel-Buffering": "no",
            },
        )

    @bp.post("/api/jobs/<job_id>/cancel")
    def api_cancel_job(job_id: str) -> Any:
        response_payload, status_code = cancel_job_resource(job_id)
        return jsonify(response_payload), status_code

    return bp
