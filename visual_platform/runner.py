from __future__ import annotations

import argparse
import concurrent.futures
import copy
import importlib.util
import json
import os
import re
import sys
import threading
import time
import traceback
import urllib.request
import warnings
from datetime import datetime
from pathlib import Path
from typing import Any


BASE_DIR = Path(__file__).resolve().parent
REPO_ROOT = BASE_DIR.parent
_debug_report_lock = threading.Lock()
_debug_report_suppressed_until = 0.0
DEBUG_REPORT_FAILURE_COOLDOWN_SECONDS = 60.0
DEBUG_REPORT_DEFAULT_URL = "http://127.0.0.1:7777/event"
DEBUG_REPORT_DEFAULT_SESSION_ID = "real-run-stall"

warnings.filterwarnings(
    "ignore",
    message=r"The balance properties of Sobol' points require n to be a power of 2\.",
    category=UserWarning,
    module=r"scipy\.stats\._qmc",
)


def _debug_report(hypothesis_id: str, location: str, msg: str, data: dict[str, Any] | None = None, run_id: str = "pre-fix") -> None:
    # #region debug-point report
    global _debug_report_suppressed_until
    _url = (os.environ.get("DEBUG_SERVER_URL") or DEBUG_REPORT_DEFAULT_URL).strip() or DEBUG_REPORT_DEFAULT_URL
    _session = (os.environ.get("DEBUG_SESSION_ID") or DEBUG_REPORT_DEFAULT_SESSION_ID).strip() or DEBUG_REPORT_DEFAULT_SESSION_ID
    _enabled = (os.environ.get("VISUAL_PLATFORM_ENABLE_DEBUG_REPORT") or "").strip().lower() in {"1", "true", "yes", "on"}
    for _env in (
        BASE_DIR / ".dbg" / "real-mode-failures.env",
        BASE_DIR / ".dbg" / "real-run-stall.env",
        BASE_DIR / ".dbg" / "real-run-stuck.env",
    ):
        try:
            content = _env.read_text(encoding="utf-8")
            _enabled = True
            for line in content.splitlines():
                if line.startswith("DEBUG_SERVER_URL="):
                    _url = line.split("=", 1)[1].strip() or _url
                elif line.startswith("DEBUG_SESSION_ID="):
                    _session = line.split("=", 1)[1].strip() or _session
            break
        except OSError:
            continue
    if not _enabled:
        return
    _now = time.monotonic()
    with _debug_report_lock:
        if _now < _debug_report_suppressed_until:
            return
    payload = {
        "sessionId": _session,
        "runId": run_id,
        "hypothesisId": hypothesis_id,
        "location": location,
        "msg": f"[DEBUG] {msg}",
        "data": data or {},
        "ts": int(time.time() * 1000),
    }
    try:
        urllib.request.urlopen(
            urllib.request.Request(
                _url,
                data=json.dumps(payload, ensure_ascii=True).encode("utf-8"),
                headers={"Content-Type": "application/json"},
            ),
            timeout=2,
        ).read()
        with _debug_report_lock:
            _debug_report_suppressed_until = 0.0
    except Exception:
        with _debug_report_lock:
            _debug_report_suppressed_until = _now + DEBUG_REPORT_FAILURE_COOLDOWN_SECONDS
    # #endregion


def _int_config(method_config: dict[str, Any], key: str, default: int, minimum: int) -> int:
    try:
        value = int(method_config.get(key, default))
    except (TypeError, ValueError):
        value = default
    return max(minimum, value)


def _resolved_method_config(method_config: dict[str, Any] | None) -> dict[str, int]:
    config = method_config if isinstance(method_config, dict) else {}
    max_generations = _int_config(config, "max_generations", 8, 1)
    pop_size = _int_config(config, "pop_size", 8, 2)
    num_samplers = _int_config(config, "num_samplers", 4, 1)
    num_evaluators = _int_config(config, "num_evaluators", 4, 1)
    derived_sample_budget = max_generations * pop_size
    max_sample_nums = _int_config(config, "max_sample_nums", derived_sample_budget, derived_sample_budget)
    return {
        "max_generations": max_generations,
        "max_sample_nums": max_sample_nums,
        "pop_size": pop_size,
        "num_samplers": num_samplers,
        "num_evaluators": num_evaluators,
    }


def _append_json_record(file_path: Path, content: dict[str, Any]) -> None:
    file_path.parent.mkdir(parents=True, exist_ok=True)
    try:
        with file_path.open("r", encoding="utf-8") as handle:
            data = json.load(handle)
    except (OSError, json.JSONDecodeError):
        data = []
    data.append(content)
    with file_path.open("w", encoding="utf-8") as handle:
        json.dump(data, handle, indent=2, ensure_ascii=True)
    # #region debug-point C:sample-persist
    _debug_report(
        "C",
        "runner.py:_append_json_record",
        "sample record persisted",
        {
            "file_path": str(file_path),
            "record_count": len(data),
            "sample_order": content.get("sample_order"),
            "score": content.get("score"),
            "score_is_none": content.get("score") is None,
            "has_algorithm": bool(str(content.get("algorithm", "") or "").strip()),
            "has_function": bool(str(content.get("function", "") or "").strip()),
            "has_program": bool(str(content.get("program", "") or "").strip()),
            "operator": content.get("operator"),
        },
    )
    # #endregion


