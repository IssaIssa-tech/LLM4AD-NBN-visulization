from __future__ import annotations

import importlib.util
import sys
from pathlib import Path
from typing import Any


BASE_DIR = Path(__file__).resolve().parent.parent
REPO_ROOT = BASE_DIR.parent


def platform_secure_evaluator(task: Any) -> Any:
    from llm4ad.base.evaluate import SecureEvaluator

    return SecureEvaluator(task, debug_mode=True)


def evaluate_generated_function(
    task: Any,
    function: Any,
    task_kwargs: dict[str, Any] | None = None,
    use_celery: bool = False,
    program_override: Any | None = None,
    research_call_id: str | None = None,
) -> tuple[float | None, float, str]:
    from llm4ad.base.code import TextFunctionProgramConverter

    program = program_override
    if program is None:
        program = TextFunctionProgramConverter.function_to_program(function, task.template_program)
    if program is None:
        return None, 0.0, ""

    import os
    from visual_platform.runtime.packing_history import PackingHistoryProxy, start_evaluation, finish_evaluation
    directory=os.environ.get('VP_RESEARCH_HISTORY_DIR')
    history_context=start_evaluation(directory,str(program),research_call_id) if directory else None

    if use_celery:
        from visual_platform.celery_worker import evaluate_program_task

        kwargs=dict(task_kwargs or {})
        if history_context:kwargs['_research_history']=history_context
        async_result = evaluate_program_task.delay(str(program), kwargs)
        result = async_result.get()
        if history_context:finish_evaluation(history_context,result.get('score'),result.get('eval_time'))
        return result.get("score"), result.get("eval_time"), str(program)

    evaluator = platform_secure_evaluator(PackingHistoryProxy(task,history_context) if history_context else task)
    score, eval_time = evaluator.evaluate_program_record_time(program)
    if history_context:finish_evaluation(history_context,score,eval_time)
    return score, eval_time, str(program)


class CeleryFuture:
    def __init__(self, async_result: Any, history_context=None):
        self.async_result = async_result
        self.history_context=history_context

    def result(self) -> tuple[Any, Any]:
        result = self.async_result.get()
        if self.history_context:
            from visual_platform.runtime.packing_history import finish_evaluation
            finish_evaluation(self.history_context,result.get('score'),result.get('eval_time'))
        return result.get("score"), result.get("eval_time")


class CeleryExecutor:
    def __init__(self, task_kwargs: dict[str, Any]):
        self.task_kwargs = task_kwargs
        from visual_platform.celery_worker import evaluate_program_task

        self.evaluate_program_task = evaluate_program_task

    def submit(self, func: Any, program: Any, *args: Any, **kwargs: Any) -> CeleryFuture:
        del func, args, kwargs
        async_result = self.evaluate_program_task.delay(str(program), self.task_kwargs)
        return CeleryFuture(async_result)

    def shutdown(self, wait: bool = True, *, cancel_futures: bool = False) -> None:
        del wait, cancel_futures

    def submit_with_history(self,program,context):
        kwargs=dict(self.task_kwargs);kwargs['_research_history']=context
        return CeleryFuture(self.evaluate_program_task.delay(str(program),kwargs),context)


def load_circle_packing_evaluation() -> Any:
    evaluation_path = REPO_ROOT / "example" / "tasks" / "circle_packing" / "EoH_settings_logs" / "evaluation.py"
    template_path = evaluation_path.parent / "template.py"

    template_spec = importlib.util.spec_from_file_location("template", template_path)
    if template_spec is None or template_spec.loader is None:
        raise RuntimeError("Unable to load Circle Packing template module.")
    template_module = importlib.util.module_from_spec(template_spec)
    sys.modules["template"] = template_module
    template_spec.loader.exec_module(template_module)

    spec = importlib.util.spec_from_file_location("platform_circle_packing_evaluation", evaluation_path)
    if spec is None or spec.loader is None:
        raise RuntimeError("Unable to load Circle Packing evaluation module.")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module.CirclePackingEvaluation


def build_circle_packing_seed_function() -> str:
    return """
import numpy as np
import math
def pack_circles(n: int) -> np.ndarray:
    \"""
    Pack n circles in a unit square to maximize sum of radii.

    Args:
        n: Number of circles to pack

    Returns:
        Numpy array of shape (n, 3) where each row is (x, y, radius)
        All values should be between 0 and 1
        Circles must not overlap

    Important: Set "all" random seeds to 2025, including the packages (such as scipy sub-packages) involving random seeds.
    \"""
    if n <= 0:
        return np.zeros((0, 3), dtype=float)

    grid_size = int(np.ceil(np.sqrt(n)))
    radius = 0.49 / grid_size

    circles = []
    for i in range(n):
        row = i // grid_size
        col = i % grid_size
        x = (col + 0.5) / grid_size
        y = (row + 0.5) / grid_size
        circles.append([x, y, radius])

    return np.array(circles, dtype=float)
"""
