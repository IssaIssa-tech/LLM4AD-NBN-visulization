"""Forced-command SSH bridge: only metadata, frozen generation, or own cleanup."""
import hashlib,json,os,signal,sys,time,urllib.request
from pathlib import Path
root=Path(__file__).resolve().parent;manifest=json.loads((root/'draft_comparison_manifest.json').read_text())
request=json.load(sys.stdin);op=request.get('op')
identity=json.loads((root/'runtime_identity.json').read_text());url='http://127.0.0.1:11442'
if op=='metadata':print(json.dumps(identity));raise SystemExit()
if op=='stop':
    pid=identity['service_pid']
    if Path(f'/proc/{pid}').exists():
        assert Path(f'/proc/{pid}/cwd').resolve()==root.resolve()
        assert str(root.parent/'llama_gpu_runtime_b6780/build/bin/llama-server').encode() in Path(f'/proc/{pid}/cmdline').read_bytes()
        os.killpg(pid,signal.SIGTERM)
    print(json.dumps(dict(status='private_service_released',pid=pid)));raise SystemExit()
assert op=='generate','Unsupported bridge operation'
call_id=request['request_id'];entry=next(r for r in manifest['unique_requests'] if r['request_id']==call_id)
folder=root/call_id;payload=json.loads((folder/'api_payload.json').read_text())
assert hashlib.sha256(json.dumps(payload,sort_keys=True).encode()).hexdigest()==entry['payload_sha256']
with (folder/'remote_started.json').open('x') as stream:json.dump(dict(call_id=call_id,payload=payload,purpose='Registered research generation'),stream)
started=time.perf_counter()
try:
    req=urllib.request.Request(url+'/v1/chat/completions',data=json.dumps(payload).encode(),headers={'Content-Type':'application/json'})
    raw=urllib.request.urlopen(req,timeout=880).read()
    with (folder/'remote_raw_response.json').open('xb') as stream:stream.write(raw)
    response=json.loads(raw);print(json.dumps(dict(ok=True,response=response,generation_wall_seconds=time.perf_counter()-started)))
except Exception as error:
    result=dict(ok=False,error=f'{type(error).__name__}: {error}',generation_wall_seconds=time.perf_counter()-started)
    with (folder/'remote_failure.json').open('x') as stream:json.dump(result,stream)
    print(json.dumps(result))
