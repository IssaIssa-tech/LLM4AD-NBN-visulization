"""Consolidate preserved unique calls without generation or candidate execution."""
import json
from collections import Counter
from datetime import datetime,timezone
from pathlib import Path
root=Path(__file__).resolve().parents[1];out=root/'output/research_consolidation_20261028'
if out.exists():raise SystemExit('Existing summary: preserve and inspect')
out.mkdir();studies=[];all_ids=[]
for name in ['regional_prompt_comparison_draft_20261028','regional_prompt_execution_contract_20261028','bounded_adaptation_pilot_20261028','bounded_feedback_repair_20261028']:
    folder=root/'output'/name;m=json.loads((folder/'draft_comparison_manifest.json').read_text(encoding='utf-8'));rows=[]
    for r in m['unique_requests']:
        o=json.loads((folder/r['request_id']/'outcome.json').read_text(encoding='utf-8'))
        rows.append(dict(call_id=r['request_id'],parent_node=r['parent']['node_id'],sample_order=r['parent']['sample_order'],profile=r['prompt_profile'],status=o['status'],score=o.get('score'),error=o.get('error'),repair_lineage=r.get('repair_lineage')))
        all_ids.append(r['request_id'])
    studies.append(dict(folder=name,unique_calls=len(rows),analytical_slots=m['analytical_slot_count'],statuses=dict(Counter(r['status'] for r in rows)),valid_scores=[r['score'] for r in rows if r['status']=='valid'],rows=rows))
assert len(all_ids)==len(set(all_ids))==32
aggregate=Counter(r['status'] for s in studies for r in s['rows'])
payload=dict(created_utc=datetime.now(timezone.utc).isoformat(),scope='Four completed 2026-10-28 generation conditions only; not all historical research',unique_model_calls=32,statuses=dict(aggregate),target_hits=0,studies=studies,
    limitations=['Adaptive sequential exploratory studies; not 32 independent tests of one hypothesis','Analytical slots overlap within the two broad comparisons','Prepared calibration, thirteen historical-reference checks and earlier patch experiments excluded from call totals','One evaluator-valid repair is protocol noncompliant; zero-radius output is degenerate'])
(out/'EVIDENCE_INDEX.json').write_text(json.dumps(payload,indent=2),encoding='utf-8')
lines=['# Current Circle Packing research evidence','',
    'Question: can NBN-guided historical-program selection and prompt design produce structurally diverse high-quality optimizers reaching at least 2.6360? Current answer: not demonstrated.',
    '', '| Completed condition | Unique LLM calls | Valid | Timeout | Exception | Invalid geometry | Static rejection | Valid scores |',
    '|---|---:|---:|---:|---:|---:|---:|---|']
for s in studies:
    c=s['statuses'];lines.append(f"| {s['folder']} | {s['unique_calls']} | {c.get('valid',0)} | {c.get('timeout',0)} | {c.get('exception',0)} | {c.get('invalid_geometry',0)} | {c.get('rejected_static',0)} | {s['valid_scores']} |")
lines.extend(['',f'Aggregate: 32 unique model calls, {dict(aggregate)}. No target hits. These counts describe sequential exploratory conditions and are not a pooled causal estimate.',
    '', '## Interpretation','',
    'The standard broad comparison and added-checklist comparison each use fourteen unique calls across sixteen analytical slots; shared parent/profile requests are not independent trials. The first yielded one low-score feasible output. The checklist reduced exceptions but increased timeouts and yielded only a zero-radius packing. The two-request bounded pilot followed the loop limits but failed geometry or execution. Its one-feedback-repair follow-up yielded a geometrically valid score of 1.50769 only by removing the required search structure; the other repair was statically rejected. No compliant repair succeeded.',
    '', 'All calls are linked to historical parent 12738 or the other frozen reference nodes in EVIDENCE_INDEX.json and per-condition manifests. The two broad comparisons included quality-only and four-region pools. The small follow-ups use only one historical parent and cannot answer regional selection effects.',
    '', 'The source NBN for these selections is frozen and HNSW-based, with operational top-level branches in code embedding space. It is not asserted to be an exact nearest-better graph or a physical basin decomposition. No new embeddings or NBN positions were computed for these recent candidates. Code hashes alone do not establish mechanism diversity, especially among failing programs.',
    '', '## Separate earlier and calibration evidence','',
    'Earlier repeated M2 scored 2.579279552688004. The strict Halton-to-Sobol patch produced one unique program scoring 2.5902372123245248 across five successful deliveries. Those tests already demonstrate constrained code-delivery capability and should not be repeated under a new name. The archived best is 2.6359372088053568; its score is not automatically comparable to a current-budget execution.',
    '', 'Four prepared-code runtime checks used zero LLM calls: 25/50/100-round historical variants finished in approximately 1.88/2.98/5.38 seconds. The unchanged M2 Halton control finished in 5.09 seconds, score 2.57928. The calibration registration mistakenly labels that control Sobol; its correction and source hash are preserved. These are prepared algorithms, not generated discoveries. The thirteen regional historical-reference diagnostics are also excluded from model-call totals.',
    '', '## Next comparison design','',
    'First check availability of a code-specialized open-source model and freeze its exact digest, quantization, context window, chat/template settings and serving configuration. Reuse one full fourteen-request broad condition, unchanged parents/prompts/evaluator/sampling seeds and generation token cap, as the proposed pilot comparison. Changing model changes tokenizer/template as well as weights and size; describe this as a model-package comparison. Do not claim a pure parameter-count effect or pool old dependent slots as independent replicates.',
    '', 'Before running, verify prompt fit without truncation and preserve prompt-token counts and raw responses. Record actual device/offload allocation and timing. Current model comparisons would be sequential under different shared load; runtime comparisons are descriptive. Keep the same twenty-second research evaluator, no repairs, and the existing failure accounting. Choose a single original prompt condition before seeing new outputs rather than combining whichever old prompt worked best per parent.',
    '', 'Proposed primary model-package outcome: evaluator-valid rate and scores, accompanied by code/geometry/contract compliance. Research outcomes remain target attainment, mechanism diversity and branch coverage when meaningful fitness is available. Only a subsequent adequately replicated selection comparison could support claims of NBN guidance. Stronger-model success is not guaranteed.',
    '', 'No model download or new generation was performed during consolidation. Full official-verifier equivalence remains unresolved. Preserve all unsuccessful outputs and every strategy revision.'])
(out/'CONSOLIDATED_FINDINGS.md').write_text('\n'.join(lines)+'\n',encoding='utf-8')
print(json.dumps(dict(unique_calls=32,statuses=dict(aggregate),target_hits=0)))
