"""Exact measured-only NBN and fixed-archive code associations; never execute sources."""
import ast,copy,hashlib,json,math,os,sqlite3
from collections import Counter
from pathlib import Path
os.environ.update(OPENBLAS_NUM_THREADS='2',OMP_NUM_THREADS='2',MKL_NUM_THREADS='2')
import numpy as np
root=Path(__file__).resolve().parent;assert root.name=='ael_nbn_analysis_20261031'
load=lambda name:json.loads((root/name).read_text())
sha=lambda raw:hashlib.sha256(raw).hexdigest()
def save(name,value):
    with (root/name).open('x',encoding='utf-8') as f:json.dump(value,f,indent=2,allow_nan=False)
assert not (root/'NBN_ANALYSIS.json').exists(),'Existing completed analysis; inspect rather than rebuild'
m=load('INPUT_MANIFEST.json');meta=load('historical_metadata.json');rep=root/'representation_512'
embedding=json.loads((rep/'EMBEDDING_RESULT.json').read_text());checks=json.loads((rep/'ANCHOR_CHECKS.json').read_text());assert checks['passed']
old=np.load(root/'historical_vectors.private.npy').astype(float);newdata=np.load(rep/'generated_embeddings.npz');new=newdata['vectors'].astype(float)
assert list(newdata['program_ids'])==[p['id'] for p in m['programs']]
old/=np.linalg.norm(old,axis=1,keepdims=True);new/=np.linalg.norm(new,axis=1,keepdims=True)
assert old.shape==(14000,256) and new.shape==(24,256)
byid={n['id']:i for i,n in enumerate(meta)};byindex={n['ofec_index']:i for i,n in enumerate(meta)}
graph=json.loads(Path(m['source_graph_reconciliation']['storage_uri']).read_text());graph=graph.get('graph',graph)
source_vectors={h:v for h,v in zip([n['code_sha256'] for n in meta],old)}
# Store one historical-only PCA fit. No new program changes its basis/scales.
mean=old.mean(axis=0);centered=old-mean;eigenvalues,eigenvectors=np.linalg.eigh(centered.T@centered/(len(old)-1));basis=eigenvectors[:,-3:][:,::-1]
for axis in range(3):
    pivot=np.argmax(abs(basis[:,axis]))
    if basis[pivot,axis]<0:basis[:,axis]*=-1
projection=centered@basis;scale=np.percentile(abs(projection),99,axis=0);scale=np.maximum(scale,1e-6)
positions=projection/scale*300;newpositions=(new-mean)@basis/scale*300
with (root/'historical_pca_transform.npz').open('xb') as f:np.savez_compressed(f,mean=mean,basis=basis,scale=scale,spread=300,explained_variance=eigenvalues[-3:][::-1]/eigenvalues.sum())
save('PROJECTION_SPEC.json',dict(fit='historical normalized cached vectors only',dimensions=3,explained_variance_ratio=(eigenvalues[-3:][::-1]/eigenvalues.sum()).tolist(),scale='Each component divided by historical 99th absolute percentile and multiplied by 300',height_in_archive_view='PCA component 3, not fitness',transform_sha256=sha((root/'historical_pca_transform.npz').read_bytes())))
cosine=np.clip(1-new@old.T,0,2);pairwise=np.clip(1-new@new.T,0,2)
truncation=json.loads((rep/'TRUNCATION_AUDIT.json').read_text());token_info={r['program_id']:r for r in truncation['programs']}
class DropNotes(ast.NodeTransformer):
    def visit_Import(self,node):return None
    def visit_ImportFrom(self,node):return None
    def visit_Expr(self,node):return None if isinstance(node.value,ast.Constant) and isinstance(node.value.value,str) else self.generic_visit(node)
def code_hashes(source):
    tree=ast.parse(source);fn=next(n for n in tree.body if isinstance(n,ast.FunctionDef) and n.name=='pack_circles')
    return dict(source=sha(source.strip().encode()),ast=sha(ast.dump(tree,include_attributes=False).encode()),body=sha(ast.dump(DropNotes().visit(copy.deepcopy(fn)),include_attributes=False).encode()))
