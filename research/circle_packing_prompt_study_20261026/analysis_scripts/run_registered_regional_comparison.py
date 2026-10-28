"""Register once, then execute frozen requests without automatic regeneration."""
import argparse, hashlib, json, os, re, site, subprocess, sys, time, urllib.request
from datetime import datetime, timezone
from pathlib import Path

def sha(data): return hashlib.sha256(data).hexdigest()
def save(path, value):
    with path.open('x', encoding='utf-8') as stream:
        json.dump(value, stream, indent=2, allow_nan=False)
        stream.flush(); os.fsync(stream.fileno())

def main():
    parser=argparse.ArgumentParser(); parser.add_argument('root',type=Path)
    parser.add_argument('--execute',action='store_true'); args=parser.parse_args()
    root=args.root.resolve(); deployment=root.parent
    dependency='/home/dyy/llm4ad_env/lib/python3.10/site-packages'
    site.addsitedir(dependency); sys.path.remove(dependency)
    private=str(Path(sys.prefix)/'lib/python3.10/site-packages')
    sys.path.insert(sys.path.index(private)+1,dependency);sys.path.insert(0,str(deployment))
    os.environ['VISUAL_PLATFORM_LOCAL_DATA_DIR']=str(deployment/'state')
    os.environ['VISUAL_PLATFORM_DB']=str(deployment/'state/platform.sqlite3')
    import numpy, scipy
    from visual_platform.services.research_history import append_event, capture_configuration, source_graph_identity
    from visual_platform.repositories.revision_repository import get_revision_record, upsert_revision
    from visual_platform.config import RUNS_DIR
    diagnostic=deployment/'regional_representatives_20261028'
    sys.path.insert(0,str(diagnostic))
    from evaluate_circle_prompt_candidates import static_screen
    manifest_bytes=(root/'draft_comparison_manifest.json').read_bytes()
    manifest=json.loads(manifest_bytes); requests=manifest['unique_requests']
    assert len(requests)==14 and len(manifest['analytical_slots'])==16
    for request in requests:
        folder=root/request['request_id']
        assert sha((folder/'prompt.txt').read_text(encoding='utf-8').encode())==request['prompt_sha256']
        assert sha((folder/'parent_candidate.py').read_text(encoding='utf-8').encode())==request['parent']['code_sha256']
    endpoint='http://127.0.0.1:11435'
    tags=json.load(urllib.request.urlopen(endpoint+'/api/tags',timeout=10))
    model=next(m for m in tags['models'] if m['name']=='qwen2.5:3b')
    expected='357c53fb659c5076de1d65ccb0b397446227b71a42be9d1603d46168015c9e4b'
    assert model['digest']==expected
    revision=manifest.get('execution_revision_id','regional-prompt-comparison-20261028'); directory=RUNS_DIR/revision
    registration=dict(manifest_sha256=sha(manifest_bytes),model=model,endpoint=endpoint,
        python=sys.version,numpy=numpy.__version__,scipy=scipy.__version__,
        source_graph_identity=source_graph_identity(manifest['source_platform_revision']),
        evaluator_hashes={p.name:sha(p.read_bytes()) for p in [diagnostic/'evaluate_regional_representatives.py',diagnostic/'evaluate_circle_prompt_candidates.py',deployment/'launch_history_platform.py']},
        runner_sha256=sha(Path(__file__).read_bytes()),order=[r['request_id'] for r in requests],
        generation_timeout_seconds=900,evaluation_timeout_seconds=20,
        sampling=dict(model='qwen2.5:3b',temperature=0.1,num_predict=1800),
        official_verifier_equivalence=False)
    registered=root/'registration.json'
    if registered.exists():
        prior=json.loads(registered.read_text()); assert prior['frozen']==registration,'Registration drift'
        assert get_revision_record(revision),'Missing registered platform revision'
    else:
        assert not get_revision_record(revision),'Existing revision without local registration'
        source=get_revision_record(manifest['source_platform_revision']); assert source
        config=dict(revision_id=revision,workspace_id=source['workspace_id'],mode='registered_prompt_comparison',
            source_revision_id=source['revision_id'],source_graph_identity=registration['source_graph_identity'],
            selected_nodes=[r['parent'] for r in requests],method=registration,llm=registration['sampling'],
            prompt='Frozen per-request prompts; hashes and complete texts in comparison manifest and request events')
        upsert_revision(revision,workspace_id=source['workspace_id'],mode=config['mode'],config=config,lifecycle_status='registered')
        directory.mkdir(parents=True,exist_ok=True); capture_configuration(directory,config)
        save(registered,dict(frozen=registration,registered_utc=datetime.now(timezone.utc).isoformat()))
        append_event(directory,'comparison_registered',dict(registration=registration,manifest=manifest))
    print('Registered',revision,flush=True)
    if not args.execute:return
    # Exclusive lock prevents concurrent executions. A stale lock requires inspection.
    with (root/'execution.lock').open('x') as lock:lock.write(str(os.getpid()))
    upsert_revision(revision,lifecycle_status='running')
    for request in requests:
        folder=root/request['request_id']; outcome=folder/'outcome.json'
        if outcome.exists():continue
        if (folder/'started.json').exists():
            raise RuntimeError('Interrupted request requires inspection; refusing duplicate model call: '+request['request_id'])
        prompt=(folder/'prompt.txt').read_text(); call_id=request['request_id']
        payload=dict(model='qwen2.5:3b',prompt=prompt,stream=False,options=dict(temperature=.1,num_predict=1800,seed=request['sampling_seed']))
        save(folder/'started.json',dict(request=payload,started_utc=datetime.now(timezone.utc).isoformat()))
        append_event(directory,'llm_request',dict(callId=call_id,parent=request['parent'],promptProfile=request['prompt_profile'],request=payload))
        started=time.perf_counter()
        try:
            req=urllib.request.Request(endpoint+'/api/generate',data=json.dumps(payload).encode(),headers={'Content-Type':'application/json'})
            raw=urllib.request.urlopen(req,timeout=900).read()
            with (folder/'raw_response.json').open('xb') as stream:stream.write(raw)
            reply=json.loads(raw);append_event(directory,'llm_response',dict(callId=call_id,response=reply))
            blocks=re.findall(r'```(?:python)?\s*\n(.*?)```',reply.get('response',''),re.S)
            result=dict(status='extraction_failure',score=None)
            if len(blocks)==1:
                candidate=folder/'candidate.py'
                with candidate.open('x') as stream:stream.write(blocks[0].strip()+'\n')
                screening=static_screen(candidate)
                if not screening['ok']:result=dict(status='rejected_static',score=None,screening=screening)
                else:
                    append_event(directory,'evaluation_started',dict(callId=call_id,codeSha256=sha(candidate.read_bytes()),timeoutSeconds=20))
                    try:
                        done=subprocess.run([sys.executable,str(deployment/'launch_history_platform.py'),'--region-worker',str(candidate)],capture_output=True,text=True,timeout=20)
                        result=json.loads(done.stdout) if done.returncode==0 else dict(status='worker_error',score=None,stderr=done.stderr)
                    except subprocess.TimeoutExpired:result=dict(status='timeout',score=None,timeout_seconds=20)
            result.update(call_id=call_id,request=request,generation_done_reason=reply.get('done_reason'),wall_seconds=time.perf_counter()-started)
        except Exception as error:
            result=dict(status='request_or_pipeline_error',score=None,call_id=call_id,error=f'{type(error).__name__}: {error}',wall_seconds=time.perf_counter()-started)
            append_event(directory,'pipeline_failure',result)
        save(outcome,result);append_event(directory,'trial_completed',result)
        print(call_id,result['status'],result.get('score'),flush=True)
    upsert_revision(revision,lifecycle_status='completed')
    append_event(directory,'comparison_completed',dict(uniqueRequests=14,analyticalSlots=16))
    print('Completed',flush=True)

if __name__=='__main__':main()
