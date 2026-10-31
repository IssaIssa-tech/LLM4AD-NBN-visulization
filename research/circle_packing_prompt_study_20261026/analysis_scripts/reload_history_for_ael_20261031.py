"""Reload only our identified private loopback platform for multi-parent projection."""
import json,os,signal,subprocess,time,urllib.request
from pathlib import Path
root=Path(__file__).resolve().parent;case=root/'ael_operator_pilot_20261031'
pid=3960609;proc=Path(f'/proc/{pid}')
assert proc.exists() and (proc/'cwd').resolve()==root
assert str(root/'launch_history_platform.py').encode() in (proc/'cmdline').read_bytes()
assert not (case/'history_app_reload.json').exists()
os.kill(pid,signal.SIGTERM)
for _ in range(50):
    if not proc.exists():break
    time.sleep(.1)
with (case/'history_app.log').open('x') as log:
    child=subprocess.Popen([str(root/'venv/bin/python'),'-u',str(root/'launch_history_platform.py')],cwd=root,stdout=log,stderr=subprocess.STDOUT,start_new_session=True)
for _ in range(30):
    try:
        result=json.load(urllib.request.urlopen('http://127.0.0.1:5015/api/revisions/ael-operator-pilot-20261031/research-history',timeout=2))
        assert all(len(a['parents'])==2 for a in result['view']['attempts'] if a['id'].endswith('-cross'))
        break
    except Exception:
        if child.poll() is not None:raise RuntimeError('Private app restart failed')
        time.sleep(.5)
else:raise RuntimeError('Private app health deadline exceeded')
record=dict(previous_pid=pid,new_pid=child.pid,status='private_platform_reloaded_and_two_parent_API_verified',attempts_observed=len(result['view']['attempts']))
with (case/'history_app_reload.json').open('x') as f:json.dump(record,f,indent=2)
print(json.dumps(record))
