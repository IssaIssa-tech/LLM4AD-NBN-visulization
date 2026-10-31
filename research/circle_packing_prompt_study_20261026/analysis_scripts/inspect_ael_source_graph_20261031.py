"""Read-only reconciliation of archive export and live graph artifact."""
import hashlib,json,os,site,sys
from pathlib import Path
root=Path(__file__).resolve().parent
dep='/home/dyy/llm4ad_env/lib/python3.10/site-packages';site.addsitedir(dep);sys.path.remove(dep);sys.path.insert(sys.path.index(str(Path(sys.prefix)/'lib/python3.10/site-packages'))+1,dep);sys.path.insert(0,str(root))
os.environ.update(VISUAL_PLATFORM_LOCAL_DATA_DIR=str(root/'state'),VISUAL_PLATFORM_DB=str(root/'state/platform.sqlite3'))
from visual_platform.services.research_history import source_graph_identity
from visual_platform.repositories.artifact_repository import list_artifacts_for_revision
identity=source_graph_identity('circle-history-verified-20261028');records=list_artifacts_for_revision('circle-history-verified-20261028',artifact_type='graph',artifact_role='full',status='ready')
record=next(r for r in records if r['artifact_id']==identity['artifactId'])
path=Path(record['storage_uri']);payload=json.loads(path.read_text());graph=payload.get('graph',payload)
print(json.dumps(dict(identity=identity,path=str(path),payload_keys=list(payload),graph_keys=list(graph),nodes=len(graph.get('nodes',[]))),indent=2))
nodes=graph['nodes'];sha=lambda data:hashlib.sha256(data).hexdigest()
rows=sorted([dict(id=n['id'],nbnNodeId=n.get('nbnNodeId'),ofecIndex=n.get('ofecIndex'),ofecParentIndex=n.get('ofecParentIndex'),codeSha256=sha(n.get('functionPreview','').strip().encode())) for n in nodes],key=lambda r:r['id'])
signature=sha(json.dumps(rows,sort_keys=True,separators=(',',':')).encode())
print('SEMANTIC_SIGNATURE',signature)
(root/'ael_parent_eligibility_20261031/source_graph_reconciliation.json').write_text(json.dumps(dict(identity=identity,storage_uri=str(path),structural_source_signature=signature,signature_fields=['id','nbnNodeId','ofecIndex','ofecParentIndex','codeSha256'],node_count=len(nodes)),indent=2))
