#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""Three-arm climb-strategy controlled experiment (see 爬法对照实验-plan.md).

Arms:
  0_vanilla : original EoH  -- anchor registered once per budget chunk, runs
              continuously, no drift / no re-seeding / no near-dup filter.
  B (ridge) : ridge following -- each segment seeds the current best, drifts
              when a new best appears, near-dup filter (<0.02) skips eval,
              operator weights explore then refine.
  C (multi) : multi-direction -- everything from B plus per-segment target-band
              selection (emptiest distance bucket around the anchor) and
              band seeds.

Run from the visual_platform directory:
  DEEPSEEK_API_KEY=... venv/bin/python tools/climb_experiment.py --smoke
  DEEPSEEK_API_KEY=... venv/bin/python tools/climb_experiment.py --phase screening
  DEEPSEEK_API_KEY=... venv/bin/python tools/climb_experiment.py --phase deep
  DEEPSEEK_API_KEY=... venv/bin/python tools/climb_experiment.py --phase verify
  DEEPSEEK_API_KEY=... venv/bin/python tools/climb_experiment.py --phase all

In-process only: reuses EoH / SecureEvaluator / llm_from_config /
load_circle_packing_evaluation / EVALUABILITY_CONSTRAINTS /
get_codet5_embedding_matrix; does not touch Flask / Celery / Redis and does
not modify production code.
"""

from __future__ import annotations

import argparse
import json
import math
import os
import sys
import tempfile
import time
from pathlib import Path
from threading import Lock
from typing import Any

import numpy as np

REPO_ROOT = Path(__file__).resolve().parents[2]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

# The LLM timeout isolation spawns `python -m visual_platform.runtime.llm_call_worker`
# as a fresh subprocess; make sure the repo root is importable from any cwd.
_existing_pythonpath = os.environ.get("PYTHONPATH", "")
os.environ["PYTHONPATH"] = (
    str(REPO_ROOT)
    + (os.pathsep + _existing_pythonpath if _existing_pythonpath else "")
)

from visual_platform.nbn.region_analysis import (
    NEIGHBORHOOD_BUCKETS,
    NOVEL_MIN_DIST,
    is_valid_score,
    neighborhood_coverage,
)
from visual_platform.runtime.database import get_connection
from visual_platform.runtime.runner_llm import TimeoutWrappedLLM, llm_from_config
from visual_platform.runtime.runner_modes import EVALUABILITY_CONSTRAINTS
from visual_platform.runtime.runner_task_loader import load_circle_packing_evaluation

# ---------------------------------------------------------------------------
# Experiment facts (frozen, from the plan document; do not change)
# ---------------------------------------------------------------------------

ANCHOR_ID = "expert-20260721_200528_90b08b24-c26a58f0"
ANCHOR_SCORE = 2.490190368396455
UPHILL_ID = "run-20260810_161034_e5de0350-s140"
UPHILL_SCORE = 2.6132239189835422
# Distance anchor->uphill AFTER the anchor code was replaced by its complete
# self-contained single-def form (nested helpers; DB code length 22609).
# The old skeleton-code distance (0.0861146) no longer applies.
UPHILL_DIST = 0.14318645000457764
SOURCE_REVISION_ID = "20260810_161034_e5de0350"

WORKSPACE_ROOT = Path(os.environ.get("CLIMB_WORKSPACE_ROOT", str(REPO_ROOT)))
DEFAULT_RESULTS_PATH = WORKSPACE_ROOT / "data" / "runs" / "climb_results.json"
DEFAULT_REPORT_PATH = WORKSPACE_ROOT / "reports" / "爬法对照实验报告.md"

ARMS = {
    "0_vanilla": {"strategy": "vanilla", "label": "0 原版 EOH"},
    "B_ridge": {"strategy": "ridge", "label": "B 脊线跟随"},
    "C_multi": {"strategy": "multi", "label": "C 多向勘探"},
}

CROSS_ORDER = {"0_vanilla": "B_ridge", "B_ridge": "C_multi", "C_multi": "B_ridge"}

EXPLORE_WEIGHTS = {"e1": 1.0, "e2": 1.0, "m1": 0.3, "m2": 0.3}
REFINE_WEIGHTS = {"e1": 0.2, "e2": 0.2, "m1": 1.0, "m2": 1.0}

IMPROVE_EPS = 1e-6
DRIFT_EPS = 1e-12
SATURATION_WINDOW = 30


def _log(message: str) -> None:
    print(f"[{time.strftime('%Y-%m-%d %H:%M:%S')}] {message}", flush=True)


def _is_failed_operator(operator: str) -> bool:
    return str(operator or "").endswith("_parse_failed") or str(operator or "").endswith(
        "_program_failed"
    )


def _node_from_record(record: dict[str, Any]) -> dict[str, Any]:
    return {
        "id": record.get("id", ""),
        "code": str(record.get("code", "") or "").strip(),
        "score": record.get("score"),
        "algorithm": str(record.get("algorithm", "") or "").strip(),
    }


def _dedup_nodes(nodes: list[dict[str, Any]]) -> list[dict[str, Any]]:
    picked: list[dict[str, Any]] = []
    seen: set[str] = set()
    for node in nodes:
        code = str(node.get("code", "") or "").strip()
        if not code or "def pack_circles" not in code:
            continue
        if code in seen:
            continue
        seen.add(code)
        picked.append(node)
    return picked


def _load_individual(individual_id: str) -> dict[str, Any]:
    with get_connection() as conn:
        row = conn.execute(
            "SELECT id, score, code, algorithm_summary, source_kind, is_expert "
            "FROM individuals WHERE id = ?",
            (individual_id,),
        ).fetchone()
    if row is None:
        raise RuntimeError(f"个体不存在于数据库：{individual_id}")
    return {
        "id": str(row["id"]),
        "score": row["score"],
        "code": str(row["code"] or "").strip(),
        "algorithm": str(row["algorithm_summary"] or "").strip(),
        "source_kind": str(row["source_kind"] or ""),
        "is_expert": bool(row["is_expert"]),
    }


def _llm_config() -> dict[str, Any]:
    api_key = os.environ.get("DEEPSEEK_API_KEY", "") or os.environ.get("OPENAI_API_KEY", "")
    if not api_key:
        raise RuntimeError("DEEPSEEK_API_KEY / OPENAI_API_KEY env var required.")
    return {
        "host": os.environ.get("VISUAL_PLATFORM_LLM_HOST", "https://api.deepseek.com"),
        "model": os.environ.get("VISUAL_PLATFORM_LLM_MODEL", "deepseek-v4-flash"),
        "key": api_key,
        "thinking": "disabled",
        "timeout": 120,
        "max_tokens": 4096,
    }


class NoCloseTimeoutLLM(TimeoutWrappedLLM):
    """One shared LLM instance across segments: EoH calls llm.close() at the
    end of every run(); keep the instance alive (same trick as region_runner's
    RegionTimeoutLLM)."""

    def close(self) -> None:
        return None


class EmbeddingStore:
    """Thread-safe code -> CodeT5 vector cache backed by the sqlite cache."""

    def __init__(self) -> None:
        self._vectors: dict[str, np.ndarray] = {}
        self._lock = Lock()

    def vector(self, code: str) -> np.ndarray:
        code = str(code or "").strip()
        with self._lock:
            cached = self._vectors.get(code)
            if cached is not None:
                return cached
        from visual_platform.nbn.bridge import get_codet5_embedding_matrix

        # Stable cache key: a fresh progress_callback lambda per call would
        # defeat @lru_cache on the CodeT5 model loader and reload the model.
        vectors, _ = get_codet5_embedding_matrix([{"function": code}])
        with self._lock:
            self._vectors[code] = vectors[0]
            return vectors[0]

    def distance(self, code_a: str, code_b: str) -> float:
        va = self.vector(code_a)
        vb = self.vector(code_b)
        similarity = float(np.clip(float(np.dot(va, vb)), -1.0, 1.0))
        return 1.0 - similarity


class NoveltyFilter:
    """Near-dup filter: skip evaluation for generated code within
    NOVEL_MIN_DIST of any already-evaluated code (thread-safe)."""

    def __init__(
        self,
        initial_codes: list[str],
        *,
        threshold: float = NOVEL_MIN_DIST,
        store: EmbeddingStore | None = None,
    ) -> None:
        self.threshold = float(threshold)
        self._lock = Lock()
        self._store = store or EmbeddingStore()
        self._codes: list[str] = []
        self._vectors: list[np.ndarray] = []
        self.filtered_codes: list[str] = []
        for code in initial_codes:
            self.force_add(code)

    def force_add(self, code: str) -> None:
        code = str(code or "").strip()
        if not code or code in self._codes:
            return
        try:
            vector = self._store.vector(code)
        except Exception:
            return
        self._codes.append(code)
        self._vectors.append(vector)

    def known_count(self) -> int:
        return len(self._codes)

    def check_and_register(self, code: str) -> bool:
        """Return True when the code is novel (evaluate it); False when it is a
        near duplicate (skip evaluation, count as filtered)."""
        code = str(code or "").strip()
        if not code:
            return True
        with self._lock:
            if code in self._codes:
                self.filtered_codes.append(code)
                return False
            try:
                vector = self._store.vector(code)
            except Exception:
                return True
            if self._vectors:
                similarities = np.clip(np.asarray(self._vectors) @ vector, -1.0, 1.0)
                if float((1.0 - similarities).min()) < self.threshold:
                    self.filtered_codes.append(code)
                    return False
            self._codes.append(code)
            self._vectors.append(vector)
            return True

    def replay(self, records: list[dict[str, Any]]) -> None:
        """Rebuild the known set from stored records after a resume."""
        for record in records:
            operator = str(record.get("operator", "") or "")
            if operator == "region_seed":
                continue
            if record.get("filtered") or _is_failed_operator(operator):
                continue
            self.force_add(str(record.get("code", "") or ""))


class ArmState:
    def __init__(
        self,
        arm_key: str,
        strategy: str,
        anchor_node: dict[str, Any],
        store: EmbeddingStore,
    ) -> None:
        self.arm_key = arm_key
        self.strategy = strategy
        self.anchor = dict(anchor_node)
        self.store = store
        self.records: list[dict[str, Any]] = []
        self.filter = (
            NoveltyFilter([anchor_node["code"]], store=store)
            if strategy in ("ridge", "multi")
            else None
        )
        self.current_best = dict(anchor_node)
        self.segments: dict[str, list[dict[str, Any]]] = {
            "screening": [],
            "deep": [],
            "verify_append": [],
            "verify_cross": [],
        }

    def replay(self) -> None:
        if self.filter is not None:
            self.filter.replay(self.records)
        best: dict[str, Any] | None = None
        for record in self.records:
            operator = str(record.get("operator", "") or "")
            if operator == "region_seed" or record.get("filtered") or _is_failed_operator(operator):
                continue
            score = record.get("score")
            if is_valid_score(score):
                if best is None or float(score) > float(best["score"]) + DRIFT_EPS:
                    best = _node_from_record(record)
        if best is not None:
            self.current_best = best

    def main_records(self) -> list[dict[str, Any]]:
        return _phase_records(self, ("screening", "deep"))


def _phase_records(state: ArmState, phases: tuple[str, ...]) -> list[dict[str, Any]]:
    records: list[dict[str, Any]] = []
    for phase in phases:
        for segment in state.segments.get(phase, []):
            records.extend(segment.get("records", []))
    return records


def _create_collecting_profiler_class() -> type:
    from llm4ad.method.eoh.profiler import EoHProfiler

    class CollectingProfiler(EoHProfiler):
        def __init__(
            self,
            log_dir: Path,
            collected: list[dict[str, Any]],
            *,
            initial_num_samples: int = 0,
        ):
            super().__init__(
                log_dir=str(log_dir),
                log_style="simple",
                create_random_path=False,
                initial_num_samples=initial_num_samples,
            )
            self._collected = collected

        def register_function(
            self,
            function: Any,
            program: str = "",
            *,
            resume_mode: bool = False,
        ) -> None:
            del resume_mode
            with self._register_function_lock:
                sample_order = self._num_samples
                self._num_samples += 1
                raw_score = getattr(function, "score", None)
                score: Any = None
                if isinstance(raw_score, (int, float)) and math.isfinite(float(raw_score)):
                    score = float(raw_score)
                self._collected.append(
                    {
                        "sample_order": sample_order,
                        "code": str(function).strip(),
                        "program": str(program or ""),
                        "score": score,
                        "operator": str(getattr(function, "operator", "") or ""),
                        "parents": list(getattr(function, "parents", []) or []),
                        "filtered": bool(getattr(function, "_filtered", False)),
                        "sample_time": getattr(function, "sample_time", None),
                        "evaluate_time": getattr(function, "evaluate_time", None),
                        "algorithm": str(getattr(function, "algorithm", "") or ""),
                    }
                )

        def _write_json(self, *args: Any, **kwargs: Any) -> None:
            del args, kwargs
            return None

        def register_population(self, pop: Any) -> None:
            del pop
            return None

        def finish(self) -> None:
            return None

    return CollectingProfiler


def _create_filtering_eoh_class() -> type:
    from llm4ad.base import TextFunctionProgramConverter
    from llm4ad.method.eoh import EoH

    class FilteringEoH(EoH):
        def __init__(self, *, novelty_filter: NoveltyFilter | None = None, **kwargs: Any):
            super().__init__(**kwargs)
            self._novelty_filter = novelty_filter

        def _sample_evaluate_register(
            self,
            prompt: str | Any,
            operator: str = "",
            parents: list | None = None,
        ) -> None:
            sample_start = time.time()
            thought, func = self._sampler.get_thought_and_function(prompt)
            sample_time = time.time() - sample_start
            self._tot_sample_nums += 1
            if thought is None or func is None:
                self._register_failed_sample(
                    sample_time=sample_time,
                    reason="LLM response could not be parsed into a valid function.",
                    operator=f"{operator}_parse_failed",
                    parents=parents,
                )
                return
            program = TextFunctionProgramConverter.function_to_program(
                func, self._template_program
            )
            if program is None:
                self._register_failed_sample(
                    sample_time=sample_time,
                    reason="Generated function could not be converted into an executable program.",
                    operator=f"{operator}_program_failed",
                    parents=parents,
                )
                return
            if self._novelty_filter is not None and not self._novelty_filter.check_and_register(
                str(func)
            ):
                func.score = None
                func.evaluate_time = 0.0
                func.sample_time = sample_time
                func.operator = operator
                func.parents = parents or []
                func.algorithm = thought
                setattr(func, "_filtered", True)
                if self._profiler is not None:
                    self._profiler.register_function(func, program=str(program))
                return
            score, eval_time = self._evaluation_executor.submit(
                self._evaluator.evaluate_program_record_time,
                program,
            ).result()
            func.score = score
            func.evaluate_time = eval_time
            func.algorithm = thought
            func.sample_time = sample_time
            func.operator = operator
            func.parents = parents or []
            if self._profiler is not None:
                self._profiler.register_function(func, program=str(program))
                self._profiler.register_population(self._population)
            self._population.register_function(func)

    return FilteringEoH


def _build_llm() -> NoCloseTimeoutLLM:
    llm = llm_from_config(_llm_config())
    return NoCloseTimeoutLLM(llm, max(15, int(_llm_config().get("timeout", 120)) + 5))


def _base_directive() -> str:
    return (
        "[CLIMB DIRECTIVE -- ridge following]\n"
        "The current highest-scoring solution of this search is seeded as the starting point. "
        "Evolve FROM it: keep its working core, move freely through small-to-medium structural "
        "changes, and your goal is to EXCEED its score. Stay related to the seeded solution; "
        "do not collapse into a trivial/naive layout and do not jump to an unrelated algorithm."
    )


def _segment_weights(segment_index: int) -> dict[str, float]:
    return dict(EXPLORE_WEIGHTS) if segment_index <= 2 else dict(REFINE_WEIGHTS)


def _segment_stats(records: list[dict[str, Any]], expected: int) -> dict[str, Any]:
    generated = len(records)
    evaluated = [
        record
        for record in records
        if not record.get("filtered") and not _is_failed_operator(record.get("operator", ""))
    ]
    filtered = sum(1 for record in records if record.get("filtered"))
    valid = [record for record in evaluated if is_valid_score(record.get("score"))]
    best = max(valid, key=lambda record: float(record["score"]), default=None)
    return {
        "generated": generated,
        "evaluated": len(evaluated),
        "filtered": filtered,
        "valid": len(valid),
        "best": best["score"] if best is not None else None,
        "overshoot": max(0, generated - expected),
    }


def _register_seeds(
    method: Any,
    seed_nodes: list[dict[str, Any]],
    label: str,
) -> int:
    accepted = 0
    for node in _dedup_nodes(seed_nodes):
        algorithm = str(node.get("algorithm", "") or "").strip() or f"{{{label} seed}}"
        ok = method.register_prescored_seed_function(
            node["code"],
            score=float(node["score"]),
            algorithm=algorithm[:600],
            operator="region_seed",
        )
        accepted += int(bool(ok))
    return accepted


def _run_eoh_segment(
    *,
    state: ArmState,
    segment_index: int,
    samples: int,
    weights: dict[str, float],
    directive: str,
    task: Any,
    llm: Any,
    base_description: str,
    log_dir: Path,
    seed_nodes: list[dict[str, Any]],
    filter_enabled: bool,
    num_samplers: int = 4,
    num_evaluators: int = 4,
    evaluability_constraints: str = EVALUABILITY_CONSTRAINTS,
) -> tuple[dict[str, Any], list[dict[str, Any]]]:
    from llm4ad.method.eoh import EoH

    collected: list[dict[str, Any]] = []
    profiler_class = _create_collecting_profiler_class()
    profiler = profiler_class(
        log_dir,
        collected,
        initial_num_samples=len(state.records),
    )
    task.task_description = (
        f"{base_description}\n\n{directive}\n\n{evaluability_constraints}"
    )
    eoh_class = _create_filtering_eoh_class() if filter_enabled else EoH
    kwargs: dict[str, Any] = dict(
        llm=llm,
        profiler=profiler,
        evaluation=task,
        max_sample_nums=samples + len(_dedup_nodes(seed_nodes)),
        max_generations=max(2, math.ceil(samples / 8) + 2),
        pop_size=8,
        selection_num=2,
        num_samplers=num_samplers,
        num_evaluators=num_evaluators,
        operator_weights=weights,
        resume_mode=True,
        debug_mode=False,
    )
    if filter_enabled:
        kwargs["novelty_filter"] = state.filter
    method = eoh_class(**kwargs)
    accepted = _register_seeds(method, seed_nodes, state.arm_key)
    if accepted <= 0:
        raise RuntimeError(f"{state.arm_key} 段 {segment_index}：种子注册失败")
    if len(method._population._population) == 0 and len(method._population._next_gen_pop) > 0:
        method._population.survival()
    method.run()
    state.records.extend(collected)
    segment_records = [record for record in collected if record.get("operator") != "region_seed"]
    stats = _segment_stats(segment_records, samples)

    drifted = False
    best_valid = max(
        (
            record
            for record in segment_records
            if is_valid_score(record.get("score"))
        ),
        key=lambda record: float(record["score"]),
        default=None,
    )
    if best_valid is not None:
        current_score = state.current_best.get("score")
        if current_score is None or float(best_valid["score"]) > float(current_score) + DRIFT_EPS:
            state.current_best = _node_from_record(best_valid)
            drifted = True

    segment_record = {
        "segment": segment_index,
        "generated": stats["generated"],
        "evaluated": stats["evaluated"],
        "filtered": stats["filtered"],
        "valid": stats["valid"],
        "best": stats["best"],
        "drift": drifted,
        "overshoot": stats["overshoot"],
        "seed_codes": [node["code"] for node in _dedup_nodes(seed_nodes)],
        "records": collected,
    }
    return segment_record, segment_records


def _run_vanilla_chunk(
    *,
    state: ArmState,
    samples: int,
    seed_node: dict[str, Any],
    task: Any,
    llm: Any,
    base_description: str,
    log_dir: Path,
) -> dict[str, Any]:
    from llm4ad.method.eoh import EoH

    collected: list[dict[str, Any]] = []
    profiler_class = _create_collecting_profiler_class()
    profiler = profiler_class(log_dir, collected, initial_num_samples=len(state.records))
    task.task_description = f"{base_description}\n\n{EVALUABILITY_CONSTRAINTS}"
    method = EoH(
        llm=llm,
        profiler=profiler,
        evaluation=task,
        max_sample_nums=samples + 1,
        max_generations=max(2, math.ceil(samples / 8) + 2),
        pop_size=8,
        selection_num=2,
        num_samplers=4,
        num_evaluators=4,
        operator_weights={},
        resume_mode=True,
        debug_mode=False,
    )
    accepted = _register_seeds(method, [seed_node], state.arm_key)
    if accepted <= 0:
        raise RuntimeError(f"{state.arm_key} 连续段：种子注册失败")
    if len(method._population._population) == 0 and len(method._population._next_gen_pop) > 0:
        method._population.survival()
    method.run()
    state.records.extend(collected)
    return {
        "chunk_samples": samples,
        "records": collected,
    }


def _run_phase_segments(
    *,
    state: ArmState,
    phase: str,
    task: Any,
    llm: Any,
    base_description: str,
    log_dir: Path,
    samples_per_segment: int,
    segment_count: int,
    start_segment: int,
    cross_strategy: str | None = None,
    checkpoint: Any | None = None,
) -> list[dict[str, Any]]:
    """Run ridge/multi-style segments for a phase (screening/deep/verify)."""
    segments_done = len(state.segments.get(phase, []))
    completed = []
    for index in range(segments_done, segment_count):
        segment_index = start_segment + index
        weights = _segment_weights(segment_index)
        seed_nodes = _build_seed_nodes(state, cross_strategy)
        directive = _build_directive(state, cross_strategy, segment_index, seed_nodes)
        _log(
            f"[{state.arm_key}] {phase} 段 {segment_index}/{start_segment + segment_count - 1} "
            f"启动（生成 {samples_per_segment}，种子 {len(_dedup_nodes(seed_nodes))}，"
            f"算子权重 {weights}）"
        )
        segment_record, _ = _run_eoh_segment(
            state=state,
            segment_index=segment_index,
            samples=samples_per_segment,
            weights=weights,
            directive=directive,
            task=task,
            llm=llm,
            base_description=base_description,
            log_dir=log_dir,
            seed_nodes=seed_nodes,
            filter_enabled=state.strategy in ("ridge", "multi"),
        )
        completed.append(segment_record)
        state.segments[phase].append(segment_record)
        if checkpoint is not None:
            checkpoint()
        _log(
            f"[{state.arm_key}] {phase} 段 {segment_index} 完成："
            f"best={segment_record['best']} evaluated={segment_record['evaluated']} "
            f"filtered={segment_record['filtered']} drift={segment_record['drift']}"
        )
    return completed


def _build_seed_nodes(
    state: ArmState,
    cross_strategy: str | None,
) -> list[dict[str, Any]]:
    strategy = cross_strategy or state.strategy
    if state.current_best.get("code"):
        seeds = [_node_from_record(state.current_best)]
    else:
        seeds = [dict(state.anchor)]
    if strategy == "multi":
        seeds.extend(_emptiest_band_candidates(state))
    return _dedup_nodes(seeds)


def _build_directive(
    state: ArmState,
    cross_strategy: str | None,
    segment_index: int,
    seed_nodes: list[dict[str, Any]],
) -> str:
    strategy = cross_strategy or state.strategy
    best_score = state.current_best.get("score")
    score_line = (
        f" The current highest score is {best_score:.6f}."
        if isinstance(best_score, (int, float))
        else ""
    )
    if strategy == "vanilla":
        return ""
    directive = (
        f"{_base_directive()}\n"
        "From the seeded highest-scoring solution, produce variants that can beat it."
        f"{score_line}"
    )
    if strategy == "multi":
        band = _emptiest_band(state)
        directive += (
            f"\n\n[DIRECTION BAND]\nAim this segment's variants at semantic distance "
            f"{band[0]:.2f}-{band[1]:.2f} from the anchor (the mountain entrance)."
        )
    return directive


def _emptiest_band(state: ArmState) -> tuple[float, float]:
    counts: dict[tuple[float, float], int] = {band: 0 for band in NEIGHBORHOOD_BUCKETS}
    anchor_code = state.anchor["code"]
    evaluated = [
        record
        for record in state.records
        if record.get("operator") != "region_seed"
        and not record.get("filtered")
        and not _is_failed_operator(record.get("operator", ""))
    ]
    for record in evaluated:
        try:
            distance = state.store.distance(anchor_code, record["code"])
        except Exception:
            continue
        for band in NEIGHBORHOOD_BUCKETS:
            if band[0] <= distance < band[1]:
                counts[band] += 1
                break
    return min(counts, key=lambda band: (counts[band], band[0]))


def _emptiest_band_candidates(state: ArmState) -> list[dict[str, Any]]:
    band = _emptiest_band(state)
    anchor_code = state.anchor["code"]
    current_code = state.current_best.get("code", anchor_code)
    candidates: list[tuple[float, dict[str, Any]]] = []
    evaluated = [
        record
        for record in state.records
        if record.get("operator") != "region_seed"
        and not record.get("filtered")
        and not _is_failed_operator(record.get("operator", ""))
        and record["code"] != current_code
    ]
    for record in evaluated:
        try:
            distance_a = state.store.distance(anchor_code, record["code"])
        except Exception:
            continue
        if band[0] <= distance_a < band[1]:
            try:
                distance_best = state.store.distance(current_code, record["code"])
            except Exception:
                distance_best = math.inf
            candidates.append((distance_best, _node_from_record(record)))
    candidates.sort(key=lambda item: item[0])
    return [node for _, node in candidates[:2]]


def _run_vanilla_phase(
    *,
    state: ArmState,
    phase: str,
    task: Any,
    llm: Any,
    base_description: str,
    log_dir: Path,
    samples_per_segment: int,
    segment_count: int,
) -> list[dict[str, Any]]:
    if len(state.segments.get(phase, [])) == segment_count:
        return list(state.segments[phase])
    if state.segments.get(phase):
        # Partial chunk from a previous run: discard it and rerun cleanly
        # (a vanilla chunk is one continuous EoH; it cannot be resumed mid-way).
        _truncate_vanilla_phase(state, phase)
    total_samples = samples_per_segment * segment_count
    if phase == "screening":
        seed_node = dict(state.anchor)
    else:
        phase_records: list[dict[str, Any]] = []
        for earlier in ("screening", "deep", "verify_append"):
            if earlier == phase:
                break
            for segment in state.segments.get(earlier, []):
                phase_records.extend(segment.get("records", []))
        best_node = _records_best(phase_records)
        # At a phase boundary the arm re-seeds with its highest KNOWN score.
        # Until a generated solution beats the trusted anchor, that is the
        # anchor itself (mirrors ridge following's "seed the current best").
        if best_node is not None and (
            not isinstance(state.anchor["score"], (int, float))
            or float(best_node["score"]) > float(state.anchor["score"]) + DRIFT_EPS
        ):
            seed_node = best_node
        else:
            seed_node = dict(state.anchor)
    _log(
        f"[{state.arm_key}] {phase} 连续块启动："
        f"样本 {total_samples}，种子 {seed_node['score']}"
    )
    chunk = _run_vanilla_chunk(
        state=state,
        samples=total_samples,
        seed_node=seed_node,
        task=task,
        llm=llm,
        base_description=base_description,
        log_dir=log_dir,
    )
    generated = [record for record in chunk["records"] if record.get("operator") != "region_seed"]
    segments: list[dict[str, Any]] = []
    for index in range(segment_count):
        slice_records = generated[index * samples_per_segment : (index + 1) * samples_per_segment]
        stats = _segment_stats(slice_records, samples_per_segment)
        segments.append(
            {
                "segment": index + 1,
                "generated": stats["generated"],
                "evaluated": stats["evaluated"],
                "filtered": stats["filtered"],
                "valid": stats["valid"],
                "best": stats["best"],
                "drift": False,
                "overshoot": 0,
                "seed_codes": [seed_node["code"]],
                "records": slice_records,
            }
        )
    state.segments[phase] = segments
    return segments


def _truncate_vanilla_phase(state: ArmState, phase: str) -> None:
    order = ("screening", "deep", "verify_append", "verify_cross")
    kept_records: list[dict[str, Any]] = []
    for name in order:
        if name == phase:
            break
        for segment in state.segments.get(name, []):
            kept_records.extend(segment.get("records", []))
    state.records = kept_records
    for name in order:
        if name >= phase:
            state.segments[name] = []
    state.replay()


def _records_best(records: list[dict[str, Any]]) -> dict[str, Any] | None:
    best: dict[str, Any] | None = None
    for record in records:
        if record.get("operator") == "region_seed" or record.get("filtered"):
            continue
        if is_valid_score(record.get("score")):
            if best is None or float(record["score"]) > float(best["score"]) + DRIFT_EPS:
                best = _node_from_record(record)
    return best


def _fresh_results(anchor_node: dict[str, Any], uphill_node: dict[str, Any]) -> dict[str, Any]:
    return {
        "meta": {
            "anchor_id": ANCHOR_ID,
            "anchor_score": ANCHOR_SCORE,
            "uphill_id": UPHILL_ID,
            "uphill_score": UPHILL_SCORE,
            "uphill_dist_expected": UPHILL_DIST,
            "llm": {
                "host": _llm_config()["host"],
                "model": _llm_config()["model"],
                "thinking": "disabled",
            },
            "pop_size": 8,
            "selection_num": 2,
            "num_samplers": 4,
            "num_evaluators": 4,
            "eval_timeout_seconds": 10,
            "novel_min_dist": NOVEL_MIN_DIST,
            "buckets": [list(band) for band in NEIGHBORHOOD_BUCKETS],
            "explore_weights": EXPLORE_WEIGHTS,
            "refine_weights": REFINE_WEIGHTS,
            "anchor_code_len": len(anchor_node["code"]),
            "uphill_code_len": len(uphill_node["code"]),
            "started_at": time.strftime("%Y-%m-%d %H:%M:%S"),
        },
        "smoke": {},
        "arms": {
            arm_key: {
                "arm": arm_key,
                "label": ARMS[arm_key]["label"],
                "strategy": ARMS[arm_key]["strategy"],
                "phases": {
                    "screening": {"segments": []},
                    "deep": {"segments": []},
                    "verify_append": {"segments": []},
                    "verify_cross": {"segments": []},
                },
            }
            for arm_key in ARMS
        },
        "retained": [],
        "conclusion": None,
        "generated_at": None,
    }


def _load_results(args: argparse.Namespace) -> dict[str, Any] | None:
    path = Path(args.results_path)
    if not path.is_file():
        return None
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return None


def _save_results(results: dict[str, Any], args: argparse.Namespace) -> None:
    path = Path(args.results_path)
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_suffix(".json.tmp")
    tmp.write_text(json.dumps(results, ensure_ascii=False, indent=2), encoding="utf-8")
    tmp.replace(path)


def _rebuild_state(
    arm_key: str,
    anchor_node: dict[str, Any],
    results: dict[str, Any] | None,
    store: EmbeddingStore,
) -> ArmState:
    state = ArmState(arm_key, ARMS[arm_key]["strategy"], anchor_node, store)
    if results is None:
        return state
    arm = results.get("arms", {}).get(arm_key)
    if not arm:
        return state
    for phase in ("screening", "deep", "verify_append", "verify_cross"):
        segments = arm.get("phases", {}).get(phase, {}).get("segments", [])
        for segment in segments:
            state.segments[phase].append(segment)
            state.records.extend(segment.get("records", []))
    state.replay()
    return state


def _phase_completed(state: ArmState, phase: str, expected_segments: int) -> bool:
    return len(state.segments.get(phase, [])) >= expected_segments


def run_smoke(
    *,
    task: Any,
    llm: Any,
    anchor_node: dict[str, Any],
    uphill_node: dict[str, Any],
    results: dict[str, Any],
    args: argparse.Namespace,
) -> None:
    smoke_samples = 5
    log_dir = Path(tempfile.mkdtemp(prefix="climb_smoke_"))
    base_description = str(task.task_description)
    store = EmbeddingStore()
    smoke: dict[str, Any] = {}

    # The expert anchor's DB `code` is the entry function only (its helpers live
    # in raw_payload.program); it is a TRUSTED prescored seed and is never
    # re-evaluated. Reproducibility here means: the DB trusted score matches the
    # plan constant AND prescored registration carries it into the run records.
    anchor_repro_ok = abs(float(anchor_node["score"]) - ANCHOR_SCORE) < 1e-12
    smoke["anchor_trusted_score"] = anchor_node["score"]
    smoke["anchor_repro_ok"] = anchor_repro_ok
    _log(
        f"冒烟 1/4：锚点可信分数复现 {anchor_node['score']}（期望 {ANCHOR_SCORE}）→ "
        f"{'OK' if anchor_repro_ok else 'FAIL'}"
    )

    _log("冒烟 2/4：距离回归守卫（锚点→上坡目标 ≈0.0861）")
    uphill_distance = store.distance(anchor_node["code"], uphill_node["code"])
    distance_ok = abs(uphill_distance - UPHILL_DIST) < 1e-3
    smoke["uphill_distance"] = uphill_distance
    smoke["distance_guard_ok"] = distance_ok
    _log(f"锚点→{UPHILL_ID} 距离：{uphill_distance:.6f}（期望 {UPHILL_DIST}）→ {'OK' if distance_ok else 'FAIL'}")

    _log("冒烟 3/4：近重复过滤正确性（注入已知重复 + 新代码）")
    filter_ = NoveltyFilter([anchor_node["code"]], store=store)
    duplicate_skipped = not filter_.check_and_register(anchor_node["code"] + "\n")
    novel_accepted = filter_.check_and_register(uphill_node["code"])
    filter_test = {
        "anchor_duplicate_skipped": duplicate_skipped,
        "novel_accepted": novel_accepted,
        "filtered_count_after_injection": len(filter_.filtered_codes),
        "known_count_after_injection": filter_.known_count(),
    }
    smoke["filter_test"] = filter_test
    _log(f"过滤测试：重复被跳过={duplicate_skipped}，新代码放行={novel_accepted} → "
         f"{'OK' if duplicate_skipped and novel_accepted else 'FAIL'}")

    _log(f"冒烟 4/4：三臂各 1 段 × {smoke_samples} 样本")
    smoke["arms"] = {}
    for arm_key, arm_meta in ARMS.items():
        state = ArmState(arm_key, arm_meta["strategy"], anchor_node, store)
        if arm_meta["strategy"] == "vanilla":
            segments = _run_vanilla_phase(
                state=state,
                phase="screening",
                task=task,
                llm=llm,
                base_description=base_description,
                log_dir=log_dir,
                samples_per_segment=smoke_samples,
                segment_count=1,
            )
        else:
            segments = _run_phase_segments(
                state=state,
                phase="screening",
                task=task,
                llm=llm,
                base_description=base_description,
                log_dir=log_dir,
                samples_per_segment=smoke_samples,
                segment_count=1,
                start_segment=1,
            )
        segment = segments[0]
        smoke["arms"][arm_key] = {
            "segment": segment,
            "seed_score_reproduced": any(
                record.get("operator") == "region_seed"
                and record.get("score") is not None
                and abs(float(record["score"]) - ANCHOR_SCORE) < 1e-9
                for record in state.records
            ),
        }
        _log(
            f"[{arm_key}] 冒烟段完成：best={segment['best']} "
            f"evaluated={segment['evaluated']} filtered={segment['filtered']}"
        )
    results["smoke"] = smoke
    _log("冒烟完成。")


def _run_screening(
    *,
    task: Any,
    llm: Any,
    anchor_node: dict[str, Any],
    results: dict[str, Any],
    args: argparse.Namespace,
) -> list[str]:
    log_dir = Path(tempfile.mkdtemp(prefix="climb_screening_"))
    base_description = str(task.task_description)
    store = EmbeddingStore()
    retained: list[str] = []
    for arm_key, arm_meta in ARMS.items():
        state = _rebuild_state(arm_key, anchor_node, results, store)
        expected = args.segments
        if _phase_completed(state, "screening", expected):
            _log(f"[{arm_key}] 筛选已存在 {expected} 段，跳过。")
            retained.append(arm_key)
            continue
        _log(f"[{arm_key}] 筛选开始（{expected} 段 × {args.samples_per_segment}）")
        if arm_meta["strategy"] == "vanilla":
            _run_vanilla_phase(
                state=state,
                phase="screening",
                task=task,
                llm=llm,
                base_description=base_description,
                log_dir=log_dir,
                samples_per_segment=args.samples_per_segment,
                segment_count=expected,
            )
        else:
            def _checkpoint_screening() -> None:
                results["arms"][arm_key]["phases"]["screening"]["segments"] = list(
                    state.segments["screening"]
                )
                _save_results(results, args)

            _run_phase_segments(
                state=state,
                phase="screening",
                task=task,
                llm=llm,
                base_description=base_description,
                log_dir=log_dir,
                samples_per_segment=args.samples_per_segment,
                segment_count=expected,
                start_segment=1,
                checkpoint=_checkpoint_screening,
            )
        results["arms"][arm_key]["phases"]["screening"]["segments"] = state.segments["screening"]
        _save_results(results, args)
        retained.append(arm_key)
        _log(f"[{arm_key}] 筛选完成，当前 best={state.current_best['score']}")
    retained = _decide_retained(results)
    results["retained"] = retained
    _save_results(results, args)
    _log(f"筛选阶段保留臂：{retained}")
    return retained


def _decide_retained(results: dict[str, Any]) -> list[str]:
    """Keep every arm whose screening best is not collapsed: best > 90% of the
    trusted anchor score or within 0.05 of the screening leader. Healthy arms
    get the deep budget so the final judgment compares equal budgets."""
    screening_best: dict[str, float] = {}
    for arm_key in ARMS:
        segments = results["arms"][arm_key]["phases"]["screening"]["segments"]
        bests = [
            float(segment["best"])
            for segment in segments
            if segment.get("best") is not None
        ]
        screening_best[arm_key] = max(bests) if bests else -math.inf
    finite = {key: best for key, best in screening_best.items() if math.isfinite(best)}
    if not finite:
        return list(ARMS)
    top_best = max(finite.values())
    retained = [
        arm_key
        for arm_key, best in finite.items()
        if best > 0.90 * ANCHOR_SCORE or best > top_best - 0.05
    ]
    return retained or sorted(finite, key=lambda key: finite[key], reverse=True)[:2]


def _run_deep(
    *,
    task: Any,
    llm: Any,
    anchor_node: dict[str, Any],
    results: dict[str, Any],
    args: argparse.Namespace,
) -> None:
    retained = results.get("retained") or _decide_retained(results)
    log_dir = Path(tempfile.mkdtemp(prefix="climb_deep_"))
    base_description = str(task.task_description)
    store = EmbeddingStore()
    for arm_key in retained:
        state = _rebuild_state(arm_key, anchor_node, results, store)
        expected = args.deep_segments
        if _phase_completed(state, "deep", expected):
            _log(f"[{arm_key}] 深挖已存在 {expected} 段，跳过。")
            continue
        _log(f"[{arm_key}] 深挖开始（{expected} 段 × {args.samples_per_segment}）")
        if ARMS[arm_key]["strategy"] == "vanilla":
            _run_vanilla_phase(
                state=state,
                phase="deep",
                task=task,
                llm=llm,
                base_description=base_description,
                log_dir=log_dir,
                samples_per_segment=args.samples_per_segment,
                segment_count=expected,
            )
        else:
            def _checkpoint_deep() -> None:
                results["arms"][arm_key]["phases"]["deep"]["segments"] = list(
                    state.segments["deep"]
                )
                _save_results(results, args)

            _run_phase_segments(
                state=state,
                phase="deep",
                task=task,
                llm=llm,
                base_description=base_description,
                log_dir=log_dir,
                samples_per_segment=args.samples_per_segment,
                segment_count=expected,
                start_segment=args.segments + 1,
                checkpoint=_checkpoint_deep,
            )
        results["arms"][arm_key]["phases"]["deep"]["segments"] = state.segments["deep"]
        _save_results(results, args)
        _log(f"[{arm_key}] 深挖完成，当前 best={state.current_best['score']}")


def _run_verify(
    *,
    task: Any,
    llm: Any,
    anchor_node: dict[str, Any],
    results: dict[str, Any],
    args: argparse.Namespace,
) -> None:
    retained = results.get("retained") or _decide_retained(results)
    log_dir = Path(tempfile.mkdtemp(prefix="climb_verify_"))
    base_description = str(task.task_description)
    store = EmbeddingStore()
    for arm_key in retained:
        state = _rebuild_state(arm_key, anchor_node, results, store)
        final_best = _final_best(state)
        verify_segments = args.verify_segments

        if not _phase_completed(state, "verify_append", verify_segments):
            _log(f"[{arm_key}] 追加复验开始（同策略 × {verify_segments} 段）")
            if ARMS[arm_key]["strategy"] == "vanilla":
                _run_vanilla_phase(
                    state=state,
                    phase="verify_append",
                    task=task,
                    llm=llm,
                    base_description=base_description,
                    log_dir=log_dir,
                    samples_per_segment=args.samples_per_segment,
                    segment_count=verify_segments,
                )
            else:
                def _checkpoint_append() -> None:
                    results["arms"][arm_key]["phases"]["verify_append"]["segments"] = list(
                        state.segments["verify_append"]
                    )
                    _save_results(results, args)

                _run_phase_segments(
                    state=state,
                    phase="verify_append",
                    task=task,
                    llm=llm,
                    base_description=base_description,
                    log_dir=log_dir,
                    samples_per_segment=args.samples_per_segment,
                    segment_count=verify_segments,
                    start_segment=args.segments + args.deep_segments + 1,
                    checkpoint=_checkpoint_append,
                )
            results["arms"][arm_key]["phases"]["verify_append"]["segments"] = state.segments[
                "verify_append"
            ]
            _save_results(results, args)

        if not _phase_completed(state, "verify_cross", verify_segments):
            cross_key = CROSS_ORDER[arm_key]
            _log(f"[{arm_key}] 交叉复验开始（改用 {cross_key} 策略 × {verify_segments} 段）")
            cross_state = ArmState(
                f"{arm_key}_cross",
                ARMS[cross_key]["strategy"],
                anchor_node,
                store,
            )
            cross_state.records = list(state.records)
            cross_state.replay()
            cross_state.current_best = {
                "id": final_best.get("id", ""),
                "code": final_best["code"],
                "score": final_best["score"],
                "algorithm": final_best.get("algorithm", ""),
            }
            if ARMS[cross_key]["strategy"] == "vanilla":
                _run_vanilla_phase(
                    state=cross_state,
                    phase="verify_cross",
                    task=task,
                    llm=llm,
                    base_description=base_description,
                    log_dir=log_dir,
                    samples_per_segment=args.samples_per_segment,
                    segment_count=verify_segments,
                )
            else:
                def _checkpoint_cross() -> None:
                    results["arms"][arm_key]["phases"]["verify_cross"] = {
                        "segments": list(cross_state.segments["verify_cross"]),
                        "cross_strategy": ARMS[cross_key]["strategy"],
                        "cross_arm": cross_key,
                    }
                    _save_results(results, args)

                _run_phase_segments(
                    state=cross_state,
                    phase="verify_cross",
                    task=task,
                    llm=llm,
                    base_description=base_description,
                    log_dir=log_dir,
                    samples_per_segment=args.samples_per_segment,
                    segment_count=verify_segments,
                    start_segment=args.segments + args.deep_segments + verify_segments + 1,
                    cross_strategy=ARMS[cross_key]["strategy"],
                    checkpoint=_checkpoint_cross,
                )
            results["arms"][arm_key]["phases"]["verify_cross"] = {
                "segments": cross_state.segments["verify_cross"],
                "cross_strategy": ARMS[cross_key]["strategy"],
                "cross_arm": cross_key,
            }
            _save_results(results, args)
        _log(f"[{arm_key}] 判死复验完成（final_best={final_best['score']}）")


def _final_best(state: ArmState) -> dict[str, Any]:
    best: dict[str, Any] | None = None
    for record in state.main_records():
        if record.get("operator") == "region_seed" or record.get("filtered"):
            continue
        if is_valid_score(record.get("score")):
            if best is None or float(record["score"]) > float(best["score"]) + DRIFT_EPS:
                best = _node_from_record(record)
    if best is None:
        best = dict(state.anchor)
    return best


def _evaluated_series(records: list[dict[str, Any]]) -> list[float | None]:
    series: list[float | None] = []
    for record in records:
        if record.get("operator") == "region_seed" or record.get("filtered"):
            continue
        if _is_failed_operator(record.get("operator", "")):
            continue
        score = record.get("score")
        series.append(float(score) if is_valid_score(score) else None)
    return series


def _saturation_metrics(series: list[float | None], window: int = SATURATION_WINDOW) -> dict[str, Any]:
    n = len(series)
    best: float | None = None
    improvements: list[int] = []
    best_at: dict[str, float] = {}
    for index, score in enumerate(series, start=1):
        if isinstance(score, (int, float)) and math.isfinite(float(score)):
            if best is None or float(score) > best + IMPROVE_EPS:
                best = max(best, float(score)) if best is not None else float(score)
                improvements.append(index)
        for checkpoint in (50, 100, 150, 200, 300):
            if index == checkpoint and checkpoint not in best_at and best is not None:
                best_at[str(checkpoint)] = best
    for checkpoint in (50, 100, 150, 200, 300):
        if checkpoint <= n and str(checkpoint) not in best_at and best is not None:
            best_at[str(checkpoint)] = best
    saturation_point: int | None = None
    if improvements and n >= window:
        improvement_set = set(improvements)
        for start in range(1, n - window + 2):
            if any(index in improvement_set for index in range(start, start + window)):
                continue
            saturation_point = start
            break
    return {
        "evaluated_count": n,
        "best": best,
        "saturation_point": saturation_point,
        "last_improvement_at": improvements[-1] if improvements else None,
        "improvement_count": len(improvements),
        "improvements": improvements,
        "best_at": best_at,
    }


def _posthoc_near_dup_count(
    records: list[dict[str, Any]],
    anchor_code: str,
    store: EmbeddingStore,
) -> int:
    seen = [anchor_code]
    count = 0
    for record in records:
        if record.get("operator") == "region_seed" or record.get("filtered"):
            continue
        if _is_failed_operator(record.get("operator", "")):
            continue
        code = record["code"]
        try:
            distances = [store.distance(code, other) for other in seen]
        except Exception:
            continue
        if min(distances) < NOVEL_MIN_DIST:
            count += 1
        else:
            seen.append(code)
    return count


def _coverage_around(
    records: list[dict[str, Any]],
    center_code: str,
    store: EmbeddingStore,
) -> dict[str, Any]:
    distances: list[float] = []
    for record in records:
        if record.get("operator") == "region_seed" or record.get("filtered"):
            continue
        if _is_failed_operator(record.get("operator", "")):
            continue
        try:
            distances.append(store.distance(center_code, record["code"]))
        except Exception:
            continue
    return neighborhood_coverage(distances)


def compute_arm_metrics(
    state: ArmState,
    store: EmbeddingStore,
) -> dict[str, Any]:
    records = state.main_records()
    evaluated_series = _evaluated_series(records)
    saturation = _saturation_metrics(evaluated_series)
    best = saturation["best"]
    delta = (best - ANCHOR_SCORE) if best is not None else None
    generated_count = sum(
        1
        for record in records
        if record.get("operator") != "region_seed"
    )
    filtered_count = sum(1 for record in records if record.get("filtered"))
    near_dup_rate = filtered_count / generated_count if generated_count else None
    posthoc_count = _posthoc_near_dup_count(records, state.anchor["code"], store)
    efficiency: float | None = None
    samples_to_95: int | None = None
    if delta is not None and delta > 0:
        efficiency = saturation["evaluated_count"] / delta
        target = ANCHOR_SCORE + 0.95 * delta
        best_so_far: float | None = None
        for index, score in enumerate(evaluated_series, start=1):
            if isinstance(score, (int, float)) and math.isfinite(float(score)):
                best_so_far = (
                    max(best_so_far, float(score))
                    if best_so_far is not None
                    else float(score)
                )
            if best_so_far is not None and best_so_far >= target:
                samples_to_95 = index
                break
    best_code = None
    for record in records:
        if record.get("operator") != "region_seed" and is_valid_score(record.get("score")):
            if float(record["score"]) == best:
                best_code = record["code"]
                break
    if best_code is None:
        best_code = state.anchor["code"]
    return {
        "best": best,
        "delta": delta,
        "generated": generated_count,
        "evaluated": saturation["evaluated_count"],
        "filtered": filtered_count,
        "near_dup_rate_measured": near_dup_rate,
        "near_dup_count_posthoc": posthoc_count,
        "saturation": saturation,
        "efficiency_evaluated_per_delta": efficiency,
        "samples_to_95pct": samples_to_95,
        "coverage_anchor": _coverage_around(records, state.anchor["code"], store),
        "coverage_best": _coverage_around(records, best_code, store),
        "best_code_len": len(best_code),
    }


def _verify_metrics(state: ArmState) -> dict[str, Any]:
    final_best = _final_best(state)
    append_segments = state.segments.get("verify_append", [])
    append_best = max(
        (
            float(segment["best"])
            for segment in append_segments
            if segment.get("best") is not None
        ),
        default=None,
    )
    cross_segments = state.segments.get("verify_cross", [])
    cross_best = max(
        (
            float(segment["best"])
            for segment in cross_segments
            if segment.get("best") is not None
        ),
        default=None,
    )
    return {
        "final_best": final_best["score"],
        "append_segments": append_segments,
        "append_best": append_best,
        "append_increment": (
            append_best - float(final_best["score"])
            if append_best is not None
            else None
        ),
        "cross_segments": cross_segments,
        "cross_best": cross_best,
        "cross_increment": (
            cross_best - float(final_best["score"])
            if cross_best is not None
            else None
        ),
    }


def _recommended_death_window(results: dict[str, Any], store: EmbeddingStore) -> int:
    max_gap = 0
    for arm_key in ARMS:
        state = _rebuild_state(arm_key, _load_individual(ANCHOR_ID), results, store)
        series = _evaluated_series(state.main_records())
        improvements: list[int] = []
        best: float | None = None
        for index, score in enumerate(series, start=1):
            if isinstance(score, (int, float)) and math.isfinite(float(score)):
                if best is None or float(score) > best + IMPROVE_EPS:
                    best = max(best, float(score)) if best is not None else float(score)
                    improvements.append(index)
        gaps = [improvements[0] - 1] if improvements else []
        gaps.extend(
            improvements[index] - improvements[index - 1]
            for index in range(1, len(improvements))
        )
        if gaps:
            max_gap = max(max_gap, max(gaps))
    return max_gap


def _conclude(results: dict[str, Any], store: EmbeddingStore) -> dict[str, Any]:
    arm0 = results["arms"]["0_vanilla"]["metrics"]
    armb = results["arms"]["B_ridge"]["metrics"]
    armc = results["arms"]["C_multi"]["metrics"]
    max_design = max(armb["best"], armc["best"]) - arm0["best"]
    if max_design > 0.005:
        winner = "B_ridge" if armb["best"] >= armc["best"] else "C_multi"
        climb_branch = f"设计爬法有效：max(B,C)−原版EOH={max_design:.4f}>0.005，移植胜者 {winner} 进 region_runner"
    else:
        winner = None
        climb_branch = (
            f"此山上爬法设计不改变峰顶：max(B,C)−原版EOH={max_design:.4f}≤0.005，"
            "瓶颈在生成器/选山，下一步做多锚点换山"
        )
    c_minus_b = armc["best"] - armb["best"]
    if c_minus_b > 0.005:
        direction_branch = f"方向控制有价值：C−B={c_minus_b:.4f}>0.005"
    else:
        direction_branch = f"方向控制无额外价值：C−B={c_minus_b:.4f}≤0.005，保留更简单的 B"
    verify_increments: list[float] = []
    for arm_key in ARMS:
        verify = results["arms"][arm_key]["verify"]
        if verify.get("append_increment") is not None:
            verify_increments.append(float(verify["append_increment"]))
        if verify.get("cross_increment") is not None:
            verify_increments.append(float(verify["cross_increment"]))
    max_verify_increment = max(verify_increments) if verify_increments else None
    recommended_window = _recommended_death_window(results, store)
    if max_verify_increment is not None and max_verify_increment > IMPROVE_EPS:
        death_branch = (
            f"判死窗口（30 样本）太短：复验最大增量={max_verify_increment:.6f}>1e-6，"
            f"推荐窗口={recommended_window}（改进前最长无进展段）"
        )
    else:
        death_branch = (
            f"判死窗口（30 样本）充分：复验最大增量={max_verify_increment}"
            if max_verify_increment is not None
            else "判死复验未完成"
        )
    return {
        "max_design_minus_vanilla": max_design,
        "climb_branch": climb_branch,
        "winner": winner,
        "c_minus_b": c_minus_b,
        "direction_branch": direction_branch,
        "max_verify_increment": max_verify_increment,
        "recommended_window": recommended_window,
        "death_branch": death_branch,
    }


def write_report(results: dict[str, Any], args: argparse.Namespace) -> None:
    lines: list[str] = []
    lines.append("# 爬山爬法对照实验报告")
    lines.append("")
    lines.append(f"生成时间：{time.strftime('%Y-%m-%d %H:%M:%S')}")
    lines.append("")
    lines.append("## 一、实验配置")
    lines.append("")
    meta = results["meta"]
    lines.append(
        "- 锚点：`%s`，分数 %.6f（DB 代码 %d 字符）"
        % (meta["anchor_id"], meta["anchor_score"], meta["anchor_code_len"])
    )
    lines.append(
        "- 上坡目标：`%s`，分数 %.6f，期望距离 %.4f"
        % (meta["uphill_id"], meta["uphill_score"], meta["uphill_dist_expected"])
    )
    lines.append(
        "- LLM：%s / %s，thinking=disabled；评测器 10 秒硬时限、确定性种子 2025"
        % (meta["llm"]["host"], meta["llm"]["model"])
    )
    lines.append(
        "- 公共配置：每段 %d 样本；pop_size=%d、selection_num=%d、num_samplers=%d、"
        "num_evaluators=%d；近重复阈值 %.2f；距离桶 %s"
        % (
            meta["samples_per_segment"] or 30,
            meta["pop_size"],
            meta["selection_num"],
            meta["num_samplers"],
            meta["num_evaluators"],
            meta["novel_min_dist"],
            meta["buckets"],
        )
    )
    lines.append("")
    smoke = results.get("smoke") or {}
    if smoke:
        lines.append("## 二、冒烟测试")
        lines.append("")
        lines.append(
            "- 锚点可信分数复现：%.6f（期望 %.6f）→ %s"
            % (
                smoke.get("anchor_trusted_score"),
                ANCHOR_SCORE,
                "OK" if smoke.get("anchor_repro_ok") else "FAIL",
            )
        )
        lines.append(
            "- 距离回归守卫：%.6f（期望 %.4f）→ %s"
            % (
                smoke.get("uphill_distance"),
                UPHILL_DIST,
                "OK" if smoke.get("distance_guard_ok") else "FAIL",
            )
        )
        filter_test = smoke.get("filter_test") or {}
        lines.append(
            "- 过滤正确性：重复被跳过=%s，新代码放行=%s"
            % (
                filter_test.get("anchor_duplicate_skipped"),
                filter_test.get("novel_accepted"),
            )
        )
        lines.append("")

    lines.append("## 三、三臂逐段表（筛选 + 深挖）")
    lines.append("")
    missing_deep = [
        arm_key
        for arm_key in ARMS
        if not results["arms"][arm_key]["phases"]["deep"]["segments"]
    ]
    if missing_deep:
        lines.append(
            "> 数据范围说明：按用户决定，B/C 在筛选（5 段 × 30）后即停止，"
            "未跑深挖与判死复验；0 原版 EOH 跑满筛选+深挖+判死复验。"
            "因此三臂最终 best 的预算不一致（B/C 各 150 样本、原版 450+120 样本），"
            "趋势性结论以 150 样本口径的筛选对比为主，判定阈值仅作参考。"
        )
        lines.append("")
    for arm_key, arm_meta in ARMS.items():
        arm = results["arms"][arm_key]
        lines.append(f"### {arm_meta['label']}（{arm_key}）")
        lines.append("")
        lines.append("| 阶段 | 段 | 生成 | 评测 | filtered | 有效 | best | 漂移 |")
        lines.append("|---|---|---|---|---|---|---|---|")
        for phase in ("screening", "deep"):
            for segment in arm["phases"][phase]["segments"]:
                lines.append(
                    "| %s | %d | %d | %d | %d | %d | %s | %s |"
                    % (
                        phase,
                        segment["segment"],
                        segment["generated"],
                        segment["evaluated"],
                        segment["filtered"],
                        segment["valid"],
                        f"{segment['best']:.6f}" if segment.get("best") is not None else "-",
                        "是" if segment.get("drift") else "",
                    )
                )
        lines.append("")
    lines.append("## 四、预声明指标（三臂同口径）")
    lines.append("")
    lines.append("| 指标 | 0 原版 EOH | B 脊线跟随 | C 多向勘探 |")
    lines.append("|---|---|---|---|")
    headers = [
        ("best", lambda m: f"{m['best']:.6f}" if m.get("best") is not None else "-"),
        ("对锚点增量", lambda m: f"{m['delta']:.6f}" if m.get("delta") is not None else "-"),
        ("评测样本数", lambda m: str(m["evaluated"])),
        ("filtered/生成", lambda m: f"{m['filtered']}/{m['generated']}"),
        (
            "近重复率(filtered/生成)",
            lambda m: (
                f"{m['near_dup_rate_measured']:.4f}"
                if m.get("near_dup_rate_measured") is not None
                else "-"
            ),
        ),
        (
            "事后口径近重复数",
            lambda m: str(m["near_dup_count_posthoc"]),
        ),
        (
            "饱和点(30样本窗口)",
            lambda m: (
                str(m["saturation"]["saturation_point"])
                if m["saturation"].get("saturation_point") is not None
                else "未饱和"
            ),
        ),
        (
            "最后改进处",
            lambda m: (
                str(m["saturation"]["last_improvement_at"])
                if m["saturation"].get("last_improvement_at") is not None
                else "-"
            ),
        ),
        (
            "效率(评测/增量)",
            lambda m: (
                f"{m['efficiency_evaluated_per_delta']:.0f}"
                if m.get("efficiency_evaluated_per_delta") is not None
                else "-"
            ),
        ),
        (
            "达95%增量所需样本",
            lambda m: (
                str(m["samples_to_95pct"])
                if m.get("samples_to_95pct") is not None
                else "-"
            ),
        ),
        (
            "覆盖(锚点/最终best)",
            lambda m: f"{m['coverage_anchor']['covered']}/{m['coverage_best']['covered']}",
        ),
    ]
    for label, fmt in headers:
        values = [
            fmt(results["arms"][arm_key]["metrics"])
            for arm_key in ("0_vanilla", "B_ridge", "C_multi")
        ]
        lines.append("| %s | %s | %s | %s |" % (label, values[0], values[1], values[2]))
    lines.append("")
    lines.append("### 饱和曲线（best @ 累计评测样本数）")
    lines.append("")
    lines.append("| 累计评测 | 0 原版 EOH | B 脊线跟随 | C 多向勘探 |")
    lines.append("|---|---|---|---|")
    for checkpoint in (50, 100, 150, 200, 300):
        values = []
        for arm_key in ("0_vanilla", "B_ridge", "C_multi"):
            best_at = results["arms"][arm_key]["metrics"]["saturation"]["best_at"]
            value = best_at.get(str(checkpoint))
            values.append(f"{value:.6f}" if value is not None else "-")
        lines.append("| %d | %s | %s | %s |" % (checkpoint, values[0], values[1], values[2]))
    lines.append("")
    lines.append("## 五、判死复验")
    lines.append("")
    lines.append("| 臂 | 最终 best | 追加 best/增量 | 交叉 best/增量（策略） |")
    lines.append("|---|---|---|---|")
    for arm_key in ARMS:
        verify = results["arms"][arm_key]["verify"]
        cross_info = results["arms"][arm_key]["phases"]["verify_cross"]
        cross_strategy = cross_info.get("cross_strategy", "-") if isinstance(cross_info, dict) else "-"
        lines.append(
            "| %s | %.6f | %s / %s | %s / %s（%s） |"
            % (
                arm_key,
                verify["final_best"],
                (
                    f"{verify['append_best']:.6f}"
                    if verify.get("append_best") is not None
                    else "-"
                ),
                (
                    f"{verify['append_increment']:.6f}"
                    if verify.get("append_increment") is not None
                    else "-"
                ),
                (
                    f"{verify['cross_best']:.6f}"
                    if verify.get("cross_best") is not None
                    else "-"
                ),
                (
                    f"{verify['cross_increment']:.6f}"
                    if verify.get("cross_increment") is not None
                    else "-"
                ),
                cross_strategy,
            )
        )
    lines.append("")
    lines.append("## 六、判定分支")
    lines.append("")
    conclusion = results.get("conclusion") or {}
    for key in ("climb_branch", "direction_branch", "death_branch"):
        lines.append(f"- {key}：{conclusion.get(key, '未完成')}")
    lines.append("")
    lines.append("原始数据：`climb_results.json`（本目录同级）。")
    lines.append("")
    report_path = Path(args.report_path)
    report_path.parent.mkdir(parents=True, exist_ok=True)
    report_path.write_text("\n".join(lines), encoding="utf-8")
    _log(f"报告已写入 {report_path}")


def main() -> None:
    parser = argparse.ArgumentParser(description="三臂爬山爬法对照实验")
    parser.add_argument("--smoke", action="store_true", help="只跑冒烟测试")
    parser.add_argument(
        "--phase",
        choices=("screening", "deep", "verify", "all"),
        default="all",
        help="运行阶段",
    )
    parser.add_argument("--segments", type=int, default=5, help="筛选段数（默认 5）")
    parser.add_argument("--deep-segments", type=int, default=10, help="深挖段数（默认 10）")
    parser.add_argument("--verify-segments", type=int, default=2, help="判死复验段数（默认 2）")
    parser.add_argument(
        "--samples-per-segment",
        type=int,
        default=30,
        help="每段样本数（默认 30，冒烟用 5）",
    )
    parser.add_argument(
        "--results-path",
        type=str,
        default=str(DEFAULT_RESULTS_PATH),
        help="结果 JSON 路径",
    )
    parser.add_argument(
        "--report-path",
        type=str,
        default=str(DEFAULT_REPORT_PATH),
        help="报告 Markdown 路径",
    )
    parser.add_argument(
        "--finalize-only",
        action="store_true",
        help="只基于已有数据计算指标/结论并写报告，不运行任何阶段",
    )
    args = parser.parse_args()

    anchor_node = _load_individual(ANCHOR_ID)
    uphill_node = _load_individual(UPHILL_ID)
    if abs(float(anchor_node["score"]) - ANCHOR_SCORE) > 1e-12:
        raise RuntimeError(
            f"锚点分数与计划不符：DB={anchor_node['score']} 计划={ANCHOR_SCORE}"
        )
    if abs(float(uphill_node["score"]) - UPHILL_SCORE) > 1e-12:
        raise RuntimeError(
            f"上坡目标分数与计划不符：DB={uphill_node['score']} 计划={UPHILL_SCORE}"
        )

    results = _load_results(args)
    if results is None:
        results = _fresh_results(anchor_node, uphill_node)
        _save_results(results, args)
    results["meta"]["samples_per_segment"] = args.samples_per_segment
    results["meta"]["segments"] = args.segments
    results["meta"]["deep_segments"] = args.deep_segments
    results["meta"]["verify_segments"] = args.verify_segments

    task = load_circle_packing_evaluation()(timeout_seconds=10)

    if args.smoke:
        llm = _build_llm()
        run_smoke(
            task=task,
            llm=llm,
            anchor_node=anchor_node,
            uphill_node=uphill_node,
            results=results,
            args=args,
        )
        _save_results(results, args)
        return

    if args.finalize_only:
        _finalize(results, anchor_node, args)
        return

    llm = _build_llm()

    if args.phase in ("screening", "all"):
        _run_screening(
            task=task,
            llm=llm,
            anchor_node=anchor_node,
            results=results,
            args=args,
        )
    if args.phase in ("deep", "all"):
        _run_deep(
            task=task,
            llm=llm,
            anchor_node=anchor_node,
            results=results,
            args=args,
        )
    if args.phase in ("verify", "all"):
        _run_verify(
            task=task,
            llm=llm,
            anchor_node=anchor_node,
            results=results,
            args=args,
        )

    _finalize(results, anchor_node, args)
    _log("全部阶段完成。")


def _finalize(
    results: dict[str, Any],
    anchor_node: dict[str, Any],
    args: argparse.Namespace,
) -> None:
    store = EmbeddingStore()
    for arm_key in ARMS:
        state = _rebuild_state(arm_key, anchor_node, results, store)
        results["arms"][arm_key]["metrics"] = compute_arm_metrics(state, store)
        results["arms"][arm_key]["verify"] = _verify_metrics(state)
    results["conclusion"] = _conclude(results, store)
    results["generated_at"] = time.strftime("%Y-%m-%d %H:%M:%S")
    _save_results(results, args)
    write_report(results, args)


if __name__ == "__main__":
    main()
