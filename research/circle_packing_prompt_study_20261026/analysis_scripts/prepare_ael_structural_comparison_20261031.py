"""Freeze a matched, finite prompt-pair follow-up; no generation or evaluation."""
import copy,difflib,hashlib,json,shutil,zipfile
from pathlib import Path

NAME='ael_structural_prompt_comparison_20261031';REVISION='ael-structural-prompt-comparison-20261031'
base=Path(__file__).resolve().parents[1];prior=base/'output/ael_operator_pilot_20261031';out=base/'output'/NAME
def sha(raw):return hashlib.sha256(raw).hexdigest()
def load(p):return json.loads(p.read_text(encoding='utf-8'))
def save(p,value):
    with p.open('x',encoding='utf-8',newline='\n') as f:json.dump(value,f,indent=2,allow_nan=False)
def write(p,value):
    with p.open('x',encoding='utf-8',newline='\n') as f:f.write(value)
assert not out.exists(),'Existing follow-up: inspect rather than duplicate'
integrity=load(prior/'ARTIFACT_INTEGRITY.json')
for item in integrity['files']:assert sha((prior/item['path']).read_bytes())==item['sha256'],item['path']
baseline=load(prior/'manifest.json');baseline_reg=load(prior/'registration.json')['frozen'];baseline_result=load(prior/'results.json')
assert sha((prior/'manifest.json').read_bytes())==baseline_reg['manifest_sha256'] and baseline_result['status']=='completed'
old_cross=(prior/'crossover_template.txt').read_text(encoding='utf-8');old_mut=(prior/'mutation_template.txt').read_text(encoding='utf-8')
old_cross_instruction='Use the supplied parent descriptions and programs to construct one new optimization algorithm. Draw useful ideas from the parents while producing a distinct implementation. Explain the combined idea briefly inside the function docstring.'
new_cross_instruction='''Construct one new optimization algorithm that integrates a substantive computational component from each supplied parent. Change the computational workflow so that the executable function body is not a copy of either parent. Moving imports, renaming variables, changing comments or docstrings, and restating a hybrid idea without changing computation do not count as integration. In the function docstring, identify one component taken from each parent and explain how they interact in the implemented workflow. Keep computation bounded for the stated budget.

Before returning the complete source, check that every external name used anywhere in it is explicitly imported, including names in type annotations. If you use np, qmc, minimize, Voronoi or another external symbol, include the corresponding numpy/scipy/math import. Do not assume imports from the parents or evaluator remain in scope. Perform this check in your response preparation; output only the requested Python code block.'''
old_mut_instruction='Produce a revised version of the supplied algorithm, using its description and code as the starting point. State the modification briefly in the function docstring and return the revised complete program.'
new_mut_instruction='''Produce one revised version of the actual crossover algorithm with one substantive computational modification to its initialization, optimization search, constraint handling or termination. An unchanged function body, import-only change, variable renaming, comment or docstring rewrite does not count as a computational modification. Describe the specific implemented modification briefly in the function docstring and return the complete revised source. Keep computation bounded for the stated budget.

Before returning the complete source, check that every external name used anywhere in it is explicitly imported, including names in type annotations. If you use np, qmc, minimize, Voronoi or another external symbol, include the corresponding numpy/scipy/math import. Do not assume imports from the crossover context or evaluator remain in scope. Perform this check in your response preparation; output only the requested Python code block.'''
assert old_cross.count(old_cross_instruction)==1 and old_mut.count(old_mut_instruction)==1
cross=old_cross.replace(old_cross_instruction,new_cross_instruction);mut=old_mut.replace(old_mut_instruction,new_mut_instruction)
out.mkdir();write(out/'crossover_template.txt',cross);write(out/'mutation_template.txt',mut)
write(out/'PROMPT_CHANGES.diff',''.join(difflib.unified_diff(old_cross.splitlines(True),cross.splitlines(True),fromfile='baseline/crossover_template.txt',tofile='structural_import/crossover_template.txt'))+'\n'+''.join(difflib.unified_diff(old_mut.splitlines(True),mut.splitlines(True),fromfile='baseline/mutation_template.txt',tofile='structural_import/mutation_template.txt')))
m=copy.deepcopy(baseline);m.update(status='prepared_not_executed',name=NAME,execution_revision_id=REVISION,previous_condition=baseline['execution_revision_id'],
    amendment='Joint structural-change and complete-import prompt requirements; same historical pairs/seeds and model/evaluator package. Existing baseline outcomes reused, not rerun.',
    baseline_provenance=dict(git_commit='1475ae764d87a828c3d7ae34f1308e31750b33fa',folder='ael_operator_pilot_20261031',manifest_sha256=sha((prior/'manifest.json').read_bytes()),results_sha256=sha((prior/'results.json').read_bytes()),registration_sha256=sha((prior/'registration.json').read_bytes()),artifact_inventory_sha256=sha((prior/'ARTIFACT_INTEGRITY.json').read_bytes()),existing_model_calls=12,existing_result_reuse=True),
    runtime_expectation=dict(model_blob_sha256=baseline_reg['runtime_identity']['model_blob_sha256'],binary_sha256=baseline_reg['runtime_identity']['binary_sha256'],chat_template_sha256=baseline_reg['runtime_identity']['chat_template_sha256'],runtime_registration=baseline_reg['runtime_identity']['runtime_registration'],numpy=baseline_reg['numpy'],scipy=baseline_reg['scipy'],minimum_free_gpu_mib=16384,idle_gpu_utilization=0),
    factor='Joint prompt-pair intervention: explicit computational change plus complete imports',
    template_sha256=dict(crossover=sha(cross.encode()),mutation=sha(mut.encode())),chains=[])
