"""Freeze two fresh bounded-adaptation requests, without generation."""
import copy,hashlib,json,shutil
from datetime import datetime,timezone
from pathlib import Path
root=Path(__file__).resolve().parents[1];source=root/'output/regional_prompt_execution_contract_20261028'
out=root/'output/bounded_adaptation_pilot_20261028'
if out.exists():raise SystemExit('Existing pilot: inspect rather than overwrite')
m=json.loads((source/'draft_comparison_manifest.json').read_text());original=copy.deepcopy(m)
selected=[r for r in m['unique_requests'] if r['parent']['sample_order']==12738]
assert len(selected)==2
addition='''
PRESCRIBED BOUNDED ADAPTATION CONDITION:
Keep the supplied reference's pairwise geometric radius calculation and sequential circle-update search structure. Replace its 40000-round outer search with exactly 100 outer rounds. Within each circle update, use at most 3 position proposals. Keep all scans of circles bounded by n, with n=26. Do not add optimization-library calls, recursive calls, while loops, restarts or additional search passes. Do not introduce other numeric loops beyond these prescribed search loops. You may modify the proposal distribution or acceptance rule as the one algorithmic change requested above, within this fixed structure. This is a researcher-prescribed work constraint, not a claim of autonomous discovery or guaranteed runtime.
Use normalized round progress iteration/99 for any cooling schedule, instead of the original 40000-round denominator. Include a safe positive denominator when acceptance uses temperature. At the end of each accepted circle update, write [x,y,r] back into circles[i]. Every proposed radius must respect boundaries and distances to all other circles. Never replace a feasible incumbent packing with a lower-scoring or infeasible final packing. Do not return the unchanged zero-radius array. Preserve a finite (26,3) result and complete imports.
'''
out.mkdir();mapping={};requests=[]
for prior in selected:
    r=copy.deepcopy(prior);old=r['request_id'];prompt=(source/old/'prompt.txt').read_text()+addition
    payload=dict(model='qwen2.5:3b',temperature=.1,num_predict=1800,sampling_seed=r['sampling_seed'],prompt=prompt)
    digest=hashlib.sha256(json.dumps(payload,sort_keys=True).encode()).hexdigest();new='request-'+digest[:16]
    folder=out/new;folder.mkdir();(folder/'prompt.txt').write_text(prompt,encoding='utf-8');shutil.copyfile(source/old/'parent_candidate.py',folder/'parent_candidate.py')
    r.update(request_id=new,previous_condition_request_id=old,request_sha256=digest,prompt_sha256=hashlib.sha256(prompt.encode()).hexdigest())
    requests.append(r);mapping[old]=new
m.update(status='draft_not_registered_not_executed',execution_revision_id='bounded-adaptation-pilot-20261028',created_utc=datetime.now(timezone.utc).isoformat(),
    unique_requests=requests,unique_generation_call_count=2,analytical_slot_count=2,
    analytical_slots=[dict(strategy='single_archival_parent',prompt_profile=r['prompt_profile'],parent_node_id=r['parent']['node_id'],request_id=r['request_id']) for r in requests],
    parent_pools={'single_archival_parent':[requests[0]['parent']]},factors=dict(parent_selection=['single_archival_parent'],prompt_profile=[r['prompt_profile'] for r in requests]),
    previous_condition='regional-execution-contract-20261028',amendment='Single-parent two-profile bounded adaptation feasibility pilot; prescribed work and update correctness package',
    inference_limit='One call per profile, one parent; cannot rank selection strategies, prove diversity, or isolate the numeric cap from other changed instructions.',
    compliance_plan='Inspect outer loop exactly 100; <=3 proposals per circle; scans bounded by n; no while/recursion/restarts/optimizer; check actual stored coordinates, geometry and score separately. Noncompliance remains a recorded outcome, never repaired.')
m['budget']['model_calls']=2
(out/'draft_comparison_manifest.json').write_text(json.dumps(m,indent=2),encoding='utf-8')
(out/'PROTOCOL.md').write_text('''# Bounded adaptation feasibility pilot

Two fresh requests, one per existing prompt profile, using archived historical parent 12738. This is a feasibility diagnostic, not a repeat of the four-region comparison. Model, sampling seed, temperature, generation length and evaluator remain unchanged. Add the complete saved bounded-adaptation package to the previous prompt text. Researcher-prescribed work constraints explicitly limit design freedom. No repair, editing, retries, replacement requests or adaptive stopping.

Exactly 100 outer rounds and at most three proposals per circle are required. The earlier prepared calibration with 100 rounds and the original thirty proposals completed in 5.38 seconds; this motivates testing a smaller fixed proposal budget but is not a runtime guarantee. Cooling normalization, incumbent protection and array write-back are additional instructions, so this pilot does not isolate a single causal sentence. Inspect compliance separately from execution and geometry. Any unsupported claim in generated comments is not evidence of implementation.

Preserve both complete histories regardless of outcome. Target remains 2.6360; no guarantee or official-verifier equivalence. No selection-strategy ranking or high-quality diversity claim is possible from two requests. Prior broad-run outcomes remain unchanged. Freeze model/environment/evaluator hashes and platform history registration before calls.
''',encoding='utf-8')
print(out)
