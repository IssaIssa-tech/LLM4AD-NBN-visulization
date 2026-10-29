"""One short visible-output check on the isolated alternate engine."""
import json,time,urllib.request
from datetime import datetime,timezone
from pathlib import Path
root=Path(__file__).resolve().parent/'coder_visible_output_check_20261029'
if root.exists():raise SystemExit('Existing check: inspect before repeating')
root.mkdir();endpoint='http://127.0.0.1:11438'
payload=dict(model='qwen2.5-coder:7b',prompt='Reply with exactly the word OK.',stream=True,options=dict(num_predict=16,num_ctx=2048,num_thread=4,num_gpu=0,temperature=0,seed=20261029))
(root/'request.json').write_text(json.dumps(dict(purpose='Runtime readiness only; not a research program',created_utc=datetime.now(timezone.utc).isoformat(),endpoint=endpoint,timeout_seconds=60,request=payload),indent=2))
started=time.perf_counter();chunks=[]
try:
    req=urllib.request.Request(endpoint+'/api/generate',data=json.dumps(payload).encode(),headers={'Content-Type':'application/json'})
    with urllib.request.urlopen(req,timeout=60) as response:
        with (root/'response.jsonl').open('x') as log:
            for line in response:
                row=json.loads(line);chunks.append(row);log.write(json.dumps(row)+'\n');log.flush()
    text=''.join(r.get('response','') for r in chunks)
    result=dict(status='visible_output_confirmed' if text.strip() and chunks[-1].get('done') else 'empty_or_incomplete',text=text,wall_seconds=time.perf_counter()-started,final=chunks[-1] if chunks else None)
except Exception as error:result=dict(status='error',error=f'{type(error).__name__}: {error}',wall_seconds=time.perf_counter()-started)
(root/'result.json').write_text(json.dumps(result,indent=2));print(json.dumps(result),flush=True)
