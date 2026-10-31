"""Private hits9 service and at-most-once generation; no candidate execution here."""
import csv,io,json,os,signal,socket,subprocess,sys,time,urllib.request
from pathlib import Path
from ael_pilot_common import NAME,MODEL,sha,save,load,write,extract,mutation_prompt,payload

root=Path(__file__).resolve().parent;assert root.name==NAME
m=load(root/'manifest.json');url='http://127.0.0.1:11444'
def api(route,data=None,timeout=10):
    request=urllib.request.Request(url+route,data=None if data is None else json.dumps(data).encode(),headers={'Content-Type':'application/json'})
    return json.load(urllib.request.urlopen(request,timeout=timeout))
def fit(p):
    rendered=api('/apply-template',dict(messages=p['messages']))['prompt']
    tokens=api('/tokenize',dict(content=rendered,add_special=True,parse_special=True))['tokens']
    return dict(input_tokens=len(tokens),maximum_output_tokens=p['max_tokens'],context_size=8192,fits=len(tokens)+p['max_tokens']<=8192,rendered_prompt_sha256=sha(rendered.encode()))
op=sys.argv[1]
if op=='start':
    assert not (root/'runtime_identity.json').exists(),'Existing runtime; inspect'
    with socket.socket() as s:assert s.connect_ex(('127.0.0.1',11444))!=0,'Port in use'
    raw=subprocess.check_output(['nvidia-smi','--query-gpu=index,uuid,memory.free,utilization.gpu','--format=csv,noheader,nounits'],text=True)
    gpus=[dict(zip(['index','uuid','free_mib','utilization'],[v.strip() for v in r])) for r in csv.reader(io.StringIO(raw))]
    gpu=next((r for r in gpus if int(r['free_mib'])>=16384 and int(r['utilization'])==0),None);assert gpu,'No idle eligible GPU'
    model=root.parent/'models/blobs'/('sha256-'+MODEL);binary=root.parent/'llama_gpu_runtime_b6780/build/bin/llama-server'
    h=__import__('hashlib').sha256()
    with model.open('rb') as f:
        for block in iter(lambda:f.read(8*1024*1024),b''):h.update(block)
    assert h.hexdigest()==MODEL and sha(binary.read_bytes())==m['binary_sha256']
    command=[str(binary),'-m',str(model),'-ngl','99','-c','8192','-t','4','-np','1','--host','127.0.0.1','--port','11444','--alias','qwen2.5-coder-7b-q4km']
    with (root/'service.log').open('x') as log:
        child=subprocess.Popen(command,cwd=root,env={**os.environ,'CUDA_VISIBLE_DEVICES':gpu['uuid']},stdout=log,stderr=subprocess.STDOUT,start_new_session=True)
    save(root/'service_started.json',dict(pid=child.pid,command=command,gpu=gpu))
    for _ in range(90):
        try:
            if api('/health',timeout=2).get('status')=='ok':break
        except Exception:
            if child.poll() is not None:raise RuntimeError('Private service exited; inspect service.log')
        time.sleep(1)
    else:raise RuntimeError('Private model health deadline exceeded')
    props=api('/props');save(root/'runtime_props.json',props)
    checks={c['crossover_id']:fit(load(root/c['crossover_id']/'api_payload.json')) for c in m['chains']}
    save(root/'crossover_context_preflight.json',checks);assert all(c['fits'] for c in checks.values())
    log=(root/'service.log').read_text(errors='replace');assert 'offloaded' in log and 'CUDA' in log,'GPU offload evidence missing'
    identity=dict(host=os.uname().nodename,service_pid=child.pid,command=command,gpu=gpu,model_blob_sha256=MODEL,binary_sha256=sha(binary.read_bytes()),runtime_registration=load(root.parent/'llama_gpu_runtime_b6780/registration.json'),manifest_sha256=sha((root/'manifest.json').read_bytes()),props_sha256=sha((root/'runtime_props.json').read_bytes()),chat_template_sha256=sha(str(props.get('chat_template','')).encode()),cross_context_preflight=checks)
    save(root/'runtime_identity.json',identity);print(json.dumps(identity));raise SystemExit()
if op=='metadata':print(json.dumps(load(root/'runtime_identity.json')));raise SystemExit()
if op=='stop':
    identity=load(root/'runtime_identity.json');pid=identity['service_pid']
    if Path(f'/proc/{pid}').exists():
        assert Path(f'/proc/{pid}/cwd').resolve()==root.resolve()
        assert identity['command'][0].encode() in Path(f'/proc/{pid}/cmdline').read_bytes()
        os.killpg(pid,signal.SIGTERM)
    result=dict(status='own_private_service_released',pid=pid);save(root/'service_released.json',result);print(json.dumps(result));raise SystemExit()
assert op=='generate'
request=json.load(sys.stdin);cid=request['call_id'];chain=next(c for c in m['chains'] if cid in [c['crossover_id'],c['mutation_id']])
folder=root/cid;folder.mkdir(exist_ok=True)
if cid==chain['crossover_id']:
    p=load(folder/'api_payload.json');assert sha(json.dumps(p,sort_keys=True).encode())==chain['payload_sha256']
else:
    code=extract(load(root/chain['crossover_id']/'raw_response.json'))
    assert sha(code.encode())==request['upstream_code_sha256'],'Mutation must use actual crossover source'
    p=payload(m,mutation_prompt(root,code),chain['mutation_seed']);save(folder/'api_payload.json',p)
assert p==request['payload'],'Frozen payload mismatch'
check=fit(p);save(folder/'context_preflight.json',check)
if not check['fits']:
    result=dict(ok=False,status='context_overflow',score=None,context_preflight=check);save(folder/'remote_failure.json',result);print(json.dumps(result));raise SystemExit()
with (folder/'remote_started.json').open('x') as f:json.dump(dict(call_id=cid,payload_sha256=sha(json.dumps(p,sort_keys=True).encode()),context_preflight=check),f)
started=time.perf_counter()
try:
    response=api('/v1/chat/completions',p,timeout=880);save(folder/'raw_response.json',response)
    result=dict(ok=True,response=response,generation_wall_seconds=time.perf_counter()-started,context_preflight=check)
except Exception as e:
    result=dict(ok=False,status='generation_failure',error=f'{type(e).__name__}: {e}',generation_wall_seconds=time.perf_counter()-started)
save(folder/'remote_result.json',result);print(json.dumps(result))
