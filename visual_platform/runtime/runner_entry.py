from __future__ import annotations

import os
import traceback
import warnings
from pathlib import Path
from typing import Any

from visual_platform.runtime.runner_llm import close_llm, llm_from_config, normalize_real_model, resolve_real_api_key
from visual_platform.runtime.runner_modes import (
    hydrate_nodes_from_db,
    normalize_node_list,
    run_direct_ai_mode,
    run_seeded_eoh_mode,
)
from visual_platform.runtime.region_runner import run_region_search_mode
from visual_platform.runtime.runner_progress import update_run_progress
from visual_platform.runtime.runner_task_loader import load_circle_packing_evaluation


warnings.filterwarnings(
    "ignore",
    message=r"The balance properties of Sobol' points require n to be a power of 2\.",
    category=UserWarning,
    module=r"scipy\.stats\._qmc",
)


def write_runner_error(config_path: Path, error: BaseException) -> None:
    revision_dir = config_path.parent
    error_path = revision_dir / "runner_error.log"
    message = "".join(traceback.format_exception(type(error), error, error.__traceback__))
    error_path.write_text(message, encoding="utf-8")


def run_real(config: dict[str, Any]) -> None:
    log_dir = Path(config["log_dir"])
    from visual_platform.services.research_history import capture_configuration
    capture_configuration(log_dir.parent, config)
    os.environ['VP_RESEARCH_HISTORY_DIR'] = str(log_dir.parent.resolve())
    llm_config = config.get("llm", {})
    method_config = config.get("method", {})
    prompt = str(config.get("prompt", "")).strip()

    selected_nodes = hydrate_nodes_from_db(normalize_node_list(config.get("selected_nodes", [])))
    reference_nodes = hydrate_nodes_from_db(normalize_node_list(config.get("reference_nodes", [])))
    initial_population_nodes = hydrate_nodes_from_db(normalize_node_list(config.get("initial_population_nodes", [])))

    run_label = str(config.get("revision_id", "") or "pre-fix")
    mode = str(config.get("mode", "seeded_eoh") or "seeded_eoh").strip()

    # Evaluation timeout: normal circle-packing evals finish in ~2s, so 10s gives
    # ample headroom while quickly killing runaway/infinite-loop candidates that
    # would otherwise pin an evaluator slot for the full timeout window.
    task_kwargs: dict[str, Any] = {
        "timeout_seconds": int(method_config.get("timeout_seconds", 10)),
    }
    update_run_progress(
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
        task_kwargs["safe_evaluate"] = False

    circle_packing_evaluation = load_circle_packing_evaluation()
    task = circle_packing_evaluation(**task_kwargs)
    llm = llm_from_config(llm_config)
    model_name = normalize_real_model(llm_config.get("model", ""))
    base_url = str(llm_config.get("host", "") or llm_config.get("base_url", "")).strip()
    api_key = resolve_real_api_key(llm_config.get("key", ""))

    try:
        if mode in {"direct_ai", "prompt_gen"}:
            run_direct_ai_mode(
                run_label=run_label,
                log_dir=log_dir,
                task=task,
                llm=llm,
                llm_config=llm_config,
                method_config=method_config,
                prompt=prompt,
                selected_nodes=selected_nodes,
                reference_nodes=reference_nodes,
                task_kwargs=task_kwargs,
                origin_kind="prompt_generated",
            )
            return

        if mode in {"real", "seeded_eoh"}:
            run_seeded_eoh_mode(
                run_label=run_label,
                log_dir=log_dir,
                task=task,
                llm=llm,
                llm_config=llm_config,
                method_config=method_config,
                prompt=prompt,
                selected_nodes=selected_nodes,
                initial_population_nodes=initial_population_nodes,
                task_kwargs=task_kwargs,
                model_name=model_name,
            )
            return

        if mode == "region_search":
            run_region_search_mode(
                run_label=run_label,
                log_dir=log_dir,
                task=task,
                llm=llm,
                llm_config=llm_config,
                method_config=method_config,
                prompt=prompt,
                region=config.get("region", {}),
                source_revision_id=str(config.get("source_revision_id", "") or "").strip() or None,
                model_name=model_name,
            )
            return

        raise RuntimeError(
            f"Unsupported mode '{mode}'. Supported modes: prompt_gen, seeded_eoh, region_search."
        )
    finally:
        close_llm(llm)
