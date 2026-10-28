"""Create a separate frozen prompt revision from existing requests; no calls."""
import hashlib,json,shutil
from datetime import datetime,timezone
from pathlib import Path
root=Path(__file__).resolve().parents[1]
source=root/'output/regional_prompt_comparison_draft_20261028'
target=root/'output/regional_prompt_execution_contract_20261028'
if target.exists():raise SystemExit('Existing condition: inspect instead of overwriting')
manifest=json.loads((source/'draft_comparison_manifest.json').read_text())
addition='''
EXECUTION CONTRACT CHECKLIST — apply before returning the program:
1. Make the program self-contained. Import every external symbol you use. For example, using qmc requires `from scipy.stats import qmc`; it is not supplied by the evaluator. Only np is prebound, and your own imports are still required.
2. The packing array has shape (n,3). Each full row contains x,y,r. Unpack three values, or explicitly slice [:,:2] when unpacking two. Keep this invariant throughout the algorithm.
3. Return imports and the single top-level pack_circles function only. Do not append example calls, assignments, print statements, or a main block. Helpers may be nested inside pack_circles.
4. Use bounded computational work suitable for the stated twenty-second budget. Avoid inheriting the historical program's tens of thousands of nested search rounds. Choose a compact search that returns a feasible packing within that budget. Do not use wall-clock or operating-system imports to stop it.
5. Check containment and pairwise non-overlap before returning. A high claimed score or a comment is not a substitute for an actual feasible array.
Return the complete program; do not explain this checklist outside the code block.
'''
target.mkdir();mapping={}
for request in manifest['unique_requests']:
    old=request['request_id'];prompt=(source/old/'prompt.txt').read_text()+addition
    payload=dict(model='qwen2.5:3b',temperature=.1,num_predict=1800,sampling_seed=request['sampling_seed'],prompt=prompt)
    digest=hashlib.sha256(json.dumps(payload,sort_keys=True).encode()).hexdigest()
    new='request-'+digest[:16];mapping[old]=new
    folder=target/new;folder.mkdir()
    (folder/'prompt.txt').write_text(prompt,encoding='utf-8')
    shutil.copyfile(source/old/'parent_candidate.py',folder/'parent_candidate.py')
    request.update(request_id=new,previous_condition_request_id=old,request_sha256=digest,prompt_sha256=hashlib.sha256(prompt.encode()).hexdigest())
for slot in manifest['analytical_slots']:slot['request_id']=mapping[slot['request_id']]
manifest.update(status='draft_not_registered_not_executed',execution_revision_id='regional-execution-contract-20261028',
    created_utc=datetime.now(timezone.utc).isoformat(),previous_condition='regional-prompt-comparison-20261028',
    amendment='Append explicit execution checklist to every previous prompt; no parent, model, sampling seed, token budget or evaluator change',
    inference_limit='Combined checklist package; cannot attribute effects separately to imports, shape, examples or bounded-work wording. Sequential exploratory follow-up, not independent confirmatory replication.')
(target/'draft_comparison_manifest.json').write_text(json.dumps(manifest,indent=2),encoding='utf-8')
(target/'PROTOCOL.md').write_text('''# Execution-contract prompt follow-up

Fourteen fresh requests, paired to the fourteen previous prompts. Preserve the same seven historical references, two parent-selection strategies, two original prompt profiles, sampling seeds, qwen2.5:3b settings, and twenty-second research evaluator. Append the saved execution checklist to all prompts. The complete package is the changed factor; its individual clauses are not isolated ablations.

This is new generation, not repair or replacement of old failures. No candidate editing, retries, repair calls, adaptive changes, or early stopping. Shared parent/profile requests remain shared between analytical slots. Log every successful and failed attempt in a new platform revision. Retain raw responses, generated code, coordinates when available, scores and errors. Compare validity, runtime and failure types to the prior condition; inspect quality and mechanism diversity only where supported. No official-verifier equivalence or guaranteed target achievement is claimed.

Registration freezes model digest, environment, evaluator hashes, runner and request order before any call. Historical programs remain textual archival references, not comparable currently evaluated incumbents. No new NBN placement is claimed by this run.
''',encoding='utf-8')
print(target)
