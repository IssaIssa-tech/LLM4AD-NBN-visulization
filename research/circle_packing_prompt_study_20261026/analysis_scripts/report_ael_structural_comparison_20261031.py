"""Compare saved matched conditions only; never rerun or repair candidate code."""
import ast,copy,html,json,math
from collections import Counter
from hashlib import sha256
from pathlib import Path

base=Path(__file__).resolve().parents[1];out=base/'output/ael_structural_prompt_comparison_20261031';prior=base/'output/ael_operator_pilot_20261031'
study=base/'LLM4AD-NBN-visualization-github/research/circle_packing_prompt_study_20261026'
load=lambda p:json.loads(p.read_text(encoding='utf-8'))
sha=lambda raw:sha256(raw).hexdigest()
m=load(out/'manifest.json');oldm=load(prior/'manifest.json');baseline=load(prior/'results.json')
assert sha((prior/'manifest.json').read_bytes())==m['baseline_provenance']['manifest_sha256']
assert sha((prior/'results.json').read_bytes())==m['baseline_provenance']['results_sha256']
assert sha((prior/'registration.json').read_bytes())==m['baseline_provenance']['registration_sha256']
for item in load(prior/'ARTIFACT_INTEGRITY.json')['files']:assert sha((prior/item['path']).read_bytes())==item['sha256']
completed=(out/'results.json').exists();new=load(out/'results.json') if completed else dict(results=[],status='prepared_no_results');newrows=new['results']
if completed:
    reg=load(out/'registration.json')['frozen'];assert reg['manifest_sha256']==sha((out/'manifest.json').read_bytes())
    for name,digest in reg['script_hashes'].items():assert sha((out/name).read_bytes())==digest
    assert reg['runtime_identity']['model_blob_sha256']==m['runtime_expectation']['model_blob_sha256']
    assert reg['runtime_identity']['binary_sha256']==m['runtime_expectation']['binary_sha256']
    assert reg['runtime_identity']['chat_template_sha256']==m['runtime_expectation']['chat_template_sha256']
    assert reg['runtime_identity']['gpu']['uuid']==m['runtime_expectation']['required_gpu_uuid']
    assert reg['evaluator_hashes']==m['evaluator_hashes']
    assert reg['numpy']==m['runtime_expectation']['numpy'] and reg['scipy']==m['runtime_expectation']['scipy']
    assert [json.loads(line) for line in (out/'ledger.jsonl').read_text(encoding='utf-8').splitlines()]==newrows

class RemoveNotes(ast.NodeTransformer):
    def visit_Import(self,node):return None
    def visit_ImportFrom(self,node):return None
    def visit_Expr(self,node):return None if isinstance(node.value,ast.Constant) and isinstance(node.value.value,str) else self.generic_visit(node)
def fingerprints(source):
    values=dict(source_sha256=sha(source.strip().encode()))
    try:
        tree=ast.parse(source);values['ast_sha256']=sha(ast.dump(tree,include_attributes=False).encode())
        fn=next((n for n in tree.body if isinstance(n,ast.FunctionDef) and n.name=='pack_circles'),None)
        if fn:values['body_sha256']=sha(ast.dump(RemoveNotes().visit(copy.deepcopy(fn)),include_attributes=False).encode())
    except SyntaxError:pass
    return values
