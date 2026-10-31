"""Append only a source-restricted, forced-command public key; preserve others."""
import hashlib,ipaddress,json,os
from pathlib import Path
root=Path(__file__).resolve().parent;data=json.loads((root/'transport_public_setup.json').read_text())
ip=ipaddress.ip_address(data['source_ip']);assert ip.version==4
key=data['public_key'];assert key.startswith('ssh-ed25519 ') and '\n' not in key
command=f'/usr/bin/python3 {root}/gpu_study_generate_bridge.py';assert (root/'gpu_study_generate_bridge.py').is_file()
line=f'restrict,from="{ip}",command="{command}" {key}'
directory=Path.home()/'.ssh';directory.mkdir(mode=0o700,exist_ok=True);authorized=directory/'authorized_keys'
before=authorized.read_text() if authorized.exists() else ''
if line not in before.splitlines():
    existed=authorized.exists()
    with authorized.open('a') as stream:stream.write(('\n' if before and not before.endswith('\n') else '')+line+'\n');stream.flush();os.fsync(stream.fileno())
    if not existed:authorized.chmod(0o600)
(root/'transport_installation.json').write_text(json.dumps(dict(public_entry_sha256=hashlib.sha256(line.encode()).hexdigest(),source_ip=str(ip),forced_command=command,existing_entries_preserved=True),indent=2))
print('Restricted public key installed; existing entries preserved')
