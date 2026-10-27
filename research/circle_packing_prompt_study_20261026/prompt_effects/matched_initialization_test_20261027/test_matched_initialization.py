"""Matched-seed initialization test reusing frozen earlier controls."""
import argparse,hashlib,json,shutil,sys
from datetime import datetime,timezone
from pathlib import Path
def sha(s): return hashlib.sha256(s.encode()).hexdigest()
def prepare():
    root=Path(__file__).resolve().parents[1]; base=root/'output/circle_prompt_effects_20261026'
    out=base/'matched_initialization_test_20261027'
    if out.exists(): raise SystemExit('Existing test; refusing overwrite')
    source=base/'feasible_initialization_test_20261027/feasible_annealed/candidate.py'
    code=source.read_text(); old='qmc.Sobol(d=2, scramble=True, seed=2025)'; assert code.count(old)==1
    control_path=base/'m2ipd_algorithm_evaluation_20261027/algorithm_results.json'
    controls=json.loads(control_path.read_text())
    out.mkdir(); trials=[]
    for row in controls['results']:
        seed=row['sobol_seed']; label=f'feasible-{seed}'
        candidate=code.replace(old,f'qmc.Sobol(d=2, scramble=True, seed={seed})')
        d=out/label; d.mkdir(); (d/'candidate.py').write_text(candidate)
        trials.append(dict(label=label,sobol_seed=seed,sha256=sha(candidate),original_control=row))
    shutil.copy2(root/'analysis/evaluate_circle_prompt_candidates.py',out)
    shutil.copy2(__file__,out/'test_matched_initialization.py')
    (out/'control_results.json').write_text(json.dumps(controls,indent=2))
    manifest=dict(registered_utc=datetime.now(timezone.utc).isoformat(),purpose='Five matched Sobol-seed initialization comparisons',
        provenance='Prepared algorithm variants; no LLM calls',algorithm_random_seed=2025,timeout_seconds=20,n=26,quality_floor=1.0,
        stopping_rule='Evaluate five feasible-initialization variants once each; reuse existing original controls; no tuning or replacement',
        control_source=str(control_path.relative_to(root)),control_file_sha256=hashlib.sha256(control_path.read_bytes()).hexdigest(),
        limitations='Reused earlier controls, not interleaved contemporaneous controls; fixed five seeds are exploratory; no statistical superiority claim',trials=trials)
    (out/'manifest.json').write_text(json.dumps(manifest,indent=2)); print(out)
def run():
    root=Path(__file__).resolve().parent;sys.path.insert(0,str(root))
    from evaluate_circle_prompt_candidates import evaluate
    if (root/'ledger.jsonl').exists() or (root/'results.json').exists(): raise SystemExit('Existing evaluations')
    manifest=json.loads((root/'manifest.json').read_text()); rows=[]
    for trial in manifest['trials']:
        path=root/trial['label']/'candidate.py'; assert sha(path.read_text())==trial['sha256']
        result=evaluate(path,20); control=trial['original_control']
        delta=result['score']-control['score'] if result['status']=='valid' and control['status']=='valid' else None
        row=dict(sobol_seed=trial['sobol_seed'],original=control,feasible=result,score_difference=delta); rows.append(row)
        with (root/'ledger.jsonl').open('a') as f:f.write(json.dumps(row)+'\n')
        print(trial['sobol_seed'],result['status'],result.get('score'),'delta',delta,flush=True)
    (root/'results.json').write_text(json.dumps(dict(manifest=manifest,matched_results=rows),indent=2))
if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('--prepare',action='store_true');a=p.parse_args()
    if a.prepare:prepare()
    else:run()
