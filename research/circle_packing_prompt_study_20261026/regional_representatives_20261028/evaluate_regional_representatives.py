"""Fixed-budget regional reference diagnostic with packing and node provenance."""
import argparse,contextlib,hashlib,io,json,math,subprocess,sys,time
from datetime import datetime,timezone
from pathlib import Path
import numpy as np
from evaluate_circle_prompt_candidates import static_screen,valid_circles

def worker(path):
    started=time.perf_counter();namespace={'__name__':'regional_reference','np':np};row={}
    try:
        with contextlib.redirect_stdout(io.StringIO()),contextlib.redirect_stderr(io.StringIO()):
            exec(compile(path.read_text(),str(path),'exec'),namespace)
            circles=np.asarray(namespace['pack_circles'](26),dtype=float)
        from visual_platform.services.research_history import clean
        row.update(shape=list(circles.shape),circles=clean(circles.tolist()))
        if circles.shape!=(26,3):row.update(status='invalid_shape',score=None)
        elif not np.isfinite(circles).all():row.update(status='nonfinite_output',score=None)
        elif not valid_circles(circles):row.update(status='invalid_geometry',score=None)
        else:row.update(status='valid',score=float(circles[:,2].sum()))
    except Exception as error:row.update(status='exception',score=None,error=f'{type(error).__name__}: {error}')
    row['runtime_seconds']=time.perf_counter()-started
    print(json.dumps(row,allow_nan=False))

def main(root):
    import scipy
    from visual_platform.runtime.database import init_db_schema
    from visual_platform.repositories.revision_repository import get_revision_record,upsert_revision
    from visual_platform.services.research_history import append_event,capture_configuration,source_graph_identity
    from visual_platform.config import RUNS_DIR
    if (root/'results.json').exists() or (root/'ledger.jsonl').exists():raise SystemExit('Existing diagnostic; refusing repeat')
    manifest=json.loads((root/'selection_manifest.json').read_text());init_db_schema()
    source=get_revision_record('circle-history-verified-20261028');assert source
    revision='regional-reference-check-20261028'
    if get_revision_record(revision):raise SystemExit('Existing revision; inspect instead')
    directory=RUNS_DIR/revision;directory.mkdir();(directory/'samples').mkdir()
    graph_identity=source_graph_identity(source['revision_id'])
    config=dict(revision_id=revision,workspace_id=source['workspace_id'],mode='regional_reference_diagnostic',source_revision_id=source['revision_id'],source_graph_identity=graph_identity,log_dir=str(directory/'samples'),selected_nodes=[dict(id=r['node_id'],nbnNodeId=r['nbn_node_id'],sampleOrder=r['sample_order'],regionNodeId=r['region_node_id'],codeSha256=r['code_sha256']) for r in manifest['references']],method=manifest['evaluation_plan'],prompt='No LLM generation: frozen historical reference diagnostic')
    upsert_revision(revision,workspace_id=source['workspace_id'],mode=config['mode'],config=config,lifecycle_status='running')
    capture_configuration(directory,config)
    rows=[];launcher=root.parent/'launch_history_platform.py'
    for reference in manifest['references']:
        path=root/reference['reference_id']/'candidate.py';assert hashlib.sha256(path.read_text().strip().encode()).hexdigest()==reference['code_sha256']
        screening=static_screen(path);started=time.perf_counter()
        if not screening['ok']:result=dict(status='rejected_static',score=None,static_screen=screening)
        else:
            try:
                done=subprocess.run([sys.executable,str(launcher),'--region-worker',str(path)],text=True,capture_output=True,timeout=20)
                if done.returncode:result=dict(status='worker_error',score=None,error=done.stderr[-2500:])
                else:
                    try:result=json.loads(done.stdout)
                    except json.JSONDecodeError:result=dict(status='worker_protocol_error',score=None,stdout=done.stdout[-2000:])
            except subprocess.TimeoutExpired:result=dict(status='timeout',score=None,timeout_seconds=20)
        result['wall_runtime_seconds']=time.perf_counter()-started
        row=dict(reference=reference,evaluation=result,completed_utc=datetime.now(timezone.utc).isoformat())
        rows.append(row);(path.parent/'evaluation.json').write_text(json.dumps(row,indent=2))
        with (root/'ledger.jsonl').open('a') as stream:stream.write(json.dumps(row)+'\n')
        append_event(directory,'historical_reference_evaluated',row)
        (root/'progress.json').write_text(json.dumps(dict(completed=len(rows),results=rows),indent=2))
        print(reference['reference_id'],result['status'],result.get('score'),flush=True)
    payload=dict(manifest=manifest,platform_revision_id=revision,environment=dict(python=sys.version,numpy=np.__version__,scipy=scipy.__version__),results=rows,model_calls=0,completed_utc=datetime.now(timezone.utc).isoformat())
    (root/'results.json').write_text(json.dumps(payload,indent=2))
    upsert_revision(revision,lifecycle_status='completed')
    append_event(directory,'reference_diagnostic_completed',dict(evaluated=len(rows),modelCalls=0,resultsPath=str(root/'results.json')))

if __name__=='__main__':
    parser=argparse.ArgumentParser();parser.add_argument('--worker',type=Path);args=parser.parse_args()
    if args.worker:worker(args.worker)
    else:main(Path(__file__).resolve().parent)
