import tempfile,unittest
from pathlib import Path
from unittest.mock import patch
from visual_platform.services.history_view import build_history_view
from visual_platform.services.research_history import append_event,read_events,capture_configuration,capture_references

class HistoryViewTests(unittest.TestCase):
    def test_linked_zero_score_and_generation_failure(self):
        with tempfile.TemporaryDirectory() as d:
            call=append_event(d,'llm_request',dict(prompt='<script>unsafe</script>'))
            append_event(d,'llm_response',dict(callId=call,response='code'))
            append_event(d,'evaluation_started',dict(callId=call,evaluationId='eval1',program='source'))
            append_event(d,'packing_output',dict(callId=call,evaluationId='eval1',circles=[[.5,.5,0]],shape=[1,3],finite=True))
            append_event(d,'evaluation_finished',dict(callId=call,evaluationId='eval1',score=0.0,status='valid_score',runtimeSeconds=.1))
            failed=append_event(d,'llm_request',dict(prompt='second'))
            append_event(d,'llm_failure',dict(callId=failed,error='timeout'))
            view=build_history_view(read_events(d))
            self.assertEqual(view['summary']['attempts'],2);self.assertEqual(view['summary']['scored'],1)
            self.assertEqual(view['summary']['failed'],1);self.assertEqual(view['summary']['bestScore'],0)
            row=next(a for a in view['attempts'] if a['id']==call)
            self.assertEqual(row['prompt'],'<script>unsafe</script>');self.assertEqual(row['packing']['circles'],[[.5,.5,0]])
    def test_shared_request_not_double_counted_and_undefined_fitness(self):
        with tempfile.TemporaryDirectory() as d:
            parent=dict(node_id='node1',nbn_node_id=7)
            manifest=dict(unique_requests=[dict(request_id='call1',parent=parent,prompt_profile='M2')],parent_pools={'a':[parent],'b':[parent]},analytical_slots=[dict(request_id='call1',strategy='a'),dict(request_id='call1',strategy='b')])
            append_event(d,'comparison_registered',dict(manifest=manifest))
            append_event(d,'llm_request',dict(callId='call1',request=dict(messages=[dict(role='user',content='exact')])) )
            append_event(d,'program_generated',dict(callId='call1',code='def function(): pass'))
            append_event(d,'trial_completed',dict(call_id='call1',status='timeout',score=None))
            view=build_history_view(read_events(d));self.assertEqual(len(view['attempts']),1);self.assertEqual(len(view['references']),1)
            self.assertEqual(view['attempts'][0]['strategies'],['a','b']);self.assertIsNone(view['summary']['bestScore'])
            self.assertIsNone(view['attempts'][0]['score']);self.assertIn('exact',view['attempts'][0]['prompt'])
    def test_configuration_and_source_snapshots_are_preserved(self):
        with tempfile.TemporaryDirectory() as d:
            node=dict(id='node1',nbnNodeId=22,functionPreview='def source(): return 1')
            cfg=dict(prompt='original',selected_nodes=[node],llm=dict(key='top-secret'))
            capture_configuration(d,cfg);capture_references(d,selected_nodes=[node]);capture_references(d,selected_nodes=[node])
            cfg['prompt']='changed';capture_configuration(d,cfg)
            node['functionPreview']='changed in memory'
            events=read_events(d);view=build_history_view(events)
            self.assertEqual(len([e for e in events if e['eventType']=='reference_programs_recorded']),1)
            self.assertEqual(view['references'][0]['recordedSource'],'def source(): return 1')
            self.assertEqual([e['kind'] for e in view['changes']],['configuration_recorded','strategy_changed'])
            self.assertEqual(view['changes'][0]['configuration']['llm']['key'],'[REDACTED]')
    def test_unlinked_evaluation_not_assigned_to_last_call(self):
        with tempfile.TemporaryDirectory() as d:
            append_event(d,'llm_request',dict(callId='call1',prompt='p'))
            append_event(d,'evaluation_finished',dict(callId=None,score=12,status='valid_score'))
            view=build_history_view(read_events(d));self.assertIsNone(view['attempts'][0]['score'])
            self.assertEqual(len(view['unlinkedEvents']),1)
    def test_normalized_samples_do_not_erase_failure_details(self):
        with tempfile.TemporaryDirectory() as d:
            append_event(d,'llm_request',dict(callId='invalid',prompt='p'))
            append_event(d,'evaluation_finished',dict(callId='invalid',score=float('-inf'),status='invalid_score'))
            append_event(d,'sample_recorded',dict(research_call_id='invalid',score=None,program='source'))
            append_event(d,'llm_request',dict(callId='exception',prompt='p'))
            append_event(d,'evaluation_exception',dict(callId='exception',error='Recorded exception'))
            append_event(d,'evaluation_finished',dict(callId='exception',score=None,status='no_score'))
            rows={a['id']:a for a in build_history_view(read_events(d))['attempts']}
            self.assertEqual(rows['invalid']['score'],{'nonfinite':'-inf'})
            self.assertEqual(rows['exception']['status'],'evaluation_exception')
    def test_api_discovery_and_projection(self):
        from flask import Flask
        from visual_platform.api.routes.research_history_routes import create_research_history_blueprint
        with tempfile.TemporaryDirectory() as d:
            root=Path(d);revision=root/'run1';revision.mkdir();(root/'empty').mkdir()
            append_event(revision,'llm_request',dict(prompt='p',callId='call1'))
            with patch('visual_platform.api.routes.research_history_routes.RUNS_DIR',root):
                app=Flask(__name__);app.register_blueprint(create_research_history_blueprint());client=app.test_client()
                self.assertEqual(len(client.get('/api/research-history').json['runs']),1)
                result=client.get('/api/revisions/run1/research-history').json
                self.assertEqual(result['schemaVersion'],2);self.assertEqual(result['view']['summary']['attempts'],1)
                self.assertEqual(client.get('/api/revisions/missing/research-history').status_code,404)

if __name__=='__main__':unittest.main()
