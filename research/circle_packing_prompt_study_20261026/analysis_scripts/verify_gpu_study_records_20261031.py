"""Verify saved history and packing; inspect outputs without executing programs."""
import ast,hashlib,json,math
from collections import Counter
from pathlib import Path
root=Path(__file__).resolve().parents[1]/'output/nbn_prompt_comparison_gpu_20261031'
manifest=json.loads((root/'draft_comparison_manifest.json').read_text(encoding='utf-8'));rows=[]
for r in manifest['unique_requests']:
    folder=root/r['request_id'];o=json.loads((folder/'outcome.json').read_text());raw=json.loads((folder/'raw_response.json').read_text())
    assert o['call_id']==r['request_id'];assert raw['choices'][0]['finish_reason']=='stop'
    usage=raw['usage'];assert usage['prompt_tokens']+1800<=8192
    row=dict(request_id=r['request_id'],status=o['status'],prompt_tokens=usage['prompt_tokens'],completion_tokens=usage['completion_tokens'])
    if o['status']=='valid':
        circles=o['circles'];assert len(circles)==26 and all(len(c)==3 and all(math.isfinite(x) for x in c) for c in circles)
        for x,y,radius in circles:assert radius>=-1e-12 and min(x-radius,y-radius,1-x-radius,1-y-radius)>=-1e-12
        clearances=[math.hypot(circles[i][0]-circles[j][0],circles[i][1]-circles[j][1])-circles[i][2]-circles[j][2] for i in range(26) for j in range(i+1,26)]
        assert min(clearances)>=-1e-12 and abs(sum(c[2] for c in circles)-o['score'])<1e-12
        code=(folder/'candidate.py').read_text();tree=ast.parse(code);function=next(n for n in tree.body if isinstance(n,ast.FunctionDef))
        row.update(score=o['score'],saved_geometry_verified=True,min_clearance=min(clearances),code_sha256=hashlib.sha256(code.encode()).hexdigest(),function_docstring=ast.get_docstring(function))
    rows.append(row)
events=[json.loads(f.read_text(encoding='utf-8')) for f in (root/'research_history').glob('*.json')];counts=Counter(e['eventType'] for e in events)
assert counts['llm_request']==counts['llm_response']==counts['program_generated']==counts['trial_completed']==14
assert counts['comparison_completed']==counts['analysis_report_saved']==counts['generation_service_released']==1
released=json.loads((root/'service_released.json').read_text());assert released['status']=='private_service_released'
with (root/'RECORD_VERIFICATION.json').open('x') as stream:json.dump(dict(rows=rows,events=dict(counts),candidate_reruns=0,model_calls_in_verification=0,service_released=released),stream,indent=2)
print('Verified 14 request/response/program/outcome links; saved packing geometry/score; no token-cap truncation; private GPU service released.')
