"""Audit saved AEL outputs, without rerunning programs or generating replacements."""
import ast,copy,html,json,math
from collections import Counter
from pathlib import Path
from ael_pilot_common import NAME,sha,load,save,write

base=Path(__file__).resolve().parents[1];out=base/'output'/NAME
study=base/'LLM4AD-NBN-visualization-github/research/circle_packing_prompt_study_20261026'
m=load(out/'manifest.json');result=load(out/'results.json');rows=result['results'];reg=load(out/'registration.json')['frozen'];history=load(out/'platform_history.json')
assert result['status']=='completed' and result['completed_chains']==6
assert sha((out/'manifest.json').read_bytes())==reg['manifest_sha256']==result['manifest_sha256']
assert len(rows)==result['actual_llm_requests']<=12
ledger=[json.loads(line) for line in (out/'ledger.jsonl').read_text(encoding='utf-8').splitlines() if line.strip()];assert ledger==rows
attempts={a['id']:a for a in history['view']['attempts']};assert set(attempts)=={r['call_id'] for r in rows}
assert len([e for e in history['events'] if e['eventType']=='llm_request'])==len(rows)
assert len([e for e in history['events'] if e['eventType']=='llm_response'])==len(rows),'Inspect generation failures before final audit'
for name,h in reg['script_hashes'].items():assert sha((out/name).read_bytes())==h
for name,h in reg['client_script_hashes'].items():assert sha((out/name).read_bytes())==h
byid={r['call_id']:r for r in rows};observations=[];packing_groups={}
source_groups={};ast_groups={};body_groups={}
class BodyOnly(ast.NodeTransformer):
    def visit_Import(self,node):return None
    def visit_ImportFrom(self,node):return None
    def visit_Expr(self,node):
        return None if isinstance(node.value,ast.Constant) and isinstance(node.value.value,str) else self.generic_visit(node)
def hashes(code):
    tree=ast.parse(code)
    fn=next(n for n in tree.body if isinstance(n,ast.FunctionDef) and n.name=='pack_circles')
    body=BodyOnly().visit(copy.deepcopy(fn))
    return dict(source=sha(code.strip().encode()),ast=sha(ast.dump(tree,include_attributes=False).encode()),function_body_without_imports_or_docstrings=sha(ast.dump(body,include_attributes=False).encode()))
parent_hashes={}
for p in m['eligible_population']:
    code=(study/p['original_candidate_path']).read_text(encoding='utf-8')
    assert sha(code.strip().encode())==p['canonical_code_sha256']
    parent_hashes[p['sample_order']]=hashes(code)
