"""Read-only comparison of the deployed history API with completed export."""
import json,urllib.request
from pathlib import Path
root=Path(__file__).resolve().parent/'ael_operator_pilot_20261031'
saved=json.loads((root/'platform_history.json').read_text())
live=json.load(urllib.request.urlopen('http://127.0.0.1:5015/api/revisions/ael-operator-pilot-20261031/research-history',timeout=10))
assert live['events']==saved['events'] and live['view']==saved['view']
assert live['view']['summary']['attempts']==12
cross=[a for a in live['view']['attempts'] if a['id'].endswith('-cross')]
mut=[a for a in live['view']['attempts'] if a['id'].endswith('-mut')]
assert len(cross)==len(mut)==6 and all(len(a['parents'])==2 for a in cross)
assert all(len(a['parents'])==1 and a['parents'][0].get('originCallId')==a['id'].removesuffix('-mut')+'-cross' for a in mut)
result=dict(passed=True,event_count=len(live['events']),attempts=12,crossover_two_parent_links=6,mutation_offspring_links=6,live_api_equals_saved_export=True)
with (root/'LIVE_HISTORY_VERIFICATION.json').open('x') as f:json.dump(result,f,indent=2)
print(json.dumps(result))
