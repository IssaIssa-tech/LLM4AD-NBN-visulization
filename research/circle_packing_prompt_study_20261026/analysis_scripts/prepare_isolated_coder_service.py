"""Prepare a private CPU-only Ollama service and download; no generation calls."""
import json,os,shutil,socket,subprocess,time,urllib.request
from pathlib import Path
from datetime import datetime,timezone
root=Path(__file__).resolve().parent/'coder7b_preparation_20261028'
if root.exists():raise SystemExit('Preparation folder exists; inspect before retrying')
with socket.socket() as probe:
    if probe.connect_ex(('127.0.0.1',11436))==0:raise SystemExit('Port already occupied; refusing reuse')
binary=shutil.which('ollama');assert binary
root.mkdir();(root/'models').mkdir()
env=os.environ.copy();env.update(OLLAMA_HOST='127.0.0.1:11436',OLLAMA_MODELS=str(root/'models'),CUDA_VISIBLE_DEVICES='-1',OLLAMA_MAX_LOADED_MODELS='1',OLLAMA_NUM_PARALLEL='1')
with (root/'service.log').open('x') as log:
    proc=subprocess.Popen([binary,'serve'],cwd=root,env=env,stdout=log,stderr=subprocess.STDOUT,start_new_session=True)
(root/'service_identity.json').write_text(json.dumps(dict(pid=proc.pid,binary=binary,endpoint=env['OLLAMA_HOST'],model_directory=env['OLLAMA_MODELS'],gpu_visibility=env['CUDA_VISIBLE_DEVICES'],purpose='Download only; CPU-only until a separately configured resource allocation',created_utc=datetime.now(timezone.utc).isoformat()),indent=2))
url='http://127.0.0.1:11436'
for attempt in range(30):
    try:
        json.load(urllib.request.urlopen(url+'/api/tags',timeout=2));break
    except Exception:
        if proc.poll() is not None:raise RuntimeError('Private service exited; inspect service.log')
        time.sleep(1)
else:raise RuntimeError('Private service unavailable')
request=urllib.request.Request(url+'/api/pull',data=json.dumps(dict(model='qwen2.5-coder:7b',stream=True)).encode(),headers={'Content-Type':'application/json'})
last=None
with (root/'download_events.jsonl').open('x') as log:
    with urllib.request.urlopen(request,timeout=1800) as response:
        for line in response:
            row=json.loads(line);log.write(json.dumps(row)+'\n');log.flush();last=row
            (root/'download_progress.json').write_text(json.dumps(row,indent=2))
            if row.get('error'):raise RuntimeError(row['error'])
assert last and last.get('status')=='success',last
tags=json.load(urllib.request.urlopen(url+'/api/tags',timeout=10))
model=next(m for m in tags['models'] if m['name']=='qwen2.5-coder:7b')
show=urllib.request.Request(url+'/api/show',data=json.dumps(dict(model=model['name'])).encode(),headers={'Content-Type':'application/json'})
details=json.load(urllib.request.urlopen(show,timeout=30))
(root/'download_completed.json').write_text(json.dumps(dict(model=model,details=details,completed_utc=datetime.now(timezone.utc).isoformat(),generation_calls=0),indent=2))
print('Download complete; no inference performed',flush=True)
