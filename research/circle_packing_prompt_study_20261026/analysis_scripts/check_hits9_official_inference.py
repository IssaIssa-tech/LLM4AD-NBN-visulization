"""Single readiness check using the complete official private runtime."""
import csv,io,json,os,socket,subprocess,time,urllib.request
from datetime import datetime,timezone
from pathlib import Path
root=Path(__file__).resolve().parent;out=root/'official_gpu_inference_check'
if out.exists():raise SystemExit('Existing check; inspect instead of repeating')
out.mkdir();rows=[]
raw=subprocess.check_output(['nvidia-smi','--query-gpu=index,uuid,memory.free,utilization.gpu','--format=csv,noheader,nounits'],text=True)
for row in csv.reader(io.StringIO(raw)):
    index,uuid,free,util=[v.strip() for v in row];rows.append(dict(index=int(index),uuid=uuid,free_mib=int(free),utilization=int(util)))
eligible=[r for r in rows if r['free_mib']>=16384 and r['utilization']==0]
if not eligible:(out/'result.json').write_text(json.dumps(dict(status='no_idle_gpu',snapshot=rows)));raise SystemExit('No idle GPU')
gpu=eligible[0]
with socket.socket() as sock:
    if sock.connect_ex(('127.0.0.1',11440))==0:raise SystemExit('Port occupied')
settings=dict(OLLAMA_HOST='127.0.0.1:11440',OLLAMA_MODELS=str(root/'models'),CUDA_VISIBLE_DEVICES=gpu['uuid'],OLLAMA_NUM_PARALLEL='1',OLLAMA_MAX_LOADED_MODELS='1',OLLAMA_NOPRUNE='true',OLLAMA_NEW_ENGINE='false',OLLAMA_FLASH_ATTENTION='false',OLLAMA_LOAD_TIMEOUT='60s')
env=os.environ.copy();env.update(settings)
payload=dict(model='qwen2.5-coder:7b',prompt=(root/'representative_prompt.txt').read_text(),stream=True,keep_alive=0,options=dict(num_predict=32,num_ctx=8192,num_thread=4,num_gpu=99,temperature=.1,seed=202612738))
(out/'registration.json').write_text(json.dumps(dict(purpose='Runtime readiness only; partial code must not be evaluated as a research candidate',created_utc=datetime.now(timezone.utc).isoformat(),gpu=gpu,settings=settings,request=payload,deadline_seconds=90),indent=2))
with (out/'service.log').open('x') as log:proc=subprocess.Popen([str(root/'official_runtime_setup/install/bin/ollama'),'serve'],cwd=root,env=env,stdout=log,stderr=subprocess.STDOUT,start_new_session=True)
(out/'service_identity.json').write_text(json.dumps(dict(pid=proc.pid,settings=settings,gpu=gpu),indent=2))
url='http://127.0.0.1:11440'
for attempt in range(30):
    try:json.load(urllib.request.urlopen(url+'/api/tags',timeout=2));break
    except Exception:
        if proc.poll() is not None:raise RuntimeError('Service exited')
        time.sleep(1)
started=time.perf_counter();chunks=[];device=None
try:
    req=urllib.request.Request(url+'/api/generate',data=json.dumps(payload).encode(),headers={'Content-Type':'application/json'})
    with urllib.request.urlopen(req,timeout=90) as response:
        with (out/'response.jsonl').open('x') as log:
            for line in response:
                row=json.loads(line);chunks.append(row);log.write(json.dumps(row)+'\n');log.flush()
                if device is None:device=json.load(urllib.request.urlopen(url+'/api/ps',timeout=5))
                if time.perf_counter()-started>90:raise TimeoutError('Overall readiness deadline')
    last=chunks[-1] if chunks else {};text=''.join(r.get('response','') for r in chunks)
    duration=last.get('eval_duration',0)/1e9;speed=last.get('eval_count',0)/duration if duration>0 else None
    result=dict(status='ready' if text.strip() and last.get('done') and any(m.get('size_vram',0)>0 for m in (device or {}).get('models',[])) else 'not_ready',text=text,wall_seconds=time.perf_counter()-started,device=device,final=last,tokens_per_second=speed,rough_max_generation_seconds=last.get('prompt_eval_duration',0)/1e9+1800/speed if speed else None)
except Exception as error:result=dict(status='readiness_error',error=f'{type(error).__name__}: {error}',wall_seconds=time.perf_counter()-started,chunks=len(chunks))
(out/'result.json').write_text(json.dumps(result,indent=2));print(json.dumps(result),flush=True)
if result['status']!='ready':
    import signal
    assert Path(f'/proc/{proc.pid}/cwd').resolve()==root.resolve();os.killpg(proc.pid,signal.SIGTERM)
