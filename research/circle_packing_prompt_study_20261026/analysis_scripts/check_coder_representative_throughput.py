"""One capped prompt-length/throughput diagnostic; no research evaluation."""
import hashlib,json,time,urllib.request
from datetime import datetime,timezone
from pathlib import Path
deployment=Path(__file__).resolve().parent;root=deployment/'coder_throughput_check_20261029'
if root.exists():raise SystemExit('Existing check; inspect instead of repeating')
source=deployment/'coder7b_comparison_draft_20261028'
manifest=json.loads((source/'draft_comparison_manifest.json').read_text())
request=max(manifest['unique_requests'],key=lambda r:len((source/r['request_id']/'prompt.txt').read_bytes()))
prompt=(source/request['request_id']/'prompt.txt').read_text();root.mkdir()
payload=dict(model='qwen2.5-coder:7b',prompt=prompt,stream=True,options=dict(num_predict=32,num_ctx=8192,num_thread=16,num_gpu=0,temperature=.1,seed=request['sampling_seed']))
(root/'registration.json').write_text(json.dumps(dict(purpose='Inference timing only; truncated response is not a research candidate and must not be evaluated',created_utc=datetime.now(timezone.utc).isoformat(),endpoint='http://127.0.0.1:11438',source_request_id=request['request_id'],request=payload,deadline_seconds=180),indent=2))
started=time.perf_counter();chunks=[]
try:
    req=urllib.request.Request('http://127.0.0.1:11438/api/generate',data=json.dumps(payload).encode(),headers={'Content-Type':'application/json'})
    with urllib.request.urlopen(req,timeout=180) as response:
        with (root/'response.jsonl').open('x') as stream:
            for line in response:
                row=json.loads(line);chunks.append(row);stream.write(json.dumps(row)+'\n');stream.flush()
                if time.perf_counter()-started>180:raise TimeoutError('Overall diagnostic deadline')
    last=chunks[-1] if chunks else {};duration=last.get('eval_duration',0)/1e9
    tokens_per_second=last.get('eval_count',0)/duration if duration>0 else None
    estimate=last.get('prompt_eval_duration',0)/1e9+1800/tokens_per_second if tokens_per_second else None
    result=dict(status='completed' if last.get('done') else 'incomplete',wall_seconds=time.perf_counter()-started,visible_text=''.join(c.get('response','') for c in chunks),final=last,tokens_per_second=tokens_per_second,rough_1800_token_seconds=estimate,warning='Short diagnostic projection under current load; not a guaranteed generation runtime')
except Exception as error:result=dict(status='diagnostic_error',error=f'{type(error).__name__}: {error}',chunks=len(chunks),wall_seconds=time.perf_counter()-started)
(root/'result.json').write_text(json.dumps(result,indent=2));print(json.dumps(result),flush=True)
