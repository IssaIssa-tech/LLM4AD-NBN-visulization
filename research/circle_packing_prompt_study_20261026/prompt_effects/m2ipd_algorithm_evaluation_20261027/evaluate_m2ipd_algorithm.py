"""Separate prospective test of frozen Sobol-seed variants; no LLM calls."""
import argparse
import ast
import hashlib
import json
import platform
import shutil
import sys
from datetime import datetime, timezone
from pathlib import Path

def digest(text):
    return hashlib.sha256(text.encode()).hexdigest()

def prepare(root):
    source = root/'output/circle_prompt_effects_20261026/m2ipd_preregistered_run'
    target = root/'output/circle_prompt_effects_20261026/m2ipd_algorithm_evaluation_20261027'
    if target.exists():
        raise SystemExit('Existing evaluation directory; inspect before proceeding.')
    frozen = json.loads((source/'run_manifest.json').read_text())
    candidates = []
    for trial in frozen['trials']:
        code = (source/trial['trial_id']/'expected_candidate.py').read_text()
        assert digest(code) == trial['expected_code_sha256']
        candidates.append((trial['trial_id'], code))
    # All executable differences must be the intended Sobol seed literal.
    normalized = []
    for trial_id, code in candidates:
        tree = ast.parse(code)
        for node in ast.walk(tree):
            if isinstance(node, ast.Call) and isinstance(node.func, ast.Attribute) and node.func.attr == 'Sobol':
                for keyword in node.keywords:
                    if keyword.arg == 'seed': keyword.value = ast.Constant(value=0)
        normalized.append(ast.dump(tree, include_attributes=False))
    assert len(set(normalized)) == 1
    target.mkdir()
    for trial_id, code in candidates:
        folder = target/trial_id
        folder.mkdir()
        (folder/'candidate.py').write_text(code, encoding='utf-8')
    shutil.copy2(root/'analysis/evaluate_circle_prompt_candidates.py',target)
    shutil.copy2(Path(__file__), target/'evaluate_m2ipd_algorithm.py')
    manifest = dict(purpose='Algorithm-only evaluation of five previously frozen expected Sobol variants',
        registered_utc=datetime.now(timezone.utc).isoformat(), provenance='Prepared expected source; not successful LLM outputs',
        n=26, timeout_seconds=20, quality_floor=1.0, geometry_epsilon=1e-12,
        precheck=False, llm_calls=0, stopping_rule='Evaluate each of five fixed candidates once; no selection or repair',
        interpretation='Seed sensitivity within one algorithm family; no structural-diversity claim',
        evaluator_sha256=hashlib.sha256((target/'evaluate_circle_prompt_candidates.py').read_bytes()).hexdigest(),
        trials=[dict(trial_id=t, sobol_seed=int(t.split('-')[-1]), code_sha256=digest(c)) for t,c in candidates])
    (target/'algorithm_manifest.json').write_text(json.dumps(manifest,indent=2))
    print(target)

def run(folder):
    sys.path.insert(0,str(folder))
    from evaluate_circle_prompt_candidates import evaluate
    import numpy, scipy
    output=folder/'algorithm_results.json'
    if output.exists() or (folder/'algorithm_ledger.jsonl').exists():
        raise SystemExit('Refusing to repeat existing evaluations')
    manifest=json.loads((folder/'algorithm_manifest.json').read_text())
    rows=[]
    for trial in manifest['trials']:
        path=folder/trial['trial_id']/'candidate.py'
        assert digest(path.read_text())==trial['code_sha256']
        result=evaluate(path,manifest['timeout_seconds'])
        result.update(trial_id=trial['trial_id'],sobol_seed=trial['sobol_seed'])
        rows.append(result)
        with (folder/'algorithm_ledger.jsonl').open('a') as stream: stream.write(json.dumps(result)+'\n')
        print(trial['trial_id'],result['status'],result.get('score'),flush=True)
    output.write_text(json.dumps(dict(manifest=manifest,environment=dict(python=sys.version,numpy=numpy.__version__,scipy=scipy.__version__,host=platform.node()),results=rows),indent=2))

if __name__=='__main__':
    parser=argparse.ArgumentParser()
    parser.add_argument('--prepare',action='store_true')
    args=parser.parse_args()
    if args.prepare: prepare(Path(__file__).resolve().parents[1])
    else: run(Path(__file__).resolve().parent)
