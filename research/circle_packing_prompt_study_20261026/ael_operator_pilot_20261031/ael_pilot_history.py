"""Register evidence, preserve lineage, evaluate once, and export on private hits1."""
import json,os,site,subprocess,sys,time
from pathlib import Path
from ael_pilot_common import NAME,REVISION,H1,sha,load,save,write

root=Path(__file__).resolve().parent;assert root.name==NAME
deployment=Path(H1);dependency='/home/dyy/llm4ad_env/lib/python3.10/site-packages'
site.addsitedir(dependency);sys.path.remove(dependency)
private=str(Path(sys.prefix)/'lib/python3.10/site-packages');sys.path.insert(sys.path.index(private)+1,dependency);sys.path.insert(0,str(deployment))
os.environ.update(VISUAL_PLATFORM_LOCAL_DATA_DIR=str(deployment/'state'),VISUAL_PLATFORM_DB=str(deployment/'state/platform.sqlite3'))
import numpy,scipy
from visual_platform.runtime.database import init_db_schema
from visual_platform.repositories.revision_repository import get_revision_record,upsert_revision
from visual_platform.services.research_history import append_event,capture_configuration,capture_references,source_graph_identity,read_events
from visual_platform.services.history_view import build_history_view
from visual_platform.config import RUNS_DIR
diag=deployment/'regional_representatives_20261028';sys.path.insert(0,str(diag))
from evaluate_circle_prompt_candidates import static_screen
init_db_schema();m=load(root/'manifest.json');directory=RUNS_DIR/REVISION
op=sys.argv[1];request={} if sys.stdin.isatty() else json.load(sys.stdin)
allowed={c[k] for c in m['chains'] for k in ['crossover_id','mutation_id']}
if op=='register':
    assert not get_revision_record(REVISION),'Existing registration; inspect'
    assert source_graph_identity(m['source_platform_revision'])==m['source_graph_identity']
    hashes={p.name:sha(p.read_bytes()) for p in [diag/'evaluate_regional_representatives.py',diag/'evaluate_circle_prompt_candidates.py',deployment/'launch_history_platform.py']}
    assert hashes==m['evaluator_hashes']
    runtime=request['runtime_identity'];assert runtime['manifest_sha256']==sha((root/'manifest.json').read_bytes()) and runtime['model_blob_sha256']==m['model_blob_sha256']
    frozen=dict(manifest_sha256=sha((root/'manifest.json').read_bytes()),runtime_identity=runtime,python=sys.version,numpy=numpy.__version__,scipy=scipy.__version__,evaluator_hashes=hashes,script_hashes={p.name:sha(p.read_bytes()) for p in root.glob('*.py')},client_script_hashes=request['client_script_hashes'])
    assert numpy.__version__=='1.26.4' and scipy.__version__=='1.15.3'
    source=get_revision_record(m['source_platform_revision']);refs={p['id']:p for c in m['chains'] for p in c['parents']}
    directory.mkdir();config=dict(revision_id=REVISION,workspace_id=source['workspace_id'],mode='ael_operator_pilot',source_revision_id=m['source_platform_revision'],source_graph_identity=m['source_graph_identity'],selected_nodes=list(refs.values()),method=m,serving=frozen,prompt='AEL crossover followed by mutation of the actual crossover output; see each recorded request')
    upsert_revision(REVISION,workspace_id=source['workspace_id'],mode=config['mode'],config=config,lifecycle_status='registered');capture_configuration(directory,config);capture_references(directory,selected_nodes=list(refs.values()))
    save(root/'registration.json',dict(frozen=frozen));append_event(directory,'operator_pilot_registered',dict(manifest=m,registration=frozen));print(json.dumps(dict(status='registered',revision=REVISION,frozen=frozen)));raise SystemExit()
assert (root/'registration.json').exists()
if op=='event':
    assert request['event_type'] in ['llm_request','llm_response','llm_failure','pipeline_failure','program_generated','trial_completed','dependent_mutation_skipped']
    p=request['payload'];assert p.get('callId') in allowed
    if request['event_type']=='llm_request':
        folder=root/p['callId'];folder.mkdir(exist_ok=True);save(folder/'request_recorded.json',p)
        upsert_revision(REVISION,lifecycle_status='running')
    event_id=append_event(directory,request['event_type'],p);print(json.dumps(dict(event_id=event_id)));raise SystemExit()
if op=='evaluate':
    cid=request['call_id'];assert cid in allowed
    folder=root/cid;folder.mkdir(exist_ok=True);code=request['code'];assert sha(code.encode())==request['code_sha256']
    write(folder/'candidate.py',code);screen=static_screen(folder/'candidate.py');save(folder/'evaluation_started.json',dict(static_screen=screen,code_sha256=request['code_sha256']))
    append_event(directory,'program_generated',dict(callId=cid,code=code,codeSha256=request['code_sha256']))
    eid=REVISION+'-'+cid;stdout='';stderr='';start=time.perf_counter()
    if not screen['ok']:result=dict(status='rejected_static',score=None,screening=screen)
    else:
        append_event(directory,'evaluation_started',dict(callId=cid,evaluationId=eid,program=code))
        try:
            done=subprocess.run([sys.executable,str(deployment/'launch_history_platform.py'),'--region-worker',str(folder/'candidate.py')],capture_output=True,text=True,timeout=20,env={**os.environ,**m['numerical_threads'],'PYTHONIOENCODING':'utf-8'})
            stdout=done.stdout;stderr=done.stderr
            if done.returncode:result=dict(status='worker_error',score=None,returncode=done.returncode,error=stderr[-3000:])
            else:
                try:result=json.loads(stdout)
                except ValueError:result=dict(status='worker_protocol_error',score=None,error='Worker response was not JSON')
        except subprocess.TimeoutExpired as error:
            stdout=error.stdout or '';stderr=error.stderr or ''
            if isinstance(stdout,bytes):stdout=stdout.decode('utf-8',errors='replace')
            if isinstance(stderr,bytes):stderr=stderr.decode('utf-8',errors='replace')
            result=dict(status='timeout',score=None,timeout_seconds=20)
    result.update(wall_runtime_seconds=time.perf_counter()-start,screening=screen,evaluation_id=eid)
    write(folder/'worker_stdout.txt',stdout);write(folder/'worker_stderr.txt',stderr);save(folder/'evaluation.json',result)
    if 'circles' in result:append_event(directory,'packing_output',dict(callId=cid,evaluationId=eid,provenance='Actual returned coordinates from one isolated evaluation',**{k:result[k] for k in ['circles','shape'] if k in result}))
    append_event(directory,'evaluation_finished',dict(callId=cid,evaluationId=eid,status=result['status'],score=result.get('score'),runtimeSeconds=result['wall_runtime_seconds']))
    append_event(directory,'trial_completed',dict(callId=cid,**result));print(json.dumps(result,allow_nan=False));raise SystemExit()
if op in ['export','finish']:
    if op=='finish':
        save(root/'results.json',request);upsert_revision(REVISION,lifecycle_status='completed');append_event(directory,'operator_pilot_completed',request)
    events=read_events(directory);view=build_history_view(events);result=dict(schemaVersion=2,revisionId=REVISION,count=len(events),events=events,view=view)
    # Versioned exports never overwrite previous recorded evidence.
    filename='platform_history.json' if op=='finish' else 'platform_history_snapshot.json'
    save(root/filename,result);print(json.dumps(dict(count=len(events),summary=view['summary'])));raise SystemExit()
raise ValueError('Unsupported operation')