parents={p['sample_order']:fingerprints((study/p['original_candidate_path']).read_text(encoding='utf-8')) for p in m['eligible_population']}
def describe(row,root,chain):
    cid=row['call_id'];folder=root/cid
    observation=dict(call_id=cid,operator=row['operator'],policy=row['policy'],status=row['status'],score=row.get('score'),error=row.get('error'),best_parent_observed_score=max(p['measuredScore'] for p in chain['parents']))
    assert load(folder/'outcome.json')==row
    if (folder/'raw_response.json').exists():
        response=load(folder/'raw_response.json');generation=load(folder/'generation_result.json')
        observation['finish_reason']=response['choices'][0].get('finish_reason')
        assert response.get('usage',{}).get('prompt_tokens',0)+1800<=8192
        assert generation['context_preflight']['fits']
        observation['actual_prompt_tokens']=response.get('usage',{}).get('prompt_tokens')
    if (folder/'candidate.py').exists():
        source=(folder/'candidate.py').read_text(encoding='utf-8')
        assert sha(source.encode())==row['code_sha256']
        observation['fingerprints']=fingerprints(source)
        body=observation['fingerprints'].get('body_sha256')
        matches=[s for s,h in parents.items() if body and h.get('body_sha256')==body]
        observation['eligible_parent_body_matches']=matches
        observation['selected_parent_body_matches']=[p['sampleOrder'] for p in chain['parents'] if p['sampleOrder'] in matches]
        if row['operator']=='mut':
            crossfolder=root/(cid.removesuffix('-mut')+'-cross')
            if (crossfolder/'candidate.py').exists():
                other=fingerprints((crossfolder/'candidate.py').read_text(encoding='utf-8'))
                observation['body_unchanged_from_crossover']=bool(body and body==other.get('body_sha256'))
                observation['source_unchanged_from_crossover']=observation['fingerprints']['source_sha256']==other['source_sha256']
    if row['status']=='valid':
        arr=row['circles'];assert row['shape']==[26,3] and len(arr)==26
        assert all(len(c)==3 and all(isinstance(x,(int,float)) and math.isfinite(x) for x in c) for c in arr)
        assert all(r>=-1e-12 and min(x-r,y-r,1-x-r,1-y-r)>=-1e-12 for x,y,r in arr)
        assert all(math.hypot(a[0]-b[0],a[1]-b[1])>=a[2]+b[2]-1e-12 for i,a in enumerate(arr) for b in arr[i+1:])
        assert math.isclose(sum(c[2] for c in arr),row['score'],rel_tol=1e-12,abs_tol=1e-12)
        observation.update(packing_sha256=sha(json.dumps(sorted(arr),separators=(',',':')).encode()),difference_from_best_parent=row['score']-observation['best_parent_observed_score'])
    else:assert row.get('score') is None
    observation['missing_name_exception']=row['status']=='exception' and 'NameError' in str(row.get('error'))
    return observation

oldchains={c['chain_id']:c for c in oldm['chains']};newchains={c['chain_id']:c for c in m['chains']}
oldobs=[describe(r,prior,oldchains[r['chain_id']]) for r in baseline['results']]
newobs=[describe(r,out,newchains[r['chain_id']]) for r in newrows]
oldbyid={r['call_id']:r for r in oldobs};newbyid={r['call_id']:r for r in newobs}
pairs=[]
for c in m['chains']:
    original=oldchains[c['baseline_chain_id']]
    assert c['parents']==original['parents'] and c['crossover_seed']==original['crossover_seed'] and c['mutation_seed']==original['mutation_seed']
    oldapi=load(prior/c['baseline_crossover_id']/'api_payload.json');newapi=load(out/c['crossover_id']/'api_payload.json')
    assert all(newapi[k]==v for k,v in oldapi.items() if k!='messages') and newapi['messages'][0]==oldapi['messages'][0]
    for stage in ['crossover','mutation']:
        before=oldbyid[c['baseline_'+stage+'_id']];after=newbyid.get(c[stage+'_id'])
        pairs.append(dict(chain_id=c['chain_id'],policy=c['policy'],operator='cross' if stage=='crossover' else 'mut',historical_parent_refs=[{key:p[key] for key in ['id','nbnNodeId','regionIndex','sampleOrder','codeSha256','measuredScore']} for p in c['parents']],baseline=before,new=after,
            difference_from_baseline=after['score']-before['score'] if after and after['status']==before['status']=='valid' else None,
            comparison_scope='Identical historical parent inputs and paired sampling seeds' if stage=='crossover' else 'Workflow comparison; crossover-derived mutation inputs may differ'))
