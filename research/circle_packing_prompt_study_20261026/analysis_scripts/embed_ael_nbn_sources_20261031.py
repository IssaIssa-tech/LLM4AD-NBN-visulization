"""Offline CPU embeddings only; validate anchors before mixing with cached history."""
import hashlib,json,os,sqlite3,sys,time
from pathlib import Path
root=Path(__file__).resolve().parent;assert root.name=='ael_nbn_analysis_20261031'
m=json.loads((root/'INPUT_MANIFEST.json').read_text());assert not (root/'EMBEDDING_RESULT.json').exists()
os.environ.update(CUDA_VISIBLE_DEVICES='',HF_HUB_OFFLINE='1',TRANSFORMERS_OFFLINE='1',HF_HOME=str(root/'private_hf_cache'),HF_MODULES_CACHE=str(root/'private_hf_modules'),TOKENIZERS_PARALLELISM='false',OMP_NUM_THREADS='2',MKL_NUM_THREADS='2')
import numpy as np,torch,transformers
from transformers import AutoConfig,AutoTokenizer,AutoModel
torch.set_num_threads(2);torch.set_num_interop_threads(1)
sha=lambda raw:hashlib.sha256(raw).hexdigest()
def save(name,value):
    with (root/name).open('x',encoding='utf-8') as f:json.dump(value,f,indent=2,allow_nan=False)
modelpath=Path(m['embedding_model_path']);assets=json.loads((root/'MODEL_ASSETS.json').read_text())
for name,digest in assets['assets'].items():assert sha((modelpath/name).read_bytes())==digest
cfg=AutoConfig.from_pretrained(str(modelpath),trust_remote_code=True,local_files_only=True)
if not hasattr(cfg,'is_decoder'):cfg.is_decoder=False
tokenizer=AutoTokenizer.from_pretrained(str(modelpath),trust_remote_code=True,local_files_only=True,use_fast=False)
model=AutoModel.from_pretrained(str(modelpath),trust_remote_code=True,local_files_only=True,config=cfg).to('cpu');model.eval()
def embed(source):
    inputs=tokenizer(source,return_tensors='pt',truncation=True,max_length=1024)
    with torch.inference_mode():
        values=model(**inputs)
        # This checkpoint returns a normalized [batch,256] tensor directly.
        assert isinstance(values,torch.Tensor) and list(values.shape)==[1,256]
        values=torch.nn.functional.normalize(values,p=2,dim=1)
    return values[0].cpu().numpy().astype(np.float32)
graph=json.loads(Path(m['source_graph_reconciliation']['storage_uri']).read_text());graph=graph.get('graph',graph)
nodes=graph['nodes'];vectors=np.load(root/'historical_vectors.private.npy');assert vectors.shape==(14000,256)
by_sample={n['sampleOrder']:i for i,n in enumerate(nodes)}
anchor_samples=[1,947,3445,7918,9180,12852,13793,14000];checks=[];computed=[];cached=[]
start=time.perf_counter()
for sample in anchor_samples:
    i=by_sample[sample];source=nodes[i]['functionPreview'].strip();v=embed(source);old=vectors[i]
    cosine=float(np.dot(v.astype(float),old.astype(float))/(np.linalg.norm(v.astype(float))*np.linalg.norm(old.astype(float))))
    error=float(np.max(np.abs(v-old)));passed=error<=5e-4 and 1-cosine<=1e-6
    checks.append(dict(sample_order=sample,node_id=nodes[i]['id'],source_sha256=sha(source.encode()),maximum_abs_error=error,cosine_similarity=cosine,passed=passed));computed.append(v);cached.append(old)
    print('ANCHOR',sample,'max_abs_error',error,'cosine',cosine,flush=True)
save('ANCHOR_CHECKS.json',dict(passed=all(c['passed'] for c in checks),checks=checks,maximum_abs_error_limit=5e-4,cosine_distance_limit=1e-6,scope='Eight declared historical source checks; does not certify semantic quality of CodeT5'))
with (root/'anchor_validation_vectors.npz').open('xb') as f:np.savez_compressed(f,recomputed=np.stack(computed),cached=np.stack(cached),sample_orders=np.array(anchor_samples))
assert all(c['passed'] for c in checks),'Historical cache/model incompatibility; refusing mixed-coordinate analysis'
conn=sqlite3.connect(Path(m['historical_cache']).as_uri()+'?mode=ro',uri=True);existing={h:np.frombuffer(v,dtype=np.float32).copy() for h,d,v in conn.execute('SELECT code_hash,dim,vector FROM embeddings')};conn.close()
unique={};truncation=[];new_count=0;cache_hits=0
for row in m['programs']:
    source=(root.parent/row['source_file']).read_text().strip();digest=sha(source.encode());assert digest==row['embedding_source_sha256']
    tokens=tokenizer(source,add_special_tokens=True,truncation=False)['input_ids']
    clipped=tokenizer(source,add_special_tokens=True,truncation=True,max_length=1024)['input_ids']
    truncation.append(dict(program_id=row['id'],source_sha256=digest,source_token_count=len(tokens),used_token_count=len(clipped),truncated=len(tokens)>1024,truncated_token_sequence_sha256=sha(np.array(clipped,dtype='<i8').tobytes())))
    if digest in unique:continue
    if digest in existing:unique[digest]=existing[digest];cache_hits+=1
    else:unique[digest]=embed(source);new_count+=1
    print('PROGRAM EMBEDDING',len(unique),'source hashes',flush=True)
matrix=np.vstack([unique[p['embedding_source_sha256']] for p in m['programs']]);assert matrix.shape==(24,256) and np.isfinite(matrix).all()
with (root/'generated_embeddings.npz').open('xb') as f:np.savez_compressed(f,vectors=matrix,program_ids=np.array([p['id'] for p in m['programs']]),source_sha256=np.array([p['embedding_source_sha256'] for p in m['programs']]))
save('TRUNCATION_AUDIT.json',dict(max_tokens=1024,tokenizer='CodeT5+ slow tokenizer; original stripped-source policy',programs=truncation,truncated_record_count=sum(r['truncated'] for r in truncation),interpretation='Changes outside the used token prefix may be invisible; distance or projection is not functional equivalence'))
source_cache_sha=sha(Path(m['historical_cache']).read_bytes());assert source_cache_sha==json.loads((root/'INPUT_AUDIT.json').read_text())['cache_sha256']
save('EMBEDDING_RESULT.json',dict(status='completed',model_calls_for_generation=0,candidate_executions=0,embedding_forward_passes=len(anchor_samples)+new_count,unique_generated_sources=len(unique),generated_records=24,cached_generated_unique_sources=cache_hits,new_generated_unique_sources=new_count,model=assets['download_provenance'],model_assets_sha256=sha((root/'MODEL_ASSETS.json').read_bytes()),python=sys.version,numpy=np.__version__,torch=torch.__version__,transformers=transformers.__version__,device='cpu',torch_threads=2,max_length=1024,anchors_passed=True,generated_vector_shape=list(matrix.shape),vectors_sha256=sha(matrix.astype('<f4').tobytes()),source_cache_unchanged=True,elapsed_seconds=time.perf_counter()-start))
print('EMBEDDING COMPLETED',new_count,'new unique vectors',flush=True)
