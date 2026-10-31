"""Verify saved eligibility outputs and write the measured-results review."""
import hashlib,html,json,math
from collections import Counter
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1];OUT=ROOT/'output/ael_parent_eligibility_20261031'
BASE=ROOT/'LLM4AD-NBN-visualization-github/research/circle_packing_prompt_study_20261026'
payload=json.loads((OUT/'results.json').read_text(encoding='utf-8'));manifest=json.loads((OUT/'manifest.json').read_text(encoding='utf-8'))
registration=json.loads((OUT/'registration.json').read_text(encoding='utf-8'))['frozen'];rows=payload['results']
assert payload['status']=='completed' and len(rows)==30 and payload['model_calls']==0
assert hashlib.sha256((OUT/'manifest.json').read_bytes()).hexdigest()==registration['manifest_sha256']
assert [r['candidate']['candidate_id'] for r in rows]==manifest['execution_order']
ledger=[json.loads(line) for line in (OUT/'ledger.jsonl').read_text(encoding='utf-8').splitlines() if line.strip()]
assert ledger==rows
valid=[];elig=[]
for row in rows:
    c=row['candidate'];evaluation=row['evaluation'];path=BASE/c['original_candidate_path']
    assert hashlib.sha256(path.read_text(encoding='utf-8').strip().encode()).hexdigest()==c['canonical_code_sha256']
    stored=json.loads((OUT/c['candidate_id']/'outcome.json').read_text());assert stored==row
    if evaluation['status']=='valid':
        circles=evaluation['circles'];assert evaluation['shape']==[26,3] and len(circles)==26
        assert all(len(q)==3 and all(isinstance(v,(int,float)) and math.isfinite(v) for v in q) for q in circles)
        eps=1e-12
        assert all(r>=-eps and x-r>=-eps and y-r>=-eps and x+r<=1+eps and y+r<=1+eps for x,y,r in circles)
        assert all(math.hypot(a[0]-b[0],a[1]-b[1])>=a[2]+b[2]-eps for i,a in enumerate(circles) for b in circles[i+1:])
        assert math.isclose(sum(q[2] for q in circles),evaluation['score'],rel_tol=1e-12,abs_tol=1e-12)
        valid.append(row)
    else:assert evaluation.get('score') is None
    expected=evaluation['status']=='valid' and evaluation['score']>0
    assert expected==row['eligible_positive_parent']
    if expected:elig.append(row)
counts=dict(Counter(r['evaluation']['status'] for r in rows));assert counts==payload['outcomes']
assert len(elig)==payload['eligible_parent_count']
assert sum(r['evaluation']['score']>=2.6360 for r in elig)==payload['target_hits']
eligible_regions=sorted({r['candidate']['region_index'] for r in elig});all_regions=sorted({r['candidate']['region_index'] for r in rows})
best=max(elig,key=lambda r:r['evaluation']['score']) if elig else None
history=json.loads((OUT/'platform_history.json').read_text());event_counts=dict(Counter(e['eventType'] for e in history['events']))
assert event_counts.get('historical_reference_evaluated')==30 and event_counts.get('llm_request',0)==0
assert len(history['view']['references'])==30
for event in history['events']:
    if event['eventType']=='historical_reference_evaluated':
        matching=next(r for r in rows if r['evaluation_id']==event['payload']['evaluationId'])
        assert matching['evaluation']==event['payload']['evaluation']
summary=dict(status='completed_and_saved_output_verified',programs_evaluated=30,outcomes=counts,eligible_positive_parents=len(elig),checked_regions=all_regions,eligible_regions=eligible_regions,best_sample=best['candidate']['sample_order'] if best else None,best_score=best['evaluation']['score'] if best else None,target_hits=payload['target_hits'],llm_calls=0,geometry_and_score_rechecked_from_saved_arrays=len(valid),candidate_programs_reexecuted_during_report=0,history_revision=payload['platform_revision_id'],history_event_counts=event_counts,thread_limits=registration['numerical_thread_limits'])
(OUT/'VERIFIED_SUMMARY.json').write_text(json.dumps(summary,indent=2),encoding='utf-8')
options=[dict(**r['candidate'],measured_score=r['evaluation']['score'],runtime_seconds=r['evaluation']['wall_runtime_seconds'],evaluation_id=r['evaluation_id'],eligibility_scope='One observed valid positive-fitness execution under the registered environment') for r in sorted(elig,key=lambda r:(-r['evaluation']['score'],r['candidate']['shortlist_rank']))]
(OUT/'eligible_parent_options.json').write_text(json.dumps(dict(selection_status='Options only; no AEL population or mating schedule has been selected',source_revision=payload['platform_revision_id'],candidates=options),indent=2),encoding='utf-8')
lines=['# AEL historical-parent eligibility results - 2026-10-31','', '**Completed historical-program diagnostic. No LLM-generated offspring in this batch.**','', f"Checked all 30 prelisted programs once. Outcomes: `{json.dumps(counts,sort_keys=True)}`. Positive-fitness eligible options: **{len(elig)}**. Eligible options span **{len(eligible_regions)}** recorded HNSW branches.",'']
if best:lines +=[f"Best observed parent: sample **{best['candidate']['sample_order']}**, score **{best['evaluation']['score']:.12f}**. Research-target hits (>=2.6360): **{payload['target_hits']}**. This is a re-evaluated historical program, not a newly discovered or evolved algorithm.",'']
lines+=['## Every measured outcome','', '| Shortlist rank | Historical sample | HNSW branch index | Outcome | Measured score | Wall seconds | Eligible positive parent |','|---:|---:|---:|---|---:|---:|---|']
for row in rows:
    c=row['candidate'];e=row['evaluation'];score=f"{e['score']:.12f}" if e.get('score') is not None else 'unmeasured'
    lines.append(f"| {c['shortlist_rank']} | {c['sample_order']} | {c['region_index']} | {e['status']} | {score} | {e['wall_runtime_seconds']:.3f} | {'yes' if row['eligible_positive_parent'] else 'no'} |")
