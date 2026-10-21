from __future__ import annotations

import ast
import builtins
import contextlib
import logging
import math
import os
import signal
import threading
import time
import uuid
from datetime import datetime
from pathlib import Path
from typing import Any, Callable

from visual_platform.runtime.runner_task_loader import (
    evaluate_generated_function as runtime_evaluate_generated_function,
    load_circle_packing_evaluation as runtime_load_circle_packing_evaluation,
)
from visual_platform.repositories.job_repository import list_active_jobs_for_workspace

logger = logging.getLogger(__name__)


class ExpertEvaluationTimeout(Exception):
    """Raised when the inline expert evaluation exceeds its wall-clock budget."""


@contextlib.contextmanager
def _eval_deadline(seconds: int):
    """Best-effort wall-clock cap for the inline expert evaluation.

    safe_evaluate is disabled (the Celery prefork worker is a daemon process and
    cannot spawn the sandbox child), so a runaway solution -- e.g. scipy.optimize
    ignoring the advisory max_time budget -- would otherwise stall the worker
    indefinitely. On a POSIX main thread we arm SIGALRM to raise after ``seconds``;
    the handler only runs once control returns to the Python interpreter, so this
    caps runaway Python-level loops (it cannot interrupt a single long C call).
    On Windows / non-main threads it degrades to a no-op.
    """
    can_arm = (
        seconds > 0
        and hasattr(signal, "SIGALRM")
        and threading.current_thread() is threading.main_thread()
    )
    if not can_arm:
        yield
        return

    def _handler(signum, frame):  # noqa: ANN001 - signal handler signature
        raise ExpertEvaluationTimeout(f"expert evaluation exceeded {seconds}s")

    previous = signal.signal(signal.SIGALRM, _handler)
    try:
        signal.setitimer(signal.ITIMER_REAL, float(seconds))
        yield
    finally:
        signal.setitimer(signal.ITIMER_REAL, 0.0)
        signal.signal(signal.SIGALRM, previous)


# 是否允许在 Worker 进程内直接 exec 提交上来的代码。
#
# 这条路径**没有真实沙箱**：正常做法是 safe_evaluate=True 另起沙箱子进程，但
# Celery prefork worker 本身是守护进程，而守护进程不允许再派生*子进程*
# （multiprocessing 会抛 AssertionError），Windows 上也没有 fork。所以这里退化成
# 了进程内 exec —— 一旦暴露到网络，就等于允许任何人通过 HTTP 接口
# （POST /api/jobs, jobType="expert_import"）在服务器上执行任意 Python。
#
# 因此默认**关闭**：需要本机自用、且代码来源可信时，显式设置
#   VISUAL_PLATFORM_ALLOW_LOCAL_CODE_EXEC=1
# 再重启服务。长期方案是把执行挪到独立的非守护子进程里（真正的沙箱）。
_ALLOW_LOCAL_CODE_EXEC_ENV = "VISUAL_PLATFORM_ALLOW_LOCAL_CODE_EXEC"
_TRUTHY = {"1", "true", "yes", "on"}


def allow_local_code_exec() -> bool:
    """进程内 exec 提交代码的总开关，默认关闭。"""
    return str(os.environ.get(_ALLOW_LOCAL_CODE_EXEC_ENV, "")).strip().lower() in _TRUTHY



def _build_expert_exec_globals() -> dict[str, Any]:
    """Build a globals namespace pre-populated with the common scientific stack.

    LLM-adapted expert solutions frequently reference modules/functions (random,
    time, scipy helpers, ...) while forgetting to emit the matching top-level
    ``import`` -> the evaluation dies with NameError even though the algorithm is
    correct. The expert import is a trusted, single-task path, so seed the exec
    namespace with the modules circle-packing solutions rely on. A program's own
    imports (when present) simply rebind these same names, so this is a safe
    superset that never changes the behaviour of self-contained code.
    """
    import itertools
    import math
    import random
    import time as _time

    import numpy as np

    namespace: dict[str, Any] = {
        "np": np,
        "numpy": np,
        "math": math,
        "random": random,
        "time": _time,
        "itertools": itertools,
    }
    try:
        import scipy
        from scipy.optimize import minimize
        from scipy.spatial.distance import pdist, squareform

        namespace.update(
            {
                "scipy": scipy,
                "minimize": minimize,
                "pdist": pdist,
                "squareform": squareform,
            }
        )
    except Exception:
        # scipy is optional; self-contained solutions bring their own imports.
        pass
    return namespace


