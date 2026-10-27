"""Add five matched feasible variants to the prior exact NBN."""
import json,os,shutil,sys
from pathlib import Path
import numpy as np
ROOT=Path(__file__).resolve().parent
PREV=ROOT.parent/'m2ipd_exact_nbn_20261027'
PLATFORM=ROOT.parent/'m2ip_exact_nbn_20261027'
os.environ['VISUAL_PLATFORM_NBN_BACKEND']='exact'
os.environ['VISUAL_PLATFORM_CODET5_CACHE']=str(ROOT/'embeddings.sqlite3')
os.environ['VISUAL_PLATFORM_CODET5_DIR']=str(ROOT.parents[1]/'private_codet5_env_20261027/model')
sys.path.insert(0,str(PLATFORM))
from visual_platform.nbn.bridge import build_nbn_graph,get_codet5_embedding_matrix

def main():
    target=ROOT/'combined_nbn_feasible_graph.json'
    if target.exists():raise SystemExit('Existing graph; refusing repeat')
    if not (ROOT/'embeddings.sqlite3').exists():shutil.copy2(PREV/'embeddings.sqlite3',ROOT/'embeddings.sqlite3')
    base=json.loads((PREV/'combined_nbn_m2ipd_graph.json').read_text())['graph']
    samples=[dict(id=n['id'],sample_order=n['mergedSampleOrder'],origin_sample_order=n['sampleOrder'],score=n.get('rawScore'),function=n.get('functionPreview',''),operator=n.get('operator',''),algorithm=n.get('algorithm',''),source_kind=n.get('sourceKind',''),source_label=n.get('sourceLabel',''),origin_kind=n.get('originKind','')) for n in base['nodes']]
    results=json.loads((ROOT/'results.json').read_text())['matched_results']; added=[]
    for row in results:
        seed=row['sobol_seed']; assert row['feasible']['status']=='valid'
        code=(ROOT/f'feasible-{seed}/candidate.py').read_text().strip()
        record=dict(id=f'prepared-feasible-{seed}',sample_order=len(samples)+1,origin_sample_order=len(samples)+1,score=row['feasible']['score'],function=code,operator='prepared_feasible_initialization',algorithm='Feasible Sobol initialization with original probabilistic acceptance',source_kind='algorithm_test',source_label='Prepared feasible initialization variant',origin_kind='algorithm_test')
        samples.append(record);added.append(dict(id=record['id'],sobol_seed=seed,score=record['score'],evaluation_status='valid',provenance='prepared_feasible_variant'))
    graph=build_nbn_graph(samples,ROOT/'build_artifacts',distance_metric='codet5p_embedding_cosine')
    nodes=graph['nodes']; ids={n['id']:i for i,n in enumerate(nodes)}
    roots=[i for i,n in enumerate(nodes) if i==n['ofecParentIndex']];assert len(roots)==1
    def branch(i):
        seen=set()
        while i!=roots[0]:
            assert i not in seen;seen.add(i);p=nodes[i]['ofecParentIndex']
            if p==roots[0]:return nodes[i]['id']
            i=p
        return nodes[i]['id']
    vectors,_=get_codet5_embedding_matrix(samples)
    v=np.asarray(vectors,dtype=float);v/=np.maximum(np.linalg.norm(v,axis=1,keepdims=True),1e-12)
    for t in added:
        i=ids[t['id']];n=nodes[i];p=nodes[n['ofecParentIndex']]
        control='prepared-sobol-m2ipd-'+str(t['sobol_seed'])
        t.update(parent_id=p['id'],parent_score=p['score'],distance_to_parent=n['distanceToParent'],top_branch_id=branch(i),matched_control_id=control,control_branch_id=branch(ids[control]),distance_to_matched_control=float(max(0,1-v[i]@v[ids[control]])))
    ai=[ids[t['id']] for t in added]
    assert len(nodes)==14045 and len(graph['edges'])==14044
    target.write_text(json.dumps({'graph':graph},ensure_ascii=False))
    report=dict(nodes=len(nodes),edges=len(graph['edges']),stats=graph.get('graphBuildStats'),variants=added,pairwise_cosine_distances=np.maximum(0,1-v[ai]@v[ai].T).tolist(),branch_definition='First descendant under global root; operational code-region proxy')
    (ROOT/'feasible_region_analysis.json').write_text(json.dumps(report,indent=2)); print(json.dumps(report,indent=2),flush=True)
if __name__=='__main__':main()