def _write_population_snapshot(log_dir: Path, generation: int, population: list[dict[str, Any]]) -> None:
    population_dir = log_dir / "population"
    population_dir.mkdir(parents=True, exist_ok=True)
    snapshot = [
        {
            "algorithm": item.get("algorithm", ""),
            "function": item.get("function", ""),
            "score": item.get("score"),
        }
        for item in population
    ]
    with (population_dir / f"pop_{generation}.json").open("w", encoding="utf-8") as handle:
        json.dump(snapshot, handle, indent=2, ensure_ascii=True)


def _mark_finished(log_dir: Path) -> None:
    population_dir = log_dir / "population"
    population_dir.mkdir(parents=True, exist_ok=True)
    with (population_dir / "end.json").open("w", encoding="utf-8") as handle:
        json.dump([], handle, indent=2)


def _write_real_run_meta(log_dir: Path, payload: dict[str, Any]) -> None:
    meta_path = log_dir / "real_run_meta.json"
    with meta_path.open("w", encoding="utf-8") as handle:
        json.dump(payload, handle, indent=2, ensure_ascii=True)


def _read_real_run_meta(log_dir: Path) -> dict[str, Any]:
    meta_path = log_dir / "real_run_meta.json"
    try:
        with meta_path.open("r", encoding="utf-8") as handle:
            payload = json.load(handle)
    except (OSError, json.JSONDecodeError):
        return {}
    return payload if isinstance(payload, dict) else {}


def _merge_real_run_meta(log_dir: Path, payload: dict[str, Any]) -> dict[str, Any]:
    meta = _read_real_run_meta(log_dir)
    meta.update(payload)
    meta["updatedAt"] = datetime.now().isoformat(timespec="seconds")
    _write_real_run_meta(log_dir, meta)
    return meta


def _recent_records(records: Any, limit: int = 24) -> list[dict[str, Any]]:
    if not isinstance(records, list):
        return []
    normalized = [item for item in records if isinstance(item, dict)]
    return normalized[-limit:]


def _record_run_timing(log_dir: Path, metric_name: str, elapsed_ms: float, *, extra: dict[str, Any] | None = None) -> dict[str, Any]:
    meta = _read_real_run_meta(log_dir)
    timings = meta.get("timings", {})
    if not isinstance(timings, dict):
        timings = {}
    metric = timings.get(metric_name, {})
    if not isinstance(metric, dict):
        metric = {}
    count = int(metric.get("count", 0) or 0) + 1
    total_ms = float(metric.get("totalMs", 0.0) or 0.0) + float(elapsed_ms)
    recent = _recent_records(metric.get("recent"))
    record = {"ms": round(float(elapsed_ms), 3), **(extra or {})}
    recent.append(record)
    metric.update(
        {
            "count": count,
            "totalMs": round(total_ms, 3),
            "avgMs": round(total_ms / count, 3),
            "maxMs": round(max(float(metric.get("maxMs", 0.0) or 0.0), float(elapsed_ms)), 3),
            "lastMs": round(float(elapsed_ms), 3),
            "recent": recent[-24:],
        }
    )
    timings[metric_name] = metric
    meta["timings"] = timings
    meta["updatedAt"] = datetime.now().isoformat(timespec="seconds")
    _write_real_run_meta(log_dir, meta)
    return metric


def _update_run_progress(log_dir: Path, **payload: Any) -> dict[str, Any]:
    meta = _read_real_run_meta(log_dir)
    progress = meta.get("progress", {})
    if not isinstance(progress, dict):
        progress = {}
    progress.update(payload)
    progress["updatedAt"] = datetime.now().isoformat(timespec="seconds")
    meta["progress"] = progress
    meta["updatedAt"] = progress["updatedAt"]
    _write_real_run_meta(log_dir, meta)
    return progress


def _normalize_node_list(raw_nodes: Any) -> list[dict[str, Any]]:
    if not isinstance(raw_nodes, list):
        return []
    return [node for node in raw_nodes if isinstance(node, dict)]


def _user_guidance_text(prompt: str) -> str:
    normalized = str(prompt or "").strip()
    if not normalized:
        return ""
    return f"User guidance:\n{normalized}"


def _selected_nodes_guidance(selected_nodes: list[dict[str, Any]]) -> str:
    if not selected_nodes:
        return ""
    lines = [
        "Selected candidate algorithms from the current solution network:",
    ]
    for index, node in enumerate(selected_nodes[:8], start=1):
        sample_order = node.get("sampleOrder", "?")
        score = node.get("rawScore", node.get("score", "?"))
        operator = node.get("operator", "?")
        summary = str(node.get("algorithm", "") or node.get("algorithmSummary", "")).strip()
        function_preview = str(node.get("functionPreview", "") or "").strip()
        snippet = ""
        if function_preview:
            snippet = function_preview[:320].replace("\r", "")
        lines.append(f"{index}. Sample {sample_order}, raw_score={score}, operator={operator}: {summary[:240]}")
        if snippet:
            lines.append(f"   Function sketch:\n{snippet}")
    lines.append("Prefer exploring around these selected candidates while still proposing diverse variants.")
    return "\n".join(lines)