def _collect_arg_names(args: ast.arguments) -> set[str]:
    names: set[str] = set()
    for arg in [*args.posonlyargs, *args.args, *args.kwonlyargs]:
        names.add(arg.arg)
    if args.vararg:
        names.add(args.vararg.arg)
    if args.kwarg:
        names.add(args.kwarg.arg)
    return names


def find_undefined_referenced_names(program_text: str, seeded_names: set[str]) -> list[str]:
    """Best-effort static scan for names referenced but defined nowhere.

    Targets the common failure where an adapted expert solution only includes
    ``pack_circles`` but calls helper functions (try_known_good, run_optimization,
    ...) that were left out of the submission -> the evaluation dies with a
    NameError several minutes in. We over-approximate 'defined' (every Store
    target, function/lambda parameter, import alias and def/class name counts as
    defined) so locals never produce false positives; a name used in Load context
    that is defined nowhere and is not a builtin or seeded module is reported.
    """
    try:
        tree = ast.parse(program_text)
    except SyntaxError:
        return []

    defined: set[str] = set(seeded_names)
    defined.update(dir(builtins))
    used: set[str] = set()

    for node in ast.walk(tree):
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
            defined.add(node.name)
            defined |= _collect_arg_names(node.args)
        elif isinstance(node, ast.Lambda):
            defined |= _collect_arg_names(node.args)
        elif isinstance(node, ast.ClassDef):
            defined.add(node.name)
        elif isinstance(node, ast.Import):
            for alias in node.names:
                defined.add((alias.asname or alias.name).split(".")[0])
        elif isinstance(node, ast.ImportFrom):
            for alias in node.names:
                defined.add(alias.asname or alias.name)
        elif isinstance(node, ast.ExceptHandler):
            # `except SomeError as e:` binds `e` via a bare string, not a Name node.
            if node.name:
                defined.add(node.name)
        elif isinstance(node, (ast.Global, ast.Nonlocal)):
            defined.update(node.names)
        elif isinstance(node, ast.Name):
            if isinstance(node.ctx, ast.Store):
                defined.add(node.id)
            elif isinstance(node.ctx, ast.Load):
                used.add(node.id)

    return sorted(name for name in used if name not in defined)


def normalize_expert_function_text(raw_text: Any) -> str:
    source = str(raw_text or "").strip()
    if not source:
        return ""
    if source.startswith("```") and source.endswith("```"):
        lines = source.splitlines()
        if len(lines) >= 2:
            source = "\n".join(lines[1:-1]).strip()
    return source.strip()


def build_external_expert_algorithm(title: str, description: str, *, accepted_as_worst: bool) -> str:
    normalized_title = str(title or "").strip()
    normalized_description = str(description or "").strip()
    parts: list[str] = []
    if normalized_title:
        parts.append(f"外部专家解：{normalized_title}")
    if normalized_description:
        parts.append(normalized_description)
    if not parts:
        parts.append("外部专家手工注入解。")
    if accepted_as_worst:
        parts.append("该解未通过有效评估，已按最差解处理。")
    return " ".join(parts)


def build_external_expert_method_config(
    source_revision_id: str | None,
    requested_method: dict[str, Any],
    *,
    read_revision_config: Callable[[str | None], dict[str, Any]],
) -> dict[str, Any]:
    method_config: dict[str, Any] = {}
    source_config = read_revision_config(source_revision_id)
    source_method = source_config.get("method", {})
    if isinstance(source_method, dict):
        method_config.update(source_method)
    method_config.update(requested_method)
    if not str(method_config.get("distance_metric", "") or "").strip():
        method_config["distance_metric"] = "codet5p_embedding_cosine"
    if "timeout_seconds" not in method_config:
        method_config["timeout_seconds"] = 120
    return method_config


