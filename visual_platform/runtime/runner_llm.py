from __future__ import annotations

import builtins
import importlib
import json
import subprocess
import sys
from typing import Any

from visual_platform.llm.support import (
    attach_llm_timeout_spec,
    build_llm_timeout_spec,
    build_openai_llm_timeout_spec,
    build_zhipu_llm_timeout_spec,
    get_llm_timeout_spec,
    normalize_real_model,
    resolve_real_api_key,
    resolve_real_api_key_with_source,
)
_LLM_CALL_WORKER_MODULE = "visual_platform.runtime.llm_call_worker"


def instantiate_llm_from_timeout_spec(spec: dict[str, Any]) -> Any:
    module = importlib.import_module(spec["factory_module"])
    factory = getattr(module, spec["factory_name"])
    llm = factory(**dict(spec["init_kwargs"]))
    return attach_llm_timeout_spec(llm, spec)


def _terminate_llm_subprocess(process: subprocess.Popen[str]) -> dict[str, Any]:
    forced_kill = False
    terminate_error = ""
    recovered = False

    try:
        process.terminate()
    except OSError as error:
        terminate_error = str(error)

    try:
        process.wait(timeout=3)
        recovered = True
    except subprocess.TimeoutExpired:
        forced_kill = True
        process.kill()
        try:
            process.wait(timeout=3)
            recovered = True
        except subprocess.TimeoutExpired:
            recovered = False

    return {
        "pid": process.pid,
        "exitcode": process.returncode,
        "cancel_attempted": True,
        "cancel_succeeded": recovered,
        "forced_kill": forced_kill,
        "recovered": recovered,
        "terminate_error": terminate_error,
    }


def _restore_remote_error(payload: dict[str, Any]) -> BaseException:
    error_type_name = str(payload.get("error_type", "RuntimeError") or "RuntimeError")
    error_message = str(payload.get("error_message", "") or "")
    traceback_text = str(payload.get("traceback", "") or "").strip()
    note = f"\nRemote traceback:\n{traceback_text}" if traceback_text else ""
    candidate = getattr(builtins, error_type_name, RuntimeError)
    if isinstance(candidate, type) and issubclass(candidate, BaseException):
        try:
            return candidate(f"{error_message}{note}".strip())
        except Exception:
            pass
    return RuntimeError(f"{error_type_name}: {error_message}{note}".strip())


def draw_sample_with_timeout(llm: Any, prompt: str, timeout_seconds: int) -> str:
    import os
    from pathlib import Path
    from visual_platform.services.research_history import append_event
    directory=os.environ.get('VP_RESEARCH_HISTORY_DIR')
    call_id=None
    if directory:
        call_id=append_event(Path(directory),'llm_request',dict(prompt=str(prompt),timeoutSeconds=timeout_seconds))
    try:
        result=_draw_sample_with_timeout(llm,prompt,timeout_seconds)
    except BaseException as error:
        if directory:append_event(Path(directory),'llm_failure',dict(callId=call_id,errorType=type(error).__name__,error=str(error)))
        raise
    if directory:append_event(Path(directory),'llm_response',dict(callId=call_id,response=result))
    return result


def _draw_sample_with_timeout(llm: Any, prompt: str, timeout_seconds: int) -> str:
    spec = get_llm_timeout_spec(llm)
    if spec is None:
        raise RuntimeError(
            "LLM timeout isolation requires a registered timeout spec. "
            "Please create the LLM through llm_from_config() or attach_llm_timeout_spec()."
        )

    resolved_timeout = max(1, int(timeout_seconds))
    request_payload = json.dumps({"llm": spec, "prompt": prompt}, ensure_ascii=False)
    worker = subprocess.Popen(
        [sys.executable, "-m", _LLM_CALL_WORKER_MODULE],
        stdin=subprocess.PIPE,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        text=True,
        encoding="utf-8",
    )
    try:
        stdout, stderr = worker.communicate(request_payload, timeout=resolved_timeout)
    except subprocess.TimeoutExpired:
        recovery = _terminate_llm_subprocess(worker)
        raise TimeoutError(
            f"LLM request timed out after {resolved_timeout} seconds. "
            f"cancel_attempted={recovery['cancel_attempted']}, "
            f"cancel_succeeded={recovery['cancel_succeeded']}, "
            f"forced_kill={recovery['forced_kill']}, "
            f"recovered={recovery['recovered']}. "
            "Please check API key, network access, model availability, or lower the timeout."
        )

    if worker.returncode != 0 and not stdout.strip():
        error = RuntimeError(
            f"LLM subprocess exited with code {worker.returncode}. "
            f"stderr={stderr.strip()[:1000]}"
        )
        raise error

    try:
        payload = json.loads(stdout)
    except json.JSONDecodeError as error:
        raise RuntimeError(
            f"LLM subprocess returned invalid JSON: {str(error)}; "
            f"stdout={stdout[:500]!r}; stderr={stderr[:500]!r}"
        ) from error

    if not payload.get("ok", False):
        error = _restore_remote_error(payload)
        raise error

    value = str(payload.get("value", ""))
    return value


