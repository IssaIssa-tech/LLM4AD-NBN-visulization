"""Ten prospective matched seed pairs, with frozen algorithms and no tuning."""
import argparse, ast, hashlib, json, platform, shutil, sys
from datetime import datetime, timezone
from pathlib import Path

SEEDS=list(range(20261201,20261211))
def sha(source): return hashlib.sha256(source.encode()).hexdigest()
def prepare():
    root=Path(__file__).resolve().parents[1];base=root/'output/circle_prompt_effects_20261026'
    out=base/'heldout_initialization_validation_20261027'
    if out.exists():raise SystemExit('Existing validation; refusing overwrite')
    sources={name:(base/'feasible_initialization_test_20261027'/folder/'candidate.py').read_text()
             for name,folder in [('original','original_annealed'),('feasible','feasible_annealed')]}
    marker='qmc.Sobol(d=2, scramble=True, seed=2025)'
    assert all(source.count(marker)==1 for source in sources.values())
    out.mkdir();pairs=[]
    for offset,seed in enumerate(SEEDS):
        programs=[]
        # Alternate order to reduce systematic ordering effects.
        order=['original','feasible'] if offset%2==0 else ['feasible','original']
        for name in order:
            source=sources[name].replace(marker,f'qmc.Sobol(d=2, scramble=True, seed={seed})')
            ast.parse(source)
            relative=f'seed-{seed}/{name}/candidate.py';path=out/relative;path.parent.mkdir(parents=True)
            path.write_text(source,encoding='utf-8')
            programs.append(dict(condition=name,file=relative,sha256=sha(source)))
        pairs.append(dict(sobol_seed=seed,programs=programs))
    for filename in ('evaluate_circle_prompt_candidates.py',):shutil.copy2(root/'analysis'/filename,out)
    shutil.copy2(__file__,out/'validate_initialization_heldout.py')
    manifest=dict(registered_utc=datetime.now(timezone.utc).isoformat(),purpose='Prospective held-out Sobol seed validation of frozen initialization choice',
        provenance='Prepared source algorithms; no LLM calls',sobol_seeds=SEEDS,n=26,numpy_random_seed=2025,
        timeout_seconds=20,quality_floor=1.0,geometry_tolerance=1e-12,llm_calls=0,
        stopping_rule='Exactly ten complete pairs, one evaluation per program; no repair, replacement, tuning or optional stopping',
        primary='Report validity for both conditions and paired score differences where both are valid',
        decision='Support improvement on this cohort only if feasible has no lower valid count, positive mean paired difference and more pairwise wins than losses; any missing pairs must be reported',
        limitations='Fixed consecutive seeds, small cohort, single n=26 and fixed NumPy seed; not independent LLM candidates or broad generalization',
        parent_hashes={k:sha(v) for k,v in sources.items()},
        evaluator_sha256=hashlib.sha256((out/'evaluate_circle_prompt_candidates.py').read_bytes()).hexdigest(),pairs=pairs)
    (out/'manifest.json').write_text(json.dumps(manifest,indent=2));print(out)

def run():
    root=Path(__file__).resolve().parent;sys.path.insert(0,str(root))
    from evaluate_circle_prompt_candidates import evaluate
    import numpy,scipy
    if (root/'ledger.jsonl').exists() or (root/'results.json').exists():raise SystemExit('Existing validation results; refusing rerun')
    manifest=json.loads((root/'manifest.json').read_text())
    assert hashlib.sha256((root/'evaluate_circle_prompt_candidates.py').read_bytes()).hexdigest()==manifest['evaluator_sha256']
    env=dict(python=sys.version,numpy=numpy.__version__,scipy=scipy.__version__,host=platform.node())
    rows=[]
    for pair in manifest['pairs']:
        row=dict(sobol_seed=pair['sobol_seed'])
        for entry in pair['programs']:
            path=root/entry['file'];assert sha(path.read_text())==entry['sha256']
            evaluation=evaluate(path,manifest['timeout_seconds'])
            if evaluation['status']=='valid':evaluation['quality_gate']='pass' if evaluation['score']>=manifest['quality_floor'] else 'below_floor'
            row[entry['condition']]=evaluation
            with (root/'ledger.jsonl').open('a') as stream:stream.write(json.dumps(dict(sobol_seed=pair['sobol_seed'],condition=entry['condition'],evaluation=evaluation))+'\n')
        row['score_difference']=row['feasible']['score']-row['original']['score'] if all(row[k]['status']=='valid' for k in ('original','feasible')) else None
        rows.append(row); print(json.dumps(row),flush=True)
        (root/'progress.json').write_text(json.dumps(dict(completed_pairs=len(rows),environment=env,matched_results=rows),indent=2))
    (root/'results.json').write_text(json.dumps(dict(manifest=manifest,environment=env,matched_results=rows,completed_utc=datetime.now(timezone.utc).isoformat()),indent=2))

if __name__=='__main__':
    parser=argparse.ArgumentParser();parser.add_argument('--prepare',action='store_true');args=parser.parse_args()
    if args.prepare:prepare()
    else:run()
