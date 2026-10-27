"""Register and run one local-LLM acceptance-rule ablation."""
import argparse, ast, hashlib, json, re, shutil, sys, urllib.request
from datetime import datetime, timezone
from pathlib import Path

def sha(text): return hashlib.sha256(text.encode()).hexdigest()
def tree(text): return ast.dump(ast.parse(text),include_attributes=False)
def extract(response):
    blocks=re.findall(r'```(?:python)?\s*\n(.*?)```',response,re.S|re.I)
    if not blocks: blocks=[response]
    eligible=[]
    for block in blocks:
        try:
            parsed=ast.parse(block.strip())
            if any(isinstance(n,ast.FunctionDef) and n.name=='pack_circles' for n in parsed.body): eligible.append(block.strip()+'\n')
        except SyntaxError: pass
    if len(eligible)!=1: raise ValueError(f'Expected one complete program; found {len(eligible)}')
    return eligible[0]

def prepare():
    root=Path(__file__).resolve().parents[1]
    out=root/'output/circle_prompt_effects_20261026/m2_acceptance_ablation_20261027'
    if out.exists(): raise SystemExit('Refusing to overwrite registered experiment')
    parent=(root/'output/circle_prompt_effects_20261026/m2ip_patch_preregistered_run/expected_patch_candidate.py').read_text()
    old='if best_r > r or np.random.random() < np.exp((best_r - r)/temperature):'
    new='if best_r > r:'
    assert parent.count(old)==1
    expected=parent.replace(old,new)
    # A different comment must not change eligibility under the new AST rule.
    assert tree(expected)==tree(expected.replace('# Acceptance with cosine annealing','# Acceptance: only radius increases'))
    assert tree(expected)!=tree(parent)
    assert extract('```python\nx = 1\n```\n```python\n'+expected+'```')==expected.strip()+'\n'
    prompt=('Return exactly one Python code block containing the COMPLETE parent program with the single edit specified below. '
        'Include imports, the full pack_circles function, and its return statement. Do not return only the edited snippet.\n'
        'Replace this condition:\n'+old+'\nwith:\n'+new+'\n'
        'Keep every other executable statement and every seed unchanged. Comments and whitespace may differ. '
        'Do not add tests or top-level execution.\nParent program:\n```python\n'+parent+'```\n')
    out.mkdir()
    (out/'parent_candidate.py').write_text(parent)
    (out/'expected_candidate.py').write_text(expected)
    shutil.copy2(root/'analysis/evaluate_circle_prompt_candidates.py',out)
    shutil.copy2(Path(__file__),out/'run_m2_acceptance_ablation.py')
    trials=[]
    for seed in range(20261140,20261145):
        trial_id=f'm2-acceptance-{seed}'; folder=out/trial_id; folder.mkdir()
        (folder/'prompt.txt').write_text(prompt)
        trials.append(dict(trial_id=trial_id,sampling_seed=seed,prompt_sha256=sha(prompt)))
    manifest=dict(registered_utc=datetime.now(timezone.utc).isoformat(),condition='M2 acceptance-rule ablation',
        hypothesis='Removing acceptance of shrinking moves may change quality; improvement is not assumed',
        parent_score_reference=2.5902372123245248,parent_sha256=sha(parent),expected_sha256=sha(expected),
        model='qwen2.5:3b',endpoint='http://127.0.0.1:11435/api/generate',temperature=0.1,num_predict=1800,
        algorithm_seed=2025,n=26,timeout_seconds=20,quality_floor=1.0,repair_calls=0,
        eligibility='Exactly one complete program whose AST equals the frozen expected program; comments/formatting ignored',
        stopping_rule='Five one-call requests; no replacements, repairs or post-hoc seed selection',
        limitations=['Same algorithm seed; repeated accepted code is delivery reliability, not five independent quality samples',
                    'Removing random acceptance also removes RNG draws and changes later proposal streams',
                    'AST rule differs from previous byte-exact rule; compliance rates are not directly comparable'],trials=trials)
    (out/'run_manifest.json').write_text(json.dumps(manifest,indent=2))
    print(out)

def run():
    root=Path(__file__).resolve().parent
    sys.path.insert(0,str(root))
    from evaluate_circle_prompt_candidates import evaluate
    ledger=root/'generation_ledger.jsonl'
    if ledger.exists() or (root/'results.json').exists(): raise SystemExit('Existing run; refusing duplicate execution')
    manifest=json.loads((root/'run_manifest.json').read_text())
    expected=(root/'expected_candidate.py').read_text()
    assert sha(expected)==manifest['expected_sha256']
    # Contemporaneous parent reference is an evaluation, not an LLM trial.
    control=evaluate(root/'parent_candidate.py',20)
    (root/'parent_reference_evaluation.json').write_text(json.dumps(control,indent=2))
    rows=[]
    for trial in manifest['trials']:
        folder=root/trial['trial_id']; row=dict(trial_id=trial['trial_id'],sampling_seed=trial['sampling_seed'])
        try:
            prompt=(folder/'prompt.txt').read_text(); assert sha(prompt)==trial['prompt_sha256']
            payload=dict(model=manifest['model'],prompt=prompt,stream=False,keep_alive='0',options=dict(temperature=0.1,seed=trial['sampling_seed'],num_predict=1800))
            (folder/'request.json').write_text(json.dumps(payload,indent=2))
            req=urllib.request.Request(manifest['endpoint'],data=json.dumps(payload).encode(),headers={'Content-Type':'application/json'})
            with urllib.request.urlopen(req,timeout=600) as response: reply=json.loads(response.read())
            (folder/'raw_reply.json').write_text(json.dumps(reply,indent=2))
            (folder/'response.txt').write_text(reply.get('response',''))
            candidate=extract(reply.get('response',''))
            path=folder/'candidate.py'; path.write_text(candidate)
            row.update(code_sha256=sha(candidate),ast_match=tree(candidate)==tree(expected),done_reason=reply.get('done_reason'))
            row['evaluation']=evaluate(path,20) if row['ast_match'] else dict(status='rejected_ast_patch_guard',score=None)
        except Exception as exc: row['evaluation']=dict(status='pipeline_or_extraction_error',score=None,error=f'{type(exc).__name__}: {exc}')
        row['timestamp_utc']=datetime.now(timezone.utc).isoformat(); rows.append(row)
        with ledger.open('a') as stream: stream.write(json.dumps(row)+'\n')
        print(json.dumps(row),flush=True)
    (root/'results.json').write_text(json.dumps(dict(manifest=manifest,parent_reference=control,outcomes=rows),indent=2))

if __name__=='__main__':
    parser=argparse.ArgumentParser(); parser.add_argument('--prepare',action='store_true'); args=parser.parse_args()
    if args.prepare: prepare()
    else: run()