archive_source_lookup={}
for i,n in enumerate(meta):archive_source_lookup.setdefault(n['code_sha256'],[]).append(i)
rows=[];measured=[];measured_vectors=[]
for d in m['historical_diagnostics']:
    c=d['candidate'];i=byid[c['node_id']]
    assert meta[i]['code_sha256']==c['canonical_code_sha256']
    measured.append(dict(id='measured-historical:'+c['node_id'],kind='historical_diagnostic',historical_id=c['node_id'],nbn_node_id=c['nbn_node_id'],sample_order=c['sample_order'],historical_region_index=meta[i]['region_index'],status=d['evaluation_status'],score=d['score'],source_sha256=c['canonical_code_sha256'],source_path='ael_parent_eligibility_20261031/'+c['candidate_file'],evaluation_id=d['evaluation_id'],position=positions[i].tolist()))
    measured_vectors.append(old[i])
parent_body={d['candidate']['node_id']:code_hashes(graph['nodes'][byid[d['candidate']['node_id']]]['functionPreview'])['body'] for d in m['historical_diagnostics']}
for i,p in enumerate(m['programs']):
    source=(root.parent/p['source_file']).read_text();assert sha(source.encode())==p['code_sha256'];h=code_hashes(source)
    order=np.argsort(cosine[i],kind='stable');top=[];distinct=[];seen=set()
    for j in order:
        n=meta[int(j)];entry=dict(historical_id=n['id'],historical_sample=n['sample_order'],historical_nbn_node_id=n['nbn_node_id'],historical_region_index=n['region_index'],source_sha256=n['code_sha256'],cosine_distance=float(cosine[i,j]),archived_score=n['archived_score'],fitness_role='archived reference, not a new-budget incumbent')
        if len(top)<5:top.append(entry)
        if n['code_sha256'] not in seen:
            seen.add(n['code_sha256']);distinct.append(entry)
        if len(top)>=5 and len(distinct)>=5:break
    nearest=top[0];tied=np.flatnonzero(abs(cosine[i]-nearest['cosine_distance'])<=1e-10)
    selected=[]
    for parent in p['parents']:
        hid=parent.get('id')
        if hid in byid:
            j=byid[hid];selected.append(dict(id=hid,kind='historical_parent',nbn_node_id=meta[j]['nbn_node_id'],region_index=meta[j]['region_index'],cosine_distance=float(cosine[i,j])))
        elif parent.get('originCallId'):
            matches=[k for k,v in enumerate(m['programs']) if v['origin_revision_id']==p['origin_revision_id'] and v['call_id']==parent['originCallId']];assert len(matches)==1
            selected.append(dict(id=m['programs'][matches[0]]['id'],kind='generated_crossover_parent',cosine_distance=float(pairwise[i,matches[0]])))
    row=dict(**p,nearest_historical=nearest,nearest5_records=top,nearest5_distinct_sources=distinct,nearest_tie_region_indices=sorted({meta[int(j)]['region_index'] for j in tied}),distance_to_selected_parents=selected,exact_source_archive_matches=[meta[j]['id'] for j in archive_source_lookup.get(h['source'],[])],measured_historical_body_matches=[key for key,value in parent_body.items() if value==h['body']],source_fingerprints=h,truncation=token_info[p['id']],position=newpositions[i].tolist())
    rows.append(row);measured.append(dict(id=p['id'],kind='generated',case=p['case'],origin_revision_id=p['origin_revision_id'],call_id=p['call_id'],operator=p['operator'],selection_policy=p['selection_policy'],status=p['evaluation_status'],score=p['score'],source_sha256=h['source'],source_path=p['source_file'],position=newpositions[i].tolist(),nearest_historical_id=nearest['historical_id'],nearest_historical_region=nearest['historical_region_index']))
    measured_vectors.append(new[i])
matrix=np.stack(measured_vectors);dist=np.clip(1-matrix@matrix.T,0,2)
ranked=[i for i,n in enumerate(measured) if n['status']=='valid' and isinstance(n['score'],(int,float)) and math.isfinite(n['score'])]
assert len(ranked)==31 and len(measured)==54
edges=[];roots=[]
for i,n in enumerate(measured):
    n['nbn_parent_id']=None;n['distance_to_better']=None
    if i not in ranked:n['fitness_status']='unranked';continue
    n['fitness_status']='observed_valid'
    better=[j for j in ranked if measured[j]['score']>n['score']]
    if not better:roots.append(n['id']);continue
    nearest=min(better,key=lambda j:(dist[i,j],measured[j]['id']))
    n['nbn_parent_id']=measured[nearest]['id'];n['distance_to_better']=float(dist[i,nearest])
    edges.append(dict(source=n['id'],target=measured[nearest]['id'],cosine_distance=float(dist[i,nearest]),source_score=n['score'],target_score=measured[nearest]['score'],type='exact_strict_nearest_better'))
    assert measured[nearest]['score']>n['score']
    assert all(dist[i,nearest]<=dist[i,j]+1e-14 for j in better)
