import pickle,tempfile,unittest
from pathlib import Path
import numpy as np
from concurrent.futures import ThreadPoolExecutor
from unittest.mock import patch
from visual_platform.runtime.packing_history import HistoryResponse,PackingHistoryProxy,start_evaluation,finish_evaluation
from visual_platform.services.research_history import read_events

class FakeTask:
    exec_code=True
    fork_proc='auto'
    safe_evaluate=False
    use_numba_accelerate=False
    use_protected_div=False
    random_seed=None
    def evaluate_program(self,program,callback,**kwargs):
        circles=np.asarray(callback(26),dtype=float)
        if not np.isfinite(circles).all():return float('-inf')
        return float(circles[:,2].sum())

class PackingHistoryTests(unittest.TestCase):
    def test_async_executor_carries_call_without_global_guessing(self):
        from visual_platform.runtime.packing_history import HistoryExecutor
        from visual_platform.services.research_history import current_call_id
        with tempfile.TemporaryDirectory() as d:
            with ThreadPoolExecutor(max_workers=2) as pool:
                wrapper=HistoryExecutor(pool,FakeTask(),d)
                current_call_id.set('asynchronous-call')
                future=wrapper.submit(None,'def pack_circles(n):\n    return [[.5,.5,0] for _ in range(n)]\n')
                current_call_id.set(None)
                score,elapsed=future.result(timeout=15)
            self.assertEqual(score,0)
            self.assertTrue(all(e['payload']['callId']=='asynchronous-call' for e in read_events(d)))
    def test_single_execution_coordinates_and_links(self):
        with tempfile.TemporaryDirectory() as d:
            context=start_evaluation(d,'source','call1');task=PackingHistoryProxy(FakeTask(),context);calls=[]
            def packing(n):calls.append(n);return [[.5,.5,0] for _ in range(n)]
            score=task.evaluate_program('evaluated source',packing)
            finish_evaluation(context,score,.1);events=read_events(d)
            self.assertEqual(calls,[26]);self.assertEqual(score,0)
            captured=next(e for e in events if e['eventType']=='packing_output')['payload']
            self.assertEqual(captured['shape'],[26,3]);self.assertEqual(len(captured['circles']),26)
            self.assertTrue(all(e['payload']['evaluationId']==context['evaluation_id'] for e in events))
            self.assertTrue(all(e['payload']['callId']=='call1' for e in events))
    def test_nonfinite_and_exception_preserved(self):
        with tempfile.TemporaryDirectory() as d:
            context=start_evaluation(d,'bad source','call2');task=PackingHistoryProxy(FakeTask(),context)
            score=task.evaluate_program('source',lambda n:[[.5,.5,float('nan')]]*26)
            finish_evaluation(context,score,.1)
            def fail(n):raise ValueError('broken')
            with self.assertRaises(ValueError):task.evaluate_program('source',fail)
            events=read_events(d)
            self.assertTrue(any(e['eventType']=='evaluation_exception' for e in events))
            capture=next(e for e in events if e['eventType']=='packing_output')['payload']
            self.assertFalse(capture['finite']);self.assertEqual(capture['circles'][0][2],{'nonfinite':'nan'})
    def test_spawn_pickle_metadata(self):
        with tempfile.TemporaryDirectory() as d:
            task=PackingHistoryProxy(FakeTask(),start_evaluation(d,'source','call3'))
            recovered=pickle.loads(pickle.dumps(task));self.assertEqual(recovered.context['call_id'],'call3')
        reply=pickle.loads(pickle.dumps(HistoryResponse('code','call4')))
        self.assertEqual(str(reply),'code');self.assertEqual(reply.research_call_id,'call4')

if __name__=='__main__':unittest.main()
