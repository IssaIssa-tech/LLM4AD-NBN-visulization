"""Check the live history API against the completed diagnostic event export."""
import json,urllib.request
from collections import Counter
from pathlib import Path
root=Path(__file__).resolve().parent/'ael_parent_eligibility_20261031'
with urllib.request.urlopen('http://127.0.0.1:5015/api/revisions/ael-parent-eligibility-20261031/research-history',timeout=20) as response:
    status=response.status;actual=json.load(response)
saved=json.loads((root/'platform_history.json').read_text());assert actual['events']==saved['events'] and actual['view']==saved['view']
counts=dict(Counter(e['eventType'] for e in actual['events']));assert counts['historical_reference_evaluated']==30 and counts.get('llm_request',0)==0
assert len(actual['view']['references'])==30
result=dict(http_status=status,revision=actual['revisionId'],events=actual['count'],historical_reference_checks=30,llm_requests=0,selected_source_snapshots=30,live_events_and_view_match_saved_export=True)
(root/'LIVE_HISTORY_VERIFICATION.json').write_text(json.dumps(result,indent=2));print(json.dumps(result))
