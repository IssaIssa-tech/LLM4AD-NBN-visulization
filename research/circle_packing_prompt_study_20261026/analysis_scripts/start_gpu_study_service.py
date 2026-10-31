"""Start only the study's private server on an idle GPU; do not generate."""
import csv,hashlib,io,json,os,socket,subprocess,time,urllib.request
from datetime import datetime,timezone
from pathlib import Path
root=Path(__file__).resolve().parent;runtime=root.parent/'llama_gpu_runtime_b6780'
if (root/'runtime_identity.json').exists():raise SystemExit('Service identity exists: inspect instead of restarting')
with socket.socket() as sock:
    if sock.connect_ex(('127.0.0.1',11442))==0:raise SystemExit('Port occupied')
raw=subprocess.check_output(['nvidia-smi','--query-gpu=index,uuid,memory.free,utilization.gpu','--format=csv,noheader,nounits'],text=True)
rows=[]
for values in csv.reader(io.StringIO(raw)):
    index,uuid,free,util=[v.strip() for v in values];rows.append(dict(index=int(index),uuid=uuid,free_mib=int(free),utilization=int(util)))
gpu=next((r for r in rows if r['free_mib']>=16384 and r['utilization']==0),None)
assert gpu,'No eligible idle GPU; no service launched'
model=root.parent/'models/blobs/sha256-60e05f2100071479f596b964f89f510f057ce397ea22f2833a0cfe029bfc2463'
digest=hashlib.sha256()
with model.open('rb') as stream:
    for block in iter(lambda:stream.read(8*1024*1024),b''):digest.update(block)
assert digest.hexdigest()=='60e05f2100071479f596b964f89f510f057ce397ea22f2833a0cfe029bfc2463'
binary=runtime/'build/bin/llama-server';env=os.environ.copy();env['CUDA_VISIBLE_DEVICES']=gpu['uuid']
command=[str(binary),'-m',str(model),'-ngl','99','-c','8192','-t','4','-np','1','--host','127.0.0.1','--port','11442','--alias','qwen2.5-coder-7b-q4km']
with (root/'service.log').open('x') as log:child=subprocess.Popen(command,cwd=root,env=env,stdout=log,stderr=subprocess.STDOUT,start_new_session=True)
identity=dict(service_pid=child.pid,service_command=command,gpu=gpu,model_blob_sha256=digest.hexdigest(),binary_sha256=hashlib.sha256(binary.read_bytes()).hexdigest(),runtime_registration=json.loads((runtime/'registration.json').read_text()),generator_host='hits_9',created_utc_host_clock=datetime.now(timezone.utc).isoformat(),bridge_sha256=hashlib.sha256((root/'gpu_study_generate_bridge.py').read_bytes()).hexdigest(),manifest_sha256=hashlib.sha256((root/'draft_comparison_manifest.json').read_bytes()).hexdigest())
for attempt in range(90):
    try:
        health=json.load(urllib.request.urlopen('http://127.0.0.1:11442/health',timeout=2))
        if health.get('status')=='ok':break
    except Exception:
        if child.poll() is not None:raise RuntimeError('Private server exited; inspect service.log')
    time.sleep(1)
else:raise RuntimeError('Health deadline exceeded')
with (root/'runtime_identity.json').open('x') as stream:json.dump(identity,stream,indent=2)
print(json.dumps(dict(status='healthy_no_generation',gpu=gpu,pid=child.pid)))