m['limitations']+=['Sequential follow-up reuses prior baseline; serving load/time and stochastic GPU variation are not randomized or removed','Structural and import instructions change together; cannot isolate their individual effects','Only crossover comparisons share identical historical input parents. Mutation compares complete workflows because new crossover outputs differ','Post-baseline hypothesis motivated by observed copying/missing imports; not a prospectively independent confirmatory trial']
m['adaptations']+=['New structural/import requirements are researcher-designed AEL-inspired adaptations, not verbatim paper prompts']
m['stopping_rule']='Six matched chains, at most twelve new LLM calls, independent of copying/quality/target. No baseline reruns, repairs, manual candidate edits, replacement calls, repeated evaluations or extension.'
for c in baseline['chains']:
    n=copy.deepcopy(c);n.update(chain_id='structural-'+c['chain_id'],crossover_id='structural-'+c['crossover_id'],mutation_id='structural-'+c['mutation_id'],baseline_chain_id=c['chain_id'],baseline_crossover_id=c['crossover_id'],baseline_mutation_id=c['mutation_id'])
    old_payload=load(prior/c['crossover_id']/'api_payload.json');api=copy.deepcopy(old_payload)
    original=api['messages'][1]['content'];assert original.count(old_cross_instruction)==1
    api['messages'][1]['content']=original.replace(old_cross_instruction,new_cross_instruction)
    # Every request field except the user operator instruction remains identical.
    check=copy.deepcopy(api);check['messages'][1]['content']=check['messages'][1]['content'].replace(new_cross_instruction,old_cross_instruction)
    assert check==old_payload
    folder=out/n['crossover_id'];folder.mkdir();write(folder/'prompt.txt',api['messages'][1]['content']);save(folder/'api_payload.json',api)
    n['prompt_sha256']=sha(api['messages'][1]['content'].encode());n['payload_sha256']=sha(json.dumps(api,sort_keys=True).encode())
    assert n['payload_sha256']!=c['payload_sha256']
    m['chains'].append(n)
