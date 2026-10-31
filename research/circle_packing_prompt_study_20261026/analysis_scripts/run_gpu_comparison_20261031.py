"""Finite GPU study: hits9 generation over restricted SSH, unchanged hits1 evaluation."""
import argparse, hashlib, json, os, re, site, subprocess, sys, time, urllib.request
from datetime import datetime, timezone
from pathlib import Path

def sha(data): return hashlib.sha256(data).hexdigest()
def save(path, value):
    with path.open('x', encoding='utf-8') as stream:
        json.dump(value, stream, indent=2, allow_nan=False)
        stream.flush(); os.fsync(stream.fileno())

def bridge(deployment, payload, timeout=900):
    credentials=deployment/'.transport_keys/gpu_study_20261031'
    command=['ssh','-T','-o','BatchMode=yes','-o','ConnectTimeout=10','-o','StrictHostKeyChecking=yes','-o',f'UserKnownHostsFile={credentials/"known_hosts"}','-i',str(credentials/'key'),'-p','8888','dyy@10.249.185.134']
    done=subprocess.run(command,input=json.dumps(payload),capture_output=True,text=True,timeout=timeout)
    if done.returncode:raise RuntimeError(f'Bridge exited {done.returncode}: {done.stderr[-2000:]}')
    return json.loads(done.stdout)

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
    assert len(requests)==manifest['unique_generation_call_count']
    assert len(manifest['analytical_slots'])==manifest['analytical_slot_count']
    assert len({r['request_id'] for r in requests})==len(requests)
    for request in requests:
        folder=root/request['request_id']
        assert sha((folder/'prompt.txt').read_text(encoding='utf-8').encode())==request['prompt_sha256']
        assert sha((folder/'parent_candidate.py').read_text(encoding='utf-8').encode())==request['parent']['code_sha256']
    endpoint='restricted SSH bridge to hits9 loopback 11442'
    service=bridge(deployment,dict(op='metadata'),60)
    assert service['model_blob_sha256']=='60e05f2100071479f596b964f89f510f057ce397ea22f2833a0cfe029bfc2463'
    assert service['manifest_sha256']==sha(manifest_bytes),'Generator manifest differs'
    model=dict(name='qwen2.5-coder:7b',quantization='Q4_K_M',model_blob_sha256=service['model_blob_sha256'])
    assert manifest['budget']['model']=='qwen2.5-coder:7b'
    # Conservative prompt-size preflight; actual tokenizer counts stay in responses.
    assert max(len((root/r['request_id']/'prompt.txt').read_bytes()) for r in requests)<8192
    revision=manifest.get('execution_revision_id','regional-prompt-comparison-20261028'); directory=RUNS_DIR/revision
    registration=dict(manifest_sha256=sha(manifest_bytes),model=model,endpoint=endpoint,
        python=sys.version,numpy=numpy.__version__,scipy=scipy.__version__,
        source_graph_identity=source_graph_identity(manifest['source_platform_revision']),
        evaluator_hashes={p.name:sha(p.read_bytes()) for p in [diagnostic/'evaluate_regional_representatives.py',diagnostic/'evaluate_circle_prompt_candidates.py',deployment/'launch_history_platform.py']},
        runner_sha256=sha(Path(__file__).read_bytes()),order=[r['request_id'] for r in requests],
        generation_timeout_seconds=900,evaluation_timeout_seconds=20,
        sampling=dict(model='qwen2.5-coder:7b',temperature=0.1,num_predict=1800),
        serving=dict(num_ctx=8192,num_thread=4,gpu_layers=99,service_identity=service,sampling=manifest['serving']['sampling']),
        comparison_caveat='New GPU serving package and host. Within-study settings fixed; no pure parameter-size or cross-package timing causality.',
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
        payload=json.loads((folder/'api_payload.json').read_text())
        assert sha(json.dumps(payload,sort_keys=True).encode())==request['payload_sha256']
        save(folder/'started.json',dict(request=payload,started_utc=datetime.now(timezone.utc).isoformat()))
        append_event(directory,'llm_request',dict(callId=call_id,parent=request['parent'],promptProfile=request['prompt_profile'],request=payload))
        started=time.perf_counter()
        try:
            remote=bridge(deployment,dict(op='generate',request_id=call_id),900)
            save(folder/'bridge_result.json',remote)
            if not remote.get('ok'):raise RuntimeError(remote.get('error','Unknown remote generation failure'))
            reply=remote['response'];save(folder/'raw_response.json',reply)
            append_event(directory,'llm_response',dict(callId=call_id,response=reply,generation_wall_seconds=remote.get('generation_wall_seconds')))
            choice=reply['choices'][0];text=choice['message']['content']
            usage=reply.get('usage',{})
            assert usage.get('prompt_tokens',0)+1800<=8192,'Context-fit check failed'
            blocks=re.findall(r'```(?:python)?\s*\n(.*?)```',text,re.S)
            result=dict(status='extraction_failure',score=None)
            if len(blocks)==1:
                candidate=folder/'candidate.py'
                with candidate.open('x') as stream:stream.write(blocks[0].strip()+'\n')
                append_event(directory,'program_generated',dict(callId=call_id,code=candidate.read_text(),codeSha256=sha(candidate.read_bytes()),parent=request['parent']))
                screening=static_screen(candidate)
                if not screening['ok']:result=dict(status='rejected_static',score=None,screening=screening)
                else:
                    append_event(directory,'evaluation_started',dict(callId=call_id,codeSha256=sha(candidate.read_bytes()),timeoutSeconds=20))
                    try:
                        done=subprocess.run([sys.executable,str(deployment/'launch_history_platform.py'),'--region-worker',str(candidate)],capture_output=True,text=True,timeout=20)
                        result=json.loads(done.stdout) if done.returncode==0 else dict(status='worker_error',score=None,stderr=done.stderr)
                    except subprocess.TimeoutExpired:result=dict(status='timeout',score=None,timeout_seconds=20)
            result.update(call_id=call_id,request=request,generation_done_reason=choice.get('finish_reason'),generation_usage=usage,generation_wall_seconds=remote.get('generation_wall_seconds'),wall_seconds=time.perf_counter()-started)
        except Exception as error:
            result=dict(status='request_or_pipeline_error',score=None,call_id=call_id,error=f'{type(error).__name__}: {error}',wall_seconds=time.perf_counter()-started)
            append_event(directory,'pipeline_failure',result)
        save(outcome,result);append_event(directory,'trial_completed',result)
        print(call_id,result['status'],result.get('score'),flush=True)
    upsert_revision(revision,lifecycle_status='completed')
    append_event(directory,'comparison_completed',dict(uniqueRequests=len(requests),analyticalSlots=len(manifest['analytical_slots'])))
    try:
        released=bridge(deployment,dict(op='stop'),30);save(root/'service_released.json',released)
        append_event(directory,'generation_service_released',released)
    except Exception as error:append_event(directory,'generation_service_cleanup_error',dict(error=str(error)))
    print('Completed',flush=True)

if __name__=='__main__':main()
