"""One small serving probe, explicitly separate from research generation."""
import json,time,urllib.request
from datetime import datetime,timezone
from pathlib import Path
root=Path(__file__).resolve().parent/'coder_service_probe_20261029'
if root.exists():raise SystemExit('Existing probe; refusing repeat')
root.mkdir();payload=dict(model='qwen2.5-coder:7b',prompt='Reply with OK.',stream=True,options=dict(num_predict=1,num_ctx=2048,num_thread=4,num_gpu=0,temperature=0,seed=20261029))
(root/'request.json').write_text(json.dumps(dict(purpose='Serving diagnostic only, not Circle Packing experiment',request=payload,timeout_seconds=45,started_utc=datetime.now(timezone.utc).isoformat()),indent=2))
started=time.perf_counter();chunks=[]
try:
    req=urllib.request.Request('http://127.0.0.1:11436/api/generate',data=json.dumps(payload).encode(),headers={'Content-Type':'application/json'})
    with urllib.request.urlopen(req,timeout=45) as response:
        with (root/'response.jsonl').open('x') as log:
            for line in response:
                row=json.loads(line);chunks.append(row);log.write(json.dumps(row)+'\n');log.flush()
    result=dict(status='completed' if chunks and chunks[-1].get('done') else 'incomplete',chunks=len(chunks),wall_seconds=time.perf_counter()-started)
except Exception as error:result=dict(status='service_probe_error',error=f'{type(error).__name__}: {error}',wall_seconds=time.perf_counter()-started,chunks=len(chunks))
(root/'result.json').write_text(json.dumps(result,indent=2));print(json.dumps(result),flush=True)
