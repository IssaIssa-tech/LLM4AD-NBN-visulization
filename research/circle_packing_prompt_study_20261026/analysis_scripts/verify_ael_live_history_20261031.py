"""Read-only final comparison of the five live histories and preserved exports."""
import hashlib
import json
import urllib.request
from pathlib import Path

root = Path(__file__).resolve().parent
index = json.loads((root / 'TRACKING_INDEX.json').read_text())
manifest = json.loads((root / 'INPUT_MANIFEST.json').read_text())
canonical = lambda value: json.dumps(value,sort_keys=True,separators=(',',':'),ensure_ascii=False,allow_nan=False).encode()
sha = lambda raw: hashlib.sha256(raw).hexdigest()
checks = []
for h in index['histories']:
    with urllib.request.urlopen('http://127.0.0.1:5015/api/revisions/' + h['revision_id'] + '/research-history',timeout=15) as response:
        live = json.load(response)
    assert len(live['events']) == h['event_count']
    assert sha(canonical(live['events'])) == h['canonical_events_sha256']
    protected = {e['event_id']: e for e in h['events']}
    for event in live['events']:
        raw = json.dumps(event,ensure_ascii=False,allow_nan=False,sort_keys=True).encode()
        assert sha(raw) == protected[event['id']]['sha256']
    checks.append(dict(revision_id=h['revision_id'],events=len(live['events']),events_match_preserved_hashes=True))
audit = json.loads((root / 'INPUT_AUDIT.json').read_text())
assert sha(Path(manifest['historical_cache']).read_bytes()) == audit['cache_sha256']
result = dict(passed=True,total_events=sum(c['events'] for c in checks),histories=checks,
              source_cache_unchanged=True,generation_calls=0,candidate_executions=0)
(root / 'FINAL_LIVE_HISTORY_CHECK.json').write_text(json.dumps(result,indent=2),encoding='utf-8')
print(json.dumps(result))
