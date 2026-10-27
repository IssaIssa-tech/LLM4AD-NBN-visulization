"""Versioned exact NBN extension for evaluated, prepared Sobol variants."""
import json, os, shutil, sys
from pathlib import Path
import numpy as np

ROOT=Path(__file__).resolve().parent
os.environ['VISUAL_PLATFORM_NBN_BACKEND']='exact'
PREVIOUS=ROOT.parent/'m2ip_exact_nbn_20261027'
os.environ['VISUAL_PLATFORM_CODET5_CACHE']=str(ROOT/'embeddings.sqlite3')
os.environ['VISUAL_PLATFORM_CODET5_DIR']=str(ROOT.parents[1]/'private_codet5_env_20261027/model')
sys.path.insert(0,str(PREVIOUS))
from visual_platform.nbn.bridge import build_nbn_graph, get_codet5_embedding_matrix

def main():
    target=ROOT/'combined_nbn_m2ipd_graph.json'
    if target.exists(): raise SystemExit('Graph already exists; refusing to repeat build')
    if not (ROOT/'embeddings.sqlite3').exists():
        shutil.copy2(PREVIOUS/'visual_platform/.codet5_embeddings_cache.sqlite3',ROOT/'embeddings.sqlite3')
    base=json.loads((PREVIOUS/'combined_nbn_m2ip_graph.json').read_text())['graph']
    samples=[]
    for n in base['nodes']:
        samples.append(dict(id=n['id'],sample_order=n['mergedSampleOrder'],origin_sample_order=n['sampleOrder'],score=n.get('rawScore'),function=n.get('functionPreview',''),operator=n.get('operator',''),algorithm=n.get('algorithm',''),source_kind=n.get('sourceKind',''),source_label=n.get('sourceLabel',''),origin_kind=n.get('originKind','')))
    results=json.loads((ROOT/'algorithm_results.json').read_text())['results']
    added=[]
    for trial in results:
        assert trial['status']=='valid'
        code=(ROOT/trial['trial_id']/'candidate.py').read_text().strip()
        record=dict(id='prepared-sobol-'+trial['trial_id'],sample_order=len(samples)+1,origin_sample_order=len(samples)+1,score=trial['score'],function=code,operator='prepared_sobol_seed_variant',algorithm='Prepared M2 Sobol seed sensitivity variant',source_kind='algorithm_test',source_label='Prepared algorithm variant; no successful LLM delivery',origin_kind='algorithm_test')
        samples.append(record)
        added.append(dict(id=record['id'],trial_id=trial['trial_id'],sobol_seed=trial['sobol_seed'],score=trial['score'],evaluation_status='valid',provenance='prepared_algorithm_variant'))
    graph=build_nbn_graph(samples,ROOT/'build_artifacts',distance_metric='codet5p_embedding_cosine')
    nodes=graph['nodes']; ids={n['id']:i for i,n in enumerate(nodes)}
    roots=[i for i,n in enumerate(nodes) if n['ofecParentIndex']==i]
    assert len(roots)==1
    def branch(i):
        visited=set()
        while i!=roots[0]:
            assert i not in visited
            visited.add(i); p=nodes[i]['ofecParentIndex']
            if p==roots[0]: return nodes[i]['id']
            i=p
        return nodes[i]['id']
    vectors,_=get_codet5_embedding_matrix(samples)
    for t in added:
        i=ids[t['id']]; n=nodes[i]; p=nodes[n['ofecParentIndex']]
        t.update(parent_id=p['id'],parent_score=p['score'],distance_to_parent=n['distanceToParent'],top_branch_id=branch(i))
    ai=[ids[t['id']] for t in added]
    v=np.asarray(vectors,dtype=float); v=v/np.maximum(np.linalg.norm(v,axis=1,keepdims=True),1e-12)
    distances=np.maximum(0,1-v[ai]@v[ai].T)
    assert len(nodes)==14040 and len(graph['edges'])==14039
    target.write_text(json.dumps({'graph':graph},ensure_ascii=False))
    (ROOT/'m2ipd_region_analysis.json').write_text(json.dumps(dict(nodes=len(nodes),edges=len(graph['edges']),stats=graph.get('graphBuildStats'),variants=added,pairwise_cosine_distances=distances.tolist(),branch_definition='First descendant under the global root; operational code-region proxy'),indent=2))
    print((ROOT/'m2ipd_region_analysis.json').read_text(),flush=True)

if __name__=='__main__': main()
