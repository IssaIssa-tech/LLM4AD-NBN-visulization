from __future__ import annotations

import json
import math
import time
from pathlib import Path
from typing import Any
from visual_platform.services.research_history import current_call_id

import numpy as np

from visual_platform.nbn.region_analysis import (
    MIN_EDGE_DIST,
    NEIGHBORHOOD_BUCKETS,
    NOVEL_MIN_DIST,
    RING_HI,
    RING_LO,
    SHIP_QUANTILE,
    candidate_child_flags,
    classify_new_samples,
    exploration_conclusion,
    final_verdict,
    family_fold,
    is_valid_score,
    neighborhood_coverage,
    normalize_valid_score,
    score_quantiles,
)
from visual_platform.runtime.runner_llm import TimeoutWrappedLLM
from visual_platform.runtime.runner_modes import (
    EVALUABILITY_CONSTRAINTS,
    distinct_function_nodes,
    hydrate_nodes_from_db,
    int_config,
    normalize_node_list,
    persist_sample_record,
    user_guidance_text,
)
from visual_platform.runtime.runner_progress import (
    has_generated_samples,
    merge_real_run_meta,
    record_run_timing,
    update_run_progress,
)
from visual_platform.runtime.runner_task_loader import CeleryExecutor
from visual_platform.services import revision_generation_service


def _region_shape_valid(region: Any) -> bool:
    if not isinstance(region, dict):
        return False
    region_type = str(region.get("type", "") or "").strip()
    a = str(region.get("a", "") or "").strip()
    if region_type not in {"edge", "expand"} or not a:
        return False
    if region_type == "edge" and not str(region.get("b", "") or "").strip():
        return False
    if region_type == "edge" and a == str(region.get("b", "") or "").strip():
        return False
    return True


def validate_region_nodes(region: dict[str, Any], nodes_by_id: dict[str, dict[str, Any]]) -> tuple[dict[str, Any] | None, str | None]:
    """Validate that region endpoints exist, are distinct, and carry valid scores."""
    region_type = str(region.get("type", "") or "").strip()
    a_id = str(region.get("a", "") or "")
    b_id = str(region.get("b", "") or "")

    a_node = nodes_by_id.get(a_id)
    if a_node is None:
        return None, f"区域端点 A 不存在于数据库：{a_id}"
    if not _node_source(a_node):
        return None, f"区域端点 A 缺少可嵌入的代码：{a_id}"
    a_score = normalize_valid_score(a_node.get("score"))
    if a_score is None:
        return None, f"区域端点 A 无有效分数（无法作为搜索锚点）：{a_id}"

    if region_type == "edge":
        b_node = nodes_by_id.get(b_id)
        if b_node is None:
            return None, f"区域端点 B 不存在于数据库：{b_id}"
        if not _node_source(b_node):
            return None, f"区域端点 B 缺少可嵌入的代码：{b_id}"
        b_score = normalize_valid_score(b_node.get("score"))
        if b_score is None:
            return None, f"区域端点 B 无有效分数：{b_id}"
        return {
            "type": region_type,
            "a": a_id,
            "b": b_id,
            "a_score": a_score,
            "b_score": b_score,
        }, None

    return {"type": region_type, "a": a_id, "a_score": a_score}, None


def _load_graph_artifact(revision_id: str | None) -> dict[str, Any] | None:
    """Best-effort load of a revision's full graph artifact (JSON on disk)."""
    if not revision_id:
        return None
    from visual_platform.config import RUNS_DIR

    graph_path = RUNS_DIR / revision_id / "graph_full.json"
    if not graph_path.is_file():
        return None
    try:
        data = json.loads(graph_path.read_text(encoding="utf-8"))
        return data if isinstance(data, dict) else None
    except (OSError, json.JSONDecodeError):
        return None


def _load_history_samples(source_revision_id: str | None) -> list[dict[str, Any]]:
    """All graph members of the source revision (merged lineage), deduplicated."""
    from visual_platform.repositories.individual_repository import (
        list_member_individuals,
    )

    if source_revision_id:
        try:
            members = list_member_individuals(source_revision_id)
            if members:
                return members
        except Exception:
            pass
    return []


def _node_source(node: dict[str, Any]) -> str:
    return (
        str(node.get("function", "") or "").strip()
        or str(node.get("program", "") or "").strip()
        or str(node.get("algorithm", "") or "").strip()
    )


def _champion_avoidance_block(
    source_revision_id: str | None,
    history_samples: list[dict[str, Any]],
    ship_threshold: float,
) -> str:
    """Describe the dominant family so prompts can explicitly avoid re-deriving it."""
    graph = _load_graph_artifact(source_revision_id)
    if not graph or not isinstance(graph.get("nodes"), list):
        return ""
    valid_nodes = [
        node
        for node in graph["nodes"]
        if is_valid_score(node.get("rawScore", node.get("score")))
    ]
    if len(valid_nodes) < 8:
        return ""
    folded = family_fold(valid_nodes)
    champion = folded["families"].get(folded["championId"]) if folded["championId"] else None
    if not champion:
        return ""
    rep_id = str(champion.get("rep_id", "") or "")
    rep_score = champion.get("rep_score")
    size = int(champion.get("size", 0) or 0)
    total_valid = max(int(folded.get("validCount", 0) or 0), 1)
    ratio = size / total_valid

    rep_source = ""
    for sample in history_samples:
        if str(sample.get("id") or "") == rep_id:
            rep_source = _node_source(sample)[:600]
            break

    lines = [
        "[AVOID -- the dominant family]",
        (
            f"The single largest family ({size} valid solutions, ~{ratio * 100:.0f}% of all valid solutions) "
            f"plateaus at score {rep_score:.6f} and has been re-derived thousands of times. "
            "Scores above it are only reachable through a DIFFERENT approach; anything scoring below "
            f"{ship_threshold:.4f} is below the useful threshold."
        ),
    ]
    if rep_source:
        lines.append(f"Dominant family representative code:\n{rep_source}")
    return "\n\n".join(lines)


