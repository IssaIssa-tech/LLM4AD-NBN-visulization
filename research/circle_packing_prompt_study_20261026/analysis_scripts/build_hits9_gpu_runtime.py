"""Build a pinned private GGUF GPU runtime and perform one readiness call."""
import csv,hashlib,io,json,os,signal,stat,subprocess,tarfile,time,urllib.request,zipfile
from datetime import datetime,timezone
from pathlib import Path
root=Path(__file__).resolve().parent;out=root/'llama_gpu_runtime_b6780'
if out.exists():raise SystemExit('Existing build; inspect rather than repeat')
out.mkdir()
def record(name,value):(out/name).write_text(json.dumps(value,indent=2))
def download(url,path,expected=None):
    h=hashlib.sha256()
    with urllib.request.urlopen(url,timeout=120) as response,path.open('xb') as stream:
        while True:
            data=response.read(1024*1024)
            if not data:break
            stream.write(data);h.update(data)
    if expected:assert h.hexdigest()==expected,'Download hash mismatch'
    return h.hexdigest()
def run(command,cwd,log,timeout=900,env=None):
    with (out/log).open('x') as stream:
        child=subprocess.Popen(command,cwd=cwd,env=env,stdout=stream,stderr=subprocess.STDOUT,start_new_session=True)
        try:code=child.wait(timeout=timeout)
        except subprocess.TimeoutExpired:os.killpg(child.pid,signal.SIGTERM);raise
        if code:raise RuntimeError(f'Command exited {code}; see {log}')
