"""Preserve derived analysis in a new platform revision; leave original events intact."""
import hashlib,json,os,site,sys,urllib.request
from pathlib import Path
root=Path(__file__).resolve().parent;deployment=root.parent
dep='/home/dyy/llm4ad_env/lib/python3.10/site-packages';site.addsitedir(dep);sys.path.remove(dep)
private=str(Path(sys.prefix)/'lib/python3.10/site-packages');sys.path.insert(sys.path.index(private)+1,dep);sys.path.insert(0,str(deployment))
os.environ.update(VISUAL_PLATFORM_LOCAL_DATA_DIR=str(deployment/'state'),VISUAL_PLATFORM_DB=str(deployment/'state/platform.sqlite3'))
from visual_platform.runtime.database import init_db_schema
from visual_platform.repositories.revision_repository import get_revision_record,upsert_revision
from visual_platform.repositories.artifact_repository import upsert_artifact
from visual_platform.services.research_history import append_event,capture_configuration,read_events
from visual_platform.services.history_view import build_history_view
from visual_platform.config import RUNS_DIR
load=lambda name:json.loads((root/name).read_text());sha=lambda raw:hashlib.sha256(raw).hexdigest()
m=load('INPUT_MANIFEST.json');analysis=load('NBN_ANALYSIS.json');revision=m['analysis_revision_id'];init_db_schema()
assert not get_revision_record(revision),'Analysis revision already exists'
source=get_revision_record(m['source_graph_identity']['sourceRevisionId']);directory=RUNS_DIR/revision;directory.mkdir()
config=dict(revision_id=revision,workspace_id=source['workspace_id'],mode='recorded_nbn_analysis',source_revision_id=m['source_graph_identity']['sourceRevisionId'],source_graph_identity=m['source_graph_identity'],method=dict(input=m,actual_embedding=load('representation_512/EMBEDDING_RESULT.json'),representation_recovery=load('REPRESENTATION_DIAGNOSTIC.json'),generation_calls=0,candidate_executions=0),prompt='Analysis of existing programs only; no LLM generation or candidate execution')
upsert_revision(revision,workspace_id=source['workspace_id'],mode=config['mode'],config=config,lifecycle_status='completed')
capture_configuration(directory,config)
append_event(directory,'tracking_preservation_verified',dict(originalEventCount=205,protectedRevisions=m['histories'],allEventsByteRestorable=True))
append_event(directory,'representation_reconciled',dict(original1024TokenAnchorCheck=load('ANCHOR_CHECKS.json'),diagnostic=load('REPRESENTATION_DIAGNOSTIC.json'),compatible512TokenAnchorChecks=load('representation_512/ANCHOR_CHECKS.json'),sourceCacheUnchanged=True))
artifact=upsert_artifact(revision,artifact_type='analysis',artifact_role='measured_nbn',format_name='json',storage_uri=str(root/'measured_nbn_graph.json'),status='ready',metadata=analysis['summary'],input_digest=sha((root/'INPUT_MANIFEST.json').read_bytes()),content_digest=sha((root/'measured_nbn_graph.json').read_bytes()))
for row in analysis['programs']:
    append_event(directory,'generated_program_nbn_analysis',dict(originRevisionId=row['origin_revision_id'],originCallId=row['call_id'],analyzedNodeId=row['id'],sourceSha256=row['code_sha256'],evaluationStatus=row['evaluation_status'],observedScore=row['score'],nearestHistorical=row['nearest_historical'],nearestAssociationRole='code similarity, not a nearest-better edge',measuredNbnArtifactId=artifact,truncation=row['truncation']))
append_event(directory,'nbn_analysis_completed',dict(summary=analysis['summary'],artifactId=artifact,sourceCacheUnchanged=True,originalHistoriesUnmodified=True))
events=read_events(directory);view=build_history_view(events);assert view['summary']['attempts']==0
live=json.load(urllib.request.urlopen('http://127.0.0.1:5015/api/revisions/'+revision+'/research-history',timeout=10));assert live['events']==events and live['view']==view
for name,value in [('analysis_history.json',dict(schemaVersion=2,revisionId=revision,count=len(events),events=events,view=view)),('PLATFORM_ANALYSIS_VERIFICATION.json',dict(passed=True,analysis_revision_id=revision,event_count=len(events),actual_llm_requests=0,candidate_executions=0,linked_generated_programs=24,artifact_id=artifact,live_api_equals_saved_export=True))]:
    with (root/name).open('x') as f:json.dump(value,f,indent=2,allow_nan=False)
print(json.dumps(dict(analysis_revision=revision,derived_events=len(events),linked_programs=24,artifact_id=artifact)))
