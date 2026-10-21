from __future__ import annotations

from pathlib import Path
from typing import Any

from flask import Blueprint, abort, send_from_directory

def create_ui_blueprint(*, static_dir: Path) -> Blueprint:
    bp = Blueprint("ui_routes", __name__)

    @bp.route("/", defaults={"path": ""})
    @bp.route("/<path:path>")
    def catch_all(path: str) -> Any:
        if str(path).startswith("api/"):
            abort(404)
        try:
            return send_from_directory(str(static_dir), path)
        except Exception:
            return send_from_directory(str(static_dir), "index.html")

    return bp
