from __future__ import annotations

import os
from typing import Any

_LLM_TIMEOUT_SPEC_ATTR = "_vp_llm_timeout_spec"


def normalize_real_model(model_name: Any) -> str:
    # Provider-agnostic: the model name is whatever the user typed for their
    # chosen OpenAI-compatible endpoint. We only trim surrounding whitespace.
    return str(model_name or "").strip()


def resolve_real_api_key_with_source(explicit_key: Any) -> tuple[str, str]:
    api_key = str(explicit_key or "").strip()
    if api_key:
        return api_key, "form"

    for env_name in (
        "ZAI_API_KEY",
        "ZHIPUAI_API_KEY",
        "GLM_API_KEY",
        "DEEPSEEK_API_KEY",
        "API_KEY",
        "OPENAI_API_KEY",
    ):
        env_key = os.getenv(env_name, "").strip()
        if env_key:
            return env_key, f"env:{env_name}"

    # 持久化凭据文件兜底（~/.config/deepseek/api_key，权限 600）
    try:
        cred_path = os.path.expanduser("~/.config/deepseek/api_key")
        with open(cred_path, "r", encoding="utf-8") as cred_file:
            cred_key = cred_file.read().strip()
        if cred_key:
            return cred_key, f"file:{cred_path}"
    except OSError:
        pass
    return "", "missing"


def resolve_real_api_key(explicit_key: Any) -> str:
    api_key, _ = resolve_real_api_key_with_source(explicit_key)
    return api_key


def build_llm_timeout_spec(factory_module: str, factory_name: str, init_kwargs: dict[str, Any]) -> dict[str, Any]:
    return {
        "factory_module": str(factory_module).strip(),
        "factory_name": str(factory_name).strip(),
        "init_kwargs": dict(init_kwargs),
    }


def build_zhipu_llm_timeout_spec(
    *,
    api_key: str,
    model: str,
    timeout: int,
    max_tokens: int,
    base_url: str,
) -> dict[str, Any]:
    return build_llm_timeout_spec(
        "llm4ad.tools.llm.zhipu_ai",
        "ZhipuAiAPI",
        {
            "api_key": api_key,
            "model": model,
            "timeout": int(timeout),
            "max_tokens": int(max_tokens),
            "base_url": base_url,
        },
    )


def build_openai_llm_timeout_spec(
    *,
    base_url: str,
    api_key: str,
    model: str,
    timeout: int,
    max_tokens: int,
    thinking: Any = None,
) -> dict[str, Any]:
    """Timeout spec for the provider-agnostic OpenAI-compatible client.

    The subprocess LLM worker reconstructs the client from this spec, so it must
    carry every field required by ``create_openai_compatible_llm``.
    """
    return build_llm_timeout_spec(
        "visual_platform.runtime.openai_llm",
        "create_openai_compatible_llm",
        {
            "base_url": base_url,
            "api_key": api_key,
            "model": model,
            "timeout": int(timeout),
            "max_tokens": int(max_tokens),
            "thinking": thinking,
        },
    )


def attach_llm_timeout_spec(llm: Any, spec: dict[str, Any]) -> Any:
    setattr(llm, _LLM_TIMEOUT_SPEC_ATTR, dict(spec))
    return llm


def get_llm_timeout_spec(llm: Any) -> dict[str, Any] | None:
    spec = getattr(llm, _LLM_TIMEOUT_SPEC_ATTR, None)
    if not isinstance(spec, dict):
        return None

    factory_module = str(spec.get("factory_module", "")).strip()
    factory_name = str(spec.get("factory_name", "")).strip()
    init_kwargs = spec.get("init_kwargs")
    if not factory_module or not factory_name or not isinstance(init_kwargs, dict):
        return None
    return {
        "factory_module": factory_module,
        "factory_name": factory_name,
        "init_kwargs": dict(init_kwargs),
    }