def create_external_expert_revision(
    *,
    runs_dir: Path,
    write_json_file: Callable[[Path, Any], None],
    insert_revision: Callable[[str, str, str, dict[str, Any]], None],
    workspace_id: str,
    source_revision_id: str | None,
    method_config: dict[str, Any],
    expert_meta: dict[str, Any],
) -> tuple[str, Path, Path, str]:
    revision_id = datetime.now().strftime("%Y%m%d_%H%M%S") + "_" + uuid.uuid4().hex[:8]
    revision_dir = runs_dir / revision_id
    log_dir = revision_dir / "log"
    revision_dir.mkdir(parents=True, exist_ok=True)
    log_dir.mkdir(parents=True, exist_ok=True)
    started_at = datetime.now().isoformat(timespec="seconds")
    config = {
        "revision_id": revision_id,
        "started_at": started_at,
        "mode": "external_expert",
        "prompt": "",
        "selected_nodes": [],
        "workspace_id": workspace_id,
        "source_revision_id": source_revision_id,
        "log_dir": str(log_dir),
        "llm": {},
        "method": method_config,
        "externalExpert": expert_meta,
    }
    write_json_file(revision_dir / "config.json", config)
    insert_revision(revision_id, workspace_id, "external_expert", config)
    return revision_id, revision_dir, log_dir, started_at