def aggregate(group):
    valid=[r for r in group if r['status']=='valid']
    return dict(attempts=len(group),valid=len(valid),outcomes=dict(Counter(r['status'] for r in group)),best_score=max((r['score'] for r in valid),default=None),target_hits=sum(r['score']>=2.636 for r in valid),missing_name_exceptions=sum(r['missing_name_exception'] for r in group),selected_parent_body_matches=sum(bool(r.get('selected_parent_body_matches')) for r in group),distinct_source_fingerprints=len({r.get('fingerprints',{}).get('source_sha256') for r in group if r.get('fingerprints',{}).get('source_sha256')}),distinct_ast_fingerprints=len({r.get('fingerprints',{}).get('ast_sha256') for r in group if r.get('fingerprints',{}).get('ast_sha256')}),distinct_normalized_body_fingerprints=len({r.get('fingerprints',{}).get('body_sha256') for r in group if r.get('fingerprints',{}).get('body_sha256')}),valid_coordinate_fingerprints=len({r['packing_sha256'] for r in valid}))
cells=[dict(arm=arm,policy=policy,operator=op,**aggregate([r for r in observations if r['policy']==policy and r['operator']==op])) for arm,observations in [('baseline_saved',oldobs),('structural_import',newobs)] for policy in ['uniform','nbn_stratified'] for op in ['cross','mut']]
summary=dict(status='completed_verified' if completed else 'prepared_not_run',baseline=aggregate(oldobs),new=aggregate(newobs),new_maximum_calls=12,pairs=pairs,cells=cells,new_observations=newobs,baseline_source=m['baseline_provenance'],limitations=m['limitations'],geometry_verification='Independent checks of saved arrays; no program reruns',structural_metric='AST function-body fingerprints omit imports/docstrings; syntax diagnostics, not semantic diversity proof',nbn_placement='Parent selections use frozen HNSW identities; no new output placement computed')
if completed:
    history=load(out/'platform_history.json');a={a['id']:a for a in history['view']['attempts']};assert set(a)==set(newbyid)
    for r in newobs:
        actual=a[r['call_id']];assert actual['status']==r['status'] and actual['score']==r['score']
        parents_actual=actual['parents'];assert parents_actual==load(out/r['call_id']/'started.json')['parents']
        if r['operator']=='cross':assert len(parents_actual)==2
        else:
            assert len(parents_actual)==1 and parents_actual[0]['originCallId']==r['call_id'].removesuffix('-mut')+'-cross'
            assert parents_actual[0]['originRevisionId']==m['execution_revision_id'] and 'nbnNodeId' not in parents_actual[0]
    summary['history_event_count']=len(history['events'])
    summary['actual_allocation']=dict(baseline_free_mib=load(prior/'runtime_identity.json')['gpu']['free_mib'],new_start_free_mib=reg['runtime_identity']['gpu']['free_mib'],new_post_load_free_mib=load(out/'post_load_memory_preflight.json')['free_mib'],original_16384_mib_guard_met_at_actual_start=int(reg['runtime_identity']['gpu']['free_mib'])>=16384)
(out/'COMPARISON_SUMMARY.json').write_text(json.dumps(summary,indent=2,allow_nan=False),encoding='utf-8',newline='\n')
def n(value):return '—' if value is None else f'{value:.6f}'
table='| Policy | Operator | Baseline valid | New valid | Baseline best | New best |\n|---|---|---:|---:|---:|---:|\n'
for policy in ['uniform','nbn_stratified']:
    for op in ['cross','mut']:
        before=next(c for c in cells if c['arm']=='baseline_saved' and c['policy']==policy and c['operator']==op);after=next(c for c in cells if c['arm']=='structural_import' and c['policy']==policy and c['operator']==op)
        table+=f"| {policy} | {op} | {before['valid']}/{before['attempts']} | {str(after['valid'])+'/'+str(after['attempts']) if completed else 'Not run'} | {n(before['best_score'])} | {n(after['best_score'])} |\n"
