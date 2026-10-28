"""Check saved repair geometry, lineage and loop compliance without execution."""
import ast,difflib,json,math
from collections import Counter
from pathlib import Path
p=Path(__file__).resolve().parents[1]/'output/bounded_feedback_repair_20261028'
m=json.loads((p/'draft_comparison_manifest.json').read_text());rows=[]
for request in m['unique_requests']:
    d=p/request['request_id'];o=json.loads((d/'outcome.json').read_text());code=(d/'candidate.py').read_text();before=(d/'failed_candidate.py').read_text()
    t=ast.parse(code);loops=[ast.unparse(n.iter) for n in ast.walk(t) if isinstance(n,ast.For)]
    row=dict(request_id=request['request_id'],lineage=request['repair_lineage'],evaluator_status=o['status'],score=o.get('score'),screening=o.get('screening'),loops=loops,required_outer_100_present='range(100)' in loops)
    if o['status']=='valid':
        a=o['circles'];assert len(a)==26 and all(len(c)==3 and all(math.isfinite(x) for x in c) for c in a)
        for x,y,r in a:assert r>=-1e-12 and min(x-r,y-r,1-x-r,1-y-r)>=-1e-12
        gaps=[math.hypot(a[i][0]-a[j][0],a[i][1]-a[j][1])-a[i][2]-a[j][2] for i in range(26) for j in range(i+1,26)]
        assert min(gaps)>=-1e-12 and abs(sum(c[2] for c in a)-o['score'])<1e-12
        row.update(saved_geometry_verified=True,min_pairwise_clearance=min(gaps),compliant_repair=False,compliance_reason='Removed required 100-round search and changed progress-dependent step schedule')
    else:row.update(compliant_repair=False,compliance_reason='Prohibited top-level execution; source also retains reused loop counter and missing best_r update')
    with (d/'source_changes.diff').open('x',encoding='utf-8') as stream:stream.writelines(difflib.unified_diff(before.splitlines(True),code.splitlines(True),fromfile='original_failed_candidate.py',tofile='llm_repair.py'))
    rows.append(row)
events=[json.loads(f.read_text(encoding='utf-8')) for f in (p/'research_history').glob('*.json')];counts=Counter(e['eventType'] for e in events)
assert counts['llm_request']==counts['llm_response']==counts['trial_completed']==2 and counts['comparison_completed']==1
result=dict(rows=rows,fully_compliant_valid_repairs=0,evaluator_valid_outputs=1,history_events=dict(counts),candidate_reruns=0,analysis_model_calls=0)
with (p/'REPAIR_ANALYSIS.json').open('x') as stream:json.dump(result,stream,indent=2)
print(json.dumps(result,indent=2))