def evaluate_external_expert_function(
    function_text: str,
    timeout_seconds: int,
    *,
    load_circle_packing_evaluation: Callable[[], Any],
    evaluate_generated_function: Callable[[Any, Any], tuple[Any, Any, Any]],
    use_celery: bool = False,
    progress_callback: Any | None = None,
) -> tuple[Any, float | None, float, str, bool]:
    eval_started_at = time.perf_counter()
    logger.info(
        "expert eval entered: use_celery=%s timeout=%ss function_text_len=%s",
        bool(use_celery),
        int(timeout_seconds),
        len(str(function_text or "")),
    )
    if callable(progress_callback):
        progress_callback("load_task", "加载评测器")
    CirclePackingEvaluation = load_circle_packing_evaluation()
    logger.info(
        "expert eval stage: task module imported at +%.2fs",
        time.perf_counter() - eval_started_at,
    )
    task_kwargs: dict[str, Any] = {"timeout_seconds": max(10, int(timeout_seconds))}
    # safe_evaluate spawns a child multiprocessing.Process for sandboxing. This
    # evaluation always runs inside a Celery prefork worker (a daemon process),
    # and daemonic processes are not allowed to have children -> the subprocess
    # start() raises AssertionError and the score comes back as None. It also
    # fails on Windows (no fork). Run the evaluation inline in all cases; the
    # expert function is a single trusted import with its own time budget.
    task_kwargs["safe_evaluate"] = False
    task = CirclePackingEvaluation(**task_kwargs)
    logger.info(
        "expert eval stage: evaluator initialized at +%.2fs",
        time.perf_counter() - eval_started_at,
    )

    from llm4ad.base.code import TextFunctionProgramConverter

    if callable(progress_callback):
        progress_callback("parse_function", "解析目标函数")
    template_program_obj = TextFunctionProgramConverter.text_to_program(task.template_program)
    if not template_program_obj or len(template_program_obj.functions) != 1:
        raise RuntimeError("无法从模板中提取目标函数名称。")
    target_func_name = template_program_obj.functions[0].name

    function, helpers_code = TextFunctionProgramConverter.text_to_function_and_helpers(function_text, target_func_name)
    if function is None:
        raise RuntimeError(f"无法把输入解析为包含目标函数 `{target_func_name}` 的 Python 代码。请确保代码中包含该函数。")

    if callable(progress_callback):
        progress_callback("build_program", "构造可执行程序")
    program = TextFunctionProgramConverter.function_to_program(function, task.template_program)
    if program is None:
        raise RuntimeError("函数无法转换为可执行程序，请检查代码是否完整。")
    logger.info(
        "expert eval setup ready: evaluator+program built in %.2fs (entry=%s)",
        time.perf_counter() - eval_started_at,
        target_func_name,
    )

    if helpers_code:
        program_str_val = str(program)
        program = TextFunctionProgramConverter.text_to_program(program_str_val)
        program = type(program)(
            preface=(program.preface + "\n" + helpers_code) if program.preface else helpers_code,
            functions=program.functions,
        )

    if use_celery:
        from visual_platform.celery_worker import evaluate_program_task
        async_result = evaluate_program_task.delay(str(program), task_kwargs)
        res = async_result.get()
        score = res.get("score")
        eval_time = res.get("eval_time")
        program_text = str(program)
    else:
        if callable(progress_callback):
            progress_callback("run_evaluation", "执行专家解评估")
        # Expert solutions legitimately contain many top-level helper functions.
        # SecureEvaluator.evaluate_program() (used by evaluate_generated_function)
        # calls text_to_function(program_str) without a target name to discover
        # the entry function, which hard-requires EXACTLY one top-level def and
        # rejects a multi-helper program with "Only one function expected, got N",
        # losing the score. We already know the entry name (target_func_name), so
        # execute the full program and score the known callable directly via the
        # task evaluator, bypassing the one-function constraint.
        program_text = str(program)
        # Fail fast on incomplete submissions. A common mistake is pasting only
        # `pack_circles` while leaving out the helper functions it calls
        # (try_known_good, run_optimization, ...); that otherwise dies with a
        # cryptic NameError minutes into evaluation. Detect it statically here.
        exec_namespace: dict[str, Any] = _build_expert_exec_globals()
        undefined_names = find_undefined_referenced_names(
            program_text, set(exec_namespace.keys())
        )
        if undefined_names:
            raise RuntimeError(
                "适配后的代码不是自包含的：调用了未定义的名称 "
                + ", ".join(undefined_names)
                + "。请把这些 helper 函数/变量的定义一并提交（只贴 "
                + f"`{target_func_name}` 而漏掉它调用的 helper 是最常见原因）。"
            )
        # Cap runaway evaluation. The solution's own max_time/total_time budgets are
        # only advisory (scipy.optimize ignores wall-clock time), so give a
        # generous multiple of the configured timeout before the watchdog fires.
        eval_deadline_seconds = max(60, int(timeout_seconds) * 3)
        logger.info(
            "expert eval start entry=%s deadline=%ss program_len=%s",
            target_func_name,
            eval_deadline_seconds,
            len(program_text),
        )
        if not allow_local_code_exec():
            raise RuntimeError(
                "服务端已禁用「在工作进程内执行提交代码」这条路径。\n"
                "该路径没有真实沙箱（Celery worker 是守护进程，无法派生沙箱子进程），"
                "开启它等于允许通过 HTTP 接口在服务器上执行任意 Python 代码。\n"
                "确认代码来源可信、且服务只监听本机时，可设置环境变量后重启：\n"
                f"  {_ALLOW_LOCAL_CODE_EXEC_ENV}=1"
            )
        eval_t0 = time.perf_counter()
        try:
            with _eval_deadline(eval_deadline_seconds):
                # exec 必须在超时保护**之内**：提交代码的顶层死循环同样要被截断，
                # 否则 worker 会被永久占住。原先 exec 在保护之外，等于没设防。
                exec(compile(program_text, "<expert_solution>", "exec"), exec_namespace)
                entry_callable = exec_namespace.get(target_func_name)
                if entry_callable is None:
                    raise RuntimeError(f"程序中找不到目标函数 `{target_func_name}`。")
                logger.info(
                    "expert eval running entry=%s (exec ready in %.2fs); scoring now",
                    target_func_name,
                    time.perf_counter() - eval_t0,
                )
                score = task.evaluate_program(program_text, entry_callable)
        except ExpertEvaluationTimeout as timeout_error:
            logger.warning("expert eval timed out entry=%s: %s", target_func_name, timeout_error)
            score = None
        eval_time = time.perf_counter() - eval_t0
        logger.info(
            "expert eval done entry=%s score=%s eval_time=%.2fs",
            target_func_name,
            score,
            eval_time,
        )

    normalized_score: float | None = None
    accepted_as_worst = False
    if isinstance(score, (int, float)) and math.isfinite(float(score)):
        normalized_score = float(score)
    else:
        accepted_as_worst = True
    return function, normalized_score, float(eval_time), program_text, accepted_as_worst


