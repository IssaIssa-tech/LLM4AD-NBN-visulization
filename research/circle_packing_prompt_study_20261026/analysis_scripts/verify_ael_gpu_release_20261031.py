"""Verify only this pilot's recorded model process/port were released."""
import json,socket,subprocess
from pathlib import Path
root=Path(__file__).resolve().parent/'ael_operator_pilot_20261031'
identity=json.loads((root/'runtime_identity.json').read_text());pid=identity['service_pid']
assert not Path(f'/proc/{pid}').exists(),'Own model process still exists'
with socket.socket() as s:assert s.connect_ex(('127.0.0.1',11444))!=0,'Private port still serving'
result=dict(passed=True,own_pid=pid,own_process_absent=True,private_port_closed=True,gpu_status=subprocess.check_output(['nvidia-smi','--query-gpu=index,memory.used,utilization.gpu','--format=csv,noheader,nounits'],text=True))
with (root/'GPU_RELEASE_VERIFICATION.json').open('x') as f:json.dump(result,f,indent=2)
print(json.dumps(result))