def _direction_seeds(region: dict[str, Any], anchor_node: dict[str, Any], graph: dict[str, Any] | None) -> list[dict[str, Any]]:
    """Return the direction endpoint node(s) for a region.

    Edge: the parent endpoint B. Expand: up to 3 nearest graph neighbours of A
    (parent + children by ascending semantic distance).
    """
    region_type = str(region.get("type", "") or "").strip()
    nodes_by_id = {}
    if graph and isinstance(graph.get("nodes"), list):
        nodes_by_id = {str(node.get("id") or ""): node for node in graph["nodes"]}
    if region_type == "edge":
        b_id = str(region.get("b", "") or "")
        b_node = nodes_by_id.get(b_id)
        return [b_node] if b_node else []

    anchor_id = str(anchor_node.get("id") or "")
    anchor_index = anchor_node.get("ofecIndex")
    peers: list[dict[str, Any]] = []
    if graph and isinstance(graph.get("edges"), list):
        for edge in graph["edges"]:
            source = str(edge.get("source") or "")
            target = str(edge.get("target") or "")
            distance = edge.get("distance")
            peer_id = None
            if source == anchor_id:
                peer_id = target
            elif target == anchor_id:
                peer_id = source
            if peer_id and peer_id != anchor_id and peer_id in nodes_by_id:
                try:
                    distance_val = float(distance)
                except (TypeError, ValueError):
                    distance_val = math.inf
                peers.append({"node": nodes_by_id[peer_id], "distance": distance_val})
    # Fallback: use ofecParentIndex/children from node records when edges are absent.
    if not peers and isinstance(anchor_index, int):
        for node in graph.get("nodes", []) if graph else []:
            parent_index = node.get("ofecParentIndex")
            if isinstance(parent_index, int) and parent_index == anchor_index:
                peers.append({"node": node, "distance": node.get("distanceToParent", math.inf)})
    peers.sort(key=lambda item: (not math.isfinite(float(item["distance"])), float(item["distance"])))
    return [item["node"] for item in peers[:3]]


def _anchor_node_dict(node: dict[str, Any]) -> dict[str, Any]:
    result = {
        "id": str(node.get("id") or ""),
        "sampleOrder": node.get("sampleOrder", node.get("sample_order")),
        "score": node.get("score"),
        "rawScore": node.get("rawScore", node.get("score")),
        "algorithm": str(node.get("algorithm", "") or node.get("algorithmSummary", "") or "").strip(),
        "functionPreview": str(
            node.get("functionPreview", "")
            or node.get("function", "")
            or node.get("program", "")
            or ""
        ).strip(),
        "operator": str(node.get("operator", "") or "").strip(),
    }
    if node.get("d_a") is not None:
        result["d_a"] = node.get("d_a")
    return result


def _pick_diverse_seed_pool(
    pool: list[dict[str, Any]],
    limit: int,
) -> list[dict[str, Any]]:
    """Pick carry-over seeds with distance-bucket diversity: keep at least one
    representative per distance band, then fill the remaining slots by score."""
    if limit <= 0 or not pool:
        return []
    by_bucket: dict[str | None, list[dict[str, Any]]] = {}
    for node in pool:
        d = node.get("d_a")
        key: str | None = None
        if isinstance(d, (int, float)) and math.isfinite(float(d)):
            for lo, hi in NEIGHBORHOOD_BUCKETS:
                if lo <= float(d) < hi:
                    key = f"{lo:.2f}-{hi:.2f}"
                    break
        by_bucket.setdefault(key, []).append(node)

    picked: list[dict[str, Any]] = []
    picked_ids: set[int] = set()
    for key in sorted(by_bucket, key=lambda k: (k is None, k or "")):
        bucket = sorted(
            by_bucket[key],
            key=lambda node: -(
                float(node.get("score") or 0.0)
                if isinstance(node.get("score"), (int, float))
                else -1e18
            ),
        )
        if bucket:
            picked.append(bucket[0])
            picked_ids.add(id(bucket[0]))
        if len(picked) >= limit:
            return picked
    rest = sorted(
        (node for node in pool if id(node) not in picked_ids),
        key=lambda node: -(
            float(node.get("score") or 0.0)
            if isinstance(node.get("score"), (int, float))
            else -1e18
        ),
    )
    picked.extend(rest)
    return picked[:limit]


def _fusion_partner_node(
    anchor: dict[str, Any],
    graph: dict[str, Any] | None,
) -> dict[str, Any] | None:
    """Nearest better-scoring partner for high-score fusion: the anchor's NBN
    parent (its nearest better solution by construction). Returns a seed-able
    node dict, or None when unavailable (root anchor / missing code)."""
    if not graph or not isinstance(graph.get("nodes"), list):
        return None
    anchor_id = str(anchor.get("id") or "")
    anchor_graph_node = next(
        (n for n in graph["nodes"] if str(n.get("id") or "") == anchor_id),
        None,
    )
    parent_index = anchor_graph_node.get("ofecParentIndex") if anchor_graph_node else None
    parent_node = None
    if isinstance(parent_index, int):
        parent_node = next(
            (n for n in graph["nodes"] if n.get("ofecIndex") == parent_index),
            None,
        )
    if parent_node is None or str(parent_node.get("id") or "") == anchor_id:
        return None
    try:
        from visual_platform.repositories import get_individuals_by_ids

        records = get_individuals_by_ids([str(parent_node.get("id") or "")])
        if not records:
            return None
        record = records[0]
        code = str(
            record.get("function")
            or record.get("program")
            or record.get("code")
            or ""
        ).strip()
        if not code:
            return None
    except Exception:
        return None
    return _anchor_node_dict(
        {
            "id": str(parent_node.get("id") or ""),
            "sampleOrder": parent_node.get("sampleOrder", parent_node.get("sample_order")),
            "score": parent_node.get("rawScore", parent_node.get("score")),
            "rawScore": parent_node.get("rawScore", parent_node.get("score")),
            "algorithm": str(parent_node.get("algorithmSummary", "") or "").strip(),
            "functionPreview": code,
        }
    )