save(out/'manifest.json',m)
write(out/'PROTOCOL.md','''# AEL matched structural/import prompt-pair follow-up

This is a separately identified, post-baseline preliminary condition. It tests a joint prompt intervention addressing parent-body copying and missing imports observed in the completed AEL operator pilot. It does not reproduce a verbatim paper prompt or the full population experiment.

Reuse the twelve saved baseline outcomes from ael_operator_pilot_20261031. Verify its manifest, results, registration and all inventoried evidence. Do not request baseline outputs again. Run the same six historical pairs in the same order, with the same pair-selection labels and per-stage sampling seeds, using one revised crossover/mutation template pair. Preserve every original historical context byte, parent source/score/NBN identity, task contract, system prompt, model weights/build, context/token budget, sampling fields and twenty-second evaluator/thread limits. Only the operator instructions change. PROMPT_CHANGES.diff records them exactly.

The crossover instruction explicitly requires integrated computational components from both parents and a changed executable workflow. The mutation instruction requires one substantive computational modification. Both require complete explicit imports. This is a bundled intervention: no individual causal claim about structural wording versus import wording is permitted.

For each chain, generate and evaluate crossover once. Mutate that actual extracted/static-contract-eligible program regardless of its measured score, geometry, timeout or exception. Mutation receives source/docstring, not evaluation feedback. Extraction/static failure causes a recorded dependent skip. Copying/noncompliance is measured, not a gate for retry, rejection, manual editing, mutation or replacement. All duplicate, invalid, missing-import, timeout and successful outcomes remain in history. Stop after six chains, at most twelve new calls regardless of target attainment. No repairs or repeated evaluations.

New generations require the same pinned Qwen2.5-Coder7B Q4_K_M/llama.cpp b6780 model, binary and chat-template hashes. Start only our private service when a GPU has >=16384MiB free and zero reported utilization, as in the prior pilot. Preserve allocation and context-fit checks before generation; wait or report pending if unavailable. Never lower resource requirements silently, download another model, use another service or stop shared workloads. Release only this condition's identified private process after execution.

Before the first request, register source/configuration/runtime hashes, exact prompts and baseline linkage in platform history. Crossovers have two historical parent links. Mutation parents have generated call/revision/hash links with no invented NBN node. Add a recorded strategy-change link to the baseline condition. Keep raw API requests/responses, extracted code, stdout/stderr, returned arrays, status/undefined fitness and timing.

Compare each matched crossover's validity, missing-import exception, score, target hit >=2.6360, exact source/full-AST/normalized-body matches to its selected parents and eligible pool, and manually inspected implemented mechanisms. Compare mutation and final workflow outcomes, including unchanged crossover bodies and score/validity differences where defined. Because mutation inputs differ, mutation-stage comparisons do not isolate mutation-prompt effects. Different source hashes or variable names alone do not establish structural diversity. Do not assign a finite fitness to failures or claim new NBN placement without an actual embedding/graph calculation.

The six paired cases are descriptive only. The baseline was run earlier, not concurrently randomized; GPU load/time and nondeterministic inference can remain confounders. Parent-selection policies also differ in source quality. Report effect directions and failures without asserting significance, policy superiority, paper reproduction or official challenge-verifier equivalence. Distinguish new prompt changes proposed after observing baseline failures from independent confirmatory evidence. Independently check saved geometry and sums without rerunning candidate programs.
''')
# Freeze package-specific copies; original pilot scripts and outcomes stay intact.
for name in ['ael_pilot_common.py','ael_pilot_gpu.py','ael_pilot_history.py','run_ael_operator_pilot_20261031.py']:
    s=(prior/name).read_text(encoding='utf-8')
    if name=='ael_pilot_common.py':s=s.replace("NAME='ael_operator_pilot_20261031'",f"NAME='{NAME}'").replace("REVISION='ael-operator-pilot-20261031'",f"REVISION='{REVISION}'")
    if name=='ael_pilot_gpu.py':
        old="props=api('/props');save(root/'runtime_props.json',props)"
        new=old+"\n    assert sha(str(props.get('chat_template','')).encode())==m['runtime_expectation']['chat_template_sha256'],'Chat template differs from baseline'\n    assert load(root.parent/'llama_gpu_runtime_b6780/registration.json')==m['runtime_expectation']['runtime_registration'],'Runtime build provenance differs'"
        assert old in s;s=s.replace(old,new)
    if name=='ael_pilot_history.py':
        s=s.replace("mode='ael_operator_pilot'","mode='ael_matched_prompt_followup'")
        marker="save(root/'registration.json',dict(frozen=frozen));append_event(directory,'operator_pilot_registered',dict(manifest=m,registration=frozen));"
        assert marker in s
        s=s.replace(marker,"save(root/'registration.json',dict(frozen=frozen));append_event(directory,'comparison_registered',dict(manifest=dict(previous_condition=m['previous_condition'],amendment=m['amendment'],stopping_rule=m['stopping_rule'])));append_event(directory,'operator_pilot_registered',dict(manifest=m,registration=frozen));")
    if name=='run_ael_operator_pilot_20261031.py':
        s=s.replace("promptProfile='AEL-'+operator","promptProfile='AEL-structural-import-'+operator")
        s=s.replace("originCallId=chain['crossover_id'],codeSha256=", "originCallId=chain['crossover_id'],originRevisionId=REVISION,codeSha256=")
    write(out/name,s)
save(out/'MATCHING_AUDIT.json',dict(passed=True,baseline_files_verified=len(integrity['files']),baseline_calls_reused=12,new_maximum_calls=12,matched_historical_pairs=6,all_non_user_instruction_payload_fields_unchanged=True,baseline_manifest_sha256=sha((prior/'manifest.json').read_bytes()),new_manifest_sha256=sha((out/'manifest.json').read_bytes()),new_crossover_ids=[c['crossover_id'] for c in m['chains']]))
# Freeze a small upload. Existing 14,000-program graph stays in place.
with zipfile.ZipFile(base/'output'/f'{NAME}_upload.zip','x',zipfile.ZIP_DEFLATED) as z:
    for p in out.rglob('*'):
        if p.is_file():z.write(p,p.relative_to(out).as_posix())
print(json.dumps(dict(status='prepared_no_calls',folder=str(out),pairs=6,maximum_new_calls=12,baseline_calls_reused=12),indent=2))
