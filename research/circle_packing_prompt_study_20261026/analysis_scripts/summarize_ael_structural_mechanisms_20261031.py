"""Add source-inspection and saved-invalid-output diagnostics, without reruns."""
import json,math
from pathlib import Path
base=Path(__file__).resolve().parents[1];root=base/'output/ael_structural_prompt_comparison_20261031'
s=json.loads((root/'COMPARISON_SUMMARY.json').read_text(encoding='utf-8'));r=json.loads((root/'results.json').read_text(encoding='utf-8'))
assert s['status']=='completed_verified' and len(r['results'])==12
assert all(o['finish_reason']=='stop' for o in s['new_observations'])
invalid=[]
for row in r['results']:
    if row['status']!='invalid_geometry':continue
    arr=row['circles'];assert row['shape']==[26,3] and all(len(c)==3 and all(isinstance(x,(int,float)) and math.isfinite(x) for x in c) for c in arr)
    minr=min(c[2] for c in arr);assert minr<0 and row['score'] is None
    invalid.append(dict(call_id=row['call_id'],minimum_returned_radius=minr,fitness=None,diagnosis='Negative radii in saved actual output; not repaired or treated as finite fitness'))
sole=next(o for o in s['new_observations'] if o['status']=='valid');baseline_pair=next(p for p in s['pairs'] if p['new'] and p['new']['call_id']==sole['call_id'])
assert sole['packing_sha256']==baseline_pair['baseline']['packing_sha256']
diag=dict(invalid_geometry_checks=invalid,all_new_responses_finished_normally=True,sole_valid_output_reuses_matching_baseline_coordinate_set=True,sole_valid_call=sole['call_id'],body_matches_by_operator={arm:{op:sum(bool(o.get('selected_parent_body_matches')) for o in observations if o['operator']==op) for op in ['cross','mut']} for arm,observations in [('baseline',[p['baseline'] for p in s['pairs']]),('new',s['new_observations'])]},actual_allocation=s['actual_allocation'])
(root/'MECHANISM_DIAGNOSTICS.json').write_text(json.dumps(diag,indent=2),encoding='utf-8',newline='\n')
text='''# Interpretation of the matched AEL prompt-pair comparison

The fixed condition completed twelve new calls. The joint structural-change/import-completeness instructions produced **one valid output**, nine exceptions and two invalid geometries. The saved baseline had **eight valid outputs** and four exceptions. New best valid score **2.109107549240501** is below the baseline's **2.5338065697852596**. Both conditions have zero hits at 2.6360.

The normalized parent-body match count decreased from **11/12 to 3/12** (crossover: 6/6 to 2/6; mutation: 5/6 to 1/6). These are exact AST-match diagnostics after excluding import/docstring nodes, not a count of new algorithm mechanisms. The only valid new output retains historical sample 12852's computational body and has exactly the same saved coordinate set and score as its matched baseline mutation. There is no demonstrated valid, structurally new, higher-quality discovery in this follow-up.

| Matched chain | Actual changes inspected | Actual outcome |
|---|---|---|
| uniform-1 | Crossover replaces initialization with Voronoi-region processing, retaining L-BFGS-B/radius adjustment. Mutation adds the missing cdist import but leaves the computational body unchanged. | Both raise ValueError on an empty min() input. Source inspection also reveals an unbound point name. These later faults are not silently reclassified as observed runtime errors. |
| uniform-2 | Adds a Voronoi-based radius overwrite after the inherited SLSQP optimizer. Mutation leaves that computational body unchanged. | Both return invalid geometry with minimum radius -0.11726882979300035. No score is assigned to these invalid outputs. |
| uniform-3 | Crossover retains sample 12849's computational body while omitting qmc import. Mutation adds the import, changes perturbation magnitude and passes scramble=True to sampler.random(). | Crossover: NameError. Mutation: TypeError for the unexpected scramble argument. Parameter/API changes do not establish a successful new mechanism. |
| nbn_stratified-1 | Introduces joint point/radius SLSQP variables but uses 2n bounds for a 3n initial vector. Mutation changes maxiter from 1000 to 500. | Both raise incompatible-bounds ValueError. A changed iteration cap is a parameter change, not evidence of structural novelty. |
| nbn_stratified-2 | Crossover retains sample 12852's body and omits qmc import. Mutation adds that import without changing computation. | Crossover: NameError. Mutation: valid at 2.109107549240501, reproducing the matched baseline packing. |
| nbn_stratified-3 | Adds Voronoi-region radius adjustment after sample 7918's style of local search. Mutation replaces Latin-hypercube sampling with uniform RNG sampling but keeps the region adjustment. | Crossover: qmc NameError. Mutation: zero-size reduction ValueError in the added region processing. The docstring/comment still calls the initialization Latin-hypercube despite the changed code. |

All twelve responses ended normally with finish_reason=stop, so these failures are not token-cap truncations. Runtime NameErrors decrease from four to three, but that does not prove complete imports: early errors can hide later unbound names. Model claims in comments/docstrings are not accepted as evidence of implementation behavior.

There were no manual candidate patches, feedback repair calls, replacements or repeat evaluations. Mutation ran on the actual static-eligible crossover source even after invalidity/exceptions, without receiving its evaluation result. All failures and actual returned invalid coordinates remain in the archive/history.

At actual startup, the same baseline GPU had 24,253MiB free, matching the baseline startup observation; after loading, 19,027MiB remained. Thus the original conservative 16GiB guard would also have passed then. The earlier relaxed allocation guard was documented before registration and did not change weights/build/template/context/sampling/evaluator; its earlier prepared version is retained. No exclusive-GPU or generation-timing comparison is claimed.

The practical selection supported by these twelve paired cases is to **retain the original AEL prompt pair as the working delivery baseline**, and retain this joint intervention as a negative result. That is a provisional choice within these cases, not statistical superiority or a claim that NBN guidance cannot work. The revised wording changed more code but did not produce a valid novel improvement.

Do not launch another search simply to obtain a positive result. A future comparison should separately register its parent choice, prompt mechanism, budgets and score/diversity criteria, and isolate individual changes if their causal effects are of interest. The present two-condition comparison is complete. The broader NBN-guided discovery goal and full AEL population experiment are not declared complete.
'''
(root/'MECHANISM_REVIEW.md').write_text(text,encoding='utf-8',newline='\n')
p=root/'COMPARISON_RESULTS.md';text=p.read_text(encoding='utf-8')+'\nSource inspection: [MECHANISM_REVIEW.md](MECHANISM_REVIEW.md). All three parent-body matches in the new condition are preserved; the only valid packing repeats the matched baseline packing. Changed code by itself did not establish successful structural diversity.\n';p.write_text(text,encoding='utf-8',newline='\n')
p=root/'ael_structural_comparison_review.html';text=p.read_text(encoding='utf-8')
marker='<h2>Interpretation boundaries</h2>';assert marker in text
text=text.replace(marker,marker+'<p><strong>Observed tradeoff:</strong> parent-body matches fell from 11/12 to 3/12, while valid outputs fell from 8/12 to 1/12. The sole valid new output repeats a baseline packing. Changed code did not yield a demonstrated valid novel improvement. <a href="MECHANISM_REVIEW.md">Read the inspected mechanisms and failures</a>.</p>')
p.write_text(text,encoding='utf-8',newline='\n');print(json.dumps(diag,indent=2))