def close_llm(llm: Any) -> None:
    close_fn = getattr(llm, "close", None)
    if callable(close_fn):
        close_fn()


class TimeoutWrappedLLM:
    def __init__(self, inner: Any, timeout_seconds: int):
        self._inner = inner
        self._timeout_seconds = max(15, int(timeout_seconds))

    def __getattr__(self, item: str) -> Any:
        return getattr(self._inner, item)

    def draw_sample(self, prompt: str | Any, *args: Any, **kwargs: Any) -> str:
        return draw_sample_with_timeout(self._inner, prompt, self._timeout_seconds)

    def draw_samples(self, prompts: list[str | Any], *args: Any, **kwargs: Any) -> list[str]:
        return [self.draw_sample(prompt, *args, **kwargs) for prompt in prompts]

    def close(self) -> None:
        close_llm(self._inner)


def llm_from_config(llm_config: dict[str, Any]) -> Any:
    from visual_platform.runtime.openai_llm import create_openai_compatible_llm

    api_key = resolve_real_api_key(llm_config.get("key", ""))
    model_name = normalize_real_model(llm_config.get("model", ""))
    base_url = str(llm_config.get("host", "") or llm_config.get("base_url", "")).strip()
    timeout = int(llm_config.get("timeout", 120))
    max_tokens = max(256, int(llm_config.get("max_tokens", 4096)))
    thinking = llm_config.get("thinking")

    if not base_url:
        raise RuntimeError(
            "未提供 API Base URL。请在表单中填写形如 https://api.openai.com/v1 的 OpenAI 兼容接口地址。"
        )
    if not model_name:
        raise RuntimeError("未提供模型名称。请在表单中填写模型名，如 gpt-4o-mini、deepseek-chat、glm-4。")
    if not api_key:
        raise RuntimeError(
            "未提供可用的 API Key。请在表单中填写 API Key，或在环境变量中设置 "
            "OPENAI_API_KEY / API_KEY。"
        )

    llm = create_openai_compatible_llm(
        base_url=base_url,
        api_key=api_key,
        model=model_name,
        timeout=timeout,
        max_tokens=max_tokens,
        thinking=thinking,
    )
    attach_llm_timeout_spec(
        llm,
        build_openai_llm_timeout_spec(
            base_url=base_url,
            api_key=api_key,
            model=model_name,
            timeout=timeout,
            max_tokens=max_tokens,
            thinking=thinking,
        ),
    )
    return llm


def probe_real_llm(llm_config: dict[str, Any]) -> dict[str, Any]:
    requested_model = normalize_real_model(llm_config.get("model", ""))
    api_key, key_source = resolve_real_api_key_with_source(llm_config.get("key", ""))
    base_url = str(llm_config.get("host", "") or llm_config.get("base_url", "")).strip()

    if not base_url:
        raise RuntimeError("API Base URL not provided. Please fill the form with an OpenAI-compatible endpoint.")
    if not requested_model:
        raise RuntimeError("Model name not provided. Please fill the form.")
    if not api_key:
        raise RuntimeError("API key not provided. Please fill the form or set OPENAI_API_KEY / API_KEY.")

    timeout_seconds = max(10, int(llm_config.get("timeout", 120)))
    max_tokens = max(256, int(llm_config.get("max_tokens", 4096)))

    llm = llm_from_config(
        {
            **llm_config,
            "model": requested_model,
            "timeout": timeout_seconds,
            "max_tokens": max_tokens,
            "host": base_url,
        }
    )
    try:
        response = draw_sample_with_timeout(
            llm,
            "Reply with exactly one short line: OK",
            max(15, timeout_seconds + 5),
        )
    finally:
        close_llm(llm)

    preview = " ".join(str(response).strip().split())
    if not preview:
        raise RuntimeError("LLM returned an empty response.")

    return {
        "ok": True,
        "requestedModel": requested_model,
        "actualModel": requested_model,
        "baseUrl": base_url,
        "timeoutSeconds": timeout_seconds,
        "maxTokens": max_tokens,
        "keySource": key_source,
        "responsePreview": preview[:200],
    }
