"""Record the actual allocation-wait outcome in the preparation-only history."""
import json,os,site,sys,urllib.request
from pathlib import Path
deployment=Path(__file__).resolve().parent;root=deployment/'ael_structural_prompt_comparison_20261031';sys.path.insert(0,str(root))
from ael_pilot_common import REVISION,save
dep='/home/dyy/llm4ad_env/lib/python3.10/site-packages';site.addsitedir(dep);sys.path.remove(dep)
private=str(Path(sys.prefix)/'lib/python3.10/site-packages');sys.path.insert(sys.path.index(private)+1,dep);sys.path.insert(0,str(deployment))
os.environ.update(VISUAL_PLATFORM_LOCAL_DATA_DIR=str(deployment/'state'),VISUAL_PLATFORM_DB=str(deployment/'state/platform.sqlite3'))
from visual_platform.runtime.database import init_db_schema
from visual_platform.repositories.revision_repository import upsert_revision
from visual_platform.services.research_history import append_event,read_events
from visual_platform.services.history_view import build_history_view
from visual_platform.config import RUNS_DIR
init_db_schema();p=json.load(sys.stdin);revision=REVISION+'-preparation';directory=RUNS_DIR/revision
assert not (root/'preparation_history_final.json').exists(),'Final preparation already recorded'
assert p['preparation_model_calls']==0
upsert_revision(revision,lifecycle_status='completed' if p['execution_started'] else 'waiting_for_resources')
append_event(directory,'preparation_allocation_outcome',p)
events=read_events(directory);view=build_history_view(events);assert view['summary']['attempts']==0
export=dict(schemaVersion=2,revisionId=revision,count=len(events),events=events,view=view)
save(root/'preparation_history_final.json',export)
live=json.load(urllib.request.urlopen('http://127.0.0.1:5015/api/revisions/'+revision+'/research-history',timeout=10))
assert live['events']==events and live['view']==view
save(root/'PREPARATION_HISTORY_VERIFICATION.json',dict(passed=True,events=len(events),attempts=0,live_api_equals_saved_export=True,execution_started=p['execution_started']))
print(json.dumps(dict(status='preparation_history_verified',events=len(events),execution_started=p['execution_started'])))
