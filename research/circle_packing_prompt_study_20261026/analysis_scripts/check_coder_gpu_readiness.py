"""Single capped GPU serving check using free capacity, with automatic unload."""
import csv,io,json,os,shutil,socket,subprocess,time,urllib.request
from datetime import datetime,timezone
from pathlib import Path
deployment=Path(__file__).resolve().parent;root=deployment/'coder_gpu_readiness_20261029'
if root.exists():raise SystemExit('Existing readiness record; inspect before repeat')
root.mkdir();gpu_rows=[]
raw=subprocess.check_output(['nvidia-smi','--query-gpu=index,uuid,memory.free,utilization.gpu','--format=csv,noheader,nounits'],text=True)
for row in csv.reader(io.StringIO(raw)):
    index,uuid,free,util=[x.strip() for x in row];gpu_rows.append(dict(index=int(index),uuid=uuid,free_mib=int(free),utilization=int(util)))
eligible=[r for r in gpu_rows if r['free_mib']>=7680 and r['utilization']<=50]
if not eligible:
    (root/'result.json').write_text(json.dumps(dict(status='no_eligible_free_capacity',snapshot=gpu_rows,model_calls=0),indent=2));raise SystemExit('No GPU meets free-capacity guard; no inference')
gpu=min(eligible,key=lambda r:(r['utilization'],-r['free_mib']))
with socket.socket() as sock:
    if sock.connect_ex(('127.0.0.1',11439))==0:raise SystemExit('Port occupied')
settings=dict(OLLAMA_HOST='127.0.0.1:11439',OLLAMA_MODELS=str(deployment/'coder7b_preparation_20261028/models'),CUDA_VISIBLE_DEVICES=gpu['uuid'],OLLAMA_NUM_PARALLEL='1',OLLAMA_MAX_LOADED_MODELS='1',OLLAMA_NOPRUNE='true',OLLAMA_NEW_ENGINE='false',OLLAMA_FLASH_ATTENTION='false')
source=deployment/'coder7b_comparison_draft_20261028';m=json.loads((source/'draft_comparison_manifest.json').read_text())
request=max(m['unique_requests'],key=lambda r:len((source/r['request_id']/'prompt.txt').read_bytes()))
payload=dict(model='qwen2.5-coder:7b',prompt=(source/request['request_id']/'prompt.txt').read_text(),stream=True,keep_alive=0,options=dict(num_predict=32,num_ctx=8192,num_thread=4,num_gpu=99,temperature=.1,seed=request['sampling_seed']))
reg=dict(purpose='Serving check only; truncated response is not a research candidate',created_utc=datetime.now(timezone.utc).isoformat(),gpu=gpu,snapshot=gpu_rows,settings=settings,request=payload,timeout_seconds=120)
(root/'registration.json').write_text(json.dumps(reg,indent=2));env=os.environ.copy();env.update(settings)
with (root/'service.log').open('x') as log:proc=subprocess.Popen([shutil.which('ollama'),'serve'],cwd=root,env=env,stdout=log,stderr=subprocess.STDOUT,start_new_session=True)
(root/'service_identity.json').write_text(json.dumps(dict(pid=proc.pid,cwd=str(root),settings=settings,gpu=gpu),indent=2))
endpoint='http://127.0.0.1:11439'
for attempt in range(30):
    try:json.load(urllib.request.urlopen(endpoint+'/api/tags',timeout=2));break
    except Exception:
        if proc.poll() is not None:raise RuntimeError('Private service exited')
        time.sleep(1)
started=time.perf_counter();chunks=[]
try:
    req=urllib.request.Request(endpoint+'/api/generate',data=json.dumps(payload).encode(),headers={'Content-Type':'application/json'})
    with urllib.request.urlopen(req,timeout=120) as response:
        with (root/'response.jsonl').open('x') as log:
            for line in response:
                row=json.loads(line);chunks.append(row);log.write(json.dumps(row)+'\n');log.flush()
                if time.perf_counter()-started>120:raise TimeoutError('Overall readiness deadline')
    final=chunks[-1] if chunks else {};duration=final.get('eval_duration',0)/1e9;speed=final.get('eval_count',0)/duration if duration>0 else None
    text=''.join(r.get('response','') for r in chunks)
    result=dict(status='ready' if final.get('done') and text.strip() else 'incomplete',text=text,wall_seconds=time.perf_counter()-started,final=final,tokens_per_second=speed,rough_max_generation_seconds=final.get('prompt_eval_duration',0)/1e9+1800/speed if speed else None)
except Exception as error:result=dict(status='readiness_error',error=f'{type(error).__name__}: {error}',wall_seconds=time.perf_counter()-started,chunks=len(chunks))
result['loaded_models_after_request']=json.load(urllib.request.urlopen(endpoint+'/api/ps',timeout=10))
(root/'result.json').write_text(json.dumps(result,indent=2));print(json.dumps(result),flush=True)
if result['status']!='ready':
    import signal
    assert Path(f'/proc/{proc.pid}/cwd').resolve()==root.resolve();os.killpg(proc.pid,signal.SIGTERM)
