"""Three-arm controlled experiment: does "anchor x another family representative"
hybrid parentage produce explorative solutions that can beat the anchor?

Run with:  venv/bin/python visual_platform/tools/ab_experiment.py

The platform (Flask on :5000, Redis, Celery worker) must be running. Each arm
submits 2 segments x 30 direct-generation samples via the prompt_gen job API;
segment 2 re-uses segment 1's best solution as an extra reference while keeping
the arm's parentage composition. Metrics (pairwise distance, above-anchor count
and ratio, best score, family-cluster count) are pre-declared and reported per
arm with a fixed conclusion branch.
"""

from __future__ import annotations

import json
import math
import os
import sys
import time
import urllib.request
from pathlib import Path

import numpy as np

ROOT = Path(__file__).resolve().parents[2]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

API = "http://127.0.0.1:5000"
WORKSPACE_ID = "a895f3aa-bc61-49f4-bc4a-53bfdd008250"
SOURCE_REVISION_ID = "20260810_161034_e5de0350"

ANCHOR_ID = "expert-20260721_190711_45613f5c-ad8e8a98"
ANCHOR_SCORE = 2.6180682546064302
NEAR_REP_ID = "history-20260711_152801_4674d01c-aa630fb8"
FAR_REP_ID = "expert-20260725_110119_0dc42c22-06c05269"

SEGMENTS = 2
SAMPLES_PER_SEGMENT = 30
CLUSTER_DIST = 0.02

ARMS: dict[str, dict] = {
    "arm1_refine": {
        "refs": [ANCHOR_ID],
        "directive": (
            "The reference is the anchor algorithm. Produce a CLOSE REFINEMENT of the "
            "anchor's exact approach: keep its core structure and only adjust details "
            "(parameters, geometric placement, iteration strategy) to push its score "
            "higher. Stay very close to the anchor semantically."
        ),
    },
    "arm2_near": {
        "refs": [ANCHOR_ID, NEAR_REP_ID],
        "directive": (
            "References are two algorithms from different families. Identify the common "
            "backbone idea in both, then produce a new algorithm that COMBINES and "
            "REORGANIZES them — inheriting structure from both, not just one. The result "
            "must be motivated by both references."
        ),
    },
    "arm3_far": {
        "refs": [ANCHOR_ID, FAR_REP_ID],
        "directive": (
            "References are two distant algorithms (the anchor and a far-away family). "
            "Produce a BOLD RECOMBINATION: take the core of one and replace its strategy "
            "with the other's, or build a hybrid that explores the semantic space between "
            "them. Do not stay near either reference; aim for something structurally new."
        ),
    },
}


def _api(path: str, payload: dict | None = None) -> dict:
    data = json.dumps(payload).encode("utf-8") if payload is not None else None
    request = urllib.request.Request(
        API + path,
        data=data,
        headers={"Content-Type": "application/json"},
        method="POST" if payload is not None else "GET",
    )
    with urllib.request.urlopen(request, timeout=90) as response:
        return json.loads(response.read().decode("utf-8"))


def _llm_config() -> dict:
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


def _submit_segment(arm_key: str, refs: list[str], method_base: dict) -> str:
    payload = {
        "workspaceId": WORKSPACE_ID,
        "jobType": "revision_generation",
        "request": {
            "mode": "prompt_gen",
            "prompt": "",
            "referenceNodeIds": refs,
            "sourceRevisionIds": [SOURCE_REVISION_ID],
            "llm": _llm_config(),
            "method": {
                **method_base,
                "max_sample_nums": SAMPLES_PER_SEGMENT,
                "relation_directive": ARMS[arm_key]["directive"],
            },
        },
    }
    response = _api("/api/jobs", payload)
    return str(response["data"]["job"]["jobId"])


def _wait_job(job_id: str, timeout_seconds: int = 3600) -> dict:
    deadline = time.time() + timeout_seconds
    while time.time() < deadline:
        job = _api(f"/api/jobs/{job_id}")["data"]["job"]
        status = str(job.get("status") or "")
        if status in {"succeeded", "failed", "cancelled"}:
            return job
        time.sleep(15)
    raise TimeoutError(f"job {job_id} did not finish within {timeout_seconds}s")


def _load_individuals(revision_id: str) -> list[dict]:
    from visual_platform.runtime.database import get_connection

    with get_connection() as conn:
        rows = conn.execute(
            "SELECT sample_order, score, code FROM individuals WHERE revision_id = ?",
            (revision_id,),
        ).fetchall()
    return [
        {
            "sample_order": int(row["sample_order"] or 0),
            "score": row["score"],
            "code": str(row["code"] or "").strip(),
        }
        for row in rows
    ]


