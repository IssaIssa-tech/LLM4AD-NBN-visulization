import json,math,tempfile,unittest
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path
from unittest.mock import patch
from visual_platform.services.research_history import append_event,read_events,capture_configuration

class HistoryTests(unittest.TestCase):
    def test_source_graph_identity_detects_modified_file(self):
        import hashlib
        from visual_platform.services.research_history import source_graph_identity
        with tempfile.TemporaryDirectory() as d:
            path=Path(d)/'graph.json';path.write_text('{}')
            record=dict(artifact_id='graph1',storage_uri=str(path),content_digest=hashlib.sha256(path.read_bytes()).hexdigest(),input_digest='input1',metadata={'nbnMode':'hnsw_static'})
            with patch('visual_platform.repositories.artifact_repository.list_artifacts_for_revision',return_value=[record]):
                identity=source_graph_identity('source1')
                self.assertEqual(identity['artifactId'],'graph1')
                path.write_text('{"changed":true}')
                with self.assertRaises(ValueError):source_graph_identity('source1')
    def test_concurrent_events_and_no_overwrite(self):
        with tempfile.TemporaryDirectory() as d:
            with ThreadPoolExecutor(max_workers=4) as pool:
                list(pool.map(lambda i:append_event(d,'attempt',{'i':i}),range(30)))
            self.assertEqual(len(read_events(d)),30)
            append_event(d,'first',{},event_id='fixed')
            with self.assertRaises(FileExistsError):append_event(d,'second',{},event_id='fixed')
            self.assertEqual([e for e in read_events(d) if e['id']=='fixed'][0]['eventType'],'first')
    def test_config_changes_secret_redaction_and_nonfinite(self):
        with tempfile.TemporaryDirectory() as d:
            config={'prompt':'first','selected_nodes':[{'id':'node1','ofecIndex':42}], 'llm':{'key':'secret'}}
            capture_configuration(d,config);capture_configuration(d,config)
            config['prompt']='revised';capture_configuration(d,config)
            append_event(d,'sample_recorded',{'score':float('-inf')})
            events=read_events(d)
            self.assertEqual(len(events),3)
            self.assertEqual(events[1]['eventType'],'strategy_changed')
            self.assertEqual(events[0]['payload']['configuration']['selected_nodes'][0]['ofecIndex'],42)
            self.assertNotIn('secret',json.dumps(events))
            self.assertEqual(events[2]['payload']['score'],{'nonfinite':'-inf'})
    def test_api_and_missing_revision(self):
        from flask import Flask
        from visual_platform.api.routes.research_history_routes import create_research_history_blueprint
        with tempfile.TemporaryDirectory() as d:
            root=Path(d);revision=root/'test-run';revision.mkdir();append_event(revision,'test',{'prompt':'<script>unsafe</script>'})
            with patch('visual_platform.api.routes.research_history_routes.RUNS_DIR',root):
                app=Flask(__name__);app.register_blueprint(create_research_history_blueprint());client=app.test_client()
                self.assertEqual(client.get('/api/revisions/missing/research-history').status_code,404)
                response=client.get('/api/revisions/test-run/research-history')
                self.assertEqual(response.status_code,200);self.assertEqual(response.json['count'],1)
    def test_llm_success_and_failure_are_linked(self):
        from visual_platform.runtime.runner_llm import draw_sample_with_timeout
        with tempfile.TemporaryDirectory() as d, patch.dict('os.environ',{'VP_RESEARCH_HISTORY_DIR':d}):
            with patch('visual_platform.runtime.runner_llm._draw_sample_with_timeout',return_value='raw code'):
                self.assertEqual(draw_sample_with_timeout(object(),'prompt one',10),'raw code')
            with patch('visual_platform.runtime.runner_llm._draw_sample_with_timeout',side_effect=TimeoutError('test timeout')):
                with self.assertRaises(TimeoutError):draw_sample_with_timeout(object(),'prompt two',10)
            events=read_events(d)
            requests={e['id'] for e in events if e['eventType']=='llm_request'}
            responses=[e for e in events if e['eventType'] in ('llm_response','llm_failure')]
            self.assertEqual(len(requests),2);self.assertEqual(len(responses),2)
            self.assertTrue(all(e['payload']['callId'] in requests for e in responses))

if __name__=='__main__':unittest.main()