lines+=['','## Conditions and preservation','', '- Existing N=26 evaluator/static screen and geometry tolerance 1e-12; twenty-second isolated-worker limit including startup. No source changes, repairs, retries or replacements.', '- Workers ran sequentially with OPENBLAS/OMP/MKL/NUMEXPR thread limits fixed at one. This condition is recorded explicitly; timing differences from old shared-load runs are not causal estimates.', '- Parent eligibility requires a valid finite score greater than zero. A zero score remains a geometrically valid recorded result but would not be a positive-fitness option.', '- All source programs, outcomes, available coordinates, stdout/stderr, start records, ledger and platform events are preserved. Archived scores are unchanged.', '- The diagnostic keeps the original frozen 30-program order and stops after those thirty attempts, regardless of target attainment.', '- Local search for prior matching completed outcomes inspected 261 result/ledger files and found none for these thirty source identities. This is the stated audit scope, not a claim about inaccessible archives.','', '## Source graph identity','', f"The archive-export SHA-256 is `{manifest['source_graph_sha256']}`. The live graph artifact stores the inner graph and has a different byte digest, recorded in `registration.json`. The input digest and all 14,000 program/source/NBN-parent identities were reconciled before registration (`source_graph_reconciliation.json`).",'', f"The selected shortlist maps to {len(all_regions)} HNSW branches: {all_regions}. These are operational code-space groups. Earlier exact-graph labels are retained separately rather than reused as current labels. This check does not establish coverage of all four supported historical HNSW branches or compute any new embedding/NBN placement.",'', '## What is now enabled','', f"There are {len(elig)} measured positive-fitness historical options available for an AEL parent-selection decision. `eligible_parent_options.json` lists them in score order for review; it does not register an initial population, crossover pair allocation, mutation schedule or generation budget.",'', 'The next research step is to freeze the first AEL operator test or full evolutionary configuration, including how NBN-guided parent choice is compared with its declared baseline. Keep model, evaluator, prompt format, call budget and failure accounting explicit. This diagnostic does not establish that a parent-selection policy or prompt is superior.','', f"History revision: `{payload['platform_revision_id']}`. Full model-generation attempts: zero. Valid coordinates and sums were independently checked from the saved arrays; no candidate was executed again while reporting. Official challenge-verifier equivalence remains unresolved."]
position=lines.index('## What is now enabled')
lines[position:position]=['The 22 eligible options are conditional on the earlier static shortlist. This was not an exhaustive runtime scan of all 14,000 historical records and does not establish the best possible executable parent pool. Static loop/import filters can exclude programs that might still finish under the time cap. No conclusion about the quality of an unrepresented branch follows from this shortlist.','']
(OUT/'AEL_PARENT_ELIGIBILITY_RESULTS.md').write_text('\n'.join(lines)+'\n',encoding='utf-8')
esc=html.escape
trs=[]
for row in rows:
    c=row['candidate'];e=row['evaluation'];s='—' if e.get('score') is None else f"{e['score']:.6f}";source='https://github.com/IssaIssa-tech/LLM4AD-NBN-visulization/blob/main/research/circle_packing_prompt_study_20261026/'+c['original_candidate_path']
    trs.append(f'<tr data-status="{esc(e["status"])}"><td>{c["sample_order"]}</td><td>{c["region_index"]}</td><td><span class="badge {"valid" if row["eligible_positive_parent"] else "failed"}">{esc(e["status"].replace("_"," "))}</span></td><td class="number">{s}</td><td class="number">{e["wall_runtime_seconds"]:.2f}</td><td>{"Yes" if row["eligible_positive_parent"] else "No"}</td><td><a href="{esc(source)}">Source</a> · <a href="{esc(c["candidate_id"])}/outcome.json">Record</a></td></tr>')
