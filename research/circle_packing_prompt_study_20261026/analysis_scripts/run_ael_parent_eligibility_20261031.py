"""At-most-once AEL historical-parent diagnostic in our private hits1 workspace."""
import argparse,hashlib,json,math,os,site,subprocess,sys,time,zipfile
from collections import Counter
from datetime import datetime,timezone
from pathlib import Path

DEPLOYMENT=Path('/mnt/data/dyy/llm4ad_nbn_research_20261013/platform_history_20261028')
def sha(data):return hashlib.sha256(data).hexdigest()
def save(path,value):
    with path.open('x',encoding='utf-8') as stream:
        json.dump(value,stream,indent=2,allow_nan=False);stream.flush();os.fsync(stream.fileno())
def bootstrap():
    dependency='/home/dyy/llm4ad_env/lib/python3.10/site-packages'
    site.addsitedir(dependency);sys.path.remove(dependency)
    private=str(Path(sys.prefix)/'lib/python3.10/site-packages')
    sys.path.insert(sys.path.index(private)+1,dependency);sys.path.insert(0,str(DEPLOYMENT))
    os.environ.update(VISUAL_PLATFORM_LOCAL_DATA_DIR=str(DEPLOYMENT/'state'),VISUAL_PLATFORM_DB=str(DEPLOYMENT/'state/platform.sqlite3'))
