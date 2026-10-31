"""Read-only input/cache audit and byte-exact snapshot of four event histories."""
import hashlib,json,os,site,sqlite3,sys,urllib.request,zipfile
from pathlib import Path
parent=Path(__file__).resolve().parent;root=parent/'ael_nbn_analysis_20261031';assert not root.exists()
root.mkdir();manifest=parent/'ael_nbn_input_manifest_20261031.json'
(root/'INPUT_MANIFEST.json').write_bytes(manifest.read_bytes());m=json.loads(manifest.read_bytes())
dep='/home/dyy/llm4ad_env/lib/python3.10/site-packages';site.addsitedir(dep);sys.path.remove(dep)
private=str(Path(sys.prefix)/'lib/python3.10/site-packages');sys.path.insert(sys.path.index(private)+1,dep);sys.path.insert(0,str(parent))
os.environ.update(VISUAL_PLATFORM_LOCAL_DATA_DIR=str(parent/'state'),VISUAL_PLATFORM_DB=str(parent/'state/platform.sqlite3'))
import numpy as np
from visual_platform.services.research_history import read_events,source_graph_identity
sha=lambda raw:hashlib.sha256(raw).hexdigest()
def save(name,value):
    with (root/name).open('x',encoding='utf-8') as f:json.dump(value,f,indent=2,allow_nan=False)
assert source_graph_identity(m['source_graph_identity']['sourceRevisionId'])==m['source_graph_identity']
graph_path=Path(m['source_graph_reconciliation']['storage_uri']);raw=graph_path.read_bytes();assert sha(raw)==m['source_graph_identity']['contentSha256']
graph=json.loads(raw);graph=graph.get('graph',graph);nodes=graph['nodes'];assert len(nodes)==14000
ids={n['id']:n for n in nodes};index={n['ofecIndex']:n for n in nodes};roots=[i for i,n in index.items() if i==n['ofecParentIndex']];assert len(roots)==1
def branch(i):
    seen=set()
    while i!=roots[0]:
        assert i not in seen;seen.add(i);p=index[i]['ofecParentIndex']
        if p==roots[0]:return i
        i=p
    return i
sources=[n['functionPreview'].strip() for n in nodes];hashes=[sha(s.encode()) for s in sources]
cache=Path(m['historical_cache']);conn=sqlite3.connect(cache.as_uri()+'?mode=ro',uri=True)
rows=conn.execute('SELECT code_hash,dim,vector FROM embeddings').fetchall();conn.close()
vectors={h:np.frombuffer(v,dtype=np.float32).copy() for h,d,v in rows};assert all(h in vectors for h in hashes)
dimensions=sorted({len(vectors[h]) for h in hashes});assert dimensions==[256],dimensions
matrix=np.vstack([vectors[h] for h in hashes]);assert np.isfinite(matrix).all()
norms=np.linalg.norm(matrix,axis=1);assert np.max(abs(norms-1))<1e-4
with (root/'historical_vectors.private.npy').open('xb') as f:np.save(f,matrix)
save('historical_vector_order.json',dict(ids=[n['id'] for n in nodes],code_hashes=hashes,shape=list(matrix.shape),vector_bytes_sha256=sha(matrix.astype('<f4').tobytes()),cache_file_sha256=sha(cache.read_bytes())))
historical_meta=[dict(id=n['id'],sample_order=n['sampleOrder'],nbn_node_id=n['nbnNodeId'],ofec_index=n['ofecIndex'],parent_index=n['ofecParentIndex'],region_index=branch(n['ofecIndex']),archived_score=n.get('rawScore',n.get('score')),code_sha256=h,position=n.get('position'),x=n.get('x'),y=n.get('y'),z=n.get('z')) for n,h in zip(nodes,hashes)]
save('historical_metadata.json',historical_meta)
event_records=[];live_checks=[]
with zipfile.ZipFile(root/'original_tracking_events.local.zip','x',zipfile.ZIP_DEFLATED) as archive:
    for h in m['histories']:
        revision=h['revision_id'];directory=parent/'state/runs'/revision;events=read_events(directory)
        assert len(events)==h['event_count']
        assert sha(json.dumps(events,sort_keys=True,separators=(',',':'),ensure_ascii=False).encode())==h['canonical_events_sha256']
        live=json.load(urllib.request.urlopen('http://127.0.0.1:5015/api/revisions/'+revision+'/research-history',timeout=15))
        assert live['events']==events
        for e in events:
            path=directory/'research_history'/(e['id']+'.json');raw=path.read_bytes()
            restored=json.dumps(e,ensure_ascii=False,allow_nan=False,sort_keys=True).encode();assert raw==restored,'Original events cannot be reproduced byte-for-byte from export'
            name=revision+'/research_history/'+path.name;archive.writestr(name,raw)
            event_records.append(dict(revision_id=revision,event_id=e['id'],event_type=e['eventType'],timestamp_utc=e['timestampUtc'],archive_path=name,sha256=sha(raw),bytes=len(raw)))
        live_checks.append(dict(revision_id=revision,event_count=len(events),model_requests=sum(e['eventType']=='llm_request' for e in events),live_events_match_saved_export=True))
assert len(event_records)==205
for program in m['programs']:
    source=parent/program['source_file'];assert sha(source.read_text().encode())==program['code_sha256']
for diagnostic in m['historical_diagnostics']:
    c=diagnostic['candidate'];source=parent/'ael_parent_eligibility_20261031'/c['candidate_file']
    assert sha(source.read_text().strip().encode())==c['canonical_code_sha256']
    node=ids[c['node_id']];assert sha(node['functionPreview'].strip().encode())==c['canonical_code_sha256']
    assert branch(node['ofecIndex'])==c['region_index']
model=Path(m['embedding_model_path']);assets={p.name:sha(p.read_bytes()) for p in sorted(model.iterdir()) if p.is_file()}
info=json.loads((model/'DOWNLOAD_INFO.json').read_text());assert assets['pytorch_model.bin']==info['pytorch_model.bin_sha256']
save('ORIGINAL_EVENT_INDEX.json',dict(events=event_records,live_checks=live_checks,original_event_count=205,all_events_byte_reproducible_from_existing_exports=True,local_zip_sha256=sha((root/'original_tracking_events.local.zip').read_bytes())))
save('MODEL_ASSETS.json',dict(path=str(model),assets=assets,download_provenance=info))
save('INPUT_AUDIT.json',dict(passed=True,model_calls=0,candidate_executions=0,historical_nodes=len(nodes),unique_historical_sources=len(set(hashes)),embedding_dimensions=dimensions,cached_vector_count=len(vectors),all_14000_cache_keys_present=True,maximum_vector_norm_error=float(np.max(abs(norms-1))),source_cache_read_only=True,cache_sha256=sha(cache.read_bytes()),graph_file_sha256=sha(graph_path.read_bytes()),source_signature=m['source_graph_reconciliation']['structural_source_signature'],histories=live_checks,original_events=205,generated_sources_verified=24,historical_diagnostic_sources_verified=30,model_weights_sha256=assets['pytorch_model.bin'],free_disk_bytes=os.statvfs(root).f_bavail*os.statvfs(root).f_frsize))
print(json.dumps(dict(status='input_and_tracking_audit_passed',historical_vectors=matrix.shape,original_events=205,new_generations=0,candidate_executions=0)))