def _selected_seed_candidates(selected_nodes: list[dict[str, Any]]) -> list[dict[str, Any]]:
    ranked: list[tuple[float, int, dict[str, Any]]] = []
    for index, node in enumerate(selected_nodes):
        function_preview = str(node.get("functionPreview", "") or "").strip()
        if not function_preview or "def pack_circles" not in function_preview:
            continue
        raw_score = node.get("rawScore", node.get("score"))
        try:
            score_value = float(raw_score)
        except (TypeError, ValueError):
            score_value = float("-inf")
        ranked.append((score_value, -index, node))

    ranked.sort(reverse=True)
    picked: list[dict[str, Any]] = []
    seen_functions: set[str] = set()
    for _, _, node in ranked:
        function_preview = str(node.get("functionPreview", "") or "").strip()
        if function_preview in seen_functions:
            continue
        seen_functions.add(function_preview)
        picked.append(node)
        if len(picked) >= 4:
            break
    return picked


def _distinct_function_nodes(selected_nodes: list[dict[str, Any]]) -> list[dict[str, Any]]:
    picked: list[dict[str, Any]] = []
    seen_functions: set[str] = set()
    for node in selected_nodes:
        function_preview = str(node.get("functionPreview", "") or "").strip()
        if not function_preview or "def pack_circles" not in function_preview:
            continue
        if function_preview in seen_functions:
            continue
        seen_functions.add(function_preview)
        picked.append(node)
    return picked


def _reference_nodes_block(selected_nodes: list[dict[str, Any]], *, heading: str, limit: int = 8) -> str:
    nodes = _distinct_function_nodes(selected_nodes)[:limit]
    if not nodes:
        return ""
    lines = [heading]
    for index, node in enumerate(nodes, start=1):
        sample_order = node.get("sampleOrder", "?")
        score = node.get("rawScore", node.get("score", "?"))
        operator = node.get("operator", "?")
        summary = str(node.get("algorithm", "") or node.get("algorithmSummary", "")).strip()
        function_preview = str(node.get("functionPreview", "") or "").strip()
        lines.append(f"Reference {index}: sample={sample_order}, raw_score={score}, operator={operator}")
        if summary:
            lines.append(f"Summary:\n{summary[:400]}")
        if function_preview:
            lines.append(f"Code:\n{function_preview[:2400]}")
    return "\n\n".join(lines)


def _normalize_real_model(model_name: Any) -> str:
    model = str(model_name or "").strip()
    if not model:
        return "glm-5.2"

    lowered = model.lower()
    # Vision-oriented variants tend to produce responses that EoH cannot parse into code.
    if lowered.endswith("v") or "vision" in lowered:
        return "glm-5.2"
    return model


def _resolve_real_api_key_with_source(explicit_key: Any) -> tuple[str, str]:
    api_key = str(explicit_key or "").strip()
    if api_key:
        return api_key, "form"

    for env_name in ("ZAI_API_KEY", "ZHIPUAI_API_KEY", "GLM_API_KEY"):
        env_key = os.getenv(env_name, "").strip()
        if env_key:
            return env_key, f"env:{env_name}"
    return "", "missing"


def _resolve_real_api_key(explicit_key: Any) -> str:
    api_key, _ = _resolve_real_api_key_with_source(explicit_key)
    return api_key


def probe_real_llm(llm_config: dict[str, Any]) -> dict[str, Any]:
    import sys

    sys.path.insert(0, str(REPO_ROOT))
    from llm4ad.tools.llm.zhipu_ai import ZhipuAiAPI

    requested_model = str(llm_config.get("model", "glm-5.2")).strip() or "glm-5.2"
    actual_model = _normalize_real_model(requested_model)
    api_key, key_source = _resolve_real_api_key_with_source(llm_config.get("key", ""))
    if not api_key:
        raise RuntimeError("API key not provided. Please fill the form or set ZAI_API_KEY / ZHIPUAI_API_KEY / GLM_API_KEY.")

    timeout_seconds = max(10, int(llm_config.get("timeout", 60)))
    max_tokens = max(256, int(llm_config.get("max_tokens", 1536)))
    base_url = str(llm_config.get("host", "https://open.bigmodel.cn/api/paas/v4/")).strip()

    llm_kwargs: dict[str, Any] = {
        "api_key": api_key,
        "model": actual_model,
        "timeout": timeout_seconds,
        "max_tokens": max_tokens,
    }
    if base_url:
        llm_kwargs["base_url"] = base_url

    llm = ZhipuAiAPI(**llm_kwargs)
    response = _draw_sample_with_timeout(
        llm,
        "Reply with exactly one short line: OK",
        max(15, timeout_seconds + 5),
    )
    preview = " ".join(str(response).strip().split())
    if not preview:
        raise RuntimeError("LLM returned an empty response.")

    return {
        "ok": True,
        "requestedModel": requested_model,
        "actualModel": actual_model,
        "baseUrl": base_url,
        "timeoutSeconds": timeout_seconds,
        "maxTokens": max_tokens,
        "keySource": key_source,
        "responsePreview": preview[:200],
    }


