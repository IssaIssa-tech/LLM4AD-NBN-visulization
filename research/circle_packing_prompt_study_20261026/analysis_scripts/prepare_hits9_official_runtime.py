"""Install a matching official runtime privately; reuse verified model weights."""
import hashlib,json,os,subprocess,tarfile,time,urllib.request
from datetime import datetime,timezone
from pathlib import Path
root=Path(__file__).resolve().parent;out=root/'official_runtime_setup'
if out.exists():raise SystemExit('Setup exists; inspect before repeating')
out.mkdir();repo='https://api.github.com/repos/ollama/ollama/releases/tags/v0.13.5'
metadata=json.load(urllib.request.urlopen(repo,timeout=30))
asset=next(a for a in metadata['assets'] if a['name']=='ollama-linux-amd64.tgz')
(out/'registration.json').write_text(json.dumps(dict(created_utc=datetime.now(timezone.utc).isoformat(),purpose='Private runtime recovery only; no research generation',asset={k:asset.get(k) for k in ['name','size','digest','browser_download_url']},release=repo),indent=2))
archive=out/asset['name'];digest=hashlib.sha256();completed=0;last=0
try:
    with urllib.request.urlopen(asset['browser_download_url'],timeout=60) as response, archive.open('xb') as stream:
        while True:
            block=response.read(1024*1024)
            if not block:break
            stream.write(block);digest.update(block);completed+=len(block)
            if time.monotonic()-last>=2:
                (out/'progress.json').write_text(json.dumps(dict(stage='downloading',completed_bytes=completed,total_bytes=asset['size']),indent=2));last=time.monotonic()
    assert completed==asset['size'],'Incomplete runtime archive'
    observed=digest.hexdigest();expected=asset.get('digest')
    if expected:assert expected=='sha256:'+observed,'Release archive digest mismatch'
    install=out/'install';install.mkdir();base=install.resolve();extracted=[]
    with tarfile.open(archive,'r:gz') as tar:
        for member in tar:
            name=member.name.removeprefix('./')
            # Only CPU/common and CUDA 12 runtime components are needed here.
            if not (name.startswith('bin/') or name.startswith('lib/ollama/')):continue
            if '/cuda_v13/' in '/'+name or '/rocm/' in '/'+name:continue
            target=(base/name).resolve();assert target==base or base in target.parents
            if member.issym():
                link=(target.parent/member.linkname).resolve();assert link==base or base in link.parents
            elif member.islnk():
                link=(base/member.linkname).resolve();assert link==base or base in link.parents
            elif not (member.isfile() or member.isdir()):continue
            tar.extract(member,path=base);extracted.append(name)
    binary=install/'bin/ollama';assert binary.is_file()
    (out/'installation.json').write_text(json.dumps(dict(archive_sha256=observed,official_digest_verified=bool(expected),binary_sha256=hashlib.sha256(binary.read_bytes()).hexdigest(),extracted=extracted),indent=2))
    (out/'progress.json').write_text(json.dumps(dict(stage='installed',completed_bytes=completed,total_bytes=asset['size']),indent=2))
    # The helper registers its GPU check, uses a private loopback port, and
    # refuses inference without an idle GPU with >=16 GiB free memory.
    result=subprocess.run(['python3',str(root/'check_hits9_official_inference.py')],capture_output=True,text=True,timeout=150)
    (out/'readiness_launcher.json').write_text(json.dumps(dict(exit_code=result.returncode,stdout=result.stdout,stderr=result.stderr),indent=2))
    print(result.stdout,flush=True)
except Exception as error:
    (out/'failure.json').write_text(json.dumps(dict(error=f'{type(error).__name__}: {error}',completed_bytes=completed),indent=2));raise