def _arm_metrics(records: list[dict]) -> dict:
    from visual_platform.nbn.bridge import get_codet5_embedding_matrix

    valid = [
        record
        for record in records
        if isinstance(record["score"], (int, float))
        and math.isfinite(float(record["score"]))
        and record["code"]
    ]
    if not valid:
        return {
            "valid": 0,
            "pairwise_avg": None,
            "above_count": 0,
            "above_ratio": 0.0,
            "best": None,
            "clusters": 0,
        }
    vectors, _ = get_codet5_embedding_matrix(
        [{"function": record["code"]} for record in valid],
        progress_callback=lambda payload: None,
    )
    similarity = np.clip(vectors @ vectors.T, -1.0, 1.0)
    np.fill_diagonal(similarity, 0.0)
    distances = 1.0 - similarity
    upper = distances[np.triu_indices(len(valid), 1)]

    above = [
        record for record in valid if float(record["score"]) > ANCHOR_SCORE + 1e-9
    ]
    best = max((float(record["score"]) for record in valid), default=None)

    # Union-find clustering on pairwise distance < CLUSTER_DIST.
    parent = list(range(len(valid)))

    def find(node: int) -> int:
        while parent[node] != node:
            parent[node] = parent[parent[node]]
            node = parent[node]
        return node

    for i in range(len(valid)):
        for j in range(i + 1, len(valid)):
            if distances[i, j] < CLUSTER_DIST:
                ri, rj = find(i), find(j)
                if ri != rj:
                    parent[ri] = rj
    clusters = len({find(i) for i in range(len(valid))})
    return {
        "valid": len(valid),
        "pairwise_avg": float(upper.mean()) if upper.size else None,
        "above_count": len(above),
        "above_ratio": round(len(above) / len(valid), 4) if valid else 0.0,
        "best": best,
        "clusters": clusters,
    }


def main() -> None:
    method_base = {
        # direct_ai budgets are derived from max(pop_size*max_generations,
        # max_sample_nums); pin both to 1 so each segment generates exactly
        # SAMPLES_PER_SEGMENT solutions.
        "pop_size": 1,
        "max_generations": 1,
        "num_samplers": 4,
        "num_evaluators": 4,
        "timeout_seconds": 10,
        "distance_metric": "codet5p_embedding_cosine",
    }
    reports: dict[str, dict] = {}
    for arm_key, arm in ARMS.items():
        print(f"\n=== {arm_key} ===", flush=True)
        refs = list(arm["refs"])
        all_records: list[dict] = []
        for segment in range(1, SEGMENTS + 1):
            print(f"  submitting segment {segment}/{SEGMENTS} refs={refs}", flush=True)
            job_id = _submit_segment(arm_key, refs, method_base)
            job = _wait_job(job_id)
            if job.get("status") != "succeeded":
                raise RuntimeError(f"{arm_key} segment {segment} failed: {job.get('error')}")
            revision_id = str(job.get("resultRevisionId") or "")
            records = _load_individuals(revision_id)
            all_records.extend(records)
            scored = [
                record
                for record in records
                if isinstance(record["score"], (int, float))
                and math.isfinite(float(record["score"]))
            ]
            best = max(scored, key=lambda record: float(record["score"]), default=None)
            if best is not None and segment < SEGMENTS:
                refs = list(arm["refs"]) + [f"run-{revision_id}-s{best['sample_order']}"]
            print(
                f"  segment {segment} done: revision={revision_id} "
                f"samples={len(records)} best={best['score'] if best else None}",
                flush=True,
            )
        metrics = _arm_metrics(all_records)
        reports[arm_key] = metrics
        print(f"  {arm_key} metrics: {json.dumps(metrics, ensure_ascii=False)}", flush=True)

    print("\n===== THREE-ARM COMPARISON =====", flush=True)
    for arm_key, metrics in reports.items():
        print(
            f"{arm_key}: valid={metrics['valid']} pairwise_avg={metrics['pairwise_avg']} "
            f"above={metrics['above_count']}({metrics['above_ratio']}) "
            f"best={metrics['best']} clusters={metrics['clusters']}",
            flush=True,
        )

    arm1 = reports["arm1_refine"]
    hybrid = [reports["arm2_near"], reports["arm3_far"]]
    hybrid_avg = [
        metrics["pairwise_avg"] for metrics in hybrid if metrics["pairwise_avg"] is not None
    ]
    hybrid_above = sum(metrics["above_count"] for metrics in hybrid)
    diversity_gap = (
        (sum(hybrid_avg) / len(hybrid_avg) - arm1["pairwise_avg"])
        if hybrid_avg and arm1["pairwise_avg"] is not None
        else 0.0
    )
    if diversity_gap > 0.01 and hybrid_above > 0:
        conclusion = "假设成立：杂交臂多样性显著更高且出现超锚点解，机制值得继续。"
    elif diversity_gap > 0.01:
        conclusion = "多样性高但无超锚点解：杂交机制有效，瓶颈在生成器质量（换模型/改 prompt）。"
    else:
        conclusion = "多样性无显著差异：杂交机制无效，改用长边填缝/地形摘要喂模型。"
    print(f"\n判定：{conclusion}", flush=True)
    print(f"多样性差距(pairwise_avg 差)={diversity_gap:.4f}，超锚点总数={hybrid_above}", flush=True)


if __name__ == "__main__":
    main()