def _build_region_guidance(
    region: dict[str, Any],
    anchor: dict[str, Any],
    direction_nodes: list[dict[str, Any]],
    *,
    d_ab: float | None,
    user_prompt: str,
    champion_block: str,
) -> str:
    region_type = str(region.get("type", "") or "").strip()
    anchor_score = anchor.get("score")
    anchor_summary = str(anchor.get("algorithm", "") or "").strip()[:400]
    anchor_code = str(anchor.get("functionPreview", "") or "").strip()[:1600]

    parts: list[str] = []
    if region_type == "edge":
        direction = direction_nodes[0] if direction_nodes else {}
        direction_score = direction.get("score")
        direction_summary = str(direction.get("algorithm", "") or "").strip()[:400]
        direction_code = str(direction.get("functionPreview", "") or "").strip()[:1600]
        goal_lines = [
            "[REGION GOAL -- fill the semantic gap between two proven endpoints]",
            (
                f"Endpoint A `{anchor.get('id')}` (score {anchor_score}) and endpoint B "
                f"`{direction.get('id')}` (score {direction_score}) are both live solutions "
                f"separated by a large semantic distance (d={d_ab:.4f}). "
                "Produce an algorithm that lies semantically BETWEEN them: keep the core "
                "structure/objective of A and adopt the placement strategy of B, or blend "
                "the two approaches into an intermediate design. Do not reproduce either "
                "endpoint verbatim."
            ),
        ]
        score_goal: list[float] = []
        if isinstance(anchor_score, (int, float)):
            score_goal.append(float(anchor_score))
        if isinstance(direction_score, (int, float)):
            score_goal.append(float(direction_score))
        if score_goal:
            target = min(score_goal)
            goal_lines.append(
                f"Score target: the endpoints score ~{max(score_goal):.4f} / {target:.4f}; "
                f"your intermediate should aim for a score of at least {target:.4f} "
                "(quality close to the endpoints, not a naive placeholder)."
            )
        if anchor_summary:
            goal_lines.append(f"Endpoint A summary:\n{anchor_summary}")
        if anchor_code:
            goal_lines.append(f"Endpoint A code:\n{anchor_code}")
        if direction_summary:
            goal_lines.append(f"Endpoint B summary:\n{direction_summary}")
        if direction_code:
            goal_lines.append(f"Endpoint B code:\n{direction_code}")
        parts.append("\n".join(goal_lines))
    else:
        goal_lines = [
            "[REGION GOAL -- evolve from the anchor, not bound by it]",
            (
                f"Anchor `{anchor.get('id')}` (score {anchor_score}) is a proven high-scoring "
                "solution, but it is unlikely to be the best possible form of this idea. "
                "Produce solutions that START from its approach and EVOLVE it: change "
                "structure, swap strategies, blend in neighbouring ideas, or make substantial "
                "improvements — as long as the result stays RELATED to the anchor "
                f"(semantic distance roughly {RING_LO:.2f} to {RING_HI:.2f}). "
                "PREFER the tight band 0.02-0.09 — close variations of the anchor's exact "
                "approach — before spreading outward. "
                "Do not copy the anchor, and do not abandon it for an unrelated algorithm. "
                "The anchor is a known sample, not the ceiling: aim to BEAT it."
            ),
        ]
        if isinstance(anchor_score, (int, float)):
            anchor_numeric = float(anchor_score)
            goal_lines.append(
                f"Quality floor: don't collapse into an empty/naive layout — aim to stay above "
                f"~{anchor_numeric * 0.8:.4f} (~80% of the anchor) while pushing for higher."
            )
        if anchor_summary:
            goal_lines.append(f"Anchor summary:\n{anchor_summary}")
        if anchor_code:
            goal_lines.append(f"Anchor code:\n{anchor_code}")
        for index, direction in enumerate(direction_nodes[:3], start=1):
            goal_lines.append(
                f"Neighbour {index}: `{direction.get('id')}` (score {direction.get('score')}) "
                f"summary: {str(direction.get('algorithm', '') or '')[:300]}"
            )
        parts.append("\n".join(goal_lines))

    if champion_block:
        parts.append(champion_block)
    guidance = user_guidance_text(user_prompt)
    if guidance:
        parts.append(guidance)
    parts.append(EVALUABILITY_CONSTRAINTS)
    return "\n\n".join(part for part in parts if part)


class RegionTimeoutLLM(TimeoutWrappedLLM):
    """Timeout wrapper whose ``close()`` is a no-op: one shared LLM instance is
    reused across every segment of a region run (EoH calls ``sampler.llm.close()``
    at the end of each ``run()``)."""

    def close(self) -> None:
        return None


def _create_region_profiler_class() -> type:
    """Return a ``RegionEoHProfiler`` subclass of the real EoHProfiler.

    The class is created lazily because importing ``llm4ad.method.*`` eagerly
    imports torch / wandb / tensorboard / sklearn (~280s in a fresh process,
    see ``llm4ad/__init__.py``). Real EOH runs already pay this cost on demand;
    module imports of the platform must not.
    """
    from llm4ad.method.eoh.profiler import EoHProfiler

    class RegionEoHProfiler(EoHProfiler):
        """Profiler that persists region samples and collects them in memory for
        per-segment drift/hit analysis."""

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
            self._cur_gen = 0

        def _write_json(
            self,
            function: Any,
            program: str = "",
            *,
            record_type: str = "history",
            record_sep: int = 200,
        ) -> None:
            del record_sep
            if not self._log_dir:
                return

            sample_order = self._num_samples
            operator = str(getattr(function, "operator", "") or "")
            if operator == "region_seed":
                prefixed_operator = "region_seed"
            else:
                prefixed_operator = f"region_{operator}" if operator else "region_unknown"
            content = {
                "sample_order": sample_order,
                "research_call_id": current_call_id.get() if 'seed' not in operator else None,
                "algorithm": getattr(function, "algorithm", ""),
                "function": str(function),
                "score": getattr(function, "score", None),
                "operator": prefixed_operator,
                "parents": getattr(function, "parents", []),
                "program": program,
            }
            self._collected.append(dict(content))
            revision_id = Path(self._log_dir).parent.name
            persist_sample_record(
                Path(self._log_dir),
                sample_order,
                content,
                sample_id=f"run-{revision_id}-s{sample_order}",
                generation=getattr(self, "_cur_gen", 0),
                source_kind="current",
                origin_kind="region_generated",
            )

            eval_time = getattr(function, "evaluate_time", None)
            if isinstance(eval_time, (int, float)):
                record_run_timing(
                    Path(self._log_dir),
                    "sampleEvaluationMs",
                    float(eval_time) * 1000.0,
                    extra={"sampleOrder": sample_order, "operator": operator},
                )
            sample_time = getattr(function, "sample_time", None)
            if isinstance(sample_time, (int, float)):
                record_run_timing(
                    Path(self._log_dir),
                    "sampleGenerationMs",
                    float(sample_time) * 1000.0,
                    extra={"sampleOrder": sample_order, "operator": operator},
                )
            update_run_progress(
                Path(self._log_dir),
                phase="region_segment",
                phaseLabel="区域搜索采样中",
                sampleCount=sample_order,
                lastSampleOrder=sample_order,
                lastOperator=operator,
                lastScore=getattr(function, "score", None),
                currentGeneration=getattr(self, "_cur_gen", 0),
            )

        def register_population(self, pop: Any) -> None:
            previous_generation = self._cur_gen
            super().register_population(pop)
            if not self._log_dir:
                return
            if getattr(pop, "generation", previous_generation) != previous_generation:
                self._cur_gen = getattr(pop, "generation", previous_generation)
                update_run_progress(
                    Path(self._log_dir),
                    phase="region_segment",
                    phaseLabel="区域搜索演化中",
                    currentGeneration=self._cur_gen,
                    populationSize=len(getattr(pop, "population", []) or []),
                )

        def finish(self) -> None:
            try:
                super().finish()
            except AttributeError:
                pass

    return RegionEoHProfiler


