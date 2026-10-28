from __future__ import annotations

import importlib.util
import math
import os
import sqlite3
import sys
from pathlib import Path

try:
    from celery import Celery
except ImportError:
    class _CeleryConfig(dict):
        def update(self, *args, **kwargs):
            super().update(*args, **kwargs)

    class Celery:  # type: ignore[override]
        def __init__(self, *_args, **_kwargs):
            self.conf = _CeleryConfig()

        def task(self, *decorator_args, **decorator_kwargs):
            del decorator_args, decorator_kwargs

            def _decorator(func):
                return func

            return _decorator

        def send_task(self, *_args, **_kwargs):
            raise RuntimeError("Celery is not installed in the current environment.")

BASE_DIR = Path(__file__).resolve().parent
REPO_ROOT = BASE_DIR.parent


def ensure_repo_root_on_path() -> None:
    """保证仓库根在 sys.path 上，且不依赖"导入时刻"这一次判断。

    只判断一次是不够的：celery 导入 app 模块期间会把 cwd 临时塞进 sys.path
    （celery.utils.imports.cwd_in_path），而 `celery -A visual_platform.celery_worker`
    本来就是从仓库根启动的，于是 cwd == 仓库根，模块级的 not-in 判断会以为
    "已经在 sys.path 里"而跳过插入；celery 随后撤销这个临时插入，仓库根就从
    sys.path 里消失了。此时 `visual_platform` 因为已进 sys.modules 仍可导入，
    但任务里延迟 import 的顶层仓库包（`llm4ad`）会 ModuleNotFoundError
    —— 专家解导入、评测器加载都会中招。
    """
    root = str(REPO_ROOT)
    if root not in sys.path:
        sys.path.insert(0, root)


ensure_repo_root_on_path()

try:
    from celery.signals import task_failure as _task_failure, task_prerun as _task_prerun
except ImportError:  # 没装 celery 时的降级分支（见上面的 Celery 占位实现）
    _task_failure = None
    _task_prerun = None

if _task_prerun is not None:
    @_task_prerun.connect
    def _ensure_repo_root_before_task(**_kwargs) -> None:
        # 每次任务执行前再确认一次，覆盖 celery 启动期的临时 cwd 插入被撤销的情况。
        ensure_repo_root_on_path()

if _task_failure is not None:
    @_task_failure.connect
    def _mark_job_failed_on_task_failure(task_id=None, exception=None, **_kwargs) -> None:
        """任务抛异常时把对应 job 标成失败。

        服务层自己的 try/except 通常已经写好了更具体的失败原因；这里兜住的是
        逃过服务层保护的异常（任务包装层报错、依赖 import 失败等），避免页面
        永远停在「运行中」而没有任何解释。
        """
        from visual_platform.services.job_service import mark_job_failed_by_task_id

        try:
            mark_job_failed_by_task_id(str(task_id or ""), exception)
        except Exception:
            # 兜底逻辑本身绝不能反过来把 worker 弄挂。
            pass

redis_url = os.environ.get("CELERY_BROKER_URL", "redis://localhost:6379/0")

celery_app = Celery(
    "llm4ad_evaluation",
    broker=redis_url,
    backend=redis_url,
)

celery_app.conf.update(
    task_serializer='json',
    accept_content=['json'],
    result_serializer='json',
    timezone='Asia/Shanghai',
    enable_utc=True,
    worker_prefetch_multiplier=1,
    task_acks_late=True,
    broker_transport_options={
        # Long-running CPU graph builds can exceed the Redis default
        # visibility timeout and get redelivered while still running.
        "visibility_timeout": 12 * 60 * 60,
    },
)

def _load_circle_packing_evaluation():
    task_dir = REPO_ROOT / "example" / "tasks" / "circle_packing" / "EoH_settings_logs"
    template_path = task_dir / "template.py"
    evaluation_path = task_dir / "evaluation.py"
    previous_template = sys.modules.get("template")

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
    try:
        spec.loader.exec_module(module)
    finally:
        if previous_template is None:
            sys.modules.pop("template", None)
        else:
            sys.modules["template"] = previous_template
    return module.CirclePackingEvaluation

@celery_app.task(name="visual_platform.celery_worker.evaluate_program")
def evaluate_program_task(program_code: str, task_kwargs: dict):
    from llm4ad.base.code import TextFunctionProgramConverter
    from llm4ad.base.evaluate import SecureEvaluator

    task_kwargs=dict(task_kwargs)
    history_context=task_kwargs.pop('_research_history',None)
    CirclePackingEvaluation = _load_circle_packing_evaluation()
    task = CirclePackingEvaluation(**task_kwargs)
    if history_context:
        from visual_platform.runtime.packing_history import PackingHistoryProxy
        task=PackingHistoryProxy(task,history_context)

    program = TextFunctionProgramConverter.text_to_program(program_code)
    if program is None:
        return {"score": None, "eval_time": 0.0}

    evaluator = SecureEvaluator(task, debug_mode=False)
    score, eval_time = evaluator.evaluate_program_record_time(program)
    
    if score is not None:
        try:
            score = float(score)
            if math.isinf(score) or math.isnan(score):
                score = None
        except (ValueError, TypeError):
            score = None

    return {
        "score": score,
        "eval_time": eval_time
    }


