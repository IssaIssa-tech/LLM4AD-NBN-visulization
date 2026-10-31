"""Create a private per-study SSH key, separate from result folders."""
import json,os,subprocess
from pathlib import Path
root=Path(__file__).resolve().parent;study=root/'nbn_prompt_comparison_gpu_20261031'
credentials=root/'.transport_keys/gpu_study_20261031'
credentials.mkdir(parents=True,exist_ok=True);credentials.chmod(0o700);key=credentials/'key'
if key.exists():raise SystemExit('Study transport key exists; inspect rather than replace')
subprocess.run(['ssh-keygen','-q','-t','ed25519','-N','','-f',str(key),'-C','issa-nbn-gpu-study-20261031'],check=True);key.chmod(0o600)
known='[10.249.185.134]:8888 ssh-ed25519 AAAAC3NzaC1lZDI1NTE5AAAAIKAM9n0TW7/qSsgT1owVNVzAl7H15uqX7E59WmauQKTI\n'
(credentials/'known_hosts').write_text(known)
route=json.loads(subprocess.check_output(['ip','-j','route','get','10.249.185.134'],text=True))[0]
source_ip=route.get('prefsrc') or route.get('src');assert source_ip
payload=dict(public_key=key.with_suffix('.pub').read_text().strip(),source_ip=source_ip,private_key_location=str(key),known_hosts_location=str(credentials/'known_hosts'),purpose='Forced-command generation bridge for the fourteen-request study only')
(study/'transport_public_setup.json').write_text(json.dumps(payload,indent=2));print(json.dumps(payload))
