"""Bounded local coordinator: direct SSH using existing keys, no tunnel/new credentials."""
import argparse,json,os,subprocess,time,traceback
from pathlib import Path
from ael_pilot_common import NAME,REVISION,H1,H9,sha,load,save,write,payload,mutation_prompt,extract

base=Path(__file__).resolve().parents[1];root=base/'output'/NAME
if not root.exists():root=Path(__file__).resolve().parent
m=load(root/'manifest.json')
keys=Path(os.environ['USERPROFILE'])/'.ssh'
def remote(host,op,data=None,timeout=930):
    if host=='h1':key=keys/'codex_hits1_dyy_ed25519';port='8000';address='10.249.47.6';command=f'{H1}/venv/bin/python {H1}/{NAME}/ael_pilot_history.py {op}'
    else:key=keys/'llm4ad_dyy_10_249_185_134_ed25519';port='8888';address='10.249.185.134';command=f'/usr/bin/python3 {H9}/{NAME}/ael_pilot_gpu.py {op}'
    done=subprocess.run(['ssh','-T','-o','BatchMode=yes','-o','ConnectTimeout=10','-i',str(key),'-p',port,'dyy@'+address,command],input=json.dumps(data or {}),capture_output=True,text=True,encoding='utf-8',timeout=timeout)
    if done.returncode:raise RuntimeError(f'{host} {op}: exit {done.returncode}: {done.stderr[-2500:]}')
    return json.loads(done.stdout)
def event(kind,p):return remote('h1','event',dict(event_type=kind,payload=p))
def perform(chain,operator,parents,code=None):
    cid=chain['crossover_id'] if operator=='cross' else chain['mutation_id'];folder=root/cid;folder.mkdir(exist_ok=True)
    if operator=='cross':api=load(folder/'api_payload.json')
    else:
        prompt=mutation_prompt(root,code);write(folder/'prompt.txt',prompt)
        api=payload(m,prompt,chain['mutation_seed']);save(folder/'api_payload.json',api)
    start=time.perf_counter();save(folder/'started.json',dict(call_id=cid,request=api,parents=parents,client_utc=__import__('datetime').datetime.now(__import__('datetime').timezone.utc).isoformat()))
    event('llm_request',dict(callId=cid,parents=parents,promptProfile='AEL-structural-import-'+operator,selectionPolicy=chain['policy'],chainId=chain['chain_id'],request=api))
    result=remote('h9','generate',dict(call_id=cid,payload=api,upstream_code_sha256=sha(code.encode()) if code is not None else None))
    save(folder/'generation_result.json',result)
    if not result.get('ok'):
        outcome=dict(call_id=cid,chain_id=chain['chain_id'],policy=chain['policy'],operator=operator,status=result.get('status','generation_failure'),score=None,error=result.get('error'),static_eligible=False)
        event('llm_failure',dict(callId=cid,**outcome))
    else:
        response=result['response'];save(folder/'raw_response.json',response)
        event('llm_response',dict(callId=cid,response=response,contextPreflight=result.get('context_preflight'),generationWallSeconds=result.get('generation_wall_seconds')))
        try:source=extract(response)
        except (ValueError,KeyError,IndexError,TypeError) as error:
            outcome=dict(call_id=cid,chain_id=chain['chain_id'],policy=chain['policy'],operator=operator,status='extraction_failure',score=None,error=str(error),static_eligible=False)
            event('pipeline_failure',dict(callId=cid,**outcome))
        else:
            write(folder/'candidate.py',source)
            evaluation=remote('h1','evaluate',dict(call_id=cid,code=source,code_sha256=sha(source.encode())),timeout=80)
            save(folder/'evaluation.json',evaluation)
            outcome=dict(call_id=cid,chain_id=chain['chain_id'],policy=chain['policy'],operator=operator,**evaluation,static_eligible=evaluation['screening']['ok'],code_sha256=sha(source.encode()),finish_reason=response['choices'][0].get('finish_reason'),generation_wall_seconds=result.get('generation_wall_seconds'))
    outcome['client_total_seconds']=time.perf_counter()-start;save(folder/'outcome.json',outcome)
    with (root/'ledger.jsonl').open('a',encoding='utf-8') as f:f.write(json.dumps(outcome,allow_nan=False)+'\n');f.flush();os.fsync(f.fileno())
    print(cid,outcome['status'],outcome.get('score'),flush=True);return outcome

def main():
    parser=argparse.ArgumentParser();parser.add_argument('--register',action='store_true');parser.add_argument('--execute',action='store_true');args=parser.parse_args()
    if args.register:
        identity=remote('h9','metadata');hashes={p.name:sha(p.read_bytes()) for p in [Path(__file__),Path(__file__).with_name('ael_pilot_common.py')]}
        registration=remote('h1','register',dict(runtime_identity=identity,client_script_hashes=hashes));save(root/'registration.json',registration);print('REGISTERED',REVISION,flush=True)
    if not args.execute:return
    assert (root/'registration.json').exists() and not (root/'results.json').exists()
    with (root/'execution.lock').open('x') as f:f.write(str(os.getpid()))
    rows=[];skips=[]
    try:
        for chain_number,chain in enumerate(m['chains'],1):
            cross=perform(chain,'cross',chain['parents']);rows.append(cross)
            if cross['static_eligible']:
                code=(root/chain['crossover_id']/'candidate.py').read_text(encoding='utf-8')
                parent=dict(id='generated:'+chain['crossover_id'],originCallId=chain['crossover_id'],originRevisionId=REVISION,codeSha256=sha(code.encode()),recordedSource=code,nbnPlacementStatus='not_computed')
                rows.append(perform(chain,'mut',[parent],code))
            else:
                reason=dict(callId=chain['mutation_id'],upstreamCallId=chain['crossover_id'],status='not_requested',reason='Crossover did not yield a static-contract-eligible program',upstreamStatus=cross['status'])
                skips.append(reason);save(root/(chain['mutation_id']+'_skipped.json'),reason);event('dependent_mutation_skipped',reason)
            temp=root/'progress.tmp';temp.write_text(json.dumps(dict(completed_chains=chain_number,actual_llm_requests=len(rows),planned_maximum_calls=12,last_completed_chain=chain['chain_id'],outcomes=[dict(call_id=r['call_id'],status=r['status'],score=r.get('score')) for r in rows])),encoding='utf-8');os.replace(temp,root/'progress.json')
        result=dict(status='completed',revision_id=REVISION,manifest_sha256=sha((root/'manifest.json').read_bytes()),actual_llm_requests=len(rows),maximum_calls=12,completed_chains=6,results=rows,dependent_skips=skips)
        save(root/'results.json',result);print(json.dumps(remote('h1','finish',result)),flush=True)
    except Exception as error:
        save(root/'coordinator_failure.json',dict(error=f'{type(error).__name__}: {error}',traceback=traceback.format_exc(),completed_calls=len(rows),policy='No automatic retry or duplicate generation'))
        raise
    finally:
        released=remote('h9','stop',timeout=30);save(root/'service_released.json',released);print(json.dumps(released),flush=True)

if __name__=='__main__':main()
