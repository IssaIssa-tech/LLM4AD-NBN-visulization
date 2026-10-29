"""One recorded service probe with Flash Attention explicitly disabled."""
import argparse,json,os,shutil,socket,subprocess,time,urllib.request
from datetime import datetime,timezone
from pathlib import Path

def main():
    parser=argparse.ArgumentParser();parser.add_argument('--new-engine',action='store_true');args=parser.parse_args()
    deployment=Path(__file__).resolve().parent;root=deployment/('coder_new_engine_diagnostic_20261029' if args.new_engine else 'coder_attention_diagnostic_20261029')
    port=11438 if args.new_engine else 11437
    if root.exists():raise SystemExit('Existing diagnostic: inspect instead of repeating')
    with socket.socket() as sock:
        if sock.connect_ex(('127.0.0.1',port))==0:raise SystemExit('Port occupied')
    root.mkdir();binary=shutil.which('ollama');assert binary
    models=deployment/'coder7b_preparation_20261028/models';assert models.exists()
    settings=dict(OLLAMA_HOST=f'127.0.0.1:{port}',OLLAMA_MODELS=str(models),CUDA_VISIBLE_DEVICES='-1',OLLAMA_MAX_LOADED_MODELS='1',OLLAMA_NUM_PARALLEL='1',OLLAMA_NOPRUNE='true',OLLAMA_FLASH_ATTENTION='false',OLLAMA_NEW_ENGINE='true' if args.new_engine else 'false')
    env=os.environ.copy();env.update(settings)
    payload=dict(model='qwen2.5-coder:7b',prompt='Reply with OK.',stream=True,options=dict(num_predict=1,num_ctx=2048,num_thread=4,num_gpu=0,temperature=0,seed=20261029))
    registration=dict(purpose='Serving diagnostic, not Circle Packing research',created_utc=datetime.now(timezone.utc).isoformat(),settings=settings,request=payload,timeout_seconds=45,
        rationale='Explicit attention disable, optionally the alternate native engine. These test runtime hypotheses, not proven root causes.',source='https://github.com/ollama/ollama/blob/v0.13.5/llm/server.go#L133-L226')
    (root/'registration.json').write_text(json.dumps(registration,indent=2))
    with (root/'service.log').open('x') as log:
        proc=subprocess.Popen([binary,'serve'],cwd=root,env=env,stdout=log,stderr=subprocess.STDOUT,start_new_session=True)
    (root/'service_identity.json').write_text(json.dumps(dict(pid=proc.pid,binary=binary,cwd=str(root),settings=settings),indent=2))
    endpoint=f'http://127.0.0.1:{port}'
    for attempt in range(30):
        try:json.load(urllib.request.urlopen(endpoint+'/api/tags',timeout=2));break
        except Exception:
            if proc.poll() is not None:raise RuntimeError('Private service exited')
            time.sleep(1)
    else:raise RuntimeError('Service startup failed')
    chunks=[];started=time.perf_counter()
    try:
        req=urllib.request.Request(endpoint+'/api/generate',data=json.dumps(payload).encode(),headers={'Content-Type':'application/json'})
        with urllib.request.urlopen(req,timeout=45) as response:
            with (root/'response.jsonl').open('x') as stream:
                for line in response:
                    row=json.loads(line);chunks.append(row);stream.write(json.dumps(row)+'\n');stream.flush()
        result=dict(status='completed' if chunks and chunks[-1].get('done') else 'incomplete',chunks=len(chunks),wall_seconds=time.perf_counter()-started,final=chunks[-1] if chunks else None)
    except Exception as error:result=dict(status='probe_error',error=f'{type(error).__name__}: {error}',chunks=len(chunks),wall_seconds=time.perf_counter()-started)
    (root/'result.json').write_text(json.dumps(result,indent=2));print(json.dumps(result),flush=True)
    if result['status']!='completed':
        # Only terminate our own newly spawned service process group.
        import signal
        assert Path(f'/proc/{proc.pid}/cwd').resolve()==root.resolve()
        os.killpg(proc.pid,signal.SIGTERM)
        (root/'cleanup.json').write_text(json.dumps(dict(terminated_private_process_group=proc.pid,reason='Diagnostic did not produce a final response')))

if __name__=='__main__':main()
