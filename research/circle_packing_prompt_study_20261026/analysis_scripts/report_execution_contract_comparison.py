"""Compare preserved paired generations; no program execution or model calls."""
import ast,hashlib,json,sys
from collections import Counter
from pathlib import Path
import numpy as np
from evaluate_circle_prompt_candidates import valid_circles
base=Path(__file__).resolve().parents[1]/'output'
p=base/'regional_prompt_execution_contract_20261028';old=base/'regional_prompt_comparison_draft_20261028'
m=json.loads((p/'draft_comparison_manifest.json').read_text()); rows=[]
for r in m['unique_requests']:
    folder=p/r['request_id'];o=json.loads((folder/'outcome.json').read_text())
    before=json.loads((old/r['previous_condition_request_id']/'outcome.json').read_text())
    raw=json.loads((folder/'raw_response.json').read_text());code=(folder/'candidate.py').read_text()
    tree=ast.parse(code)
    ranges=[ast.unparse(n) for n in ast.walk(tree) if isinstance(n,ast.Call) and isinstance(n.func,ast.Name) and n.func.id=='range']
    if o['status']=='valid':
        a=np.asarray(o['circles']);assert valid_circles(a);assert abs(float(a[:,2].sum())-o['score'])<1e-12
        assert np.all(a[:,2]==0)
    rows.append(dict(request_id=r['request_id'],previous_request_id=r['previous_condition_request_id'],
        parent=r['parent']['node_id'],profile=r['prompt_profile'],before=before['status'],after=o['status'],
        before_score=before.get('score'),after_score=o.get('score'),error=o.get('error'),ranges=ranges,
        done_reason=raw.get('done_reason'),code_sha256=hashlib.sha256(code.encode()).hexdigest()))
events=[json.loads(f.read_text()) for f in (p/'research_history').glob('*.json')]
counts=Counter(e['eventType'] for e in events)
assert counts['llm_request']==counts['llm_response']==counts['trial_completed']==14
assert counts['comparison_completed']==1
groups=[];by_id={r['request_id']:r for r in rows}
for strategy in m['factors']['parent_selection']:
    for profile in m['factors']['prompt_profile']:
        selected=[by_id[s['request_id']] for s in m['analytical_slots'] if s['strategy']==strategy and s['prompt_profile']==profile]
        groups.append(dict(strategy=strategy,profile=profile,statuses=dict(Counter(r['after'] for r in selected))))
result=dict(before=dict(Counter(r['before'] for r in rows)),after=dict(Counter(r['after'] for r in rows)),
    paired_transitions=dict(Counter(r['before']+' -> '+r['after'] for r in rows)),groups=groups,rows=rows,
    history_events=dict(counts),unique_code_hashes=len({r['code_sha256'] for r in rows}),target_hits=0,
    candidates_reexecuted=0,model_calls_in_analysis=0,shared_slots_not_independent=True)
with (p/'PAIRED_ANALYSIS.json').open('x') as stream:json.dump(result,stream,indent=2)
lines=['# Execution-contract prompt comparison','',
    'All fourteen new requests completed. Every request, response and terminal outcome is present in the downloaded platform history. Original outcomes remain unchanged. Analysis did not execute candidate code.',
    '', '| Outcome | Previous prompt | Added checklist |','|---|---:|---:|']
for status in ['valid','timeout','exception','invalid_geometry','rejected_static']:
    lines.append(f"| {status} | {result['before'].get(status,0)} | {result['after'].get(status,0)} |")
lines.extend(['','Previous valid score: 0.3267410733963663. New valid score: 0.0. Neither condition reached 2.6360. The zero-score packing passes the current geometry check because all radii are zero; it is a degenerate feasible output, not useful optimization progress.',
    '', '| Selection | Original prompt profile | Valid | Timeout | Exception | Invalid |','|---|---|---:|---:|---:|---:|'])
for g in groups:
    c=g['statuses'];lines.append(f"| {g['strategy']} | {g['profile']} | {c.get('valid',0)} | {c.get('timeout',0)} | {c.get('exception',0)} | {c.get('invalid_geometry',0)} |")
lines.extend(['','Each cell contains four analytical slots; two requests are shared across selection strategies. Fourteen unique requests underlie sixteen slots. These are descriptive outcomes, not independent replicated evidence of a strategy ranking.',
    '', '## Source inspection','',
    '- Seven previous missing-qmc exceptions and the previous top-level-example rejection do not recur. This does not isolate which checklist sentence caused the change.',
    '- Ten timeouts retain nested iterative searches. Their outer literal loop limits span 3,000–40,000. Source structure is consistent with excessive work, but is not a measured runtime beyond the twenty-second cutoff.',
    '- One exception indexes a 26-row array with the search iteration counter, eventually reaching index 26. Another combines incompatible three-coordinate and two-coordinate arrays.',
    '- The sole valid program initializes zero radii and updates local x/y/radius variables without writing the improvements back to its returned circles array. Saved coordinates confirm all radii remain zero.',
    '- All fourteen responses report normal stop rather than token-limit truncation. Fourteen distinct code hashes are not evidence of useful structural diversity.',
    '', '## Research conclusion','',
    'The checklist did not improve useful feasible score in this pilot. Exceptions fell from nine to two while timeouts increased from three to ten. These counts cannot establish that NBN selection is ineffective: execution and optimization correctness dominate, there is one sample per parent/profile, and the archival parents are long-running textual references rather than comparable current-budget incumbents.',
    '', 'Do not change the registered budget or silently repair these candidates. Before another broad generation batch, audit the historical reference context and small-model ability to produce an executable, bounded program. A proposed next diagnostic should separately test a complete executable reference and a precise work-budget contract with a small fixed number of requests, then decide whether a larger paired selection study is warranted. Register that protocol before calls; any change of model or runtime must be explicit.',
    '', 'No new NBN placement, official-verifier equivalence, or final algorithm superiority is claimed. Retain the unsuccessful outputs and current twenty-second research condition in the experiment history.'])
with (p/'PAIRED_REPORT.md').open('x',encoding='utf-8') as stream:stream.write('\n'.join(lines)+'\n')
print(json.dumps({k:v for k,v in result.items() if k!='rows'},indent=2))