valid=[]
for r in rows:
    folder=out/r['call_id'];assert load(folder/'outcome.json')==r
    api=load(folder/'api_payload.json');raw=load(folder/'raw_response.json');gen=load(folder/'generation_result.json')
    assert api==load(folder/'started.json')['request']
    assert gen['context_preflight']['fits'] and raw.get('usage',{}).get('prompt_tokens',0)+1800<=8192
    assert attempts[r['call_id']]['status']==r['status'] and attempts[r['call_id']]['score']==r.get('score')
    assert attempts[r['call_id']]['parents']==load(folder/'started.json')['parents']
    if r['operator']=='cross':assert len(attempts[r['call_id']]['parents'])==2
    else:
        parents=attempts[r['call_id']]['parents'];assert len(parents)==1
        cross=r['call_id'].removesuffix('-mut')+'-cross'
        assert parents[0]['originCallId']==cross and 'nbnNodeId' not in parents[0]
        assert parents[0]['recordedSource']==(out/cross/'candidate.py').read_text(encoding='utf-8')
    observation=dict(call_id=r['call_id'],policy=r['policy'],operator=r['operator'],status=r['status'],score=r.get('score'),finish_reason=r.get('finish_reason'),generation_seconds=r.get('generation_wall_seconds'),evaluation_seconds=r.get('wall_runtime_seconds'),error=r.get('error'))
    if (folder/'candidate.py').exists():
        code=(folder/'candidate.py').read_text(encoding='utf-8');assert sha(code.encode())==r['code_sha256']
        try:h=hashes(code)
        except SyntaxError:h=dict(source=sha(code.strip().encode()))
        observation['fingerprints']=h
        observation['parent_matches']={kind:[s for s,hs in parent_hashes.items() if hs.get(kind)==value] for kind,value in h.items()}
        for kind,groups in [('source',source_groups),('ast',ast_groups),('function_body_without_imports_or_docstrings',body_groups)]:
            if kind in h:groups.setdefault(h[kind],[]).append(r['call_id'])
    if r['status']=='valid':
        circles=r['circles'];assert r['shape']==[26,3] and len(circles)==26
        assert all(len(c)==3 and all(isinstance(v,(float,int)) and math.isfinite(v) for v in c) for c in circles)
        eps=1e-12
        boundary_margin=min(min(x-radius,y-radius,1-x-radius,1-y-radius,radius) for x,y,radius in circles)
        pair_margin=min(math.hypot(a[0]-b[0],a[1]-b[1])-a[2]-b[2] for i,a in enumerate(circles) for b in circles[i+1:])
        assert boundary_margin>=-eps and pair_margin>=-eps
        assert math.isclose(sum(c[2] for c in circles),r['score'],abs_tol=1e-12,rel_tol=1e-12)
        packsha=sha(json.dumps(sorted(circles),separators=(',',':')).encode());packing_groups.setdefault(packsha,[]).append(r['call_id'])
        observation.update(packing_sha256=packsha,verified_sum_of_radii=sum(c[2] for c in circles),minimum_boundary_or_radius_margin=boundary_margin,minimum_pair_margin=pair_margin)
        valid.append(r)
    else:assert r.get('score') is None
    chain=next(c for c in m['chains'] if c['chain_id']==r['chain_id']);bestparent=max(p['measuredScore'] for p in chain['parents'])
    observation['best_parent_observed_score']=bestparent
    observation['difference_from_best_parent']=r['score']-bestparent if r['status']=='valid' else None
    cross=byid.get(chain['crossover_id'])
    if r['operator']=='mut':observation['difference_from_crossover']=r['score']-cross['score'] if r['status']=='valid' and cross['status']=='valid' else None
    observations.append(observation)
cells=[]
for policy in ['uniform','nbn_stratified']:
    for op in ['cross','mut']:
        group=[r for r in rows if r['policy']==policy and r['operator']==op];good=[r['score'] for r in group if r['status']=='valid']
        cells.append(dict(policy=policy,operator=op,attempts=len(group),valid=len(good),outcomes=dict(Counter(r['status'] for r in group)),best_score=max(good,default=None),mean_valid_score=sum(good)/len(good) if good else None,target_hits=sum(s>=2.636 for s in good)))
