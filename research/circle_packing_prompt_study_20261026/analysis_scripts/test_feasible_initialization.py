"""Frozen 2x2 algorithm ablation; prepared code, zero LLM calls."""
import argparse, hashlib, json, shutil, sys
from datetime import datetime, timezone
from pathlib import Path

def sha(text): return hashlib.sha256(text.encode()).hexdigest()
def prepare():
    root=Path(__file__).resolve().parents[1]
    source=root/'output/circle_prompt_effects_20261026/m2_acceptance_ablation_20261027/parent_candidate.py'
    parent=source.read_text()
    old='''    circles[:, 2] = np.minimum(np.minimum(circles[:, 0], 1 - circles[:, 0]),
                              np.minimum(circles[:, 1], 1 - circles[:, 1])) * 0.2'''
    new='''    # Deterministic feasible radii; all centres constrain every assignment.
    for i in range(n):
        x, y = circles[i, :2]
        radius = min(x, 1 - x, y, 1 - y)
        for j in range(n):
            if i != j:
                distance = np.hypot(x - circles[j, 0], y - circles[j, 1])
                radius = min(radius, distance - circles[j, 2])
        circles[i, 2] = max(0.0, radius)'''
    acceptance='if best_r > r or np.random.random() < np.exp((best_r - r)/temperature):'
    assert parent.count(old)==1 and parent.count(acceptance)==1
    out=root/'output/circle_prompt_effects_20261026/feasible_initialization_test_20261027'
    if out.exists(): raise SystemExit('Existing test; refusing overwrite')
    out.mkdir(); rows=[]
    for feasible in (False,True):
        for monotone in (False,True):
            label=('feasible' if feasible else 'original')+'_'+('monotone' if monotone else 'annealed')
            code=parent.replace(old,new) if feasible else parent
            if monotone: code=code.replace(acceptance,'if best_r > r:')
            d=out/label; d.mkdir(); (d/'candidate.py').write_text(code)
            rows.append(dict(label=label,feasible_initialization=feasible,monotone_acceptance=monotone,sha256=sha(code)))
    shutil.copy2(root/'analysis/evaluate_circle_prompt_candidates.py',out)
    shutil.copy2(__file__,out/'test_feasible_initialization.py')
    manifest=dict(registered_utc=datetime.now(timezone.utc).isoformat(),purpose='2x2 initialization/acceptance algorithm ablation',
        provenance='Prepared researcher-specified code; no LLM generation',n=26,seed=2025,timeout_seconds=20,
        quality_floor=1.0,geometry_tolerance=1e-12,repairs=0,llm_calls=0,
        stopping_rule='Exactly one evaluation per frozen condition, no tuning or replacement',
        hypothesis='Feasible initialization may remove persistent initial overlaps under monotone acceptance; quality improvement is unknown',
        limitation='One deterministic setting; changing acceptance changes RNG consumption; no structural-diversity or statistical superiority claim',conditions=rows)
    (out/'manifest.json').write_text(json.dumps(manifest,indent=2)); print(out)

def run():
    root=Path(__file__).resolve().parent; sys.path.insert(0,str(root))
    from evaluate_circle_prompt_candidates import evaluate
    if (root/'ledger.jsonl').exists() or (root/'results.json').exists(): raise SystemExit('Existing evaluations')
    manifest=json.loads((root/'manifest.json').read_text()); rows=[]
    for condition in manifest['conditions']:
        path=root/condition['label']/'candidate.py'; assert sha(path.read_text())==condition['sha256']
        result=evaluate(path,20); row=dict(condition=condition,evaluation=result); rows.append(row)
        with (root/'ledger.jsonl').open('a') as stream: stream.write(json.dumps(row)+'\n')
        print(condition['label'],result['status'],result.get('score'),flush=True)
    (root/'results.json').write_text(json.dumps(dict(manifest=manifest,results=rows),indent=2))

if __name__=='__main__':
    p=argparse.ArgumentParser(); p.add_argument('--prepare',action='store_true'); args=p.parse_args()
    if args.prepare: prepare()
    else: run()
