from __future__ import annotations

import re
from pathlib import Path
from typing import Any, Callable

from visual_platform.llm.support import (
    attach_llm_timeout_spec,
    build_openai_llm_timeout_spec,
    normalize_real_model as runtime_normalize_real_model,
    resolve_real_api_key_with_source as runtime_resolve_real_api_key_with_source,
)
from visual_platform.runtime.runner_llm import (
    close_llm,
    draw_sample_with_timeout as runtime_draw_sample_with_timeout,
)

_TRANSLATION_CACHE: dict[str, str] = {}


def translate_algorithm_cache_key(text: str, llm_config: dict[str, Any]) -> str:
    requested_model = str(llm_config.get("model", "")).strip()
    base_url = str(llm_config.get("host", "") or llm_config.get("base_url", "")).strip()
    return f"{requested_model}|{base_url}|{text}"


def translate_algorithm_text(
    text: str,
    llm_config: dict[str, Any],
    *,
    translation_cache: dict[str, str] | None = None,
    base_dir_parent: Path | None = None,
    normalize_real_model: Callable[[str], str] = runtime_normalize_real_model,
    resolve_real_api_key_with_source: Callable[[str], tuple[str, str | None]] = runtime_resolve_real_api_key_with_source,
    draw_sample_with_timeout: Callable[[Any, str, int], str] = runtime_draw_sample_with_timeout,
) -> str:
    del base_dir_parent
    source = str(text or "").strip()
    if not source:
        return ""
    if re.search(r"[\u4e00-\u9fff]", source):
        return source

    if source.startswith("{") and source.endswith("}"):
        source = source[1:-1].strip()

    exact_replacements = {
        "No high-level summary provided by the model.": "模型未提供高层摘要。",
        "Fallback deterministic grid baseline injected by the visual platform to guarantee a feasible initializer.": "由可视化平台注入的确定性网格保底基线，用于保证初始化阶段至少存在一个可行解。",
        "LLM response could not be parsed into a valid function.": "LLM 响应无法解析为有效函数。",
        "Generated function could not be converted into an executable program.": "生成的函数无法转换为可执行程序。",
    }
    if source in exact_replacements:
        return exact_replacements[source]

    cache = translation_cache if isinstance(translation_cache, dict) else _TRANSLATION_CACHE

    cache_key = translate_algorithm_cache_key(source, llm_config)
    cached = cache.get(cache_key)
    if cached:
        return cached

    from visual_platform.runtime.openai_llm import create_openai_compatible_llm

    requested_model = str(llm_config.get("model", "")).strip()
    actual_model = normalize_real_model(requested_model)
    api_key, _ = resolve_real_api_key_with_source(llm_config.get("key", ""))
    base_url = str(llm_config.get("host", "") or llm_config.get("base_url", "")).strip()
    if not api_key:
        raise RuntimeError("未提供可用的 API Key，无法翻译算法说明。")
    if not base_url:
        raise RuntimeError("未提供 API Base URL，无法翻译算法说明。")
    if not actual_model:
        raise RuntimeError("未提供模型名称，无法翻译算法说明。")

    timeout_seconds = max(10, int(llm_config.get("timeout", 60)))
    max_tokens = max(256, int(llm_config.get("max_tokens", 512)))

    prompt = (
        "请将下面这段英文算法说明翻译成自然、简洁、准确的中文。"
        "必须保留原文中的具体策略、步骤和侧重点，不要泛化，不要补充原文没有的信息，"
        "不要解释，不要加标题，不要使用项目符号，只输出中文译文。\n\n"
        f"英文算法说明：\n{source}"
    )

    llm = create_openai_compatible_llm(
        base_url=base_url,
        api_key=api_key,
        model=actual_model,
        timeout=timeout_seconds,
        max_tokens=max_tokens,
    )
    attach_llm_timeout_spec(
        llm,
        build_openai_llm_timeout_spec(
            base_url=base_url,
            api_key=api_key,
            model=actual_model,
            timeout=timeout_seconds,
            max_tokens=max_tokens,
        ),
    )
    try:
        translated = draw_sample_with_timeout(llm, prompt, max(15, timeout_seconds + 5)).strip()
    finally:
        close_llm(llm)

    translated = translated.strip().strip("`").strip()
    if not translated:
        raise RuntimeError("模型返回了空的翻译结果。")

    cache[cache_key] = translated
    return translated