def _embed_samples(samples: list[dict[str, Any]], *, label: str) -> np.ndarray:
    from visual_platform.nbn.bridge import get_codet5_embedding_matrix

    vectors, _ = get_codet5_embedding_matrix(samples)
    return vectors


def _segment_stats(
    segment_samples: list[dict[str, Any]],
    region: dict[str, Any],
    anchor_vectors: dict[str, np.ndarray],
    parent_vector: np.ndarray | None,
    history_vectors: np.ndarray | None,
    ship_threshold: float,
    *,
    gap_upper: float | None = None,
) -> dict[str, Any]:
    generated = len(segment_samples)
    valid_samples = [
        sample for sample in segment_samples if is_valid_score(sample.get("score"))
    ]
    invalid = generated - len(valid_samples)
    best_score: float | None = None
    if valid_samples:
        best_score = max(float(sample["score"]) for sample in valid_samples)

    hits: list[dict[str, Any]] = []
    candidate_children: list[dict[str, Any]] = []
    novel_count = 0
    ship_count = 0
    if valid_samples:
        vectors = _embed_samples(
            [{"function": str(sample.get("function", "") or "")} for sample in valid_samples],
            label="segment_valid_samples",
        )
        d_parent_all: np.ndarray | None = None
        if region.get("type") == "expand" and parent_vector is not None:
            d_parent_all = 1.0 - np.clip(
                np.dot(vectors, np.asarray(parent_vector, dtype=np.float32).reshape(1, -1).T),
                -1.0,
                1.0,
            ).reshape(-1)
        records = classify_new_samples(
            vectors,
            [sample.get("score") for sample in valid_samples],
            region,
            anchor_vectors,
            history_vectors,
            ship_threshold=ship_threshold,
        )
        for sample, record in zip(valid_samples, records, strict=False):
            sample["_region"] = record
            if record["hit"]:
                hits.append(
                    {
                        "sample_order": sample.get("sample_order"),
                        "score": record["score"],
                        "d_a": record["d_a"],
                    }
                )
            if record["novel"]:
                novel_count += 1
            if record["ship"]:
                ship_count += 1
            if region.get("type") == "expand":
                d_parent = (
                    float(d_parent_all[int(record["index"])])
                    if d_parent_all is not None
                    else None
                )
                if candidate_child_flags(
                    record["d_a"],
                    d_parent,
                    gap_upper=gap_upper,
                ):
                    candidate_children.append(
                        {
                            "sample_order": sample.get("sample_order"),
                            "score": record["score"],
                            "d_a": record["d_a"],
                        }
                    )

    drift = len(hits) == 0 and novel_count == 0 and generated > 0
    return {
        "generated": generated,
        "valid": len(valid_samples),
        "invalid": invalid,
        "hit_count": len(hits),
        "hit_ids": [str(item.get("sample_order")) for item in hits],
        "hits": hits,
        "candidate_child_count": len(candidate_children),
        "candidate_children": candidate_children,
        "novel_count": novel_count,
        "ship_count": ship_count,
        "drift": drift,
        "best_score": best_score,
    }


def _ledger_record(
    segment: int,
    revision_id: str,
    seeds: list[str],
    stats: dict[str, Any],
    *,
    verdict: str | None = None,
    anchor_switched: bool = False,
    note: str = "",
) -> dict[str, Any]:
    return {
        "segment": segment,
        "revision_id": revision_id,
        "seeds": seeds,
        "verdict": verdict,
        "anchor_switched": anchor_switched,
        "note": note,
        **stats,
    }


def _write_ledger(revision_dir: Path, records: list[dict[str, Any]]) -> None:
    path = revision_dir / "region_ledger.jsonl"
    with path.open("w", encoding="utf-8") as handle:
        for record in records:
            handle.write(json.dumps(record, ensure_ascii=False) + "\n")