def _write_runner_error(config_path: Path, error: BaseException) -> None:
    run_dir = config_path.parent
    error_path = run_dir / "runner_error.log"
    message = "".join(traceback.format_exception(type(error), error, error.__traceback__))
    error_path.write_text(message, encoding="utf-8")
    # #region debug-point E:runner-error
    _debug_report("E", "runner.py:_write_runner_error", "runner error captured", {"run_dir": str(run_dir), "error": str(error)[:500]})
    # #endregion


def _has_generated_samples(log_dir: Path) -> bool:
    samples_dir = log_dir / "samples"
    if not samples_dir.exists():
        return False
    return any(samples_dir.glob("samples_*.json"))


def _draw_sample_with_timeout(llm: Any, prompt: str, timeout_seconds: int) -> str:
    done = threading.Event()
    result: dict[str, Any] = {}

    def _worker() -> None:
        try:
            result["value"] = llm.draw_sample(prompt)
        except BaseException as error:
            result["error"] = error
        finally:
            done.set()

    worker = threading.Thread(target=_worker, name="llm-draw-sample", daemon=True)
    worker.start()
    if not done.wait(timeout_seconds):
        # #region debug-point B:draw-sample-timeout
        _debug_report(
            "B",
            "runner.py:_draw_sample_with_timeout",
            "llm draw_sample timed out",
            {"timeout_seconds": timeout_seconds, "prompt_size": len(prompt)},
        )
        # #endregion
        raise TimeoutError(
            f"LLM request timed out after {timeout_seconds} seconds. "
            "Please check API key, network access, model availability, or lower the timeout."
        )
    if "error" in result:
        error = result["error"]
        # #region debug-point B:draw-sample-error
        _debug_report(
            "B",
            "runner.py:_draw_sample_with_timeout",
            "llm draw_sample raised error",
            {
                "error_type": type(error).__name__,
                "error_message": str(error)[:500],
                "prompt_size": len(prompt),
            },
        )
        # #endregion
        raise result["error"]
    value = str(result.get("value", ""))
    # #region debug-point B:draw-sample-success
    _debug_report(
        "B",
        "runner.py:_draw_sample_with_timeout",
        "llm draw_sample returned",
        {"response_len": len(value), "response_preview": value[:300], "prompt_size": len(prompt)},
    )
    # #endregion
    return value


def _parse_sampler_response(response: str, template_program: str) -> tuple[str | None, Any | None]:
    from llm4ad.base import SampleTrimmer
    from llm4ad.method.eoh.sampler import EoHSampler

    thought = EoHSampler.trim_thought_from_response(response)
    code = SampleTrimmer.trim_preface_of_function(response)
    function = SampleTrimmer.sample_to_function(code, template_program)
    if thought is None and function is not None:
        thought = "{No high-level summary provided by the model.}"
    return thought, function


def _direct_generation_prompt(
    task_description: str,
    template_function: Any,
    *,
    user_prompt: str,
    reference_nodes: list[dict[str, Any]],
    attempt_index: int,
    total_attempts: int,
) -> str:
    temp_func = copy.deepcopy(template_function)
    temp_func.body = ""
    prompt_parts = [
        task_description,
        "You are not running an EOH operator this time.",
        "Your task is to directly propose one strong new algorithm for this problem.",
    ]
    guidance_text = _user_guidance_text(user_prompt)
    if guidance_text:
        prompt_parts.append(guidance_text)
    reference_block = _reference_nodes_block(
        reference_nodes,
        heading="Historical reference algorithms chosen by the user:",
    )
    if reference_block:
        prompt_parts.append(reference_block)
    prompt_parts.append(
        (
            f"This is proposal {attempt_index} of {total_attempts}. "
            "It should be meaningfully different from previous references, not a trivial rewrite."
        )
    )
    prompt_parts.append(
        "\n".join(
            [
                "Output requirements:",
                "1. First, describe your new algorithm and main steps in one sentence inside boxed {}.",
                "2. Next, implement exactly the following Python function signature.",
                "3. Keep the function name and arguments unchanged.",
                "4. Do not output any explanation outside the boxed summary and the function code.",
                str(temp_func),
            ]
        )
    )
    return "\n\n".join(part for part in prompt_parts if part)


def _sample_file_for_order(log_dir: Path, sample_order: int) -> Path:
    file_index = (sample_order - 1) // 200
    lower = file_index * 200 + 1
    upper = (file_index + 1) * 200
    return log_dir / "samples" / f"samples_{lower}~{upper}.json"


