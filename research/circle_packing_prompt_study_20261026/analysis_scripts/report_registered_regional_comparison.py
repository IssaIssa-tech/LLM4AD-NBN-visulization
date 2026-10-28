"""Analyze saved outcomes only; never generate or rerun candidates."""
import ast,hashlib,json
from collections import Counter
from pathlib import Path

ROOT=Path(__file__).resolve().parents[1]
p=ROOT/'output/regional_prompt_comparison_draft_20261028'
m=json.loads((p/'draft_comparison_manifest.json').read_text())
rows={}; fingerprints=[]
for request in m['unique_requests']:
    folder=p/request['request_id'];row=json.loads((folder/'outcome.json').read_text())
    response=json.loads((folder/'raw_response.json').read_text())
    assert row['call_id']==request['request_id']
    code=(folder/'candidate.py').read_text()
    tree=ast.parse(code)
    digest=hashlib.sha256(code.encode()).hexdigest()
    fingerprints.append(hashlib.sha256(ast.dump(tree,include_attributes=False).encode()).hexdigest())
    rows[request['request_id']]=dict(request_id=request['request_id'],parent_node=request['parent']['node_id'],
        profile=request['prompt_profile'],status=row['status'],score=row.get('score'),error=row.get('error'),
        screening=row.get('screening'),done_reason=response.get('done_reason'),code_sha256=digest,
        ast_sha256=fingerprints[-1],packing_recorded='circles' in row)

def summarize(items):
    valid=[r['score'] for r in items if r['status']=='valid']
    return dict(slots=len(items),statuses=dict(Counter(r['status'] for r in items)),valid_scores=valid,
        target_hits=sum(s>=2.6360 for s in valid))

groups=[]
for strategy in m['factors']['parent_selection']:
    for profile in m['factors']['prompt_profile']:
        selected=[rows[s['request_id']] for s in m['analytical_slots'] if s['strategy']==strategy and s['prompt_profile']==profile]
        groups.append(dict(strategy=strategy,profile=profile,**summarize(selected)))
result=dict(unique_requests=summarize(list(rows.values())),groups=groups,rows=list(rows.values()),
    errors=dict(Counter(r['error'] for r in rows.values() if r['error'])),unique_code_hashes=len({r['code_sha256'] for r in rows.values()}),
    unique_ast_hashes=len(set(fingerprints)),analytical_slots=16,shared_slots_not_independent=True,
    no_candidates_rerun=True,official_verifier_equivalence=False)
destination=p/'COMPARISON_ANALYSIS.json'
with destination.open('x') as stream:json.dump(result,stream,indent=2)
lines=['# Preliminary registered comparison results','',
    'Fourteen unique requests completed. Sixteen analytical slots include shared responses; they are not sixteen independent generations.',
    '', 'Unique outcomes: '+str(result['unique_requests']['statuses'])+'. No result reached 2.6360.',
    '', '| Parent strategy | Prompt | Slots | Valid | Timeout | Exception | Static rejection |',
    '|---|---|---:|---:|---:|---:|---:|']
for group in groups:
    c=group['statuses'];lines.append(f"| {group['strategy']} | {group['profile']} | {group['slots']} | {c.get('valid',0)} | {c.get('timeout',0)} | {c.get('exception',0)} | {c.get('rejected_static',0)} |")
lines.extend(['','## Failure inspection','',
    'Seven exceptions report missing `qmc`; the saved programs use it without importing it. Two report too many values to unpack. One static rejection contains top-level example execution, contrary to the prompt contract. Three programs exceeded the fixed twenty-second research execution budget. All model replies report `done_reason=stop`, rather than length truncation.',
    '', 'The single valid packing has sum of radii 0.3267410733963663. It is geometrically feasible under this evaluator but low quality. Fourteen different code hashes and fourteen AST fingerprints describe syntactic differences, not evidence of fourteen useful mechanisms or diverse high-quality solutions.',
    '', '## Interpretation and next condition','',
    'This pilot does not support selecting a superior prompt or parent-selection strategy. One sample per parent/profile, overlapping parents, widespread execution failure, and a budget different from archival evaluation prevent strong ranking or parent-improvement claims. NBN groups are from a frozen HNSW code-space graph, not proven physical basins. The target is not achieved, and official-verifier equivalence remains unverified.',
    '', 'Preserve this condition unchanged. A proposed next condition should test an explicit self-contained-import/interface requirement and bounded-work instruction against the existing prompt while retaining the same parent pools and evaluator. Any repair policy requires separate registration, its own model-call accounting, and preservation of pre-repair failures. Do not silently fix and replace these results.',
    '', 'No embeddings or new NBN placements were calculated in this analysis. Failures have no invented finite scores. Do not add them as fitness-ranked discoveries to the old viewer.',
    '', 'Analysis reads saved artifacts only; no LLM requests or candidate reevaluations were performed.'])
with (p/'COMPARISON_REPORT.md').open('x',encoding='utf-8') as stream:stream.write('\n'.join(lines)+'\n')
print(json.dumps(result,indent=2))