def _write_report(
    revision_dir: Path,
    *,
    region: dict[str, Any],
    anchor: dict[str, Any],
    neighborhood: list[dict[str, Any]],
    coverage: dict[str, Any],
    novel_rate: float,
    conclusion: dict[str, Any],
    fusion_mode: str,
    fusion_used_segments: list[int],
    direction_nodes: list[dict[str, Any]],
    d_ab: float | None,
    ship_threshold: float,
    segments: list[dict[str, Any]],
    verdict: str,
    anchor_trail: list[dict[str, Any]],
) -> None:
    lines = [
        "# 区域搜索报告（region_search）",
        "",
        f"- 区域: {json.dumps(region, ensure_ascii=False)}",
        f"- 锚点 A: `{anchor.get('id')}` (score={anchor.get('score')})",
    ]
    if region.get("type") == "edge" and direction_nodes:
        lines.append(
            f"- 端点 B: `{direction_nodes[0].get('id')}` (score={direction_nodes[0].get('score')})"
        )
    if d_ab is not None:
        lines.append(f"- 端点语义距离 d(A,B)={d_ab:.5f}")
    lines.append(f"- 出货分位阈值 P{int(round(SHIP_QUANTILE * 100))}={ship_threshold:.6f}")
    lines.extend(
        [
            "",
            "| 段 | generated | valid | invalid | hits | 候选子节点 | novel | ships | best | drift |",
            "|---|---|---|---|---|---|---|---|---|---|",
        ]
    )
    for record in segments:
        lines.append(
            f"| {record.get('segment')} | {record.get('generated', 0)} | {record.get('valid', 0)} "
            f"| {record.get('invalid', 0)} | {record.get('hit_count', 0)} "
            f"| {record.get('candidate_child_count', 0)} | {record.get('novel_count', 0)} "
            f"| {record.get('ship_count', 0)} | {record.get('best_score', '-')} "
            f"| {'是' if record.get('drift') else '否'} |"
        )
    total_generated = sum(int(r.get("generated", 0) or 0) for r in segments)
    total_valid = sum(int(r.get("valid", 0) or 0) for r in segments)
    total_hits = sum(int(r.get("hit_count", 0) or 0) for r in segments)
    total_candidates = sum(int(r.get("candidate_child_count", 0) or 0) for r in segments)
    total_novel = sum(int(r.get("novel_count", 0) or 0) for r in segments)
    total_ships = sum(int(r.get("ship_count", 0) or 0) for r in segments)
    region_best = max(
        (float(r.get("best_score") or 0.0) for r in segments if r.get("best_score") is not None),
        default=None,
    )
    trail_text = " → ".join(
        "{0}:{1}({2})".format(item.get("segment"), item.get("id"), item.get("score"))
        for item in anchor_trail
    )
    lines.extend(
        [
            "",
            f"## 结论：{verdict}",
            "",
            f"- 总计：generated={total_generated}, valid={total_valid}, "
            f"hits={total_hits}, 候选子节点={total_candidates}, novel={total_novel}, ships={total_ships}",
            f"- 区域内 best：{region_best}（锚点初始 {anchor.get('score')}）",
            f"- 锚点邻域成员（0.02~0.30，语义距离）：{len(neighborhood)} 个",
            (
                f"- 邻域最高分：{max((float(item['score']) for item in neighborhood if item.get('score') is not None), default=None)}"
            ),
            (
                f"- 邻域覆盖：{coverage.get('covered', 0)}/{coverage.get('total', len(NEIGHBORHOOD_BUCKETS))} 桶"
                f"（{coverage.get('buckets', {})}）"
            ),
            f"- 新颖率：{novel_rate * 100:.1f}%（近重复率 {(1.0 - novel_rate) * 100:.1f}%）",
            f"- 探索结论：{conclusion.get('conclusion', '仍有空间')}",
            f"- 融合模式：{fusion_mode}"
            + (
                f"，使用段：{fusion_used_segments}"
                if fusion_used_segments
                else ""
            ),
            (
                f"- 超越锚点：{'是' if region_best is not None and isinstance(anchor.get('score'), (int, float)) and region_best > float(anchor.get('score')) else '否'}"
            ),
            (
                f"- 有效率：{total_valid / total_generated * 100:.1f}%"
                if total_generated
                else "- 有效率：-"
            ),
            f"- 锚点漂移轨迹：{trail_text}",
            "- 拓扑验收：revision 完成后会自动重建 NBN 图，可在图上查看长边是否被切分/走廊是否加密。",
        ]
    )
    if total_generated == 0:
        lines.extend(
            [
                "",
                "> ⚠️ 本次所有段都没有生成任何新解（每段预算被初始种子占满）。",
                "> 这里的 BUDGET_OUT 与「新颖率 0%」**不代表该区域没货**，而是根本没搜：",
                "> 请把「每段样本数」调到大于本段种子数（edge 区域至少是 2）后重跑。",
            ]
        )
    (revision_dir / "region_report.md").write_text("\n".join(lines) + "\n", encoding="utf-8")


