"""Inspect frozen two-call pilot artifacts; no candidate execution."""
import ast,json,math
from collections import Counter
from pathlib import Path
p=Path(__file__).resolve().parents[1]/'output/bounded_adaptation_pilot_20261028'
m=json.loads((p/'draft_comparison_manifest.json').read_text());rows=[]
for r in m['unique_requests']:
    d=p/r['request_id'];o=json.loads((d/'outcome.json').read_text());t=ast.parse((d/'candidate.py').read_text())
    loops=[ast.unparse(n.iter) for n in ast.walk(t) if isinstance(n,ast.For)]
    row=dict(request_id=r['request_id'],profile=r['prompt_profile'],status=o['status'],score=o.get('score'),error=o.get('error'),runtime_seconds=o.get('runtime_seconds'),loop_iterables=loops,
        outer_100_present='range(100)' in loops,proposal_3_present='range(3)' in loops,
        while_present=any(isinstance(n,ast.While) for n in ast.walk(t)),
        loop_limits_compliant=sorted(loops) in [sorted(['range(100)','range(n)','range(3)','range(n)']),sorted(['range(100)','range(n)','range(n)','range(3)','range(n)'])])
    if 'circles' in o:
        a=o['circles'];violations=[]
        for i in range(len(a)):
            for j in range(i+1,len(a)):
                gap=math.hypot(a[i][0]-a[j][0],a[i][1]-a[j][1])-a[i][2]-a[j][2]
                if gap < -1e-12:violations.append(dict(i_zero_based=i,j_zero_based=j,clearance=gap))
        row['overlapping_pairs']=violations
    rows.append(row)
events=[json.loads(f.read_text(encoding='utf-8')) for f in (p/'research_history').glob('*.json')];counts=Counter(e['eventType'] for e in events)
assert counts['llm_request']==counts['llm_response']==counts['trial_completed']==2 and counts['comparison_completed']==1
assert all(r['loop_limits_compliant'] and not r['while_present'] for r in rows)
with (p/'PILOT_ANALYSIS.json').open('x') as stream:json.dump(dict(rows=rows,history_events=dict(counts),model_calls_in_analysis=0,candidate_reruns=0),stream,indent=2)
print(json.dumps(rows,indent=2))