@celery_app.task(name="visual_platform.celery_worker.import_external_expert_solution")
def import_external_expert_solution_task(
    revision_id: str,
    source_revision_id: str | None,
    title: str,
    description: str,
    function_text: str,
    method_config: dict,
):
    from visual_platform.services.expert_service import run_external_expert_import
    from visual_platform.services.expert_service import build_external_expert_evaluator
    from visual_platform.services.expert_service import build_external_expert_algorithm
    from visual_platform.services import workspace_service
    from visual_platform.services.graph_service import ensure_graph_build_task
    from visual_platform.config import DEFAULT_GRAPH_NODE_LIMIT
    from visual_platform.repositories.job_repository import upsert_job

    def _update_progress(r_dir, status, label, **kw):
        job_status = status if status in {"failed", "succeeded", "cancelled"} else "running"
        upsert_job(
            f"expert-import:{revision_id}",
            revision_id,
            "expert_import",
            status=job_status,
            stage=status,
            stage_label=label,
            current=int(kw.get("currentStep", 0) or 0) if "currentStep" in kw else None,
            total=int(kw.get("totalSteps", 0) or 0) if "totalSteps" in kw else None,
            percent=(
                round((float(kw.get("currentStep", 0)) / float(kw.get("totalSteps", 1))) * 100.0, 3)
                if kw.get("currentStep") is not None and kw.get("totalSteps")
                else None
            ),
            message=label,
            error=str(kw.get("error", "") or "").strip() or None,
            payload=kw,
            finished_at=kw.get("finishedAt") if job_status in {"failed", "succeeded", "cancelled"} else None,
        )

    return run_external_expert_import(
        revision_id=revision_id,
        source_revision_id=source_revision_id,
        title=title,
        description=description,
        function_text=function_text,
        method_config=method_config,
        resolve_revision_dir=workspace_service.get_revision_dir,
        update_external_expert_progress=_update_progress,
        evaluate_external_expert_function=build_external_expert_evaluator(),
        build_external_expert_algorithm=build_external_expert_algorithm,
        ensure_graph_build_task=ensure_graph_build_task,
        default_graph_limit=DEFAULT_GRAPH_NODE_LIMIT,
        auto_build_graph=True
    )


def run_history_import_task(
    revision_id: str,
    source_key: str,
    source_revision_id: str | None,
    method_config: dict | None,
    *,
    task_id: str | None = None,
):
    from visual_platform.importer.history import execute_history_import_job

    return execute_history_import_job(
        revision_id=revision_id,
        source_key=source_key,
        source_revision_id=source_revision_id,
        method_config=method_config if isinstance(method_config, dict) else {},
        task_id=task_id,
    )


@celery_app.task(bind=True, name="visual_platform.celery_worker.import_history_samples")
def import_history_samples_task(
    self,
    revision_id: str,
    source_key: str,
    source_revision_id: str | None = None,
    method_config: dict | None = None,
):
    task_id = str(getattr(getattr(self, "request", None), "id", "") or "").strip() or None
    return run_history_import_task(
        revision_id=revision_id,
        source_key=source_key,
        source_revision_id=source_revision_id,
        method_config=method_config,
        task_id=task_id,
    )


def run_graph_build_task(
    job_id: str | None,
    revision_id: str,
    source_revision_id: str | None,
    method_config: dict | None,
    max_nodes: int,
    cluster_id: str | None,
    *,
    task_id: str | None = None,
):
    from visual_platform.runtime.graph_executor import execute_graph_build_job

    return execute_graph_build_job(
        revision_id,
        job_id=job_id,
        method_config=method_config if isinstance(method_config, dict) else {},
        max_nodes=max_nodes,
        source_revision_id=source_revision_id,
        cluster_id=cluster_id,
        task_id=task_id,
    )


@celery_app.task(bind=True, name="visual_platform.celery_worker.build_graph")
def build_graph_task(
    self,
    revision_id: str,
    job_id: str | None = None,
    source_revision_id: str | None = None,
    method_config: dict | None = None,
    max_nodes: int = 50000,
    cluster_id: str | None = None,
):
    task_id = str(getattr(getattr(self, "request", None), "id", "") or "").strip() or None
    return run_graph_build_task(
        job_id=job_id,
        revision_id=revision_id,
        source_revision_id=source_revision_id,
        method_config=method_config,
        max_nodes=max_nodes,
        cluster_id=cluster_id,
        task_id=task_id,
    )


def run_revision_launch_task(
    revision_id: str,
    config_path: str,
    *,
    task_id: str | None = None,
):
    from visual_platform.runtime import revision_executor

    return revision_executor.run_revision_launch_task(
        revision_id=revision_id,
        config_path=config_path,
        task_id=task_id,
    )


@celery_app.task(
    bind=True,
    name="visual_platform.celery_worker.launch_revision_runner",
    # "database is locked" during graph-build write bursts is transient;
    # retrying beats leaving the revision stuck in launch_requested.
    autoretry_for=(sqlite3.OperationalError,),
    retry_backoff=15,
    retry_backoff_max=120,
    max_retries=5,
)
def launch_revision_runner_task(
    self,
    revision_id: str,
    config_path: str,
):
    task_id = str(getattr(getattr(self, "request", None), "id", "") or "").strip() or None
    return run_revision_launch_task(
        revision_id=revision_id,
        config_path=config_path,
        task_id=task_id,
    )


def run_revision_stop_task(
    revision_id: str,
    *,
    task_id: str | None = None,
):
    from visual_platform.runtime import revision_executor

    return revision_executor.run_revision_stop_task(
        revision_id=revision_id,
        task_id=task_id,
    )


@celery_app.task(bind=True, name="visual_platform.celery_worker.stop_revision_runner")
def stop_revision_runner_task(
    self,
    revision_id: str,
):
    task_id = str(getattr(getattr(self, "request", None), "id", "") or "").strip() or None
    return run_revision_stop_task(
        revision_id=revision_id,
        task_id=task_id,
    )
