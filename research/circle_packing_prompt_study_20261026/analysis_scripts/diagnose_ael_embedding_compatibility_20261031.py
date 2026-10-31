"""Diagnose historical representation settings using two saved historical sources."""
import hashlib,json,os
from pathlib import Path
root=Path(__file__).resolve().parent;assert root.name=='ael_nbn_analysis_20261031'
os.environ.update(CUDA_VISIBLE_DEVICES='',HF_HUB_OFFLINE='1',TRANSFORMERS_OFFLINE='1',HF_HOME=str(root/'private_hf_cache'),HF_MODULES_CACHE=str(root/'private_hf_modules'),TOKENIZERS_PARALLELISM='false',OMP_NUM_THREADS='2')
import numpy as np,torch
from transformers import AutoConfig,AutoTokenizer,AutoModel
torch.set_num_threads(2);torch.set_num_interop_threads(1)
m=json.loads((root/'INPUT_MANIFEST.json').read_text());path=m['embedding_model_path']
cfg=AutoConfig.from_pretrained(path,trust_remote_code=True,local_files_only=True);cfg.is_decoder=False
model=AutoModel.from_pretrained(path,trust_remote_code=True,local_files_only=True,config=cfg).to('cpu').eval()
g=json.loads(Path(m['source_graph_reconciliation']['storage_uri']).read_text());g=g.get('graph',g);nodes=g['nodes'];by_sample={n['sampleOrder']:i for i,n in enumerate(nodes)}
old=np.load(root/'historical_vectors.private.npy');results=[]
for fast in [False,True]:
    tok=AutoTokenizer.from_pretrained(path,local_files_only=True,trust_remote_code=True,use_fast=fast)
    for length in [256,512,1024,2048]:
        for sample in [1,9180]:
            i=by_sample[sample];source=nodes[i]['functionPreview'].strip();inp=tok(source,return_tensors='pt',truncation=True,max_length=length)
            with torch.inference_mode():v=torch.nn.functional.normalize(model(**inp),p=2,dim=1)[0].numpy()
            error=float(np.max(abs(v-old[i])));cos=float(v.astype(float)@old[i].astype(float)/(np.linalg.norm(v.astype(float))*np.linalg.norm(old[i].astype(float))))
            results.append(dict(use_fast=fast,max_length=length,sample_order=sample,used_tokens=int(inp['input_ids'].shape[-1]),maximum_abs_error=error,cosine_similarity=cos,passed=error<=5e-4 and 1-cos<=1e-6))
            print(fast,length,sample,error,cos,flush=True)
passing=[dict(use_fast=fast,max_length=length) for fast in [False,True] for length in [256,512,1024,2048] if all(r['passed'] for r in results if r['use_fast']==fast and r['max_length']==length)]
with (root/'REPRESENTATION_DIAGNOSTIC.json').open('x') as f:json.dump(dict(results=results,settings_matching_both_anchors=passing,generation_calls=0,candidate_executions=0),f,indent=2)
assert passing,'No tested setting reproduces both historical anchors'