def main():
    parser=argparse.ArgumentParser();parser.add_argument('--unpack',action='store_true');parser.add_argument('--execute',action='store_true');parser.add_argument('--launch',action='store_true');args=parser.parse_args()
    assert Path(__file__).resolve().parent==DEPLOYMENT
    root=DEPLOYMENT/'ael_parent_eligibility_20261031'
    if args.unpack:
        assert not root.exists(),'Existing batch; inspect rather than replace'
        archive=zipfile.ZipFile(DEPLOYMENT/'ael_parent_candidate_upload.zip')
        manifest=json.loads(archive.read('manifest.json'));allowed={'manifest.json',*[c['candidate_file'] for c in manifest['candidates']]}
        assert set(archive.namelist())==allowed
        for name in allowed:assert (root/name).resolve().is_relative_to(root)
        root.mkdir()
        for name in allowed:
            path=root/name;path.parent.mkdir(parents=True,exist_ok=True)
            with path.open('xb') as stream:stream.write(archive.read(name))
    raw=(root/'manifest.json').read_bytes();manifest=json.loads(raw);candidates=manifest['candidates']
    assert len(candidates)==30 and manifest['evaluation']['timeout_seconds']==20
    assert [c['candidate_id'] for c in candidates]==manifest['execution_order']
    for candidate in candidates:
        path=root/candidate['candidate_file']
        assert sha(path.read_bytes())==candidate['transport_bytes_sha256']
        assert sha(path.read_text(encoding='utf-8').strip().encode())==candidate['canonical_code_sha256']
    bootstrap()
    import numpy,scipy
    from visual_platform.runtime.database import init_db_schema
    from visual_platform.config import RUNS_DIR
    from visual_platform.repositories.revision_repository import get_revision_record,upsert_revision
    from visual_platform.services.research_history import append_event,capture_configuration,capture_references,source_graph_identity,read_events
    from visual_platform.services.history_view import build_history_view
    diagnostic=DEPLOYMENT/'regional_representatives_20261028';sys.path.insert(0,str(diagnostic))
    from evaluate_circle_prompt_candidates import static_screen
    init_db_schema();source=get_revision_record(manifest['source_platform_revision']);assert source
    graph_identity=source_graph_identity(source['revision_id'])
    # The archived HTTP export wraps the graph; the imported artifact stores
    # its inner graph. Their byte hashes have different, explicit roles.
    expectation=json.loads((root/'source_graph_expectation.json').read_text())
    reconciliation=json.loads((root/'source_graph_reconciliation.json').read_text())
    assert manifest['source_graph_sha256']==graph_identity['inputDigest']==expectation['archive_export_sha256']
    assert reconciliation['identity']==graph_identity
    assert reconciliation['structural_source_signature']==expectation['structural_source_signature']
    frozen=dict(manifest_sha256=sha(raw),python=sys.version,numpy=numpy.__version__,scipy=scipy.__version__,source_graph_identity=graph_identity,
        runner_sha256=sha(Path(__file__).read_bytes()),evaluator_hashes={p.name:sha(p.read_bytes()) for p in [diagnostic/'evaluate_regional_representatives.py',diagnostic/'evaluate_circle_prompt_candidates.py',DEPLOYMENT/'launch_history_platform.py']},
        graph_source_reconciliation=reconciliation,numerical_thread_limits=manifest['evaluation']['numerical_threads'],evaluation=manifest['evaluation'],execution_order=manifest['execution_order'],model_calls=0,host=os.uname().nodename,logical_cpu_count=os.cpu_count())
    revision=manifest['execution_revision_id'];directory=RUNS_DIR/revision
    if (root/'registration.json').exists():
        assert json.loads((root/'registration.json').read_text())['frozen']==frozen,'Registration drift'
        assert get_revision_record(revision)
    else:
        assert not get_revision_record(revision),'Existing platform revision without this registration'
        directory.mkdir()
        references=[]
        for c in candidates:
            references.append(dict(id=c['node_id'],nbnNodeId=c['nbn_node_id'],regionNodeId=c['region_node_id'],sampleOrder=c['sample_order'],codeSha256=c['canonical_code_sha256'],archivedScore=c['archived_score'],originalShortlistBranch=c['original_shortlist_branch_index'],functionPreview=(root/c['candidate_file']).read_text(encoding='utf-8')))
        config=dict(revision_id=revision,workspace_id=source['workspace_id'],mode='ael_parent_eligibility_diagnostic',source_revision_id=source['revision_id'],source_graph_identity=graph_identity,selected_nodes=references,method=frozen,prompt='No LLM generation: fixed historical AEL parent eligibility diagnostic')
        upsert_revision(revision,workspace_id=source['workspace_id'],mode=config['mode'],config=config,lifecycle_status='registered')
        capture_configuration(directory,config);capture_references(directory,selected_nodes=references)
        save(root/'registration.json',dict(frozen=frozen,registered_utc=datetime.now(timezone.utc).isoformat()))
        append_event(directory,'parent_eligibility_registered',dict(manifest=manifest,registration=frozen))
    print('REGISTERED',revision,flush=True)
    if args.launch:
        assert not (root/'launch.json').exists(),'Existing launch; inspect progress instead'
        with (root/'run.log').open('x') as log:
            child=subprocess.Popen([sys.executable,'-u',str(Path(__file__).resolve()),'--execute'],cwd=DEPLOYMENT,stdin=subprocess.DEVNULL,stdout=log,stderr=log,start_new_session=True)
        save(root/'launch.json',dict(pid=child.pid,launched_utc=datetime.now(timezone.utc).isoformat(),revision_id=revision))
        print('LAUNCHED',child.pid,flush=True);return
    if not args.execute:return
    assert not (root/'results.json').exists(),'Completed diagnostic; refusing repeated execution'
    with (root/'execution.lock').open('x') as stream:stream.write(str(os.getpid()))
    upsert_revision(revision,lifecycle_status='running');append_event(directory,'parent_eligibility_started',dict(pid=os.getpid(),candidateCount=30,modelCalls=0))
    env={**os.environ,**frozen['numerical_thread_limits'],'PYTHONIOENCODING':'utf-8'};rows=[]
    for c in candidates:
        folder=root/c['candidate_id'];folder.mkdir(exist_ok=True);outcome=folder/'outcome.json'
        if outcome.exists():rows.append(json.loads(outcome.read_text()));continue
        assert not (folder/'started.json').exists(),'Interrupted candidate; inspect before any repeat'
        path=root/c['candidate_file'];screening=static_screen(path)
        save(folder/'started.json',dict(candidate=c,evaluation_id=revision+'-'+c['candidate_id'],started_utc=datetime.now(timezone.utc).isoformat(),static_screen=screening))
        started=time.perf_counter();stdout='';stderr=''
        if not screening['ok']:evaluation=dict(status='rejected_static',score=None,static_screen=screening)
        else:
            try:
                done=subprocess.run([sys.executable,str(DEPLOYMENT/'launch_history_platform.py'),'--region-worker',str(path)],capture_output=True,text=True,timeout=20,env=env)
                stdout=done.stdout;stderr=done.stderr
                if done.returncode:evaluation=dict(status='worker_error',score=None,returncode=done.returncode,error=stderr[-3000:])
                else:
                    try:evaluation=json.loads(stdout)
                    except ValueError:evaluation=dict(status='worker_protocol_error',score=None,error='Worker did not return JSON')
            except subprocess.TimeoutExpired as error:
                stdout=error.stdout or '';stderr=error.stderr or ''
                if isinstance(stdout,bytes):stdout=stdout.decode('utf-8',errors='replace')
                if isinstance(stderr,bytes):stderr=stderr.decode('utf-8',errors='replace')
                evaluation=dict(status='timeout',score=None,timeout_seconds=20)
        evaluation['wall_runtime_seconds']=time.perf_counter()-started
        with (folder/'worker_stdout.txt').open('x',encoding='utf-8') as stream:stream.write(stdout)
        with (folder/'worker_stderr.txt').open('x',encoding='utf-8') as stream:stream.write(stderr)
        score=evaluation.get('score');eligible=evaluation.get('status')=='valid' and isinstance(score,(int,float)) and math.isfinite(score) and score>0
        row=dict(candidate=c,evaluation_id=revision+'-'+c['candidate_id'],evaluation=evaluation,eligible_positive_parent=eligible,reaches_research_target=eligible and score>=2.6360,completed_utc=datetime.now(timezone.utc).isoformat())
        save(outcome,row)
        with (root/'ledger.jsonl').open('a',encoding='utf-8') as stream:stream.write(json.dumps(row,allow_nan=False)+'\n');stream.flush();os.fsync(stream.fileno())
        append_event(directory,'historical_reference_evaluated',dict(reference=c,evaluationId=row['evaluation_id'],evaluation=evaluation,eligiblePositiveParent=eligible))
        rows.append(row)
        temporary=root/'progress.tmp';temporary.write_text(json.dumps(dict(completed=len(rows),total=30,outcomes=dict(Counter(r['evaluation']['status'] for r in rows)),eligible=sum(r['eligible_positive_parent'] for r in rows)),indent=2));os.replace(temporary,root/'progress.json')
        print(len(rows),c['candidate_id'],evaluation['status'],score,'eligible='+str(eligible),flush=True)
    result=dict(status='completed',registration=frozen,manifest=manifest,platform_revision_id=revision,results=rows,model_calls=0,outcomes=dict(Counter(r['evaluation']['status'] for r in rows)),eligible_parent_count=sum(r['eligible_positive_parent'] for r in rows),target_hits=sum(r['reaches_research_target'] for r in rows),completed_utc=datetime.now(timezone.utc).isoformat())
    save(root/'results.json',result);upsert_revision(revision,lifecycle_status='completed')
    append_event(directory,'parent_eligibility_completed',dict(evaluated=30,outcomes=result['outcomes'],eligible=result['eligible_parent_count'],modelCalls=0,resultsPath=str(root/'results.json')))
    events=read_events(directory);save(root/'platform_history.json',dict(schemaVersion=2,revisionId=revision,count=len(events),coverage='Historical parent diagnostic; no LLM requests',events=events,view=build_history_view(events)))
    print('COMPLETED',json.dumps(dict(outcomes=result['outcomes'],eligible=result['eligible_parent_count'],target_hits=result['target_hits'])),flush=True)
if __name__=='__main__':main()
