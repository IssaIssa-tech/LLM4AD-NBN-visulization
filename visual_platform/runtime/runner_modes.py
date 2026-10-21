from __future__ import annotations

import copy
import json
import math
import os
import time
from pathlib import Path
from typing import Any

from visual_platform.repositories import get_individuals_by_ids, insert_individual
from visual_platform.runtime.runner_llm import TimeoutWrappedLLM, draw_sample_with_timeout
from visual_platform.runtime.runner_progress import (
    has_generated_samples,
    merge_real_run_meta,
    record_run_timing,
    update_run_progress,
)
from visual_platform.runtime.runner_task_loader import CeleryExecutor, evaluate_generated_function
from visual_platform.services import revision_generation_service


def int_config(method_config: dict[str, Any], key: str, default: int, minimum: int) -> int:
    try:
        value = int(method_config.get(key, default))
    except (TypeError, ValueError):
        value = default
    return max(minimum, value)


def resolved_method_config(method_config: dict[str, Any] | None) -> dict[str, int]:
    config = method_config if isinstance(method_config, dict) else {}
    max_generations = int_config(config, "max_generations", 8, 1)
    pop_size = int_config(config, "pop_size", 8, 2)
    num_samplers = int_config(config, "num_samplers", 4, 1)
    num_evaluators = int_config(config, "num_evaluators", 4, 1)
    derived_sample_budget = max_generations * pop_size
    # derived_sample_budget 只作为"没显式给 max_sample_nums 时的默认值"，
    # 不能拿它当下限：提示词生成（prompt_gen）只送 max_sample_nums，不送
    # pop_size/max_generations，一旦把默认的 8×8=64 当下限，表单里"生成数量"
    # 填 1 也会真的跑 64 次 LLM。EoH 需要的下限（≥ pop_size×max_generations）
    # 由 run_seeded_eoh_mode 自己施加，与这里无关。
    max_sample_nums = int_config(config, "max_sample_nums", derived_sample_budget, 1)
    return {
        "max_generations": max_generations,
        "max_sample_nums": max_sample_nums,
        "pop_size": pop_size,
        "num_samplers": num_samplers,
        "num_evaluators": num_evaluators,
    }


def normalize_node_list(raw_nodes: Any) -> list[dict[str, Any]]:
    if not isinstance(raw_nodes, list):
        return []
    normalized: list[dict[str, Any]] = []
    for node in raw_nodes:
        if isinstance(node, dict):
            normalized.append(node)
        elif isinstance(node, str):
            node_id = node.strip()
            if node_id:
                normalized.append({"id": node_id})
    return normalized


def hydrate_nodes_from_db(nodes: list[dict[str, Any]]) -> list[dict[str, Any]]:
    ids_to_fetch = [node["id"] for node in nodes if "id" in node and "functionPreview" not in node and "function" not in node]
    if not ids_to_fetch:
        return nodes

    db_records = get_individuals_by_ids(ids_to_fetch)
    db_map = {record["id"]: record for record in db_records}

    hydrated: list[dict[str, Any]] = []
    for node in nodes:
        hydrated_node = dict(node)
        node_id = hydrated_node.get("id")
        if isinstance(node_id, str) and node_id in db_map:
            record = db_map[node_id]
            hydrated_node["functionPreview"] = record.get("code") or record.get("function") or ""
            hydrated_node["programPreview"] = record.get("program") or record.get("code") or record.get("function") or ""
            hydrated_node["score"] = record.get("score")
            hydrated_node["rawScore"] = record.get("score")
            hydrated_node["algorithm"] = record.get("algorithm_summary") or record.get("algorithm") or ""
            raw_payload = record.get("raw_payload")
            if raw_payload:
                try:
                    raw = json.loads(raw_payload)
                except Exception:
                    raw = None
                if isinstance(raw, dict):
                    for key, value in raw.items():
                        hydrated_node.setdefault(key, value)
        hydrated.append(hydrated_node)
    return hydrated


def user_guidance_text(prompt: str) -> str:
    normalized = str(prompt or "").strip()
    if not normalized:
        return ""
    return f"User guidance:\n{normalized}"


