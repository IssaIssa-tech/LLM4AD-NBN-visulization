"""按 revision 提供 3D 视图数据的接口。

- GET /api/revisions/<id>/basin3d           NBN 锥树 3D 数据（首次访问现场生成并缓存）
- GET /api/revisions/<id>/mds3d             MDS 语义空间数据（依赖上一步产物）
- GET /api/revisions/<id>/basin3d/status    两份数据是否已就绪（前端用来决定按钮文案）

失败时返回 {"ok": false, "error": {"code", "message"}}，message 里带「下一步怎么办」。
"""

from __future__ import annotations

from typing import Any

from flask import Blueprint, jsonify, request, send_file

from visual_platform.services.basin3d_service import (
    Basin3dError,
    ensure_mds,
    ensure_nbn,
    status as basin3d_status,
)


def create_basin3d_blueprint() -> Blueprint:
    bp = Blueprint("basin3d_routes", __name__)

    def _rebuild_requested() -> bool:
        return str(request.args.get("rebuild", "") or "").strip().lower() in {"1", "true", "yes"}

    def _serve(builder: Any, revision_id: str, kind: str) -> Any:
        try:
            path = builder(revision_id, rebuild=_rebuild_requested())
        except Basin3dError as exc:
            return (
                jsonify({"ok": False, "error": {"code": f"{kind}_unavailable", "message": str(exc)}}),
                409,
            )
        except Exception as exc:  # noqa: BLE001 - 路由必须始终返回 JSON
            return (
                jsonify(
                    {
                        "ok": False,
                        "error": {"code": f"{kind}_error", "message": f"生成 3D 数据失败：{exc}"},
                    }
                ),
                500,
            )
        return send_file(path, mimetype="application/json")

    @bp.get("/api/revisions/<revision_id>/basin3d")
    def api_revision_basin3d(revision_id: str) -> Any:
        return _serve(ensure_nbn, revision_id, "basin3d")

    @bp.get("/api/revisions/<revision_id>/mds3d")
    def api_revision_mds3d(revision_id: str) -> Any:
        return _serve(ensure_mds, revision_id, "mds3d")

    @bp.get("/api/revisions/<revision_id>/basin3d/status")
    def api_revision_basin3d_status(revision_id: str) -> Any:
        return jsonify({"ok": True, "data": basin3d_status(revision_id)})

    return bp
