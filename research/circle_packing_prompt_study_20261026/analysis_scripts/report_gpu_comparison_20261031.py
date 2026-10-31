"""Consolidate the finite study's saved records only; never regenerate or execute."""
import argparse,ast,hashlib,json
from collections import Counter
from pathlib import Path
parser=argparse.ArgumentParser();parser.add_argument('root',type=Path);args=parser.parse_args();root=args.root
manifest=json.loads((root/'draft_comparison_manifest.json').read_text(encoding='utf-8'))
if (root/'RESULTS.json').exists():raise SystemExit('Existing report; inspect instead of overwrite')
rows=[]
for request in manifest['unique_requests']:
    folder=root/request['request_id'];path=folder/'outcome.json'
    if not path.exists():raise SystemExit('Study incomplete; no report emitted')
    outcome=json.loads(path.read_text(encoding='utf-8'))
    row=dict(request_id=request['request_id'],parent=request['parent'],profile=request['prompt_profile'],status=outcome['status'],score=outcome.get('score'),error=outcome.get('error'),screening=outcome.get('screening'),generation_finish=outcome.get('generation_done_reason'),generation_usage=outcome.get('generation_usage'),generation_seconds=outcome.get('generation_wall_seconds'),total_seconds=outcome.get('wall_seconds'))
    if (folder/'candidate.py').exists():
        code=(folder/'candidate.py').read_text(encoding='utf-8');row['code_sha256']=hashlib.sha256(code.encode()).hexdigest()
        try:
            tree=ast.parse(code);row['ast_sha256']=hashlib.sha256(ast.dump(tree,include_attributes=False).encode()).hexdigest()
            row['mechanism_inspection_aids']=dict(imports=[ast.unparse(n) for n in ast.walk(tree) if isinstance(n,(ast.Import,ast.ImportFrom))],loop_iterables=[ast.unparse(n.iter) for n in ast.walk(tree) if isinstance(n,ast.For)],while_count=sum(isinstance(n,ast.While) for n in ast.walk(tree)))
        except SyntaxError:row['ast_sha256']=None
    rows.append(row)
assert len(rows)==14 and len({r['request_id'] for r in rows})==14
by_id={r['request_id']:r for r in rows}
def stats(selected):
    scores=[r['score'] for r in selected if r['status']=='valid']
    return dict(slots=len(selected),statuses=dict(Counter(r['status'] for r in selected)),valid_scores=scores,best_valid_score=max(scores) if scores else None,target_hits=sum(s>=2.6360 for s in scores),unique_valid_code_hashes=len({r.get('code_sha256') for r in selected if r['status']=='valid'}))
cells=[]
for strategy in manifest['factors']['parent_selection']:
    for profile in manifest['factors']['prompt_profile']:
        selected=[by_id[s['request_id']] for s in manifest['analytical_slots'] if s['strategy']==strategy and s['prompt_profile']==profile]
        assert len(selected)==4
        cells.append(dict(strategy=strategy,profile=profile,**stats(selected)))
result=dict(unique_calls=stats(rows),analytical_slot_count=16,shared_slots_not_independent=True,cells=cells,rows=rows,model_calls_in_analysis=0,candidate_reexecutions=0,nbn_placement_status='Not calculated in this report; no invented fitness for failures',official_verifier_equivalence=False)
with (root/'RESULTS.json').open('x',encoding='utf-8') as stream:json.dump(result,stream,indent=2)
lines=['# Finite NBN selection and prompt comparison — GPU study','',
    'Fourteen registered unique requests finished. Sixteen analytical slots share two responses across parent-selection groups; they are not sixteen independent trials.',
    '', '| Selection | Prompt | Valid / 4 | Target hits | Best valid score | Outcomes |','|---|---|---:|---:|---:|---|']
for cell in cells:
    lines.append(f"| {cell['strategy']} | {cell['profile']} | {cell['statuses'].get('valid',0)} | {cell['target_hits']} | {cell['best_valid_score']} | {cell['statuses']} |")
lines.extend(['',f"Unique-call outcomes: {result['unique_calls']['statuses']}. Valid scores: {result['unique_calls']['valid_scores']}. Target hits: {result['unique_calls']['target_hits']}.",
    '', 'The study used fixed Qwen2.5-Coder 7B Q4_K_M weights and a pinned llama.cpp GPU runtime on hits_9. Evaluation remained on hits_1 with the registered worker/dependencies and twenty-second limit. No repair, replacement call or manual candidate patch was permitted. See registration.json, the manifest and exact saved prompts for provenance.',
    '', 'This is a preliminary descriptive comparison, one sample per parent/profile. Parent groups overlap and differ in code as well as archived quality. Prompt profiles are complete instruction packages. A higher valid count alone cannot establish a robust ranking, broad generalization or causal benefit from an NBN label.',
    '', 'Unique source/AST hashes are inspection aids, not proof of meaningful mechanism diversity. Inspect successful program mechanisms and scored-program embedding/NBN placement before drawing a diversity conclusion. No new NBN placement is claimed by this report. Missing or invalid fitness remains unranked. The frozen historical graph is HNSW-based, not an exact or physical basin guarantee.',
    '', 'The 2.6360 target is checked against the named research evaluator. Its timeout/tolerance settings and full official-verifier equivalence remain separately qualified. Report the outcome even if no target hit occurs; do not extend the batch until success. Connect supported prompt/parent choices to algorithm design only where the evidence permits.'])
with (root/'RESULTS_REPORT.md').open('x',encoding='utf-8') as stream:stream.write('\n'.join(lines)+'\n')
print(json.dumps(result['unique_calls']))