def build_external_expert_evaluator() -> Callable[..., tuple[Any, float | None, float, str, bool]]:
    def _bound_evaluator(function_text: str, timeout_seconds: int, **kwargs: Any) -> tuple[Any, float | None, float, str, bool]:
        return evaluate_external_expert_function(
            function_text,
            timeout_seconds,
            load_circle_packing_evaluation=runtime_load_circle_packing_evaluation,
            evaluate_generated_function=runtime_evaluate_generated_function,
            **kwargs,
        )

    return _bound_evaluator


def run_external_expert_import(
    *,
    revision_id: str,
    source_revision_id: str | None,
    title: str,
    description: str,
    function_text: str,
    method_config: dict[str, Any],
    resolve_revision_dir: Callable[[str | None], Path | None],
    update_external_expert_progress: Callable[..., dict[str, Any]],
    evaluate_external_expert_function: Callable[..., tuple[Any, float | None, float, str, bool]],
    build_external_expert_algorithm: Callable[..., str],
    ensure_graph_build_task: Callable[..., dict[str, Any]],
    default_graph_limit: int,
    auto_build_graph: bool,
) -> dict[str, Any]:
    from visual_platform.repositories.individual_repository import insert_individual, next_sample_order
    from visual_platform.repositories.revision_repository import upsert_revision

    revision_dir = resolve_revision_dir(revision_id)
    if revision_dir is None:
        raise RuntimeError(f"Expert import revision directory not found: {revision_id}")

    log_dir = revision_dir / "log"
    timeout_seconds = int(method_config.get("timeout_seconds", 120) or 120)

    try:
        update_external_expert_progress(
            revision_dir,
            "evaluating",
            "Evaluating external expert solution",
            currentStep=1,
            totalSteps=3,
            evalSubPhase="queued",
            evalSubPhaseLabel="Preparing evaluation",
        )
        function, score, eval_time, program_text, accepted_as_worst = evaluate_external_expert_function(
            function_text,
            timeout_seconds=timeout_seconds,
            use_celery=False,
            progress_callback=lambda subphase, label: update_external_expert_progress(
                revision_dir,
                "evaluating",
                "Evaluating external expert solution",
                currentStep=1,
                totalSteps=3,
                evalSubPhase=subphase,
                evalSubPhaseLabel=label,
            ),
        )

        sample_order = next_sample_order(revision_id)
        sample_id = f"expert-{revision_id}-{uuid.uuid4().hex[:8]}"
        update_external_expert_progress(
            revision_dir,
            "persisting",
            "Persisting imported expert solution",
            currentStep=2,
            totalSteps=3,
            sampleOrder=sample_order,
        )
        insert_individual(
            {
                "id": sample_id,
                "revision_id": revision_id,
                "sample_order": sample_order,
                "generation": 0,
                "score": score,
                "function": str(function or function_text),
                "algorithm": build_external_expert_algorithm(
                    title,
                    description,
                    accepted_as_worst=accepted_as_worst,
                ),
                "program": program_text,
                "operator": "external_expert_manual",
                "source_kind": "external_expert",
                "origin_kind": "external_expert",
                "source_label": "external_expert",
                "source_revision_id": source_revision_id,
                "expert_title": title,
                "expert_description": description,
                "evaluate_time": eval_time,
                "accepted_as_worst": accepted_as_worst,
            }
        )

        finished_at = datetime.now().isoformat(timespec="seconds")
        upsert_revision(
            revision_id,
            lifecycle_status="completed",
            graph_status="stale",
            error="",
            finished_at=finished_at,
        )

        result = {
            "revisionId": revision_id,
            "nodeId": sample_id,
            "sampleOrder": sample_order,
            "score": score,
            "acceptedAsWorst": accepted_as_worst,
        }

        update_external_expert_progress(
            revision_dir,
            "succeeded",
            "External expert solution imported",
            currentStep=3,
            totalSteps=3,
            finishedAt=finished_at,
            graphStatus="building" if auto_build_graph else "stale",
            **result,
        )

        if auto_build_graph:
            ensure_graph_build_task(
                revision_dir,
                log_dir,
                method_config=method_config,
                max_nodes=default_graph_limit,
                source_revision_id=source_revision_id,
                cluster_id=None,
            )
        return result
    except Exception as error:
        upsert_revision(
            revision_id,
            lifecycle_status="failed",
            graph_status="failed",
            error=str(error),
            finished_at=datetime.now().isoformat(timespec="seconds"),
        )
        update_external_expert_progress(
            revision_dir,
            "failed",
            "External expert import failed",
            error=str(error),
        )
        raise


