"""Acceptance verification: real platform/evaluator, synthetic model replies only."""
import json,os,site,sys,unittest,uuid
from pathlib import Path
from unittest.mock import patch

def main():
    root=Path(__file__).resolve().parent;dep='/home/dyy/llm4ad_env/lib/python3.10/site-packages'
    site.addsitedir(dep);sys.path.remove(dep);sys.path.insert(sys.path.index(str(Path(sys.prefix)/'lib/python3.10/site-packages'))+1,dep);sys.path.insert(0,str(root))
    os.environ.update(VISUAL_PLATFORM_LOCAL_DATA_DIR=str(root/'state'),VISUAL_PLATFORM_DB=str(root/'state/platform.sqlite3'),CELERY_BROKER_URL='memory://')
    modules=['visual_platform.tests.test_research_history','visual_platform.tests.test_packing_history','visual_platform.tests.test_history_view']
    suite=unittest.TestSuite(unittest.defaultTestLoader.loadTestsFromName(name) for name in modules)
    tests=unittest.TextTestRunner(verbosity=2).run(suite);assert tests.wasSuccessful(),'History unit tests failed'
    from visual_platform.runtime.app_factory import create_app
    from visual_platform.config import RUNS_DIR
    from visual_platform.repositories.workspace_repository import create_workspace
    from visual_platform.repositories.revision_repository import upsert_revision
    from visual_platform.runtime.runner_entry import run_real
    from visual_platform.runtime.runner_modes import persist_sample_record
    from visual_platform.runtime.runner_llm import draw_sample_with_timeout
    from visual_platform.runtime.runner_task_loader import load_circle_packing_evaluation,evaluate_generated_function
    from visual_platform.runtime.packing_history import HistoryExecutor
    from visual_platform.services.research_history import capture_configuration,read_events,source_graph_identity
    from llm4ad.base.code import TextFunctionProgramConverter
    from collections import Counter
    app=create_app();revision='history-acceptance-'+uuid.uuid4().hex[:10];directory=RUNS_DIR/revision;log=directory/'log';log.mkdir(parents=True)
    workspace=create_workspace('History tracking verification',description='Synthetic acceptance checks only; excluded from research findings')
    manifest=json.loads((root/'nbn_prompt_comparison_gpu_20261031/draft_comparison_manifest.json').read_text());parents=[]
    for request in manifest['unique_requests']:
        node=request['parent'];item=dict(id=node['node_id'],nbnNodeId=node['nbn_node_id'])
        if item not in parents:parents.append(item)
        if len(parents)==2:break
    config=dict(revision_id=revision,workspace_id=workspace,mode='direct_ai',source_revision_id='circle-history-verified-20261028',source_graph_identity=source_graph_identity('circle-history-verified-20261028'),log_dir=str(log),prompt='Synthetic history verification: original prompt',selected_nodes=parents,reference_nodes=parents,initial_population_nodes=[],method=dict(max_sample_nums=4,timeout_seconds=4,use_celery=False,verificationOnly=True),llm=dict(model='synthetic-no-model-call',timeout=10,key='verification-secret'))
    upsert_revision(revision,workspace_id=workspace,mode='direct_ai',config=config,lifecycle_status='running')
    valid='def pack_circles(n):\n    import numpy as np\n    return np.array([[(i % 6 + .5) / 6, (i // 6 + .5) / 6, .49 / 6] for i in range(n)])\n'
    invalid='def pack_circles(n):\n    import numpy as np\n    return np.array([[.5,.5,.6] for _ in range(n)])\n'
    broken='def pack_circles(n):\n    raise ValueError("synthetic verification exception")\n'
    response=lambda code:'{Synthetic verification, not an experiment.}\n```python\n'+code+'```'
    from visual_platform.services import revision_generation_service
    original_complete=revision_generation_service.complete_run
    def complete_without_graph(*args,**kwargs):return original_complete(*args,**dict(kwargs,trigger_graph_build=False))
    with patch('visual_platform.runtime.runner_entry.llm_from_config',return_value=object()),patch('visual_platform.runtime.runner_entry.close_llm'),patch('visual_platform.runtime.runner_llm._draw_sample_with_timeout',side_effect=[response(valid),response(invalid),response(broken),'This synthetic reply has no program.']),patch.object(revision_generation_service,'complete_run',side_effect=complete_without_graph):
        run_real(config)
    with patch('visual_platform.runtime.runner_llm._draw_sample_with_timeout',side_effect=TimeoutError('synthetic generation timeout')):
        try:draw_sample_with_timeout(object(),'Synthetic timeout check',5)
        except TimeoutError:pass
        else:raise AssertionError('Expected synthetic timeout')
    # Exercise actual serialized Celery task execution through an in-memory
    # broker and worker; no shared Redis/broker or external model is used.
    from visual_platform.celery_worker import celery_app
    from celery.contrib.testing.worker import start_worker
    celery_app.conf.update(broker_url='memory://',result_backend='cache+memory://',task_always_eager=False,task_serializer='json',result_serializer='json',accept_content=['json'])
    task=load_circle_packing_evaluation()(timeout_seconds=4)
    with start_worker(celery_app,pool='solo',concurrency=1,perform_ping_check=False):
        for index,code in enumerate([valid,invalid],start=5):
            with patch('visual_platform.runtime.runner_llm._draw_sample_with_timeout',return_value=response(code)):
                reply=draw_sample_with_timeout(object(),'Synthetic queued evaluation '+str(index),5)
            function=TextFunctionProgramConverter.text_to_function(code)
            score,elapsed,program=evaluate_generated_function(task,function,task_kwargs={'timeout_seconds':4},use_celery=True,research_call_id=reply.research_call_id)
            persist_sample_record(log,index,dict(research_call_id=reply.research_call_id,selected_node_ids=[p['id'] for p in parents],program=program,score=score,synthetic=True))
    # Exercise the same asynchronous executor hook used by EoH/regional modes.
    from concurrent.futures import ThreadPoolExecutor
    with patch('visual_platform.runtime.runner_llm._draw_sample_with_timeout',return_value=response(valid)):
        reply=draw_sample_with_timeout(object(),'Synthetic asynchronous executor check',5)
    function=TextFunctionProgramConverter.text_to_function(valid);program=TextFunctionProgramConverter.function_to_program(function,task.template_program)
    with ThreadPoolExecutor(max_workers=1) as pool:
        score,elapsed=HistoryExecutor(pool,task,directory).submit(None,program).result(timeout=15)
    assert score is not None
    config['prompt']='Synthetic history verification: revised prompt';capture_configuration(directory,config)
    upsert_revision(revision,config=config,lifecycle_status='completed')
    result=app.test_client().get(f'/api/revisions/{revision}/research-history');assert result.status_code==200
    snapshot=result.json;events=snapshot['events'];counts=Counter(e['eventType'] for e in events)
    assert counts['llm_request']==8 and counts['llm_response']==7 and counts['llm_failure']==1,counts
    assert counts['strategy_changed']==1 and counts['reference_programs_recorded']==1
    assert snapshot['view']['summary']['attempts']==8
    assert all(r.get('recordedSource') and r.get('nbnNodeId') is not None for r in snapshot['view']['references'])
    assert 'verification-secret' not in json.dumps(snapshot)
    assert any(e['eventType']=='evaluation_exception' for e in events)
    assert any(e['eventType']=='evaluation_finished' and e['payload']['score']=={'nonfinite':'-inf'} for e in events),'Nonfinite outcome was lost'
    assert app.test_client().get('/api/research-history').status_code==200
    assert app.test_client().get('/static/research-history.html').status_code==200
    out=root/'history_feature_verification_20261031';out.mkdir(exist_ok=True)
    (out/'acceptance_snapshot.json').write_text(json.dumps(snapshot,indent=2))
    summary=dict(verificationOnly=True,revision=revision,workspace=workspace,unit_tests=tests.testsRun,events=dict(counts),view_summary=snapshot['view']['summary'],real_model_calls=0,actual_evaluator=True,celery_json_memory_broker_worker=True,asynchronous_executor=True,config_change_preserved=True,original_reference_source_preserved=True)
    (out/'acceptance_result.json').write_text(json.dumps(summary,indent=2));print(json.dumps(summary,indent=2),flush=True)

if __name__=='__main__':main()