def run_region_search_mode(
    *,
    run_label: str,
    log_dir: Path,
    task: Any,
    llm: Any,
    llm_config: dict[str, Any],
    method_config: dict[str, Any],
    prompt: str,
    region: dict[str, Any],
    source_revision_id: str | None,
    model_name: str,
) -> None:
    del model_name
    from llm4ad.method.eoh import EoH

    RegionEoHProfiler = _create_region_profiler_class()
    revision_id = log_dir.parent.name
    if not _region_shape_valid(region):
        raise RuntimeError("区域定义无效：需要 {type: 'edge'|'expand', a, b?}。")

    region_segments = int_config(method_config, "region_segments", 5, 1)
    samples_per_segment = int_config(method_config, "samples_per_segment", 30, 1)
    resolved = {
        "pop_size": int_config(method_config, "pop_size", 8, 2),
        "num_samplers": int_config(method_config, "num_samplers", 4, 1),
        "num_evaluators": int_config(method_config, "num_evaluators", 4, 1),
    }
    operator_preference = str(method_config.get("operator_preference", "balanced") or "balanced")
    operator_weights = method_config.get("operator_weights") or {}
    selection_num = int_config(method_config, "selection_num", 2, 1)
    fusion_mode = str(method_config.get("fusion_mode", "none") or "none").strip().lower()
    if fusion_mode not in {"none", "auto", "always"}:
        fusion_mode = "none"

    update_run_progress(
        log_dir,
        phase="region_prepare",
        phaseLabel="准备区域搜索上下文",
        mode="region_search",
        region=region,
        regionSegments=region_segments,
        samplesPerSegment=samples_per_segment,
    )

    endpoint_records = hydrate_nodes_from_db(
        normalize_node_list(
            [region.get("a"), region.get("b") if region.get("type") == "edge" else None]
        )
    )
    endpoints_by_id = {str(node.get("id") or ""): node for node in endpoint_records}
    validated, validation_error = validate_region_nodes(region, endpoints_by_id)
    if validation_error is not None:
        raise RuntimeError(validation_error)
    assert validated is not None

    anchor = _anchor_node_dict(endpoints_by_id[validated["a"]])
    history_samples = _load_history_samples(source_revision_id)
    valid_history_samples = [
        sample for sample in history_samples if is_valid_score(sample.get("score"))
    ]
    history_vectors: np.ndarray | None = None
    if valid_history_samples:
        history_vectors = _embed_samples(valid_history_samples, label="history")
    history_scores = [
        float(sample["score"])
        for sample in valid_history_samples
        if isinstance(sample.get("score"), (int, float))
    ]
    ship_threshold = float(score_quantiles(history_scores, (SHIP_QUANTILE,)).get("p75", float("nan")))
    if not math.isfinite(ship_threshold):
        ship_threshold = max(
            [float(validated.get("a_score") or 0.0)]
            + ([float(validated.get("b_score") or 0.0)] if validated["type"] == "edge" else [])
        )
    if not math.isfinite(ship_threshold):
        raise RuntimeError("无法计算出货分位阈值：没有可用的历史有效分数。")

    champion_block = _champion_avoidance_block(source_revision_id, history_samples, ship_threshold)
    graph = _load_graph_artifact(source_revision_id)

    # Preflight embeddings: loads the CodeT5 model once, before spending any LLM
    # budget, and lets us enforce the minimum edge length.
    anchor_vectors: dict[str, np.ndarray] = {}
    anchor_embedding = _embed_samples(
        [{"function": anchor.get("functionPreview", "") or "def pack_circles(n):\n    return __import__('numpy').zeros((n, 3))"}],
        label="anchor",
    )
    anchor_vectors["a"] = anchor_embedding[0]
    d_ab: float | None = None
    if validated["type"] == "edge":
        b_node = endpoints_by_id[validated["b"]]
        direction_nodes = [_anchor_node_dict(b_node)]
        b_embedding = _embed_samples(
            [{"function": b_node.get("functionPreview", "") or "def pack_circles(n):\n    return __import__('numpy').zeros((n, 3))"}],
            label="direction",
        )
        anchor_vectors["b"] = b_embedding[0]
        similarity = float(np.clip(np.dot(anchor_embedding[0], b_embedding[0]), -1.0, 1.0))
        d_ab = 1.0 - similarity
        if d_ab < MIN_EDGE_DIST:
            raise RuntimeError(
                f"短边不值得填：d(A,B)={d_ab:.4f} < {MIN_EDGE_DIST:.2f}，两端近乎重复，中间没有可开采空间。"
            )
    else:
        direction_nodes = [
            _anchor_node_dict(node)
            for node in _direction_seeds(validated, anchor, graph)
        ]

    # Anchor-parent vector for the online "candidate NBN child" test: samples
    # closer to the anchor than to its parent are likely to hang under the
    # anchor in the rebuilt tree. Falls back to a fixed bound when the parent
    # is unknown (root anchor / after the anchor drifts).
    parent_vector: np.ndarray | None = None
    gap_upper: float | None = None
    if validated["type"] == "expand" and graph and isinstance(graph.get("nodes"), list):
        anchor_graph_node = next(
            (n for n in graph["nodes"] if str(n.get("id") or "") == anchor.get("id")),
            None,
        )
        parent_index = anchor_graph_node.get("ofecParentIndex") if anchor_graph_node else None
        parent_node = None
        if isinstance(parent_index, int):
            parent_node = next(
                (n for n in graph["nodes"] if n.get("ofecIndex") == parent_index),
                None,
            )
        parent_distance = anchor_graph_node.get("distanceToParent") if anchor_graph_node else None
        try:
            parent_distance = float(parent_distance)
        except (TypeError, ValueError):
            parent_distance = None
        if parent_node is not None:
            from visual_platform.repositories import get_individuals_by_ids

            parent_records = get_individuals_by_ids([str(parent_node.get("id") or "")])
            parent_code = ""
            if parent_records:
                parent_code = str(
                    parent_records[0].get("function")
                    or parent_records[0].get("program")
                    or parent_records[0].get("code")
                    or ""
                ).strip()
            if parent_code:
                parent_embedding = _embed_samples(
                    [{"function": parent_code}],
                    label="anchor_parent",
                )
                parent_vector = parent_embedding[0]
                if parent_distance is not None and parent_distance > MIN_EDGE_DIST:
                    gap_upper = parent_distance

    update_run_progress(
        log_dir,
        phase="region_prepare",
        phaseLabel="区域上下文就绪",
        anchorId=anchor.get("id"),
        directionIds=[node.get("id") for node in direction_nodes],
        historyCount=len(valid_history_samples),
        shipThreshold=ship_threshold,
        distanceToDirection=d_ab,
    )

    sampler_llm = RegionTimeoutLLM(llm, max(15, int(llm_config.get("timeout", 120)) + 5))
    evaluation_executor = CeleryExecutor({"timeout_seconds": int(method_config.get("timeout_seconds", 10))}) if method_config.get("use_celery", False) else None
    base_task_description = str(getattr(task, "task_description", "") or "")
    template_function = getattr(task, "template_program", "")

    collected: list[dict[str, Any]] = []
    segment_records: list[dict[str, Any]] = []
    running_sample_count = 0
    consecutive_drift = 0
    stopped_fracture = False
    hit_pool: list[dict[str, Any]] = []
    current_anchor = dict(anchor)
    anchor_trail: list[dict[str, Any]] = [
        {"segment": 0, "id": anchor.get("id"), "score": anchor.get("score")}
    ]
    anchor_switched = False
    fusion_partner = _fusion_partner_node(anchor, graph)
    fusion_active = fusion_mode == "always"
    fusion_used_segments: list[int] = []
    best_so_far: float | None = None
    no_improve_count = 0

    for segment in range(1, region_segments + 1):
        segment_started_at = time.perf_counter()
        active_anchor = current_anchor

        seed_source_nodes: list[dict[str, Any]] = [active_anchor]
        if fusion_active and fusion_partner is not None:
            seed_source_nodes.append(fusion_partner)
        if validated["type"] == "edge":
            seed_source_nodes.extend(direction_nodes)
        if hit_pool:
            seed_source_nodes.extend(hit_pool)
        seed_nodes = distinct_function_nodes(seed_source_nodes)
        if not seed_nodes:
            raise RuntimeError("区域种子为空：端点代码无法转换为可执行的 pack_circles 函数。")

        guidance = _build_region_guidance(
            validated,
            active_anchor,
            direction_nodes,
            d_ab=d_ab,
            user_prompt=prompt,
            champion_block=champion_block,
        )
        task.task_description = f"{base_task_description}\n\n{guidance}"

        update_run_progress(
            log_dir,
            phase="region_segment",
            phaseLabel=f"区域搜索：第 {segment}/{region_segments} 段",
            currentSegment=segment,
            totalSegments=region_segments,
            seedCount=len(seed_nodes),
            requestedSeedCount=len(seed_source_nodes),
        )

        segment_offset_start = running_sample_count
        profiler = RegionEoHProfiler(
            log_dir,
            collected,
            initial_num_samples=segment_offset_start,
        )
        method = EoH(
            llm=sampler_llm,
            profiler=profiler,
            evaluation=task,
            # 种子注册本身也占用 EoH 的采样预算（每个种子让 _tot_sample_nums +1），
            # 所以预算要加上本段种子数。否则当种子数 ≥ 每段样本数时（典型是 edge 区域：
            # A、B 两个端点都是种子，而用户把每段样本数填成 2），EoH 循环一次都不进，
            # 本段生成 0 个新解，报告却给 BUDGET_OUT + "新颖率 0%"，看着像"区域没货"，
            # 实际是根本没搜。
            max_sample_nums=samples_per_segment + len(seed_nodes),
            max_generations=max(2, math.ceil(samples_per_segment / max(resolved["pop_size"], 1)) + 2),
            pop_size=max(resolved["pop_size"], len(seed_nodes)),
            selection_num=selection_num,
            num_samplers=resolved["num_samplers"],
            num_evaluators=resolved["num_evaluators"],
            operator_preference=operator_preference,
            operator_weights=operator_weights,
            resume_mode=True,
            debug_mode=False,
            evaluation_executor=evaluation_executor,
        )

        from visual_platform.runtime.packing_history import instrument_eoh
        instrument_eoh(method,task,log_dir.parent)

        accepted_seeds = 0
        for node in seed_nodes:
            function_preview = str(node.get("functionPreview", "") or "").strip()
            raw_score = node.get("rawScore", node.get("score"))
            numeric_score = (
                float(raw_score)
                if isinstance(raw_score, (int, float)) and math.isfinite(float(raw_score))
                else None
            )
            summary = str(node.get("algorithm", "") or node.get("algorithmSummary", "") or "").strip()
            if function_preview and numeric_score is not None:
                ok = method.register_prescored_seed_function(
                    function_preview,
                    score=numeric_score,
                    algorithm=(
                        "{Region seed reused without re-evaluation. "
                        f"node={node.get('id')}, score={raw_score}, summary={summary[:200]}"
                        "}"
                    ),
                    operator="region_seed",
                )
            elif function_preview:
                ok = method.register_seed_function(
                    function_preview,
                    algorithm=(
                        "{Region seed evaluated at registration. "
                        f"node={node.get('id')}, summary={summary[:200]}"
                        "}"
                    ),
                    operator="region_seed",
                )
            else:
                ok = False
            if ok:
                accepted_seeds += 1
        if accepted_seeds <= 0:
            raise RuntimeError("区域种子都没有通过注册/评估，无法启动区域 EOH。")

        if len(method._population._population) == 0 and len(method._population._next_gen_pop) > 0:
            method._population.survival()

        method.run()
        running_sample_count = profiler._num_samples

        segment_slice = [
            sample
            for sample in collected
            if sample.get("sample_order", -1) >= segment_offset_start
            and not str(sample.get("operator", "") or "").startswith("region_seed")
        ]

        stats = _segment_stats(
            segment_slice,
            validated,
            anchor_vectors,
            parent_vector if validated["type"] == "expand" else None,
            history_vectors,
            ship_threshold=ship_threshold,
            gap_upper=gap_upper if validated["type"] == "expand" else None,
        )
        drift = bool(stats["drift"])
        consecutive_drift = consecutive_drift + 1 if drift else 0
        if stats["hit_count"] > 0 or stats["novel_count"] > 0 or stats["candidate_child_count"] > 0:
            hit_pool_ids = {str(sample.get("id")) for sample in hit_pool}
            d_a_by_order: dict[int, float] = {}
            for hit in stats.get("hits") or []:
                sample_order = hit.get("sample_order")
                if sample_order is not None and hit.get("d_a") is not None:
                    try:
                        d_a_by_order[int(sample_order)] = float(hit["d_a"])
                    except (TypeError, ValueError):
                        continue
            for sample in segment_slice:
                record = sample.get("_region") or {}
                is_candidate = (
                    record.get("hit")
                    or record.get("novel")
                    or any(
                        item.get("sample_order") == sample.get("sample_order")
                        for item in stats.get("candidate_children") or []
                    )
                )
                if is_candidate:
                    node_dict = _anchor_node_dict(
                        {
                            "id": f"run-{revision_id}-s{sample.get('sample_order')}",
                            "sampleOrder": sample.get("sample_order"),
                            "score": sample.get("score"),
                            "rawScore": sample.get("score"),
                            "algorithm": sample.get("algorithm", ""),
                            "functionPreview": sample.get("function", ""),
                            "d_a": d_a_by_order.get(int(sample.get("sample_order") or -1)),
                        }
                    )
                    if node_dict["id"] not in hit_pool_ids:
                        hit_pool.append(node_dict)
            # Distance-bucket diversity: one representative per band, rest by score.
            hit_pool = _pick_diverse_seed_pool(
                hit_pool,
                max(4, resolved["pop_size"] - 1),
            )

        # Anchor drift: when this segment beat the current anchor, move the
        # search centre to the new best solution so the cluster keeps growing
        # around the improving idea.
        segment_best = stats.get("best_score")
        current_anchor_score = current_anchor.get("score")
        drifted_this_segment = False
        if (
            segment_best is not None
            and (
                not isinstance(current_anchor_score, (int, float))
                or float(segment_best) > float(current_anchor_score)
            )
        ):
            best_sample = max(
                (s for s in segment_slice if is_valid_score(s.get("score"))),
                key=lambda s: float(s["score"]),
                default=None,
            )
            if best_sample is not None:
                new_anchor_id = f"run-{revision_id}-s{best_sample.get('sample_order')}"
                current_anchor = _anchor_node_dict(
                    {
                        "id": new_anchor_id,
                        "sampleOrder": best_sample.get("sample_order"),
                        "score": best_sample.get("score"),
                        "rawScore": best_sample.get("score"),
                        "algorithm": best_sample.get("algorithm", ""),
                        "functionPreview": best_sample.get("function", ""),
                    }
                )
                new_anchor_embedding = _embed_samples(
                    [{"function": str(best_sample.get("function", "") or "")}],
                    label="drifted_anchor",
                )
                anchor_vectors["a"] = new_anchor_embedding[0]
                parent_vector = None
                gap_upper = None
                anchor_trail.append(
                    {
                        "segment": segment,
                        "id": new_anchor_id,
                        "score": best_sample.get("score"),
                    }
                )
                anchor_switched = True
                drifted_this_segment = True

        # Best-so-far / no-improvement tracking for auto fusion: after two
        # segments without any improvement, allow the anchor idea to fuse with
        # its nearest better-scoring partner next segment.
        if segment_best is not None:
            if best_so_far is None or float(segment_best) > best_so_far + 1e-12:
                best_so_far = float(segment_best)
                no_improve_count = 0
            else:
                no_improve_count += 1
        else:
            no_improve_count += 1
        if fusion_active and fusion_partner is not None:
            fusion_used_segments.append(segment)
        fusion_active = fusion_mode == "always" or (
            fusion_mode == "auto" and no_improve_count >= 2
        )

        if drifted_this_segment:
            segment_note = "anchor drifted to a higher-scoring solution"
        elif int(stats.get("generated", 0) or 0) == 0:
            segment_note = (
                "本段没有生成任何新解：预算被初始种子占满"
                f"（种子数 {len(seed_nodes)} ≥ 每段样本数 {samples_per_segment}）。"
                "该段的 BUDGET_OUT / 新颖率 0% 不代表区域没货，请把「每段样本数」调到大于种子数后重跑。"
            )
        else:
            segment_note = ""

        record = _ledger_record(
            segment,
            revision_id,
            seeds=[str(node.get("id") or "") for node in seed_nodes],
            stats=stats,
            anchor_switched=drifted_this_segment,
            note=segment_note,
        )
        segment_records.append(record)
        elapsed_ms = round((time.perf_counter() - segment_started_at) * 1000.0, 3)
        record_run_timing(
            log_dir,
            "regionSegmentMs",
            elapsed_ms,
            extra={"segment": segment},
        )
        update_run_progress(
            log_dir,
            phase="region_segment",
            phaseLabel=f"区域搜索：第 {segment}/{region_segments} 段完成",
            currentSegment=segment,
            totalSegments=region_segments,
            segmentStats=stats,
            segmentElapsedMs=elapsed_ms,
            sampleCount=running_sample_count,
            lastSegmentBestScore=stats.get("best_score"),
        )

        if consecutive_drift >= 2:
            stopped_fracture = True
            break

    verdict = final_verdict(segment_records, stopped_fracture=stopped_fracture)
    final_record = _ledger_record(
        segment_records[-1]["segment"] if segment_records else 0,
        revision_id,
        seeds=[],
        stats={
            "generated": sum(int(r.get("generated", 0) or 0) for r in segment_records),
            "valid": sum(int(r.get("valid", 0) or 0) for r in segment_records),
            "invalid": sum(int(r.get("invalid", 0) or 0) for r in segment_records),
            "hit_count": sum(int(r.get("hit_count", 0) or 0) for r in segment_records),
            "candidate_child_count": sum(int(r.get("candidate_child_count", 0) or 0) for r in segment_records),
            "novel_count": sum(int(r.get("novel_count", 0) or 0) for r in segment_records),
            "ship_count": sum(int(r.get("ship_count", 0) or 0) for r in segment_records),
            "best_score": max(
                (float(r.get("best_score") or 0.0) for r in segment_records if r.get("best_score") is not None),
                default=None,
            ),
            "drift": False,
        },
        verdict=verdict,
        note="final",
    )
    neighborhood: list[dict[str, Any]] = []
    neighborhood_seen: set[str] = set()
    for seg_record in segment_records:
        for hit in seg_record.get("hits") or []:
            node_id = f"run-{revision_id}-s{hit.get('sample_order')}"
            if node_id in neighborhood_seen:
                continue
            neighborhood_seen.add(node_id)
            neighborhood.append(
                {
                    "id": node_id,
                    "d_a": hit.get("d_a"),
                    "score": hit.get("score"),
                }
            )
    neighborhood.sort(key=lambda item: -(float(item["score"]) if item["score"] is not None else -1e18))
    final_record["neighborhood"] = neighborhood
    d_as = [float(item["d_a"]) for item in neighborhood if item.get("d_a") is not None]
    coverage = (
        neighborhood_coverage(d_as)
        if d_as
        else {"covered": 0, "total": len(NEIGHBORHOOD_BUCKETS), "buckets": {}}
    )
    total_valid_f = int(final_record["valid"])
    total_novel_f = int(final_record["novel_count"])
    novel_rate = total_novel_f / total_valid_f if total_valid_f else 0.0
    conclusion = exploration_conclusion(segment_records)
    final_record["coverage"] = coverage
    final_record["novelRate"] = round(novel_rate, 4)
    final_record["dupRate"] = round(max(0.0, 1.0 - novel_rate), 4)
    final_record["conclusion"] = conclusion
    final_record["fusionMode"] = fusion_mode
    final_record["fusionUsedSegments"] = fusion_used_segments
    _write_ledger(log_dir.parent, [*segment_records, final_record])
    _write_report(
        log_dir.parent,
        region=validated,
        anchor=anchor,
        neighborhood=neighborhood,
        coverage=coverage,
        novel_rate=novel_rate,
        conclusion=conclusion,
        fusion_mode=fusion_mode,
        fusion_used_segments=fusion_used_segments,
        direction_nodes=direction_nodes,
        d_ab=d_ab,
        ship_threshold=ship_threshold,
        segments=segment_records,
        verdict=verdict,
        anchor_trail=anchor_trail,
    )
    task.task_description = base_task_description

    total_generated = int(final_record["generated"])
    total_valid = int(final_record["valid"])
    total_ships = int(final_record["ship_count"])
    total_candidates = int(final_record.get("candidate_child_count", 0) or 0)
    region_best = final_record["best_score"]
    merge_real_run_meta(
        log_dir,
        {
            "mode": "region_search",
            "region": validated,
            "regionSummary": {
                "verdict": verdict,
                "segments": segment_records,
                "generated": total_generated,
                "valid": total_valid,
                "hits": int(final_record["hit_count"]),
                "novel": int(final_record["novel_count"]),
                "ships": total_ships,
                "candidateChildCount": total_candidates,
                "neighborhoodCount": len(neighborhood),
                "coverage": coverage,
                "novelRate": final_record["novelRate"],
                "dupRate": final_record["dupRate"],
                "conclusion": conclusion,
                "fusionMode": fusion_mode,
                "fusionUsedSegments": fusion_used_segments,
                "anchorTrail": anchor_trail,
                "regionBest": region_best,
                "bestScore": region_best,
                "shipThreshold": ship_threshold,
                "anchorSwitched": anchor_switched,
                "stoppedFracture": stopped_fracture,
            },
            "promptLength": len(prompt),
            "sampleCount": total_generated,
            "validSampleCount": total_valid,
        },
    )

    if not has_generated_samples(log_dir):
        raise RuntimeError("区域搜索没有产出任何可记录样本。请检查 LLM 配置与区域端点后重试。")

    revision_generation_service.complete_run(
        log_dir,
        phase="completed",
        phase_label=f"区域搜索完成（{verdict}）",
        message=f"区域搜索完成：verdict={verdict}, generated={total_generated}, valid={total_valid}, ships={total_ships}。",
        result={
            "mode": "region_search",
            "region": validated,
            "verdict": verdict,
            "segments": segment_records,
            "generated": total_generated,
            "valid": total_valid,
            "hits": int(final_record["hit_count"]),
            "novel": int(final_record["novel_count"]),
            "ships": total_ships,
            "candidateChildCount": total_candidates,
            "neighborhoodCount": len(neighborhood),
            "coverage": coverage,
            "novelRate": final_record["novelRate"],
            "dupRate": final_record["dupRate"],
            "conclusion": conclusion,
            "fusionMode": fusion_mode,
            "fusionUsedSegments": fusion_used_segments,
            "anchorTrail": anchor_trail,
            "regionBest": region_best,
            "bestScore": region_best,
        },
    )
