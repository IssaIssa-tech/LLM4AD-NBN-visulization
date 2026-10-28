from __future__ import annotations

from flask import Flask
from visual_platform.api.routes.research_history_routes import create_research_history_blueprint
from flask.json.provider import DefaultJSONProvider

from visual_platform.api.routes.artifact_routes import create_artifact_blueprint
from visual_platform.api.routes.basin3d_routes import create_basin3d_blueprint
from visual_platform.api.routes.job_routes import create_job_blueprint
from visual_platform.api.routes.misc_routes import create_misc_blueprint
from visual_platform.api.routes.revision_routes import create_revision_blueprint
from visual_platform.api.routes.ui_routes import create_ui_blueprint
from visual_platform.api.routes.workspace_routes import create_workspace_blueprint
from visual_platform.config import RUNS_DIR, STATIC_DIR
from visual_platform.runtime.database import init_db_schema
from visual_platform.services.graph_query_service import sanitize_json_scalars


class _SafeJSONProvider(DefaultJSONProvider):
    """Flask JSON provider that scrubs non-finite floats (NaN / ±Infinity).

    Python's json module emits ``-Infinity`` / ``NaN`` which are valid for
    ``json.loads`` but rejected by the browser's ``JSON.parse``. Historical
    revisions can carry ``-inf`` scores (invalid solutions) that otherwise leak
    into every workspace/revision/job payload and break the whole frontend.
    """

    def dumps(self, obj, **kwargs):
        return super().dumps(sanitize_json_scalars(obj), **kwargs)


def create_app() -> Flask:
    init_db_schema()
    RUNS_DIR.mkdir(parents=True, exist_ok=True)

    app = Flask(__name__, static_folder=str(STATIC_DIR), static_url_path="/static")
    app.json = _SafeJSONProvider(app)
    app.register_blueprint(create_job_blueprint())
    app.register_blueprint(create_research_history_blueprint())
    app.register_blueprint(create_workspace_blueprint())
    app.register_blueprint(create_revision_blueprint())
    app.register_blueprint(create_artifact_blueprint())
    app.register_blueprint(create_misc_blueprint())
    app.register_blueprint(create_basin3d_blueprint())
    app.register_blueprint(create_ui_blueprint(static_dir=STATIC_DIR))
    return app
