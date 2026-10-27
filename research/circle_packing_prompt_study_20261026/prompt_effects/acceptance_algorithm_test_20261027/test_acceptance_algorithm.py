"""Prospective paired evaluation of frozen source; no LLM calls."""
import argparse, hashlib, json, shutil, sys
from datetime import datetime, timezone
from pathlib import Path

def digest(path):
    return hashlib.sha256(path.read_text().encode()).hexdigest()

def prepare():
    root=Path(__file__).resolve().parents[1]
    source=root/'output/circle_prompt_effects_20261026/m2_acceptance_ablation_20261027'
    out=root/'output/circle_prompt_effects_20261026/acceptance_algorithm_test_20261027'
    if out.exists(): raise SystemExit('Refusing to overwrite test')
    prior=json.loads((source/'run_manifest.json').read_text())
    assert digest(source/'parent_candidate.py')==prior['parent_sha256']
    assert digest(source/'expected_candidate.py')==prior['expected_sha256']
    out.mkdir()
    for name in ('parent_candidate.py','expected_candidate.py','evaluate_circle_prompt_candidates.py'):
        shutil.copy2(source/name,out/name)
    shutil.copy2(__file__,out/'test_acceptance_algorithm.py')
    manifest=dict(registered_utc=datetime.now(timezone.utc).isoformat(),purpose='Paired algorithm-only acceptance ablation',
        provenance='Previously frozen prepared source, not accepted LLM output',n=26,algorithm_seed=2025,
        timeout_seconds=20,quality_floor=1.0,llm_calls=0,
        stopping_rule='One parent evaluation and one frozen-edit evaluation; no repair, tuning or replacement',
        limitations='Single deterministic setting; removal of acceptance RNG draws also changes later proposal streams; not a diversity or statistical superiority test',
        programs=[dict(label='parent',file='parent_candidate.py',sha256=prior['parent_sha256']),dict(label='greedy_acceptance',file='expected_candidate.py',sha256=prior['expected_sha256'])])
    (out/'manifest.json').write_text(json.dumps(manifest,indent=2))
    print(out)

def run():
    root=Path(__file__).resolve().parent
    sys.path.insert(0,str(root))
    from evaluate_circle_prompt_candidates import evaluate
    out=root/'results.json'
    if out.exists() or (root/'ledger.jsonl').exists(): raise SystemExit('Existing test; refusing duplicate')
    manifest=json.loads((root/'manifest.json').read_text())
    rows=[]
    for entry in manifest['programs']:
        path=root/entry['file']; assert digest(path)==entry['sha256']
        row=dict(label=entry['label'],evaluation=evaluate(path,20))
        rows.append(row)
        with (root/'ledger.jsonl').open('a') as stream: stream.write(json.dumps(row)+'\n')
        print(json.dumps(row),flush=True)
    out.write_text(json.dumps(dict(manifest=manifest,results=rows,completed_utc=datetime.now(timezone.utc).isoformat()),indent=2))

if __name__=='__main__':
    parser=argparse.ArgumentParser(); parser.add_argument('--prepare',action='store_true'); args=parser.parse_args()
    if args.prepare: prepare()
    else: run()