(out/'COMPARISON_RESULTS.md').write_text(f'''# AEL matched structural/import prompt follow-up

Status: **{summary['status']}**. Saved baseline: {summary['baseline']['attempts']} calls. New condition: {summary['new']['attempts']} calls, {summary['new']['valid']} valid outputs. New best score: {n(summary['new']['best_score'])}; target hits >=2.6360: {summary['new']['target_hits'] if completed else 'not evaluated'}.

{table}
Baseline has {summary['baseline']['selected_parent_body_matches']} selected-parent body matches and {summary['baseline']['missing_name_exceptions']} missing-name exceptions. The new condition has {summary['new']['selected_parent_body_matches']} matches and {summary['new']['missing_name_exceptions']} missing-name exceptions{'' if completed else ' because it has not run; these are not experimental outcomes'}.

This compares a joint structural-change/import-completeness prompt intervention against saved prior baseline outcomes. Baseline calls were not repeated. Crossover inputs are matched historical pairs/seeds. Mutation inputs are actual new crossover outputs, so mutation comparisons concern the workflow, not an isolated mutation-prompt effect. The sequential small sample, potentially varying shared-host load and bundled instruction change prevent strong causal or superiority claims. Fingerprint differences do not establish algorithmic diversity without source inspection. Failed fitness stays undefined. No new NBN placement or official-verifier equivalence is claimed.

The allocation amendment in PRE_REGISTRATION_AMENDMENT.json preserves its original prepared version. Model/build/template/context/sampling and evaluator stay pinned. Read PROTOCOL.md, PROMPT_CHANGES.diff, exact call folders and platform history for the complete process. Research results are never repaired or replaced during reporting.
''',encoding='utf-8',newline='\n')
data=json.dumps(summary,ensure_ascii=False).replace('<','\\u003c')
page='''<!doctype html><html lang="en"><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1"><title>AEL matched prompt comparison</title><style>*{box-sizing:border-box}body{font:16px/1.5 system-ui,sans-serif;background:#f2f6fb;color:#17283f;margin:0;padding:26px}main{max-width:1300px;margin:auto}h1{font-size:29px;line-height:1.25}h2{font-size:21px}.muted{color:#52657d}.cards{display:grid;grid-template-columns:repeat(4,1fr);gap:12px;margin:22px 0}.card,section{background:white;border:1px solid #d9e2ef;border-radius:12px;padding:18px}.card strong{font-size:28px;display:block}section{margin-bottom:18px}.scroll{overflow:auto}table{width:100%;border-collapse:collapse;font-size:14px}th,td{text-align:left;padding:10px;border-bottom:1px solid #e0e7f0}th{background:#f3f6fa}select,button{font:inherit;background:white;border:1px solid #9eafc5;border-radius:6px;padding:7px}.warn{border-left:4px solid #af710f;padding-left:14px}.valid{color:#186c45}.failure{color:#9a2441}pre{max-height:420px;overflow:auto;white-space:pre-wrap;overflow-wrap:anywhere;background:#102038;color:#f0f5fc;padding:15px}#status{font-weight:600}@media(max-width:700px){body{padding:12px}.cards{grid-template-columns:repeat(2,1fr)}h1{font-size:24px}}</style><main><h1>AEL: explicit structural changes and complete imports</h1><p class="muted">Circle Packing N=26 · same historical pairs, model and evaluator · saved baseline reused</p><p id="status"></p><div class="cards" id="cards"></div><section><h2>Selection × operator comparison</h2><div class="scroll"><table><thead><tr><th>Selection</th><th>Operator</th><th>Baseline valid</th><th>New valid</th><th>Baseline best</th><th>New best</th></tr></thead><tbody id="cells"></tbody></table></div></section><section><h2>Matched attempts</h2><p><label>Selection <select id="policy"><option value="all">All</option><option>uniform</option><option>nbn_stratified</option></select></label> <label>Operator <select id="operator"><option value="all">All</option><option value="cross">Crossover</option><option value="mut">Mutation</option></select></label></p><div class="scroll"><table><thead><tr><th>Pair</th><th>Baseline outcome</th><th>New outcome</th><th>Baseline score</th><th>New score</th><th>Δ valid score</th><th>New parent-body match</th></tr></thead><tbody id="pairs"></tbody></table></div></section><section id="details"><h2>Recorded pair details</h2><div id="selected">Choose a pair to inspect status, parent-body comparisons and score provenance.</div></section><section><h2>Interpretation boundaries</h2><p class="warn">The intervention changes structural and import requirements together. This small sequential follow-up reuses an earlier baseline. It cannot isolate those two instructions or establish general superiority.</p><p>Crossover compares matched historical inputs. Mutation compares the complete workflow because its crossover input can differ. Source/body fingerprints are syntax diagnostics; mechanism diversity requires code inspection. No generated-program NBN placement is implied.</p><p><a href="COMPARISON_RESULTS.md">Results and limits</a> · <a href="PROMPT_CHANGES.diff">Exact prompt changes</a> · <a href="PROTOCOL.md">Registered protocol</a> · <a href="PRE_REGISTRATION_AMENDMENT.json">Allocation amendment</a> · <a href="platform_history.json">History export when completed</a></p></section></main><script>
const s=__DATA__,complete=s.status==='completed_verified',el=id=>document.getElementById(id),num=v=>v==null?'—':v.toFixed(6),node=(tag,value)=>{let n=document.createElement(tag);n.textContent=value;return n};el('status').textContent=complete?'Completed: saved outputs independently verified.':'Prepared: no new experimental results yet.';
for(const [label,value] of [['Saved baseline calls',s.baseline.attempts],['New calls',s.new.attempts],['New valid outputs',complete?s.new.valid:'Not run'],['New best score',num(s.new.best_score)]]){let c=document.createElement('div');c.className='card';c.append(node('span',label),node('strong',value));el('cards').append(c)}
for(const policy of ['uniform','nbn_stratified'])for(const op of ['cross','mut']){let a=s.cells.find(c=>c.arm==='baseline_saved'&&c.policy===policy&&c.operator===op),b=s.cells.find(c=>c.arm==='structural_import'&&c.policy===policy&&c.operator===op),tr=document.createElement('tr');for(const v of [policy,op,a.valid+'/'+a.attempts,complete?b.valid+'/'+b.attempts:'Not run',num(a.best_score),num(b.best_score)])tr.append(node('td',v));el('cells').append(tr)}
function detail(p){let box=el('selected');box.replaceChildren(node('h3',p.chain_id+' / '+p.operator),node('p',p.comparison_scope),node('pre',JSON.stringify(p,null,2)));let links=document.createElement('p');for(const [label,file] of p.new?[['New prompt',p.new.call_id+'/prompt.txt'],['New response',p.new.call_id+'/raw_response.json'],['New source',p.new.call_id+'/candidate.py']]:p.operator==='cross'?[['Planned complete prompt',p.chain_id+'-cross/prompt.txt']]:[['Planned mutation template','mutation_template.txt']]){let a=node('a',label);a.href=file;a.target='_blank';links.append(a,document.createTextNode(' · '))}let old=node('a','Saved baseline prompt');old.href='../ael_operator_pilot_20261031/'+p.baseline.call_id+'/prompt.txt';old.target='_blank';links.append(old);box.append(links);el('details').scrollIntoView({behavior:'smooth'})}
function render(){el('pairs').replaceChildren();for(const p of s.pairs){if(el('policy').value!=='all'&&p.policy!==el('policy').value)continue;if(el('operator').value!=='all'&&p.operator!==el('operator').value)continue;let tr=document.createElement('tr'),td=document.createElement('td'),b=node('button',p.chain_id.replace('structural-','')+' / '+p.operator);b.onclick=()=>detail(p);td.append(b);tr.append(td);for(const v of [p.baseline.status,p.new?p.new.status:'Not requested',num(p.baseline.score),num(p.new?.score),num(p.difference_from_baseline),p.new?p.new.selected_parent_body_matches?.join(', ')||'None detected':'—'])tr.append(node('td',v));el('pairs').append(tr)}}el('policy').onchange=render;el('operator').onchange=render;render();window.__comparisonReady=true;
</script></html>'''.replace('__DATA__',data)
(out/'ael_structural_comparison_review.html').write_text(page,encoding='utf-8',newline='\n')
print(json.dumps({k:summary[k] for k in ['status','baseline','new']},indent=2))