def _persist_sample_record(log_dir: Path, sample_order: int, payload: dict[str, Any]) -> None:
    content = {"sample_order": sample_order, **payload}
    _append_json_record(_sample_file_for_order(log_dir, sample_order), content)


def _llm_from_config(llm_config: dict[str, Any]) -> Any:
    from llm4ad.tools.llm.zhipu_ai import ZhipuAiAPI

    api_key = _resolve_real_api_key(llm_config.get("key", ""))
    model_name = _normalize_real_model(llm_config.get("model", "glm-5.2"))
    llm_kwargs: dict[str, Any] = {
        "model": model_name,
        "timeout": int(llm_config.get("timeout", 60)),
        "max_tokens": max(256, int(llm_config.get("max_tokens", 1536))),
    }
    base_url = str(llm_config.get("host", "https://open.bigmodel.cn/api/paas/v4/")).strip()
    if base_url:
        llm_kwargs["base_url"] = base_url
    if not api_key:
        raise RuntimeError("未提供可用的 API Key。请在表单中填写 API Key，或在环境变量中设置 ZAI_API_KEY / ZHIPUAI_API_KEY / GLM_API_KEY。")
    if api_key:
        llm_kwargs["api_key"] = api_key
    return ZhipuAiAPI(**llm_kwargs)


def _platform_secure_evaluator(task: Any) -> Any:
    from llm4ad.base import SecureEvaluator

    return SecureEvaluator(task, debug_mode=False)


def _evaluate_generated_function(task: Any, function: Any) -> tuple[float | None, float, str]:
    from llm4ad.base import TextFunctionProgramConverter

    program = TextFunctionProgramConverter.function_to_program(function, task.template_program)
    if program is None:
        return None, 0.0, ""
    evaluator = _platform_secure_evaluator(task)
    score, eval_time = evaluator.evaluate_program_record_time(program)
    return score, eval_time, str(program)


def _close_llm(llm: Any) -> None:
    close_fn = getattr(llm, "close", None)
    if callable(close_fn):
        close_fn()


class _TimeoutWrappedLLM:
    """Enforce request timeouts for EOH sampler calls."""

    def __init__(self, inner: Any, timeout_seconds: int):
        self._inner = inner
        self._timeout_seconds = max(15, int(timeout_seconds))

    def __getattr__(self, item: str) -> Any:
        return getattr(self._inner, item)

    def draw_sample(self, prompt: str | Any, *args: Any, **kwargs: Any) -> str:
        return _draw_sample_with_timeout(self._inner, prompt, self._timeout_seconds)

    def draw_samples(self, prompts: list[str | Any], *args: Any, **kwargs: Any) -> list[str]:
        return [self.draw_sample(prompt, *args, **kwargs) for prompt in prompts]

    def close(self) -> None:
        _close_llm(self._inner)


def _load_circle_packing_evaluation():
    evaluation_path = REPO_ROOT / "example" / "tasks" / "circle_packing" / "EoH_settings&logs" / "evaluation.py"
    import sys

    sys.path.insert(0, str(evaluation_path.parent))
    spec = importlib.util.spec_from_file_location("platform_circle_packing_evaluation", evaluation_path)
    if spec is None or spec.loader is None:
        raise RuntimeError("Unable to load Circle Packing evaluation module.")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module.CirclePackingEvaluation


def _build_circle_packing_seed_function() -> str:
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


