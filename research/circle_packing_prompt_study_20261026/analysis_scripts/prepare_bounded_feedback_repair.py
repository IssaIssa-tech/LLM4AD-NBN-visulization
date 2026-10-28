"""Register a fixed one-repair opportunity for each new bounded-pilot failure."""
import copy,hashlib,json,shutil
from datetime import datetime,timezone
from pathlib import Path
root=Path(__file__).resolve().parents[1];source=root/'output/bounded_adaptation_pilot_20261028';out=root/'output/bounded_feedback_repair_20261028'
if out.exists():raise SystemExit('Existing condition: do not overwrite or repeat')
m=json.loads((source/'draft_comparison_manifest.json').read_text());out.mkdir();requests=[]
for prior in m['unique_requests']:
    old=prior['request_id'];code=(source/old/'candidate.py').read_text();result=json.loads((source/old/'outcome.json').read_text())
    assert result['status'] in ['invalid_geometry','exception']
    if result['status']=='invalid_geometry':
        feedback='''The saved (26,3) result contains an overlapping pair, zero-based rows 21 and 23, with clearance -0.07747797522398742. Boundary-only initial radii do not guarantee pairwise feasibility. The update accepts only radius increases, so an invalid initial packing may stay invalid. Make initialization pairwise feasible before optimization, retaining the Latin Hypercube centers and deterministic seed. Preserve pairwise distance-based proposal radii, the existing proposal mechanism, and accepted array write-back. Do not replace the search with a new optimizer, grid or constant packing. Ensure the final output has nonnegative radii and no overlaps. A feasibility correction is not evidence of improved search quality.'''
    else:
        feedback='''The evaluator raised NameError: name 'circircles' is not defined. The intended array is circles. Inspection also finds that '_' is both the outer round counter and proposal counter, so the cooling calculation uses an overwritten counter; give these distinct names and use the outer round divided by 99 consistently. best_r is initialized but never updated when a new best proposal is selected; correct that bookkeeping. Preserve the current initializer, distance-based radius calculation and search/proposal mechanism. Do not add a new optimizer or replace the algorithm. These are identified repairs, not a request to redesign the search.'''
    prompt='''Return exactly one complete Python code block, with imports and a single top-level pack_circles(n: int) -> np.ndarray function. No examples, top-level execution or prose outside the block. Only numpy, math and scipy imports are permitted. Repair this exact failed program with the smallest changes needed for the feedback below. The evaluator supplies np but no other symbols; include complete imports. Preserve seed 2025. Keep exactly 100 outer rounds, at most three proposals per circle, and scans bounded by n. Do not add while loops, recursion, restarts, other search passes or optimizer calls. Return a finite (n,3) array of x,y,r; containment, nonnegative radii and pairwise non-overlap are required. The n=26 research execution limit is twenty seconds, not an asserted official challenge rule. Target 2.6360 is an objective, not a guaranteed or claimed outcome. No subsequent repair is allowed in this condition.

Recorded evaluation feedback and source inspection:
'''+feedback+'\n\nExact failed source:\n```python\n'+code+'\n```\n'
    payload=dict(model='qwen2.5:3b',temperature=.1,num_predict=1800,sampling_seed=prior['sampling_seed'],prompt=prompt)
    digest=hashlib.sha256(json.dumps(payload,sort_keys=True).encode()).hexdigest();new='request-'+digest[:16]
    folder=out/new;folder.mkdir();(folder/'prompt.txt').write_text(prompt,encoding='utf-8');shutil.copyfile(source/old/'parent_candidate.py',folder/'parent_candidate.py');(folder/'failed_candidate.py').write_text(code,encoding='utf-8');(folder/'initial_outcome.json').write_text(json.dumps(result,indent=2),encoding='utf-8')
    r=copy.deepcopy(prior);r.update(request_id=new,previous_condition_request_id=old,prompt_profile='one_feedback_repair_of_'+prior['prompt_profile'],prompt_sha256=hashlib.sha256(prompt.encode()).hexdigest(),request_sha256=digest,
        repair_lineage=dict(source_revision='bounded-adaptation-pilot-20261028',source_call_id=old,failed_code_sha256=hashlib.sha256(code.encode()).hexdigest(),initial_status=result['status'],repair_attempt=1,maximum_repair_calls=1))
    requests.append(r)
m.update(status='draft_not_registered_not_executed',execution_revision_id='bounded-feedback-repair-20261028',created_utc=datetime.now(timezone.utc).isoformat(),unique_requests=requests,
    analytical_slots=[dict(strategy='single_archival_parent',prompt_profile=r['prompt_profile'],parent_node_id=r['parent']['node_id'],request_id=r['request_id']) for r in requests],
    previous_condition='bounded-adaptation-pilot-20261028',amendment='One error-informed repair per frozen bounded candidate; exact initial source, failure evidence and historical node lineage preserved',
    inference_limit='Case study of two post-selected failed programs, not a controlled repair-effect estimate or NBN selection comparison',
    factors=dict(parent_selection=['single_archival_parent'],prompt_profile=[r['prompt_profile'] for r in requests]))
m['budget'].update(model_calls=2,repair_calls=2,maximum_repair_calls_per_initial_candidate=1)
(out/'draft_comparison_manifest.json').write_text(json.dumps(m,indent=2),encoding='utf-8')
(out/'PROTOCOL.md').write_text('''# Bounded-program feedback repair case study

Prior-work review: M2-R changed a structural prompt package and returned 0/5 valid (four invalid geometry, one unpacking exception). Code-checked M2 allowed one error-informed repair after an eight-second precheck; all five repaired candidates failed before full evaluation. Those results remain negative evidence and are not repeated here.

The new case study repairs exactly two newly generated 100-round bounded programs. Each receives its complete failed source and exact evaluation/source-inspection feedback; the historical parent/node and original call ID remain linked in the manifest. The feedback is researcher-assisted, not autonomous diagnosis. One repair request per source, no retries, manual patches or replacement candidates. Model/settings and twenty-second evaluator remain fixed. No initial candidate is regenerated or reevaluated.

Report pre/post status, actual geometry, score and work-limit compliance. Review code diffs for unrequested changes. A successful repair measures delivery/feasibility only and is not a demonstrated improvement over a valid incumbent. These two selected failures cannot estimate population repair success or compare NBN regions. Preserve both failures even if repairs succeed; invalid outcomes get no invented score. Registration precedes all calls. No official-verifier equivalence is claimed.
''',encoding='utf-8')
print(out)