try:
    record('progress.json',dict(stage='preparing_private_build_tools'))
    package=json.load(urllib.request.urlopen('https://pypi.org/pypi/cmake/3.31.6/json',timeout=30))
    wheel=next(x for x in package['urls'] if x['filename'].endswith('.whl') and 'manylinux2014_x86_64' in x['filename'])
    cmake_archive=out/wheel['filename'];cmake_sha=download(wheel['url'],cmake_archive,wheel['digests']['sha256'])
    tools=out/'tools';tools.mkdir()
    with zipfile.ZipFile(cmake_archive) as archive:
        for item in archive.infolist():
            target=(tools/item.filename).resolve();assert tools.resolve() in target.parents or target==tools.resolve()
        archive.extractall(tools)
    cmake=tools/'cmake/data/bin/cmake';cmake.chmod(cmake.stat().st_mode|stat.S_IXUSR)
    for item in (cmake.parent).iterdir():
        if item.is_file():item.chmod(item.stat().st_mode|stat.S_IXUSR)
    source_url='https://codeload.github.com/ggml-org/llama.cpp/tar.gz/refs/tags/b6780'
    source_archive=out/'llama-b6780.tar.gz';source_sha=download(source_url,source_archive)
    with tarfile.open(source_archive,'r:gz') as archive:
        for item in archive:
            target=(out/item.name).resolve();assert out.resolve() in target.parents
            assert not item.issym() and not item.islnk(),'Unexpected source link'
            archive.extract(item,path=out)
    source=out/'llama.cpp-b6780';assert source.is_dir()
    record('registration.json',dict(created_utc=datetime.now(timezone.utc).isoformat(),purpose='Private GPU runtime preparation and one truncated serving check only',source_release='https://github.com/ggml-org/llama.cpp/releases/tag/b6780',source_url=source_url,source_archive_sha256=source_sha,cmake_version='3.31.6',cmake_wheel_sha256=cmake_sha,model_blob_sha256='60e05f2100071479f596b964f89f510f057ce397ea22f2833a0cfe029bfc2463',cuda_architecture=86,build_parallelism=4))
    env=os.environ.copy();env['PATH']='/usr/local/cuda/bin:'+env.get('PATH','')
    record('progress.json',dict(stage='configuring'))
    run([str(cmake),'-S',str(source),'-B',str(out/'build'),'-DGGML_CUDA=ON','-DCMAKE_CUDA_COMPILER=/usr/local/cuda/bin/nvcc','-DCMAKE_CUDA_ARCHITECTURES=86','-DCMAKE_BUILD_TYPE=Release','-DLLAMA_CURL=OFF','-DLLAMA_BUILD_TESTS=OFF'],out,'configure.log',180,env)
    record('progress.json',dict(stage='building',parallelism=4))
    run([str(cmake),'--build',str(out/'build'),'--target','llama-server','-j','4'],out,'build.log',900,env)
    binary=out/'build/bin/llama-server';assert binary.is_file()
    record('progress.json',dict(stage='built',binary_sha256=hashlib.sha256(binary.read_bytes()).hexdigest()))
    raw=subprocess.check_output(['nvidia-smi','--query-gpu=index,uuid,memory.free,utilization.gpu','--format=csv,noheader,nounits'],text=True)
    rows=[]
    for values in csv.reader(io.StringIO(raw)):
        index,uuid,free,util=[v.strip() for v in values];rows.append(dict(index=int(index),uuid=uuid,free_mib=int(free),utilization=int(util)))
    eligible=[g for g in rows if g['free_mib']>=16384 and g['utilization']==0]
    if not eligible:record('readiness.json',dict(status='not_run_no_idle_gpu',snapshot=rows,model_calls=0));raise SystemExit('Built; no idle GPU for check')
    gpu=eligible[0];env['CUDA_VISIBLE_DEVICES']=gpu['uuid'];model=root/'models/blobs/sha256-60e05f2100071479f596b964f89f510f057ce397ea22f2833a0cfe029bfc2463'
    command=[str(binary),'-m',str(model),'-ngl','99','-c','8192','-t','4','-np','1','--host','127.0.0.1','--port','11441']
    with (out/'serving.log').open('x') as log:server=subprocess.Popen(command,cwd=out,env=env,stdout=log,stderr=subprocess.STDOUT,start_new_session=True)
    record('service_identity.json',dict(pid=server.pid,command=command,gpu=gpu,cwd=str(out)))
    try:
        for attempt in range(60):
            try:
                health=json.load(urllib.request.urlopen('http://127.0.0.1:11441/health',timeout=2))
                if health.get('status')=='ok':break
            except Exception:
                if server.poll() is not None:raise RuntimeError('Private llama-server exited')
            time.sleep(1)
        else:raise RuntimeError('Server readiness deadline exceeded')
        prompt=(root/'representative_prompt.txt').read_text()
        payload=dict(messages=[dict(role='system',content='You are Qwen, created by Alibaba Cloud. You are a helpful assistant.'),dict(role='user',content=prompt)],max_tokens=32,temperature=.1,seed=202612738,stream=False)
        record('readiness_request.json',dict(purpose='Short diagnostic, not a research candidate; never evaluate the truncated code',request=payload))
        started=time.perf_counter();req=urllib.request.Request('http://127.0.0.1:11441/v1/chat/completions',data=json.dumps(payload).encode(),headers={'Content-Type':'application/json'})
        reply=json.load(urllib.request.urlopen(req,timeout=90));record('readiness_response.json',reply)
        text=reply.get('choices',[{}])[0].get('message',{}).get('content','')
        result=dict(status='responded' if text.strip() else 'empty',wall_seconds=time.perf_counter()-started,usage=reply.get('usage'),gpu=gpu,warning='32-token serving check only; no algorithm or research score')
        record('readiness.json',result);record('progress.json',dict(stage='readiness_completed',result=result));print(json.dumps(result),flush=True)
    finally:
        if server.poll() is None:os.killpg(server.pid,signal.SIGTERM)
        record('cleanup.json',dict(private_server_process_group_stopped=server.pid,reason='Release diagnostic GPU memory; no research batch started'))
except Exception as error:
    record('failure.json',dict(error=f'{type(error).__name__}: {error}'));raise