def submit_expert_solution(
    payload: dict[str, Any],
) -> tuple[dict[str, Any], int]:
    request_started_at = time.perf_counter()
    requested_workspace_id = str(payload.get("workspace_id", "") or "").strip()
    title = str(payload.get("title", "") or "").strip()
    description = str(payload.get("description", "") or "").strip()
    function_text = normalize_expert_function_text(payload.get("function_text", payload.get("function", "")))
    method_payload = payload.get("method", {})
    if not isinstance(method_payload, dict):
        method_payload = {}

    if not function_text:
        return {"ok": False, "error": "请至少提供一段可评估的 `pack_circles` 函数代码。"}, 400

    from visual_platform.services import workspace_service

    if requested_workspace_id:
        workspace_service.activate_workspace(requested_workspace_id)

    active_workspace = workspace_service.get_active_workspace()
    if active_workspace is None:
        return {"ok": False, "error": "未找到对应工作台。"}, 404

    source_revision_id = str(active_workspace.get("current_revision_id", "") or "").strip() or None
    active_jobs = list_active_jobs_for_workspace(
        active_workspace["workspace_id"],
        job_types=("revision_generation", "history_import", "expert_import"),
    )
    if active_jobs:
        return {"ok": False, "error": "当前工作台的版本任务仍在执行中，请先停止后再注入外部专家解。"}, 400

    from visual_platform.repositories import revision_repository
    def _read_revision_config(revision_id):
        normalized_revision_id = str(revision_id or "").strip()
        if not normalized_revision_id:
            return {}
        rec = revision_repository.get_revision_record(normalized_revision_id)
        return rec.get("config", {}) if rec else {}

    method_config = build_external_expert_method_config(
        source_revision_id,
        method_payload,
        read_revision_config=_read_revision_config,
    )
    method_config["use_celery"] = True

    from visual_platform.config import RUNS_DIR
    def _write_json(path, data):
        import json
        with path.open("w", encoding="utf-8") as f:
            json.dump(data, f, ensure_ascii=False)

    revision_id, revision_dir, _log_dir, started_at = create_external_expert_revision(
        runs_dir=RUNS_DIR,
        write_json_file=_write_json,
        insert_revision=revision_repository.insert_revision,
        workspace_id=active_workspace["workspace_id"],
        source_revision_id=source_revision_id,
        method_config=method_config,
        expert_meta={
            "title": title,
            "description": description,
            "acceptedAsWorst": False,
        },
    )
    workspace_service.update_workspace_revision(active_workspace["workspace_id"], revision_id)
    from visual_platform.repositories.job_repository import upsert_job
    upsert_job(
        f"expert-import:{revision_id}",
        revision_id,
        "expert_import",
        status="queued",
        stage="queued",
        stage_label="Queued",
        current=0,
        total=3,
        percent=0.0,
        message="Waiting for external expert import to start",
        payload={"requestedUseCelery": True},
        started_at=started_at
    )

    try:
        from visual_platform.celery_worker import celery_app

        async_result = celery_app.send_task(
            "visual_platform.celery_worker.import_external_expert_solution",
            kwargs={
                "revision_id": revision_id,
                "source_revision_id": source_revision_id,
                "title": title,
                "description": description,
                "function_text": function_text,
                "method_config": method_config,
            },
        )
    except Exception as error:
        upsert_job(
            f"expert-import:{revision_id}", revision_id, "expert_import",
            status="failed", stage="failed", stage_label="Worker submit failed", error=str(error)
        )
        revision_repository.upsert_revision(revision_id, lifecycle_status="failed", graph_status="failed", error=str(error))
        return {"ok": False, "error": f"Worker 任务提交失败：{error}"}, 503

    upsert_job(
        f"expert-import:{revision_id}", revision_id, "expert_import",
        status="queued", stage="queued", stage_label="Queued in worker",
        payload={"taskId": async_result.id, "requestedUseCelery": True}
    )
    return {
        "ok": True,
        "queued": True,
        "revisionId": revision_id,
        "workspaceId": active_workspace["workspace_id"],
        "startedAt": started_at,
    }, 200