def run_real(config: dict[str, Any]) -> None:
    import sys

    sys.path.insert(0, str(REPO_ROOT))

    from llm4ad.method.eoh import EoH
    from llm4ad.method.eoh.profiler import EoHProfiler

    class PlatformEoHProfiler(EoHProfiler):
        def _write_json(self, function: Any, program: str = "", *, record_type: str = "history", record_sep: int = 200) -> None:
            if not self._log_dir:
                return
            sample_order = self._num_samples
            content = {
                "sample_order": sample_order,
                "algorithm": getattr(function, "algorithm", ""),
                "function": str(function),
                "score": getattr(function, "score", None),
                "operator": getattr(function, "operator", ""),
                "program": program,
            }
            if record_type == "history":
                lower_bound = ((sample_order - 1) // record_sep) * record_sep
                upper_bound = lower_bound + record_sep
                filename = f"samples_{lower_bound + 1}~{upper_bound}.json"
            else:
                filename = "samples_best.json"
            path = Path(self._samples_json_dir) / filename
            try:
                with path.open("r", encoding="utf-8") as handle:
                    data = json.load(handle)
            except (OSError, json.JSONDecodeError):
                data = []
            data.append(content)
            with path.open("w", encoding="utf-8") as handle:
                json.dump(data, handle, indent=2, ensure_ascii=True)
            if record_type == "history":
                eval_time = getattr(function, "evaluate_time", None)
                if isinstance(eval_time, (int, float)):
                    _record_run_timing(
                        Path(self._log_dir),
                        "sampleEvaluationMs",
                        float(eval_time) * 1000.0,
                        extra={"sampleOrder": sample_order, "operator": str(getattr(function, "operator", "") or "")},
                    )
                sample_time = getattr(function, "sample_time", None)
                if isinstance(sample_time, (int, float)):
                    _record_run_timing(
                        Path(self._log_dir),
                        "sampleGenerationMs",
                        float(sample_time) * 1000.0,
                        extra={"sampleOrder": sample_order, "operator": str(getattr(function, "operator", "") or "")},
                    )
                _update_run_progress(
                    Path(self._log_dir),
                    phase="sampling",
                    phaseLabel="样本评估中",
                    sampleCount=sample_order,
                    lastSampleOrder=sample_order,
                    lastOperator=str(getattr(function, "operator", "") or ""),
                    lastScore=getattr(function, "score", None),
                    currentGeneration=self._cur_gen,
                )

        def register_population(self, pop: Any) -> None:
            previous_generation = self._cur_gen
            super().register_population(pop)
            if not self._log_dir:
                return
            if getattr(pop, "generation", previous_generation) != previous_generation:
                _update_run_progress(
                    Path(self._log_dir),
                    phase="eoh_running",
                    phaseLabel="EOH 演化中",
                    currentGeneration=getattr(pop, "generation", previous_generation),
                    populationSize=len(getattr(pop, "population", []) or []),
                )

        def finish(self) -> None:
            try:
                super().finish()
            except AttributeError:
                pass
            _mark_finished(Path(self._log_dir))
            _update_run_progress(Path(self._log_dir), phase="finished", phaseLabel="已完成")

    CirclePackingEvaluation = _load_circle_packing_evaluation()

    log_dir = Path(config["log_dir"])
    llm_config = config.get("llm", {})
    method_config = config.get("method", {})
    prompt = str(config.get("prompt", "")).strip()
    selected_nodes = _normalize_node_list(config.get("selected_nodes", []))
    reference_nodes = _normalize_node_list(config.get("reference_nodes", []))
    initial_population_nodes = _normalize_node_list(config.get("initial_population_nodes", []))
    run_label = str(config.get("run_id", "pre-fix"))
    mode = str(config.get("mode", "seeded_eoh") or "seeded_eoh").strip()

    # #region debug-point A:run-real-entry
    _debug_report(
        "A",
        "runner.py:run_real:entry",
        "entered run_real",
        {
            "run_id": run_label,
            "log_dir": str(log_dir),
            "model": llm_config.get("model"),
            "timeout": llm_config.get("timeout"),
            "method": method_config,
            "selected_count": len(selected_nodes),
            "prompt_len": len(prompt),
        },
        run_id=run_label,
    )
    # #endregion

    task_kwargs: dict[str, Any] = {
        "timeout_seconds": int(method_config.get("timeout_seconds", 120)),
    }
    _update_run_progress(
        log_dir,
        phase="boot",
        phaseLabel="初始化运行上下文",
        mode=mode,
        promptLength=len(prompt),
        selectedNodeCount=len(selected_nodes),
        referenceNodeCount=len(reference_nodes),
        initialPopulationNodeCount=len(initial_population_nodes),
    )
    if os.name == "nt":
        # The visual platform already runs inside a subprocess. On Windows,
        # nested safe-evaluation worker processes can fail with WinError 6
        # when spawning from this runner context, which turns every score into
        # None. Use in-process evaluation here so real mode can complete.
        task_kwargs["safe_evaluate"] = False
    task = CirclePackingEvaluation(**task_kwargs)
    llm = _llm_from_config(llm_config)
    model_name = _normalize_real_model(llm_config.get("model", "glm-5.2"))
    base_url = str(llm_config.get("host", "https://open.bigmodel.cn/api/paas/v4/")).strip()
    api_key = _resolve_real_api_key(llm_config.get("key", ""))
    # #region debug-point A:llm-init
    _debug_report(
        "A",
        "runner.py:run_real:llm-init",
        "llm initialized",
        {"run_id": run_label, "resolved_model": model_name, "has_key": bool(api_key), "base_url": base_url},
        run_id=run_label,
    )
    # #endregion

    try:
        if mode == "direct_ai":
            from llm4ad.base import TextFunctionProgramConverter

            template_function = TextFunctionProgramConverter.text_to_function(task.template_program)
            if template_function is None:
                raise RuntimeError("Unable to load the circle packing template function.")
            resolved_method = _resolved_method_config(method_config)
            total_attempts = resolved_method["max_sample_nums"]
            valid_sample_count = 0
            persisted_samples: list[dict[str, Any]] = []
            _update_run_progress(
                log_dir,
                phase="direct_ai_sampling",
                phaseLabel="AI 直接生成中",
                totalAttempts=total_attempts,
                completedAttempts=0,
            )
            for sample_order in range(1, total_attempts + 1):
                sample_started_at = time.perf_counter()
                _update_run_progress(
                    log_dir,
                    phase="direct_ai_sampling",
                    phaseLabel="AI 直接生成中",
                    totalAttempts=total_attempts,
                    currentAttempt=sample_order,
                    completedAttempts=sample_order - 1,
                )
                prompt_text = _direct_generation_prompt(
                    task.task_description,
                    template_function,
                    user_prompt=prompt,
                    reference_nodes=reference_nodes or selected_nodes,
                    attempt_index=sample_order,
                    total_attempts=total_attempts,
                )
                response = _draw_sample_with_timeout(llm, prompt_text, max(15, int(llm_config.get("timeout", 60)) + 5))
                thought, func = _parse_sampler_response(response, task.template_program)
                sample_payload: dict[str, Any]
                if thought is None or func is None:
                    sample_payload = {
                        "algorithm": "{LLM response could not be parsed into a valid function.}",
                        "function": "",
                        "program": "",
                        "score": None,
                        "operator": "direct_ai_parse_failed",
                    }
                else:
                    score, eval_time, program_text = _evaluate_generated_function(task, func)
                    if program_text:
                        sample_payload = {
                            "algorithm": thought,
                            "function": str(func),
                            "program": program_text,
                            "score": score,
                            "operator": "direct_ai",
                        }
                        if score is not None and not (isinstance(score, float) and score == float("-inf")):
                            valid_sample_count += 1
                    else:
                        sample_payload = {
                            "algorithm": "{Generated function could not be converted into an executable program.}",
                            "function": str(func),
                            "program": "",
                            "score": None,
                            "operator": "direct_ai_program_failed",
                        }
                    sample_payload["evaluate_time"] = eval_time
                _persist_sample_record(log_dir, sample_order, sample_payload)
                persisted_samples.append({"sample_order": sample_order, **sample_payload})
                elapsed_ms = round((time.perf_counter() - sample_started_at) * 1000.0, 3)
                _record_run_timing(log_dir, "directAiAttemptMs", elapsed_ms, extra={"attempt": sample_order})
                _update_run_progress(
                    log_dir,
                    phase="direct_ai_sampling",
                    phaseLabel="AI 直接生成中",
                    totalAttempts=total_attempts,
                    currentAttempt=sample_order,
                    completedAttempts=sample_order,
                    lastAttemptMs=elapsed_ms,
                    lastScore=sample_payload.get("score"),
                )
            population = sorted(
                persisted_samples,
                key=lambda item: float(item["score"]) if item.get("score") is not None else float("-inf"),
                reverse=True,
            )[: max(1, min(len(persisted_samples), resolved_method["pop_size"]))]
            _write_population_snapshot(log_dir, 1, population)
            _write_real_run_meta(
                log_dir,
                {
                    "mode": "direct_ai",
                    "referenceNodesCount": len(reference_nodes or selected_nodes),
                    "promptLength": len(prompt),
                    "sampleCount": total_attempts,
                    "validSampleCount": valid_sample_count,
                },
            )
            _mark_finished(log_dir)
            if valid_sample_count <= 0:
                raise RuntimeError(
                    "AI 直接生成没有产生任何可行算法。请调整提示词、候选参考或模型设置后重试。"
                )
            return

        guidance_text = _user_guidance_text(prompt)
        if guidance_text:
            task.task_description = f"{task.task_description}\n\n{guidance_text}"

        seed_nodes = _distinct_function_nodes(initial_population_nodes or selected_nodes)
        if not seed_nodes:
            raise RuntimeError("初始种群为空。请先把节点加入“初始种群”后再运行 EOH。")

        resolved_method = _resolved_method_config(method_config)
        resolved_method["pop_size"] = max(resolved_method["pop_size"], len(seed_nodes))
        resolved_method["max_sample_nums"] = max(
            resolved_method["max_sample_nums"],
            resolved_method["pop_size"] * resolved_method["max_generations"],
        )
        sampler_llm = _TimeoutWrappedLLM(llm, max(15, int(llm_config.get("timeout", 60)) + 5))
        method = EoH(
            llm=sampler_llm,
            profiler=PlatformEoHProfiler(log_dir=str(log_dir), log_style="simple", create_random_path=False),
            evaluation=task,
            max_sample_nums=resolved_method["max_sample_nums"],
            max_generations=resolved_method["max_generations"],
            pop_size=resolved_method["pop_size"],
            num_samplers=resolved_method["num_samplers"],
            num_evaluators=resolved_method["num_evaluators"],
            resume_mode=True,
            debug_mode=False,
        )
        selected_seeded = 0
        _update_run_progress(
            log_dir,
            phase="initial_population",
            phaseLabel="初始化种群评估中",
            initialPopulationCount=len(seed_nodes),
            completedSeedCount=0,
            acceptedSeedCount=0,
            currentGeneration=0,
        )
        for index, node in enumerate(seed_nodes, start=1):
            function_preview = str(node.get("functionPreview", "") or "").strip()
            raw_score = node.get("rawScore", node.get("score", "?"))
            sample_order = node.get("sampleOrder", "?")
            summary = str(node.get("algorithm", "") or node.get("algorithmSummary", "")).strip()
            operator = str(node.get("operator", "") or "initial_population").strip() or "initial_population"
            _update_run_progress(
                log_dir,
                phase="initial_population",
                phaseLabel="初始化种群评估中",
                initialPopulationCount=len(seed_nodes),
                currentSeedIndex=index,
                currentSeedSampleOrder=sample_order,
                currentSeedScore=raw_score,
                currentSeedSummary=summary[:160],
                completedSeedCount=index - 1,
                acceptedSeedCount=selected_seeded,
            )
            seed_started_at = time.perf_counter()
            numeric_raw_score = float(raw_score) if isinstance(raw_score, (int, float)) and math.isfinite(float(raw_score)) else None
            if function_preview and numeric_raw_score is not None:
                seeded_ok = method.register_prescored_seed_function(
                    function_preview,
                    score=numeric_raw_score,
                    algorithm=(
                        "{User selected historical candidate reused as an explicit initial population member without re-evaluation. "
                        f"sample={sample_order}, raw_score={raw_score}, summary={summary[:240]}"
                        "}"
                    ),
                    operator=f"selected_{operator}",
                )
                timing_name = "seedRegistrationMs"
            else:
                seeded_ok = method.register_seed_function(
                    function_preview,
                    algorithm=(
                        "{User selected historical candidate used as an explicit initial population member. "
                        f"sample={sample_order}, raw_score={raw_score}, summary={summary[:240]}"
                        "}"
                    ),
                    operator=f"selected_{operator}",
                )
                timing_name = "seedEvaluationMs"
            elapsed_ms = round((time.perf_counter() - seed_started_at) * 1000.0, 3)
            _record_run_timing(
                log_dir,
                timing_name,
                elapsed_ms,
                extra={"sampleOrder": sample_order, "accepted": bool(seeded_ok), "reusedScore": timing_name == "seedRegistrationMs"},
            )
            if seeded_ok:
                selected_seeded += 1
            _update_run_progress(
                log_dir,
                phase="initial_population",
                phaseLabel="初始化种群评估中",
                initialPopulationCount=len(seed_nodes),
                currentSeedIndex=index,
                currentSeedSampleOrder=sample_order,
                completedSeedCount=index,
                acceptedSeedCount=selected_seeded,
                lastSeedElapsedMs=elapsed_ms,
                lastSeedAccepted=bool(seeded_ok),
                lastSeedReusedScore=timing_name == "seedRegistrationMs",
                lastCompletedSeedSampleOrder=sample_order,
            )
        _write_real_run_meta(
            log_dir,
            {
                "mode": "seeded_eoh",
                "initialPopulationCount": len(seed_nodes),
                "registeredSeedCount": selected_seeded,
                "promptLength": len(prompt),
                "guidanceApplied": bool(guidance_text),
            },
        )
        if selected_seeded <= 0:
            raise RuntimeError("指定的初始种群都没有通过评估，无法启动 EOH。")
        if len(method._population) == 0 and len(method._population._next_gen_pop) > 0:
            method._population.survival()
        _update_run_progress(
            log_dir,
            phase="eoh_running",
            phaseLabel="EOH 演化中",
            initialPopulationCount=len(seed_nodes),
            completedSeedCount=len(seed_nodes),
            acceptedSeedCount=selected_seeded,
            currentGeneration=getattr(method._population, "generation", 0),
            populationSize=len(getattr(method._population, "population", []) or []),
        )
        # #region debug-point B:eoh-run-start
        _debug_report(
            "B",
            "runner.py:run_real:eoh-run-start",
            "starting EoH.run",
            {"run_id": run_label, "selected_seeded": selected_seeded, "mode": "seeded_eoh"},
            run_id=run_label,
        )
        # #endregion
        method.run()
        # #region debug-point B:eoh-run-done
        _debug_report(
            "B",
            "runner.py:run_real:eoh-run-done",
            "EoH.run returned",
            {"run_id": run_label, "has_samples": _has_generated_samples(log_dir), "mode": "seeded_eoh"},
            run_id=run_label,
        )
        # #endregion
        if not _has_generated_samples(log_dir):
            raise RuntimeError(
                f"Real mode finished without producing any valid samples. "
                f"Requested model='{llm_config.get('model', '')}', actual model='{model_name}'. "
                "This usually means the API response could not be parsed into valid code, "
                "the model is unsuitable for code generation, or the API key/request failed."
            )
    finally:
        _close_llm(llm)


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--config", required=True, help="Path to the run config json file.")
    args = parser.parse_args()

    config_path = Path(args.config)
    with config_path.open("r", encoding="utf-8") as handle:
        config = json.load(handle)

    exit_code = 0
    try:
        mode = str(config.get("mode", "direct_ai") or "direct_ai").strip()
        if mode in {"real", "seeded_eoh", "direct_ai"}:
            run_real(config)
        else:
            raise RuntimeError(f"Unsupported mode '{mode}'. Supported modes: direct_ai, seeded_eoh.")
    except Exception as error:
        exit_code = 1
        _write_runner_error(config_path, error)
        raise
    finally:
        # Some LLM SDKs keep background worker threads alive after the run has
        # already persisted samples and the end marker. Force this subprocess to
        # terminate so the web app can observe the run as finished.
        sys.stdout.flush()
        sys.stderr.flush()
        os._exit(exit_code)


if __name__ == "__main__":
    main()
