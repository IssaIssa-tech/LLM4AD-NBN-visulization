from __future__ import annotations

import re
from typing import Any, Callable

from visual_platform.runtime.runner_llm import (
    close_llm,
    draw_sample_with_timeout as runtime_draw_sample_with_timeout,
    llm_from_config as runtime_llm_from_config,
)

# The circle-packing task exposes exactly one entry function. Keep this in sync
# with example/tasks/circle_packing/.../template.py.
TARGET_FUNCTION_NAME = "pack_circles"

# Adaptation rewrites a whole external script (often several hundred lines) in a
# single completion, so it needs a far larger budget than a normal per-sample
# call -- whose form default is only 60s. Use a generous default floor here and
# let a larger form `timeout` raise it further (never lower it below the floor,
# or big rewrites would regress to the 60s default). The subprocess hard cap
# sits a fixed grace above the socket timeout so the socket governs first.
DEFAULT_ADAPT_TIMEOUT_SECONDS = 600
ADAPT_SUBPROCESS_GRACE_SECONDS = 30

# Adaptation must emit the whole rewritten script in one completion. The form's
# per-sample default (4096 tokens, ~300 lines) truncates anything bigger, so --
# like the timeout above -- use a generous adaptation-specific floor and only
# let a larger form value raise it further. 16384 tokens covers ~1200 lines of
# code plus the trailing notes section.
DEFAULT_ADAPT_MAX_TOKENS = 16384

_CODE_FENCE_RE = re.compile(r"```(?:python|py)?\s*(.*?)```", re.DOTALL | re.IGNORECASE)


def _build_adapt_prompt(raw_code: str, *, time_budget_seconds: int) -> str:
    return (
        "你是一名算法工程师。下面给你一段用于「单位正方形内圆装填（circle packing）」问题的 Python 代码，"
        "它通常是一个独立脚本：可能包含多个顶层函数、把实例规模写死（如 N=26）、"
        "在模块顶层直接执行搜索、并用 print(json.dumps(...)) 把结果打印到标准输出。\n\n"
        "请把它改写成一个可被评测器直接调用的单入口函数，严格满足以下约束：\n"
        f"1. 必须定义一个顶层函数 `def {TARGET_FUNCTION_NAME}(n):`，返回形状为 (n, 3) 的 numpy 数组，"
        "每行是 (x, y, radius)，所有值都在 [0, 1] 内，圆之间不重叠、且完整落在单位正方形内。\n"
        "2. 【最重要】必须忠实保留原代码的真实算法逻辑与策略，不允许把它替换成平凡的网格/常量基线，"
        "更不允许把最终坐标写死返回。目的是让这段代码在代码相似度图里落在它真实所属的位置。\n"
        "3. 把原来的所有 helper 函数和 import 放到 `pack_circles` 之前的模块顶层，或嵌套进 `pack_circles` 内部；"
        "不允许残留任何模块顶层的可执行语句（不能有顶层循环、顶层赋值触发的搜索、print、sys.stdout 写出等）。\n"
        "4. 把写死的实例规模（如 N=26）全部替换为入参 `n`。\n"
        "5. 把 `print(json.dumps(...))` 之类的标准输出，改成 `return` 一个 numpy 数组。\n"
        "6. 原代码用什么随机种子就保留什么，逐字不动：不允许新增、删除或修改任何随机种子"
        "（包括 np.random.seed(...)、np.random.default_rng(...)、scipy 采样器的 seed 等）。"
        "原代码的可复现性由它自己已有的种子保证，你不需要、也不允许额外强加一个统一种子。\n"
        "7. 【严禁改动算法强度】必须原样保留原代码的所有算法超参数：重启/试验次数（如 trial 循环次数）、"
        "迭代上限（如 maxiter）、种群规模、容差（如 ftol）、步长、扰动幅度等数值，一律与原代码逐字一致，"
        "绝不允许以「节省时间 / 适配时间预算」为由把它们调小——评测器有充足的墙钟预算，不需要你压缩算法。\n"
        f"8. 仅当原代码里存在一个显式的墙钟时间上限变量（如 TIME_LIMIT / max_time，单位为秒）且其值超过 {time_budget_seconds} 秒时，"
        f"才可以把这一个变量下调到 {time_budget_seconds} 秒；除此之外不得改动任何数值参数。\n"
        "9. 保留函数运行所需的全部 import（numpy、scipy 等）。\n\n"
        "输出格式：先输出一个完整的 Python 代码块（用 ```python 包裹），代码块之后可以附上一段简短的中文改动说明"
        "（只说明你做了哪些结构性/格式改写；若未改动任何算法参数，请明确写「算法参数保持原样」）。不要输出与此无关的内容。\n\n"
        "待改写的代码：\n"
        f"```python\n{raw_code}\n```"
    )


