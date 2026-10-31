"""Preserve the prepared follow-up in platform history without inventing a run."""
import json,os,site,sys
from pathlib import Path
deployment=Path(__file__).resolve().parent;root=deployment/'ael_structural_prompt_comparison_20261031'
sys.path.insert(0,str(root))
from ael_pilot_common import NAME,REVISION,sha,load,save
dependency='/home/dyy/llm4ad_env/lib/python3.10/site-packages';site.addsitedir(dependency);sys.path.remove(dependency)
private=str(Path(sys.prefix)/'lib/python3.10/site-packages');sys.path.insert(sys.path.index(private)+1,dependency);sys.path.insert(0,str(deployment))
os.environ.update(VISUAL_PLATFORM_LOCAL_DATA_DIR=str(deployment/'state'),VISUAL_PLATFORM_DB=str(deployment/'state/platform.sqlite3'))
from visual_platform.runtime.database import init_db_schema
from visual_platform.repositories.revision_repository import get_revision_record,upsert_revision
from visual_platform.services.research_history import append_event,capture_configuration,capture_references,source_graph_identity,read_events
from visual_platform.services.history_view import build_history_view
from visual_platform.config import RUNS_DIR
init_db_schema();m=load(root/'manifest.json');revision=REVISION+'-preparation'
assert not get_revision_record(revision),'Existing preparation history; inspect rather than duplicate'
identity=source_graph_identity(m['source_platform_revision']);assert identity==m['source_graph_identity']
refs=list({p['id']:p for c in m['chains'] for p in c['parents']}.values());directory=RUNS_DIR/revision;directory.mkdir()
source=get_revision_record(m['source_platform_revision'])
config=dict(revision_id=revision,workspace_id=source['workspace_id'],mode='prepared_prompt_comparison',source_revision_id=m['source_platform_revision'],source_graph_identity=identity,selected_nodes=refs,method=m,planned_requests=[dict(callId=c['crossover_id'],request=load(root/c['crossover_id']/'api_payload.json'),status='planned_not_requested') for c in m['chains']],mutation_template=(root/'mutation_template.txt').read_text(),prompt='Preparation only; no new model calls or candidate evaluations',execution_revision_id=REVISION)
upsert_revision(revision,workspace_id=source['workspace_id'],mode=config['mode'],config=config,lifecycle_status='waiting_for_resources')
capture_configuration(directory,config);capture_references(directory,selected_nodes=refs)
append_event(directory,'comparison_registered',dict(manifest=dict(previous_condition=m['previous_condition'],amendment=m['amendment'],stopping_rule=m['stopping_rule'])))
append_event(directory,'pre_registration_engineering_amendment',m['pre_registration_engineering_amendment'])
append_event(directory,'generation_deferred',dict(reason='GPU allocation guard unmet before model startup; preparation is not an executed research condition',modelCalls=0,manifestSha256=sha((root/'manifest.json').read_bytes()),executionRevisionId=REVISION))
events=read_events(directory);view=build_history_view(events);assert view['summary']['attempts']==0
save(root/'preparation_history.json',dict(schemaVersion=2,revisionId=revision,count=len(events),events=events,view=view))
print(json.dumps(dict(revision=revision,event_count=len(events),actual_model_calls=0,planned_historical_pairs=6)))
