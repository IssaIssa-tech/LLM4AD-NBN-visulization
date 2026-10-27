"""Offline draft planner for the evidence-based prompt/parent workflow."""
import ast,hashlib,json
from datetime import datetime,timezone
from pathlib import Path

def sha(text):return hashlib.sha256(text.encode()).hexdigest()

def main():
    root=Path(__file__).resolve().parents[1];base=root/'output/circle_prompt_effects_20261026'
    out=base/'prompt_guided_design_v1'
    if out.exists():raise SystemExit('Existing draft; refusing overwrite')
    parent=base/'m2ip_patch_preregistered_run/expected_patch_candidate.py'
    source=parent.read_text(encoding='utf-8');parsed=ast.parse(source)
    assert [n.name for n in parsed.body if isinstance(n,ast.FunctionDef)]==['pack_circles']
    results=json.loads((base/'m2ip_patch_execution_20261027/results.json').read_text())
    assert sha(source)==results['manifest']['expected_code_sha256']
    assert all(r['final']['status']=='valid' for r in results['outcomes'])
    prompt='''You are designing a Circle Packing heuristic from a verified parent.
Return exactly one Python code block containing the complete program, with
exactly one top-level function pack_circles(n: int) -> np.ndarray. Approved
imports: numpy, math and scipy. No top-level tests, calls or helper functions.
Return a finite (n, 3) array of x, y, radius values in the unit square, with
nonnegative radii and all-pairs non-overlap. The evaluator uses n=26,
maximizes sum of radii, and enforces a 20-second isolated execution limit.
Use bounded computation and deterministic random seeds. Aim for total radii
at least 1.0; avoid all-zero fallback. Preserve this function contract and
replace one substantive algorithmic component of the parent: initialization,
placement, local search or repair. Do not only rename variables or constants.
Return the entire program. Do not include prose or execution examples.
Parent program:
```python
'''+source+'```\n'
    plan=dict(status='draft_not_registered_not_executed',created_utc=datetime.now(timezone.utc).isoformat(),
        purpose='Reviewable prompt/parent-selection workflow design',
        parent=dict(file=str(parent.relative_to(root)),code_sha256=sha(source),reference_score=2.5902372123245248,
                    choice_status='proposed first parent; executable reference supported, new prompt-parent combination untested'),
        prompt=dict(name='combined_contract_M2_v1',sha256=sha(prompt),status='new version, not identical to earlier tested template'),
        proposed_model=dict(name='qwen2.5:3b',temperature=0.1,num_predict=1800,endpoint='http://127.0.0.1:11435/api/generate',status='must verify at registration'),
        proposed_sampling_seeds=list(range(20261301,20261306)),budget_calls=5,parent_changes_within_batch=False,
        evaluation=dict(n=26,timeout_seconds=20,quality_floor=1.0,evaluator_sha256=hashlib.sha256((root/'analysis/evaluate_circle_prompt_candidates.py').read_bytes()).hexdigest()),
        selection=dict(prompt='fixed M2; no adaptive selector claimed',incumbent='strict valid-score improvement; ties retain incumbent',archive='preserve all outcomes; flag raw and AST duplicates'),
        untested=['parent/template combination','incumbent-selection rule as a workflow','benefit of any future multi-parent or branch policy'])
    out.mkdir();(out/'parent_candidate.py').write_text(source,encoding='utf-8')
    (out/'prompt_M2_v1.txt').write_text(prompt,encoding='utf-8')
    (out/'draft_plan.json').write_text(json.dumps(plan,indent=2),encoding='utf-8')
    print(json.dumps(dict(output=str(out),status=plan['status'],parent_hash_verified=True,prior_valid_trials=len(results['outcomes']),network_calls=0),indent=2))

if __name__=='__main__':main()