def _extract_code_and_notes(response_text: str) -> tuple[str, str]:
    text = str(response_text or "").strip()
    if not text:
        return "", ""
    match = _CODE_FENCE_RE.search(text)
    if match:
        code = match.group(1).strip()
        notes = text[match.end():].strip()
        return code, notes
    # No fenced block: treat the whole thing as code, with no notes.
    return text, ""


def _validate_adapted_code(code: str) -> list[str]:
    warnings: list[str] = []
    if not code:
        return ["模型返回了空的改写结果。"]
    try:
        from llm4ad.base.code import TextFunctionProgramConverter

        program = TextFunctionProgramConverter.text_to_program(code)
        if program is None:
            warnings.append("改写结果无法通过 Python 语法解析，请检查是否被截断。")
            return warnings
        function_names = {f.name for f in program.functions}
        if TARGET_FUNCTION_NAME not in function_names:
            warnings.append(
                f"改写结果里没有找到目标函数 `{TARGET_FUNCTION_NAME}`，评测时会失败。"
            )
        if program.preface and re.search(r"(?m)^\s*print\s*\(", program.preface):
            warnings.append("检测到模块顶层仍有 print(...)，可能导致评测异常。")
    except Exception as error:  # pragma: no cover - validation must never break the response
        warnings.append(f"改写结果本地校验时出现异常：{error}")
    return warnings


def adapt_expert_solution_code(
    raw_code: str,
    llm_config: dict[str, Any],
    *,
    time_budget_seconds: int = 60,
    llm_from_config: Callable[[dict[str, Any]], Any] = runtime_llm_from_config,
    draw_sample_with_timeout: Callable[[Any, str, int], str] = runtime_draw_sample_with_timeout,
) -> dict[str, Any]:
    source = str(raw_code or "").strip()
    if not source:
        raise RuntimeError("请先粘贴需要改写的外部解代码。")
    if not isinstance(llm_config, dict):
        llm_config = {}

    # Follow the form `timeout` when it is larger than the adaptation floor, so
    # users can dial the budget up for slow/reasoning models; otherwise fall
    # back to the generous default floor. The completion is streamed, so this
    # socket timeout applies between chunks and the subprocess cap below governs
    # the total wall-clock budget.
    timeout_seconds = max(DEFAULT_ADAPT_TIMEOUT_SECONDS, int(llm_config.get("timeout", 0) or 0))
    normalized_config = {
        **llm_config,
        "timeout": timeout_seconds,
        "max_tokens": max(DEFAULT_ADAPT_MAX_TOKENS, int(llm_config.get("max_tokens", 0) or 0)),
    }

    prompt = _build_adapt_prompt(source, time_budget_seconds=max(5, int(time_budget_seconds)))

    llm = llm_from_config(normalized_config)
    try:
        response_text = draw_sample_with_timeout(
            llm, prompt, timeout_seconds + ADAPT_SUBPROCESS_GRACE_SECONDS
        )
    finally:
        close_llm(llm)

    adapted_code, notes = _extract_code_and_notes(response_text)
    if not adapted_code:
        raise RuntimeError("模型没有返回可用的改写代码，请重试或调整提示。")

    warnings = _validate_adapted_code(adapted_code)
    return {
        "ok": True,
        "adaptedCode": adapted_code,
        "notes": notes,
        "warnings": warnings,
    }
