from pathlib import Path
import re
from flask import Blueprint,abort,jsonify
from visual_platform.config import RUNS_DIR
from visual_platform.services.research_history import read_events
from visual_platform.services.history_view import build_history_view

def create_research_history_blueprint():
    bp=Blueprint('research_history_routes',__name__)
    @bp.get('/api/research-history')
    def runs():
        result=[]
        for directory in RUNS_DIR.iterdir() if RUNS_DIR.is_dir() else []:
            if not directory.is_dir() or directory.resolve().parent!=RUNS_DIR.resolve():continue
            files=list((directory/'research_history').glob('*.json'))
            if files:result.append(dict(revisionId=directory.name,eventCount=len(files),updatedAt=max(p.stat().st_mtime for p in files)))
        return jsonify(dict(runs=sorted(result,key=lambda r:(-r['updatedAt'],r['revisionId']))))
    @bp.get('/api/revisions/<revision_id>/research-history')
    def history(revision_id):
        if not re.fullmatch(r'[A-Za-z0-9_-]+',revision_id):abort(400)
        root=RUNS_DIR.resolve();directory=(root/revision_id).resolve()
        if directory.parent!=root or not directory.is_dir():abort(404)
        events=read_events(directory)
        return jsonify(dict(schemaVersion=2,revisionId=revision_id,events=events,count=len(events),view=build_history_view(events),
            coverage='New instrumented platform runs only; earlier external scripts are not automatically backfilled.'))
    return bp
