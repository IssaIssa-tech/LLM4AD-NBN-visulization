from pathlib import Path
import re
from flask import Blueprint,abort,jsonify
from visual_platform.config import RUNS_DIR
from visual_platform.services.research_history import read_events

def create_research_history_blueprint():
    bp=Blueprint('research_history_routes',__name__)
    @bp.get('/api/revisions/<revision_id>/research-history')
    def history(revision_id):
        if not re.fullmatch(r'[A-Za-z0-9_-]+',revision_id):abort(400)
        root=RUNS_DIR.resolve();directory=(root/revision_id).resolve()
        if directory.parent!=root or not directory.is_dir():abort(404)
        events=read_events(directory)
        return jsonify(dict(revisionId=revision_id,events=events,count=len(events),
            coverage='New instrumented platform runs only; earlier external scripts are not automatically backfilled.'))
    return bp
