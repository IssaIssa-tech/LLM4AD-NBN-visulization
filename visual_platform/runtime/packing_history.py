"""Capture the actual callable output inside the existing isolated evaluator."""
from __future__ import annotations
import hashlib
import math
import uuid
from visual_platform.services.research_history import append_event

class HistoryResponse(str):
    def __new__(cls,value,call_id=None):
        obj=super().__new__(cls,value);obj.research_call_id=call_id;return obj

class PackingHistoryProxy:
    def __init__(self,task,context):self.task=task;self.context=context
    def __getattr__(self,name):return getattr(object.__getattribute__(self,'task'),name)
    def evaluate_program(self,program_str,callable_func,**kwargs):
        import numpy as np
        context=self.context;directory=context['revision_dir']
        def capture(*args,**call_kwargs):
            output=callable_func(*args,**call_kwargs)
            try:
                array=np.asarray(output,dtype=np.float64)
                payload=dict(callId=context.get('call_id'),evaluationId=context['evaluation_id'],shape=list(array.shape),circles=array.tolist(),finite=bool(np.isfinite(array).all()),programSha256=hashlib.sha256(program_str.encode()).hexdigest(),provenance='Actual evaluation output; not an additional execution')
                append_event(directory,'packing_output',payload)
            except (ValueError,TypeError) as error:
                append_event(directory,'packing_capture_failed',dict(callId=context.get('call_id'),evaluationId=context['evaluation_id'],error=str(error)))
            return output
        try:return self.task.evaluate_program(program_str,capture,**kwargs)
        except Exception as error:
            append_event(directory,'evaluation_exception',dict(callId=context.get('call_id'),evaluationId=context['evaluation_id'],errorType=type(error).__name__,error=str(error)))
            raise

def start_evaluation(directory,program,call_id=None):
    context=dict(revision_dir=str(directory),call_id=call_id,evaluation_id=uuid.uuid4().hex)
    append_event(directory,'evaluation_started',dict(callId=call_id,evaluationId=context['evaluation_id'],program=program,programSha256=hashlib.sha256(program.encode()).hexdigest()))
    return context

def finish_evaluation(context,score,elapsed):
    status='valid_score' if isinstance(score,(int,float)) and math.isfinite(score) else 'invalid_score' if isinstance(score,(int,float)) else 'no_score'
    append_event(context['revision_dir'],'evaluation_finished',dict(callId=context.get('call_id'),evaluationId=context['evaluation_id'],score=score,runtimeSeconds=elapsed,status=status,targetScore=2.6360,targetReached=status=='valid_score' and score>=2.6360,verifier='Existing platform evaluator; official challenge verifier equivalence unverified'))

def evaluate_with_history(task,program,context):
    from visual_platform.runtime.runner_task_loader import platform_secure_evaluator
    evaluator=platform_secure_evaluator(PackingHistoryProxy(task,context))
    score,elapsed=evaluator.evaluate_program_record_time(program)
    finish_evaluation(context,score,elapsed)
    return score,elapsed

class HistoryExecutor:
    """Carry the sampling-thread call id explicitly into each evaluator job."""
    def __init__(self,delegate,task,revision_dir):
        self.delegate=delegate;self.task=task;self.revision_dir=str(revision_dir)
    def submit(self,func,program,*args,**kwargs):
        from visual_platform.services.research_history import current_call_id
        context=start_evaluation(self.revision_dir,str(program),current_call_id.get())
        # Existing Celery adapter transports context explicitly to its worker.
        if hasattr(self.delegate,'submit_with_history'):
            return self.delegate.submit_with_history(program,context)
        return self.delegate.submit(evaluate_with_history,self.task,program,context)
    def shutdown(self,*args,**kwargs):return self.delegate.shutdown(*args,**kwargs)

def instrument_eoh(method,task,revision_dir):
    method._evaluation_executor=HistoryExecutor(method._evaluation_executor,task,revision_dir)