assert len(edges)==len(ranked)-len(roots)
measured_graph=dict(rule='argmin cosine distance over observed valid nodes with strictly greater measured score',nodes=measured,edges=edges,root_ids=roots,ranked_nodes=len(ranked),unranked_nodes=len(measured)-len(ranked),source_graph_identity=m['source_graph_identity'],fitness_provenance=m['evaluation_provenance'],source_graph_role='background context only; archived fitness not ranked against present fitness')
save('measured_nbn_graph.json',measured_graph)
histregions=Counter(n['region_index'] for n in meta);nearestregions=Counter(r['nearest_historical']['historical_region_index'] for r in rows)
summaries=[]
for case in sorted({r['case'] for r in rows}):
    group=[r for r in rows if r['case']==case];good=[r for r in group if r['evaluation_status']=='valid']
    summaries.append(dict(case=case,records=len(group),valid=len(good),nearest_region_counts=dict(Counter(r['nearest_historical']['historical_region_index'] for r in group)),nearest_archive_distance_min=float(min(r['nearest_historical']['cosine_distance'] for r in group)),nearest_archive_distance_median=float(np.median([r['nearest_historical']['cosine_distance'] for r in group])),nearest_archive_distance_max=float(max(r['nearest_historical']['cosine_distance'] for r in group)),unique_source_hashes=len({r['source_fingerprints']['source'] for r in group}),unique_body_hashes=len({r['source_fingerprints']['body'] for r in group}),truncated_records=sum(r['truncation']['truncated'] for r in group),valid_body_matches_to_measured_history=sum(bool(r['measured_historical_body_matches']) for r in good)))
summary=dict(status='completed',generation_calls=0,candidate_executions=0,historical_archive_nodes=14000,generated_records=24,generated_valid=9,generated_failed=15,measured_records=54,measured_ranked=31,measured_unranked=23,measured_edges=len(edges),strict_maximum_root_count=len(roots),strict_maximum_roots=roots,maximum_observed_score=max(measured[i]['score'] for i in ranked),target_score=2.636,target_hits=sum(measured[i]['score']>=2.636 for i in ranked),historical_region_counts=dict(histregions),generated_nearest_region_counts=dict(nearestregions),cohorts=summaries,embedding=dict(model=embedding['model'],dimension=256,max_tokens=512,anchor_count=len(checks['checks']),maximum_anchor_abs_error=max(c['maximum_abs_error'] for c in checks['checks']),truncated_generated_records=truncation['truncated_record_count'],unique_generated_sources=embedding['unique_generated_sources'],new_unique_vectors=embedding['new_generated_unique_sources']),novelty_caution='Nearest archive association and body/embedding differences do not prove functional novelty or a new attraction basin. Prefix truncation may hide edits.',fitness_caution='Archived HNSW edges and new measured-only strict NBN edges are distinct; no mixed-fitness nearest-better claim')
save('NBN_ANALYSIS.json',dict(summary=summary,programs=rows))
with (root/'generated_pairwise_cosine_distances.npz').open('xb') as f:np.savez_compressed(f,distances=pairwise,ids=np.array([p['id'] for p in m['programs']]))
with (root/'measured_pairwise_cosine_distances.npz').open('xb') as f:np.savez_compressed(f,distances=dist,ids=np.array([p['id'] for p in measured]))
archive_nodes=[dict(id=n['id'],sample=n['sample_order'],nbnNodeId=n['nbn_node_id'],region=n['region_index'],archivedScore=n['archived_score'],p=[round(float(v),5) for v in positions[i]]) for i,n in enumerate(meta)]
archive_edges=[[i,byindex[n['parent_index']]] for i,n in enumerate(meta) if n['parent_index']!=n['ofec_index']]
save('VIEWER_DATA.json',dict(summary=summary,historical=archive_nodes,archived_edges=archive_edges,generated=rows,measured=measured_graph))
assert sha(Path(m['historical_cache']).read_bytes())==load('INPUT_AUDIT.json')['cache_sha256']
print(json.dumps(summary,indent=2))
