"""Synthetic deployment verification; never an experiment or an LLM request."""
import json,uuid
import sys,platform
from pathlib import Path
import numpy as np
from unittest.mock import patch
from visual_platform.config import RUNS_DIR
from visual_platform.runtime.app_factory import create_app
from visual_platform.runtime.runner_llm import draw_sample_with_timeout
from visual_platform.runtime.runner_task_loader import load_circle_packing_evaluation,evaluate_generated_function
from visual_platform.services.research_history import append_event,capture_configuration,read_events
from llm4ad.base.code import TextFunctionProgramConverter

def main():
    revision='history-smoke-'+uuid.uuid4().hex[:12];directory=RUNS_DIR/revision;directory.mkdir(parents=True)
    capture_configuration(directory,dict(revision_id=revision,mode='synthetic_history_verification',selected_nodes=[dict(id='synthetic-parent',nbnNodeId='synthetic-nbn-node')],prompt='Synthetic smoke test only'))
    source='''def pack_circles(n):
    import numpy as np
    return np.array([[(i % 6 + .5) / 6, (i // 6 + .5) / 6, .49 / 6] for i in range(n)])
'''
    with patch.dict('os.environ',{'VP_RESEARCH_HISTORY_DIR':str(directory)}):
        with patch('visual_platform.runtime.runner_llm._draw_sample_with_timeout',return_value=source):
            response=draw_sample_with_timeout(object(),'Synthetic prompt; no model call',10)
        function=TextFunctionProgramConverter.text_to_function(source)
        task=load_circle_packing_evaluation()(timeout_seconds=10)
        score,elapsed,program=evaluate_generated_function(task,function,research_call_id=response.research_call_id)
        assert score is not None and score>0
        append_event(directory,'sample_recorded',dict(id='synthetic-sample',research_call_id=response.research_call_id,score=score,program=program,synthetic=True))
    events=read_events(directory)
    assert len([e for e in events if e['eventType']=='packing_output'])==1
    assert all(e['payload'].get('callId')==response.research_call_id for e in events if e['eventType'] in ('evaluation_started','evaluation_finished','packing_output'))
    app=create_app();client=app.test_client()
    result=client.get(f'/api/revisions/{revision}/research-history');assert result.status_code==200
    assert result.json['count']==len(events)
    assert client.get('/static/research-history.html').status_code==200
    summary=dict(synthetic=True,revision=revision,events=len(events),score=score,packing_outputs=1,history_api=200,history_page=200,model_calls=0,environment=dict(python=sys.version,numpy=np.__version__,host=platform.node()))
    (Path(__file__).resolve().parent/('verification-'+revision+'.json')).write_text(json.dumps(summary,indent=2))
    print(json.dumps(summary,indent=2))

if __name__=='__main__':main()
