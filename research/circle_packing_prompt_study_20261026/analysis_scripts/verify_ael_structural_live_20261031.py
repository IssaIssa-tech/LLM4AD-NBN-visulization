"""Read-only final history/process checks for this condition only."""
import json,socket,sys,urllib.request
from pathlib import Path
parent=Path(__file__).resolve().parent;root=parent/'ael_structural_prompt_comparison_20261031'
if sys.argv[1]=='history':
    saved=json.loads((root/'platform_history.json').read_text());result=json.loads((root/'results.json').read_text())
    revision='ael-structural-prompt-comparison-20261031'
    live=json.load(urllib.request.urlopen('http://127.0.0.1:5015/api/revisions/'+revision+'/research-history',timeout=10))
    assert live['events']==saved['events'] and live['view']==saved['view']
    a=live['view']['attempts'];assert len(a)==result['actual_llm_requests']
    cross=[r for r in a if r['id'].endswith('-cross')];mut=[r for r in a if r['id'].endswith('-mut')]
    assert len(cross)==6 and all(len(r['parents'])==2 for r in cross)
    assert all(len(r['parents'])==1 and r['parents'][0].get('originCallId')==r['id'].removesuffix('-mut')+'-cross' and r['parents'][0].get('originRevisionId')==revision for r in mut)
    record=dict(passed=True,event_count=len(live['events']),actual_llm_requests=len(a),crossover_two_parent_links=len(cross),mutation_generated_parent_links=len(mut),live_api_equals_saved_export=True)
    target=root/'LIVE_HISTORY_VERIFICATION.json'
else:
    identity=json.loads((root/'runtime_identity.json').read_text());pid=identity['service_pid'];assert not Path(f'/proc/{pid}').exists()
    with socket.socket() as sock:assert sock.connect_ex(('127.0.0.1',11444))!=0
    record=dict(passed=True,own_pid=pid,own_model_process_absent=True,private_port_closed=True);target=root/'GPU_RELEASE_VERIFICATION.json'
with target.open('x') as f:json.dump(record,f,indent=2)
print(json.dumps(record))