summary=dict(status='completed_verified_from_saved_records',actual_model_calls=len(rows),chains=6,outcomes=dict(Counter(r['status'] for r in rows)),valid_outputs=len(valid),best_score=max((r['score'] for r in valid),default=None),target_score=2.636,target_hits=sum(r['score']>=2.636 for r in valid),cells=cells,observations=observations,source_groups=source_groups,ast_groups=ast_groups,body_groups=body_groups,packing_groups=packing_groups,history_event_count=len(history['events']),geometry_verification='Independent checks of saved arrays; no program re-execution',nbn_placement='Parent selection uses frozen HNSW graph; generated-program NBN placement not computed',scope='Finite operator pilot; not the full AEL algorithm or a statistically conclusive policy comparison')
save(out/'VERIFIED_SUMMARY.json',summary)
def number(x):return '—' if x is None else f'{x:.6f}'
table='| Selection | Operator | Calls | Valid | Best valid score | Target hits |\n|---|---|---:|---:|---:|---:|\n'
for c in cells:table+=f"| {c['policy']} | {c['operator']} | {c['attempts']} | {c['valid']} | {number(c['best_score'])} | {c['target_hits']} |\n"
details='| Call | Outcome | Score | Δ best observed parent |\n|---|---|---:|---:|\n'
for o in observations:details+=f"| {o['call_id']} | {o['status']} | {number(o['score'])} | {number(o['difference_from_best_parent'])} |\n"
write(out/'RESULTS.md',f'''# AEL operator pilot: measured outcomes

Completed {len(rows)} model calls across six pre-registered chains. {len(valid)} valid outputs; best valid score {number(summary['best_score'])}; {summary['target_hits']} outputs reached 2.6360. No retries, manual candidate patches, or repeated evaluations were used.

{table}
{details}
Scores and geometry were independently checked from saved returned arrays. Failed attempts retain undefined fitness. Historical parent scores are single observations under the same evaluation environment; archive scores are not substituted as current fitness.

There are {len(source_groups)} distinct stripped sources, {len(ast_groups)} distinct ASTs, and {len(packing_groups)} exact coordinate-set fingerprints among valid outputs. These counts measure syntax and saved packings, not independent algorithm mechanisms or physical basins. `VERIFIED_SUMMARY.json` also reports comparisons to parent function ASTs with import/docstring nodes omitted; this normalization is only a syntactic diagnostic, not a proof of semantic equivalence.

The two selection policies use different historical programs and parent quality. Three seeds per policy support descriptive results only. This pilot uses one common AEL crossover/mutation prompt pair, not a matched comparison with EoH or other papers. No new NBN embedding or placement is claimed. The bounded operator test is complete; the supervisor's broader research question and a full AEL population study are not declared complete.

All parent IDs/NBN nodes, full prompts/responses, generated code, both parent links for crossover, generated-parent lineage for mutation, coordinates, errors, runtime identities and configuration are saved in this folder and the platform export. The fixed protocol and source scripts remain unchanged.
''')
escaped=json.dumps(dict(summary=summary,manifest=m,rows=rows),ensure_ascii=False).replace('<','\\u003c')
page='''<!doctype html><html lang="en"><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1"><title>AEL operator pilot — saved results</title><style>
*{box-sizing:border-box}body{font:16px/1.55 system-ui,sans-serif;background:#f3f6fb;color:#16263e;margin:0;padding:28px}main{max-width:1300px;margin:auto}h1{font-size:30px;line-height:1.2;margin:0 0 10px}h2{font-size:21px}.muted{color:#536881}.cards{display:grid;grid-template-columns:repeat(4,1fr);gap:12px;margin:24px 0}.card,section{background:white;border:1px solid #dce3ec;border-radius:12px;padding:18px}.card strong{display:block;font-size:29px}.tag{display:inline-block;padding:2px 8px;background:#e5ecf6;border-radius:5px}.valid{background:#d9f4e6;color:#145b37}.exception,.invalid_geometry{background:#ffe2e6;color:#8b1c35}section{margin:18px 0}table{border-collapse:collapse;width:100%;font-size:14px}th,td{text-align:left;padding:10px;border-bottom:1px solid #dce3ec}th{background:#f4f7fb}.scroll{overflow:auto}button,select{font:inherit;border:1px solid #a7b7cb;background:white;border-radius:6px;padding:7px 10px}button{cursor:pointer}pre{background:#112038;color:#edf3fc;padding:15px;max-height:480px;overflow:auto;white-space:pre-wrap;overflow-wrap:anywhere;font-size:13px}details{margin:12px 0}#detail{scroll-margin-top:15px}.warn{border-left:5px solid #c17b1b;padding-left:14px}@media(max-width:700px){body{padding:14px}.cards{grid-template-columns:repeat(2,1fr)}h1{font-size:25px}}
</style><main><h1>AEL crossover and mutation: Circle Packing N=26</h1><p class="muted">Finite operator pilot · six fixed chains · local Qwen2.5-Coder 7B · saved execution records</p><div class="cards" id="cards"></div><section><h2>Selection policy × operator</h2><div class="scroll"><table><thead><tr><th>Selection</th><th>Operator</th><th>Calls</th><th>Valid</th><th>Best valid score</th><th>Target hits</th></tr></thead><tbody id="cells"></tbody></table></div></section><section><h2>All attempts</h2><p><label>Selection <select id="policy"><option value="all">All</option><option>uniform</option><option>nbn_stratified</option></select></label> <label>Outcome <select id="status"><option value="all">All</option></select></label></p><div class="scroll"><table><thead><tr><th>Call</th><th>Outcome</th><th>Score</th><th>Δ best parent</th><th>Parent / offspring record</th></tr></thead><tbody id="attempts"></tbody></table></div></section><section id="detail"><h2>Trace an attempt</h2><p class="muted">Choose a call to inspect both historical parents or the actual generated crossover parent, followed by the prompt, response, source, and evaluation.</p><div id="selected"></div></section><section><h2>What these results establish</h2><p class="warn">This is a completed operator pilot. It is not the full AEL population experiment, proof that either selection policy is better, or a guarantee of reaching 2.6360.</p><p>Three pairs per policy and differing parent quality limit comparison. Source and AST uniqueness are syntax diagnostics. Generated programs have no newly computed NBN placement. Saved coordinates were independently checked without executing programs again.</p><p id="diversity"></p><p><a href="RESULTS.md">Measured-results report</a> · <a href="VERIFIED_SUMMARY.json">Verification details</a> · <a href="manifest.json">Frozen protocol and parent choices</a> · <a href="platform_history.json">Complete platform history</a></p></section></main><script>
const data=__DATA__,s=data.summary;const el=id=>document.getElementById(id),num=v=>v==null?'—':v.toFixed(6);const text=(tag,value)=>{const n=document.createElement(tag);n.textContent=value;return n};
for(const [label,value] of [['Model calls',s.actual_model_calls],['Valid outputs',s.valid_outputs],['Best score',num(s.best_score)],['Hits ≥ 2.6360',s.target_hits]]){let d=document.createElement('div');d.className='card';d.append(text('span',label),text('strong',value));el('cards').append(d)}
for(const c of s.cells){let tr=document.createElement('tr');for(const v of [c.policy,c.operator,c.attempts,c.valid,num(c.best_score),c.target_hits])tr.append(text('td',v));el('cells').append(tr)}
for(const status of Object.keys(s.outcomes)){let opt=text('option',status);opt.value=status;el('status').append(opt)}
function show(id){let row=data.rows.find(r=>r.call_id===id),obs=s.observations.find(r=>r.call_id===id),chain=data.manifest.chains.find(c=>c.chain_id===row.chain_id),box=el('selected');box.replaceChildren(text('h3',id));let parents=row.operator==='cross'?chain.parents:[{originCallId:chain.crossover_id,codeSha256:data.rows.find(r=>r.call_id===chain.crossover_id).code_sha256,nbnPlacementStatus:'not_computed'}];for(const [label,value] of [['Parent and lineage',parents],['Observed result',obs],['Evaluation with returned coordinates',row]]){let d=document.createElement('details');d.open=true;d.append(text('summary',label),text('pre',JSON.stringify(value,null,2)));box.append(d)}let links=text('p','');for(const [label,file] of [['Prompt','prompt.txt'],['API request','api_payload.json'],['Raw model response','raw_response.json'],['Source','candidate.py']]){let a=text('a',label);a.href=id+'/'+file;a.target='_blank';links.append(a,document.createTextNode(' · '))}box.append(links);el('detail').scrollIntoView({behavior:'smooth'})}
function render(){el('attempts').replaceChildren();for(const o of s.observations){if(el('policy').value!=='all'&&o.policy!==el('policy').value)continue;if(el('status').value!=='all'&&o.status!==el('status').value)continue;let tr=document.createElement('tr'),button=text('button',o.call_id);button.onclick=()=>show(o.call_id);let td=document.createElement('td');td.append(button);tr.append(td);let status=text('span',o.status);status.className='tag '+o.status;td=document.createElement('td');td.append(status);tr.append(td,text('td',num(o.score)),text('td',num(o.difference_from_best_parent)));const c=data.manifest.chains.find(c=>c.chain_id===o.call_id.replace(/-(cross|mut)$/,''));tr.append(text('td',o.operator==='cross'?c.parents.map(p=>'s'+p.sampleOrder+' / NBN '+p.nbnNodeId).join(' + '):'Crossover offspring: '+c.crossover_id));el('attempts').append(tr)}}
el('policy').onchange=render;el('status').onchange=render;render();el('diversity').textContent=Object.keys(s.source_groups).length+' stripped sources; '+Object.keys(s.ast_groups).length+' ASTs; '+Object.keys(s.packing_groups).length+' exact valid coordinate-set fingerprints. Full matching evidence is in the verification JSON.';
</script></html>'''.replace('__DATA__',escaped)
write(out/'ael_operator_pilot_review.html',page)
print(json.dumps({k:summary[k] for k in ['actual_model_calls','valid_outputs','best_score','target_hits','outcomes','cells']},indent=2))