best_text='—' if best is None else f"{best['evaluation']['score']:.6f}"
page='''<!doctype html><html lang="en"><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1"><title>AEL parent eligibility</title><style>
body{margin:0;background:#f4f7fc;color:#18253a;font:15px/1.6 Segoe UI,Arial,sans-serif}main{max-width:1200px;margin:35px auto;padding:0 25px}.eyebrow{font-weight:700;letter-spacing:2px;color:#2462e5;font-size:12px}h1{font-size:31px;margin:8px 0}.sub{color:#65768f}.notice{background:#e8f0ff;border:1px solid #c4d6fa;border-radius:10px;padding:14px 18px}.metrics{display:grid;grid-template-columns:repeat(4,1fr);gap:14px;margin:25px 0}.metric{padding:18px;border:1px solid #dee6f2;border-radius:11px;background:white}.metric span{display:block;color:#64758e;font-size:13px}.metric strong{font-size:28px}.controls{display:flex;gap:12px;margin:20px 0}input,select{padding:11px;border:1px solid #cdd8e8;border-radius:7px;font:inherit}input{flex:1}.table{overflow:auto;background:white;border:1px solid #dbe4ef;border-radius:11px}table{width:100%;border-collapse:collapse;white-space:nowrap}th,td{padding:13px 16px;text-align:left;border-bottom:1px solid #edf1f7}th{font-size:12px;text-transform:uppercase;letter-spacing:.5px;color:#6b7d96;background:#f9fbfe}.number{text-align:right;font-variant-numeric:tabular-nums}.badge{font-size:12px;border-radius:15px;padding:4px 10px}.valid{color:#18734d;background:#e0f5e9}.failed{color:#a34c37;background:#fff0ea}a{color:#235ed1}footer{color:#687a94;font-size:13px;margin:24px 0 35px}#count{font-size:13px;color:#64758e}@media(max-width:700px){main{padding:0 14px;margin-top:20px}.metrics{grid-template-columns:1fr 1fr}.controls{flex-wrap:wrap}input{flex-basis:100%}h1{font-size:25px}}
</style><main><div class="eyebrow">LLM4AD · CIRCLE PACKING N=26</div><h1>AEL parent eligibility</h1><p class="sub">Thirty historical programs checked under the registered 20-second evaluator.</p><div class="notice">Historical-parent diagnostic completed. No new LLM programs were generated in this batch.</div><div class="metrics">'''
for name,value in [('Programs checked',30),('Eligible positive parents',len(elig)),('Eligible NBN branches',len(eligible_regions)),('Best measured score',best_text)]:page+=f'<div class="metric"><span>{name}</span><strong>{value}</strong></div>'
page+='</div><div class="controls"><input id="search" placeholder="Search sample, branch or outcome" aria-label="Search"><select id="status" aria-label="Outcome"><option value="all">All outcomes</option>'+''.join(f'<option value="{esc(s)}">{esc(s.replace("_"," "))}</option>' for s in counts)+'</select></div><p id="count">30 / 30 records</p><div class="table"><table><thead><tr><th>Sample</th><th>NBN branch</th><th>Outcome</th><th>Measured score</th><th>Seconds</th><th>Eligible</th><th>Evidence</th></tr></thead><tbody>'+''.join(trs)+'</tbody></table></div>'
page+=f'<footer>Research target: ≥2.6360 · Target hits: {payload["target_hits"]} · LLM calls: 0<br>Scores are existing-research-evaluator measurements, not official-verifier certification. One observed execution per program; prior archived scores remain unchanged.<br>NBN branches refer to the frozen HNSW graph. All failures are retained. <a href="AEL_PARENT_ELIGIBILITY_RESULTS.md">Full report</a> · <a href="results.json">Complete results</a> · <a href="platform_history.json">Recorded history</a></footer>'
page+='''</main><script>const rows=[...document.querySelectorAll('tbody tr')],search=document.querySelector('#search'),status=document.querySelector('#status');function filter(){let n=0;for(const row of rows){row.hidden=!((status.value==='all'||row.dataset.status===status.value)&&row.textContent.toLowerCase().includes(search.value.toLowerCase()));if(!row.hidden)n++;}document.querySelector('#count').textContent=n+' / '+rows.length+' records';}search.oninput=filter;status.onchange=filter;window.__eligibilityReady=true;</script></html>'''
(OUT/'ael_parent_eligibility_review.html').write_text(page,encoding='utf-8')
print(json.dumps(summary,indent=2))
