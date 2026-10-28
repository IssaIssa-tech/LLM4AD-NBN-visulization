"""Prepare an auditable 2x2 preliminary design; no LLM requests or evaluation."""
import ast,hashlib,json,math
from datetime import datetime,timezone
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]
BASE=ROOT/'LLM4AD-NBN-visualization-github/research/circle_packing_prompt_study_20261026'
GRAPH=BASE/'historical_data/circle_packing_historical_nbn_14000.json'
OUT=ROOT/'output/regional_prompt_comparison_draft_20261028'
def sha(text):return hashlib.sha256(text.encode()).hexdigest()
def main():
    if OUT.exists():raise SystemExit('Existing comparison draft; refusing overwrite')
    selection=json.loads((ROOT/'output/regional_representatives_20261028/selection_manifest.json').read_text())
    assert hashlib.sha256(GRAPH.read_bytes()).hexdigest()==selection['source_graph_sha256']
    graph=json.loads(GRAPH.read_text())['graph'];nodes=graph['nodes'];by_id={n['id']:n for n in nodes}
    root=next(n['ofecIndex'] for n in nodes if n['ofecIndex']==n['ofecParentIndex']);by_index={n['ofecIndex']:n for n in nodes}
    def branch(index):
        seen=set()
        while index!=root:
            assert index not in seen;seen.add(index);p=by_index[index]['ofecParentIndex']
            if p==root:return by_index[index]['id']
            index=p
        return by_index[index]['id']
    positive=sorted((n for n in nodes if isinstance(n.get('rawScore'),(int,float)) and math.isfinite(n['rawScore']) and n['rawScore']>0),key=lambda n:(-n['rawScore'],n['sampleOrder']))
    quality=[];seen=set()
    for node in positive:
        key=sha(node['functionPreview'].strip())
        if key not in seen:quality.append(node);seen.add(key)
        if len(quality)==4:break
    regional=[by_id[r['node_id']] for r in selection['references'] if r['role']=='high_score']
    assert len(regional)==4 and len({branch(n['ofecIndex']) for n in regional})==4
    pools={'quality_only_top4':quality,'nbn_region_top4':regional}
    contract='''Generate a new optimization algorithm for packing 26 circles of possibly different radii in the unit square. Maximize the sum of radii; research target is at least 2.6360. This target is not guaranteed.
Return exactly one Python code block containing a complete program with exactly one top-level function pack_circles(n: int) -> np.ndarray. Approved imports: numpy, math, scipy. Do not include top-level execution, examples, helper functions or prose outside the code block. Return a finite (n, 3) array of (x,y,r), nonnegative radii, containment and all-pairs non-overlap. Use deterministic random seeds fixed to 2025 and bounded computation. The research evaluator uses n=26 and a 20-second isolated execution limit. This is a research limit, not a claimed official challenge rule.
The supplied historical program is an archival design reference, not a currently scored incumbent. Its stored score may come from a different environment or runtime budget. Preserve the interface, but generate your own executable algorithm under the stated research budget.
'''
    additions={
        'contract_M2':'Replace one substantive component of the reference: initialization, placement, local search or repair. Do not merely rename variables or change constants. Preserve useful components when appropriate.\n',
        'contract_M2_structural_exploration':'Replace one substantive component of the reference: initialization, placement, local search or repair. Do not merely rename variables or change constants. Explore a meaningfully different mechanism from the reference rather than restating its iteration/proposal pattern. State the changed mechanism briefly in the function docstring. The NBN branch label supplied below is an operational code-space grouping, not a proof of a physical basin or a quality guarantee.\n'}
    OUT.mkdir();requests={};slots=[];pool_records={};diagnostics=[]
    for strategy,pool in pools.items():
        pool_records[strategy]=[]
        for node in pool:
            code=node['functionPreview'].strip();seed=202600000+node['sampleOrder'];region=branch(node['ofecIndex'])
            parent=dict(node_id=node['id'],sample_order=node['sampleOrder'],nbn_node_id=node.get('nbnNodeId'),region_node_id=region,code_sha256=sha(code),archived_score=node['rawScore'],score_provenance='archived_not_current_budget',usage='textual_archival_reference_not_incumbent')
            pool_records[strategy].append(parent)
            for profile,addition in additions.items():
                metadata=f"Reference node: {node['id']}\nArchived score (not current-budget fitness): {node['rawScore']}\n"
                if profile=='contract_M2_structural_exploration':metadata+=f'NBN top-level branch: {region}\n'
                prompt=contract+addition+metadata+'Reference source:\n```python\n'+code+'\n```\n'
                request=dict(model='qwen2.5:3b',temperature=.1,num_predict=1800,sampling_seed=seed,prompt=prompt)
                key=sha(json.dumps(request,sort_keys=True));request_id='request-'+key[:16]
                if request_id not in requests:
                    directory=OUT/request_id;directory.mkdir();(directory/'prompt.txt').write_text(prompt,encoding='utf-8');(directory/'parent_candidate.py').write_text(code,encoding='utf-8')
                    requests[request_id]=dict(request_id=request_id,parent=parent,prompt_profile=profile,prompt_sha256=sha(prompt),sampling_seed=seed,request_sha256=key)
                slots.append(dict(strategy=strategy,prompt_profile=profile,parent_node_id=node['id'],request_id=request_id))
    for node_id in sorted({n['id'] for p in pools.values() for n in p}):
        node=by_id[node_id];tree=ast.parse(node['functionPreview'])
        literal_ranges=[call.args[0].value for call in ast.walk(tree) if isinstance(call,ast.Call) and isinstance(call.func,ast.Name) and call.func.id=='range' and call.args and isinstance(call.args[0],ast.Constant) and isinstance(call.args[0].value,int)]
        diagnostics.append(dict(node_id=node_id,sample_order=node['sampleOrder'],literal_range_arguments=literal_ranges,largest_literal_range=max(literal_ranges,default=None),interpretation='Source structure only; not a runtime estimate'))
    manifest=dict(status='draft_not_registered_not_executed',created_utc=datetime.now(timezone.utc).isoformat(),purpose='Preliminary comparison of parent selection and prompt profiles',source_graph_sha256=selection['source_graph_sha256'],source_backend=graph['graphBuildStats'],source_platform_revision='circle-history-verified-20261028',factors=dict(parent_selection=list(pools),prompt_profile=list(additions)),parent_pools=pool_records,analytical_slots=slots,unique_requests=list(requests.values()),analytical_slot_count=len(slots),unique_generation_call_count=len(requests),overlap_policy='Identical parent/prompt/model/seed requests are generated once and shared across strategy slots; shared outcomes are not independent replicates',budget=dict(per_generated_program_seconds=20,model='qwen2.5:3b',temperature=.1,num_predict=1800,repair_calls=0,model_calls=len(requests)),parent_policy='All selected archival programs may be references despite diagnostic timeouts; no archived score becomes a current-budget incumbent',outcome_policy='Retain every response, failure, extracted code, score, coordinates and selection/graph metadata; report unsuccessful attempts',limitations=['One generation per parent/profile; preliminary descriptive comparison only','Prompt profiles differ as complete instruction packages; no single-sentence causal inference','HNSW regions are operational, not guaranteed true basins','Existing 20-second limit is a research condition; official verifier equivalence remains unresolved'],before_execution=['Confirm and freeze evaluator source hash and environment','Verify local model digest and endpoint','Bind each trial to platform history and source graph artifact','Review runtime policy and official-verifier limits; no unlabelled challenge-compatible claims'],source_complexity=diagnostics)
    (OUT/'draft_comparison_manifest.json').write_text(json.dumps(manifest,indent=2),encoding='utf-8')
    print(json.dumps(dict(slots=len(slots),unique_calls=len(requests),pools=pool_records,source_complexity=diagnostics),indent=2))
if __name__=='__main__':main()