def distinct_function_nodes(selected_nodes: list[dict[str, Any]]) -> list[dict[str, Any]]:
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


def classify_seed_dropouts(selected_nodes: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """Explain which selected seed nodes ``distinct_function_nodes`` discards.

    Nodes are dropped silently there, so a run that selected N nodes could seed
    far fewer without any signal. The most common cause is that a node's source
    individual was deleted from the DB (its revision was removed), so hydration
    could not recover its code. Surface each dropped node with a reason so the UI
    / run meta can tell the user why the population is smaller than expected.
    """
    dropped: list[dict[str, Any]] = []
    seen_functions: set[str] = set()
    for node in selected_nodes:
        node_id = node.get("id")
        function_preview = str(node.get("functionPreview", "") or "").strip()
        if not function_preview:
            reason = "missing_code"
        elif "def pack_circles" not in function_preview:
            reason = "no_entry_function"
        elif function_preview in seen_functions:
            reason = "duplicate"
        else:
            seen_functions.add(function_preview)
            continue
        dropped.append({"id": node_id, "reason": reason})
    return dropped


def reference_nodes_block(selected_nodes: list[dict[str, Any]], *, heading: str, limit: int = 8) -> str:
    nodes = distinct_function_nodes(selected_nodes)[:limit]
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


def parse_sampler_response(response: str, template_program: str) -> tuple[str | None, Any | None]:
    from llm4ad.base import SampleTrimmer
    from llm4ad.method.eoh.sampler import EoHSampler

    thought = EoHSampler.trim_thought_from_response(response)
    code = SampleTrimmer.trim_preface_of_function(response)
    function = SampleTrimmer.sample_to_function(code, template_program)
    if thought is None and function is not None:
        thought = "{No high-level summary provided by the model.}"
    return thought, function


# Fixed evaluability constraints, mirroring expert_adapt_service._build_adapt_prompt.
# Guarantees whatever the model proposes can be scored by the circle-packing evaluator.
EVALUABILITY_CONSTRAINTS = (
    "Mandatory evaluability hard constraints (violating any of these makes the solution INVALID, "
    "scored -inf or timed out):\n"
    "1. Define exactly one top-level entry function `def pack_circles(n: int) -> np.ndarray` returning a shape (n, 3) "
    "array, each row (x, y, radius).\n"
    "2. Validity: for any two circles, center distance >= r_i + r_j - 1e-12; radius >= 0; every circle fully inside "
    "[0,1]^2 (x-r >= -1e-12, x+r <= 1+1e-12, y likewise).\n"
    "3. No executable statements outside the function (no top-level loops/calls/print/assignment that triggers "
    "execution); if you need libraries other than numpy/math (e.g. scipy), put the import as the first line inside "
    "the function or before `def`.\n"
    "4. Determinism: fix every random seed to 2025, including numpy/scipy internals.\n"
    "5. Hard time limit ~10 seconds: no scipy.optimize with large budgets, no loops over ~1000 iterations, no "
    "time.sleep; prefer constructive/lightweight algorithms.\n"
    "6. The function must return normally; do not raise exceptions."
)


def direct_generation_prompt(
    task_description: str,
    template_function: Any,
    *,
    user_prompt: str,
    reference_nodes: list[dict[str, Any]],
    attempt_index: int,
    total_attempts: int,
    relation_directive: str = "",
) -> str:
    temp_func = copy.deepcopy(template_function)
    temp_func.body = ""
    prompt_parts = [
        task_description,
        "You are not running an EOH operator this time.",
        "Your task is to directly propose one strong new algorithm for this problem.",
    ]
    guidance_text = user_guidance_text(user_prompt)
    if guidance_text:
        prompt_parts.append(guidance_text)
    if relation_directive.strip():
        prompt_parts.append(f"[RELATION DIRECTIVE]\n{relation_directive.strip()}")
    reference_block = reference_nodes_block(
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
    prompt_parts.append(EVALUABILITY_CONSTRAINTS)
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


def persist_sample_record(
    log_dir: Path,
    sample_order: int,
    payload: dict[str, Any],
    *,
    sample_id: str | None = None,
    generation: int | None = None,
    source_kind: str = "current",
    origin_kind: str | None = None,
) -> None:
    revision_id = log_dir.parent.name
    individual = {
        "id": sample_id or f"sample-{revision_id}-{sample_order}",
        "revision_id": revision_id,
        "sample_order": sample_order,
        "generation": 0 if generation is None else int(generation),
        "source_kind": source_kind,
        "origin_kind": origin_kind or source_kind,
        **payload,
    }
    insert_individual(individual)


def run_direct_ai_mode(
    *,
    run_label: str,
    log_dir: Path,
    task: Any,
    llm: Any,
    llm_config: dict[str, Any],
    method_config: dict[str, Any],
    prompt: str,
    selected_nodes: list[dict[str, Any]],
    reference_nodes: list[dict[str, Any]],
    task_kwargs: dict[str, Any],
    origin_kind: str = "prompt_generated",
) -> None:
    from llm4ad.base.code import TextFunctionProgramConverter

    template_function = TextFunctionProgramConverter.text_to_function(task.template_program)
    if template_function is None:
        raise RuntimeError("Unable to load the circle packing template function.")

    resolved_method = resolved_method_config(method_config)
    total_attempts = resolved_method["max_sample_nums"]
    valid_sample_count = 0
    active_reference_nodes = reference_nodes or selected_nodes
    relation_directive = str(method_config.get("relation_directive", "") or "")
    if not active_reference_nodes:
        raise RuntimeError("未选择任何参考节点。请先把节点加入“任务篮”后再发起提示词生成。")

    update_run_progress(
        log_dir,
        phase="direct_ai_sampling",
        phaseLabel="AI 直接生成中",
        totalAttempts=total_attempts,
        completedAttempts=0,
    )

    for sample_order in range(1, total_attempts + 1):
        sample_started_at = time.perf_counter()
        update_run_progress(
            log_dir,
            phase="direct_ai_sampling",
            phaseLabel="AI 直接生成中",
            totalAttempts=total_attempts,
            currentAttempt=sample_order,
            completedAttempts=sample_order - 1,
        )

        prompt_text = direct_generation_prompt(
            task.task_description,
            template_function,
            user_prompt=prompt,
            reference_nodes=active_reference_nodes,
            attempt_index=sample_order,
            total_attempts=total_attempts,
            relation_directive=relation_directive,
        )
        response = draw_sample_with_timeout(llm, prompt_text, max(15, int(llm_config.get("timeout", 120)) + 5))
        thought, func = parse_sampler_response(response, task.template_program)
        sample_parents = [str(node.get("functionPreview", "")) for node in active_reference_nodes]

        if thought is None or func is None:
            sample_payload: dict[str, Any] = {
                "algorithm": "{LLM response could not be parsed into a valid function.}",
                "function": "",
                "program": "",
                "score": None,
                "operator": "direct_ai_parse_failed",
                "parents": sample_parents,
            }
        else:
            score, eval_time, program_text = evaluate_generated_function(
                task,
                func,
                task_kwargs=task_kwargs,
                use_celery=bool(method_config.get("use_celery", False)),
            )
            if program_text:
                sample_payload = {
                    "algorithm": thought,
                    "function": str(func),
                    "program": program_text,
                    "score": score,
                    "operator": "direct_ai",
                    "parents": sample_parents,
                    "evaluate_time": eval_time,
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
                    "parents": sample_parents,
                    "evaluate_time": eval_time,
                }

        persist_sample_record(
            log_dir,
            sample_order,
            sample_payload,
            sample_id=f"run-{run_label}-s{sample_order}",
            generation=1,
            source_kind="current",
            origin_kind=origin_kind,
        )

        elapsed_ms = round((time.perf_counter() - sample_started_at) * 1000.0, 3)
        record_run_timing(log_dir, "directAiAttemptMs", elapsed_ms, extra={"attempt": sample_order})
        update_run_progress(
            log_dir,
            phase="direct_ai_sampling",
            phaseLabel="AI 直接生成中",
            totalAttempts=total_attempts,
            currentAttempt=sample_order,
            completedAttempts=sample_order,
            lastAttemptMs=elapsed_ms,
            lastScore=sample_payload.get("score"),
        )

    merge_real_run_meta(
        log_dir,
        {
            "mode": "direct_ai",
            "referenceNodesCount": len(active_reference_nodes),
            "promptLength": len(prompt),
            "sampleCount": total_attempts,
            "validSampleCount": valid_sample_count,
        },
    )
    if valid_sample_count <= 0:
        raise RuntimeError("AI 直接生成没有产出任何可用算法。请调整提示词、参考节点或模型设置后重试。")

    revision_generation_service.complete_run(
        log_dir,
        phase="completed",
        phase_label="AI 直接生成完成",
        message=f"AI 直接生成完成，共产出 {total_attempts} 个样本。",
        result={
            "mode": "direct_ai",
            "sampleCount": total_attempts,
            "validSampleCount": valid_sample_count,
            "referenceNodeCount": len(active_reference_nodes),
        },
    )


def run_seeded_eoh_mode(
    *,
    run_label: str,
    log_dir: Path,
    task: Any,
    llm: Any,
    llm_config: dict[str, Any],
    method_config: dict[str, Any],
    prompt: str,
    selected_nodes: list[dict[str, Any]],
    initial_population_nodes: list[dict[str, Any]],
    task_kwargs: dict[str, Any],
    model_name: str,
) -> None:
    from llm4ad.method.eoh import EoH
    from llm4ad.method.eoh.profiler import EoHProfiler

    class PlatformEoHProfiler(EoHProfiler):
        def _write_json(self, function: Any, program: str = "", *, record_type: str = "history", record_sep: int = 200) -> None:
            del record_sep
            if not self._log_dir:
                return

            sample_order = self._num_samples
            content = {
                "sample_order": sample_order,
                "algorithm": getattr(function, "algorithm", ""),
                "function": str(function),
                "score": getattr(function, "score", None),
                "operator": getattr(function, "operator", ""),
                "parents": getattr(function, "parents", []),
                "program": program,
            }
            if record_type == "history":
                revision_id = Path(self._log_dir).parent.name
                persist_sample_record(
                    Path(self._log_dir),
                    sample_order,
                    content,
                    sample_id=f"run-{revision_id}-s{sample_order}",
                    generation=getattr(self, "_cur_gen", 0),
                    source_kind="current",
                    origin_kind="eoh_generated",
                )

                eval_time = getattr(function, "evaluate_time", None)
                if isinstance(eval_time, (int, float)):
                    record_run_timing(
                        Path(self._log_dir),
                        "sampleEvaluationMs",
                        float(eval_time) * 1000.0,
                        extra={"sampleOrder": sample_order, "operator": str(getattr(function, "operator", "") or "")},
                    )

                sample_time = getattr(function, "sample_time", None)
                if isinstance(sample_time, (int, float)):
                    record_run_timing(
                        Path(self._log_dir),
                        "sampleGenerationMs",
                        float(sample_time) * 1000.0,
                        extra={"sampleOrder": sample_order, "operator": str(getattr(function, "operator", "") or "")},
                    )

                update_run_progress(
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
                update_run_progress(
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
            update_run_progress(Path(self._log_dir), phase="finalizing", phaseLabel="运行结果封口中")

    guidance_text = user_guidance_text(prompt)
    if guidance_text:
        task.task_description = f"{task.task_description}\n\n{guidance_text}"

    seed_source_nodes = initial_population_nodes or selected_nodes
    seed_nodes = distinct_function_nodes(seed_source_nodes)
    dropped_seed_nodes = classify_seed_dropouts(seed_source_nodes)
    if dropped_seed_nodes:
        # The selected population shrank; make the reason visible instead of
        # silently proceeding with fewer seeds than the user picked.
        missing_ids = [str(d.get("id")) for d in dropped_seed_nodes if d.get("reason") == "missing_code"]
        update_run_progress(
            log_dir,
            phase="initial_population",
            phaseLabel="初始化种群评估中",
            requestedSeedCount=len(seed_source_nodes),
            droppedSeedCount=len(dropped_seed_nodes),
            droppedSeedNodes=dropped_seed_nodes,
            droppedSeedMissingIds=missing_ids,
        )
    if not seed_nodes:
        if dropped_seed_nodes:
            missing = [str(d.get("id")) for d in dropped_seed_nodes if d.get("reason") == "missing_code"]
            detail = (
                f"（共 {len(dropped_seed_nodes)} 个被跳过）"
                + (f"，其中以下节点已不存在于数据库（可能随所属 revision 被删除）：{', '.join(missing)}" if missing else "")
            )
            raise RuntimeError(
                "初始种群为空：选中的节点都无法作为种子使用" + detail + "。"
            )
        raise RuntimeError("初始种群为空。请先把节点加入“初始种群”后再运行 EOH。")

    resolved_method = resolved_method_config(method_config)
    resolved_method["pop_size"] = max(resolved_method["pop_size"], len(seed_nodes))
    resolved_method["max_sample_nums"] = max(
        resolved_method["max_sample_nums"],
        resolved_method["pop_size"] * resolved_method["max_generations"],
    )

    operator_preference = method_config.get("operator_preference", "balanced")
    operator_weights = method_config.get("operator_weights") or {}
    selection_num = int_config(method_config, "selection_num", 2, 1)
    sampler_llm = TimeoutWrappedLLM(llm, max(15, int(llm_config.get("timeout", 120)) + 5))
    evaluation_executor = CeleryExecutor(task_kwargs) if method_config.get("use_celery", False) else None

    method = EoH(
        llm=sampler_llm,
        profiler=PlatformEoHProfiler(log_dir=str(log_dir), log_style="simple", create_random_path=False),
        evaluation=task,
        max_sample_nums=resolved_method["max_sample_nums"],
        max_generations=resolved_method["max_generations"],
        pop_size=resolved_method["pop_size"],
        selection_num=selection_num,
        num_samplers=resolved_method["num_samplers"],
        num_evaluators=resolved_method["num_evaluators"],
        operator_preference=operator_preference,
        operator_weights=operator_weights,
        resume_mode=True,
        debug_mode=False,
        evaluation_executor=evaluation_executor,
    )

    selected_seeded = 0
    update_run_progress(
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

        update_run_progress(
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
        record_run_timing(
            log_dir,
            timing_name,
            elapsed_ms,
            extra={
                "sampleOrder": sample_order,
                "accepted": bool(seeded_ok),
                "reusedScore": timing_name == "seedRegistrationMs",
            },
        )
        if seeded_ok:
            selected_seeded += 1

        update_run_progress(
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

    merge_real_run_meta(
        log_dir,
        {
            "mode": "seeded_eoh",
            "initialPopulationCount": len(seed_nodes),
            "requestedSeedCount": len(seed_source_nodes),
            "droppedSeedCount": len(dropped_seed_nodes),
            "droppedSeedNodes": dropped_seed_nodes,
            "registeredSeedCount": selected_seeded,
            "promptLength": len(prompt),
            "guidanceApplied": bool(guidance_text),
        },
    )
    if selected_seeded <= 0:
        raise RuntimeError("指定的初始种群都没有通过评估，无法启动 EOH。")

    if len(method._population._population) == 0 and len(method._population._next_gen_pop) > 0:
        method._population.survival()

    update_run_progress(
        log_dir,
        phase="eoh_running",
        phaseLabel="EOH 演化中",
        initialPopulationCount=len(seed_nodes),
        completedSeedCount=len(seed_nodes),
        acceptedSeedCount=selected_seeded,
        currentGeneration=getattr(method._population, "generation", 0),
        populationSize=len(getattr(method._population, "population", []) or []),
    )

    method.run()

    if not has_generated_samples(log_dir):
        raise RuntimeError(
            f"Real mode finished without producing any valid samples. "
            f"Requested model='{llm_config.get('model', '')}', actual model='{model_name}'. "
            "This usually means the API response could not be parsed into valid code, "
            "the model is unsuitable for code generation, or the API key/request failed."
        )

    revision_generation_service.complete_run(
        log_dir,
        phase="completed",
        phase_label="EOH 演化完成",
        message="EOH 运行完成，已生成 revision 并提交后续图构建。",
        result={
            "mode": "seeded_eoh",
            "selectedSeedCount": len(seed_nodes),
            "acceptedSeedCount": selected_seeded,
            "currentGeneration": getattr(method._population, "generation", 0),
        },
    )
