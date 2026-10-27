"""Build a separate, reproducible NBN for historical Circle Packing + 30 trials.

This script never alters the source historical graph or its embedding cache.
It aborts before model inference if any historical graph code is absent from
the copied cache, preventing accidental re-embedding of the historical cohort.
"""
from __future__ import annotations

import hashlib
import json
import os
import shutil
import sqlite3
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SOURCE_GRAPH = ROOT / "llm4ad_from_server" / "visual_platform" / "runs" / "20261017_165510_f7091449" / "graphs" / "ofec_nbn__codet5p_embedding_cosine__full__n50000.json"
SOURCE_CACHE = ROOT / "llm4ad_from_server" / "visual_platform" / ".codet5_embeddings_cache.sqlite3"
RAW_RUNS = ROOT / "output" / "circle_prompt_preflight_20261025" / "repeated_candidates_raw"
OUT = ROOT / "output" / "circle_prompt_preflight_20261025" / "combined_nbn_20261026_v2"


def code_hash(code: str) -> str:
    return hashlib.sha256(code.strip().encode("utf-8")).hexdigest()


def cache_hashes(cache_path: Path, hashes: list[str]) -> set[str]:
    with sqlite3.connect(cache_path) as con:
        present: set[str] = set()
        for start in range(0, len(hashes), 900):
            chunk = hashes[start:start + 900]
            marks = ",".join("?" for _ in chunk)
            present.update(row[0] for row in con.execute(
                f"SELECT code_hash FROM embeddings WHERE code_hash IN ({marks})", chunk
            ))
    return present


def historical_samples() -> list[dict]:
    graph = json.loads(SOURCE_GRAPH.read_text(encoding="utf-8"))["graph"]
    samples: list[dict] = []
    for node in graph["nodes"]:
        code = str(node.get("functionPreview") or "").strip()
        if not code:
            raise RuntimeError(f"Historical node {node['id']} has no function preview.")
        samples.append({
            "id": node["id"],
            "sample_order": int(node["sampleOrder"]),
            "origin_sample_order": int(node["sampleOrder"]),
            "score": node.get("rawScore"),
            "function": code,
            "operator": node.get("operator", ""),
            "algorithm": node.get("algorithm", ""),
            "source_kind": "historical",
            "source_label": "historical Circle Packing archive",
            "origin_kind": "historical",
        })
    return samples


def trial_samples(start_order: int) -> tuple[list[dict], list[dict]]:
    samples: list[dict] = []
    manifest: list[dict] = []
    order = start_order
    for run_dir in sorted(RAW_RUNS.glob("repeated_*_20261025")):
        evaluation = json.loads((run_dir / "evaluation.json").read_text(encoding="utf-8"))
        by_arm = {item["arm"]: item for item in evaluation["results"]}
        parts = run_dir.name.split("_")
        profile, sampling_seed = parts[1], int(parts[3])
        for arm in ("m1_parameter", "m2_structural", "m3_diversity"):
            record = by_arm[arm]
            code = (run_dir / arm / "candidate.py").read_text(encoding="utf-8").strip()
            status = str(record["status"])
            score = record.get("score") if status == "valid" else None
            identifier = f"prompt-{profile}-{sampling_seed}-{arm}"
            samples.append({
                "id": identifier,
                "sample_order": order,
                "origin_sample_order": order,
                "score": score,
                "function": code,
                "operator": arm,
                "algorithm": f"Prompt trial: {profile}; sampling seed {sampling_seed}; evaluator status {status}",
                "source_kind": "prompt_trial",
                "source_label": f"prompt trial ({profile})",
                "origin_kind": "prompt_trial",
                "generation": sampling_seed,
            })
            manifest.append({
                "id": identifier,
                "sample_order": order,
                "run": run_dir.name,
                "arm": arm,
                "profile": profile,
                "sampling_seed": sampling_seed,
                "evaluation_status": status,
                "score": score,
                "code_sha256": code_hash(code),
            })
            order += 1
    return samples, manifest


def main() -> None:
    if OUT.exists():
        raise SystemExit(f"Refusing to overwrite existing output: {OUT}")
    if not SOURCE_CACHE.exists():
        raise SystemExit(f"Required source cache is absent: {SOURCE_CACHE}")
    historical = historical_samples()
    trials, manifest = trial_samples(len(historical) + 1)
    if len(historical) != 14000 or len(trials) != 30:
        raise SystemExit(f"Unexpected cohort size: historical={len(historical)}, trials={len(trials)}")

    # The guard runs before creating the output folder or loading the model.
    historical_hashes = [code_hash(s["function"]) for s in historical]
    cached_historical = cache_hashes(SOURCE_CACHE, historical_hashes)
    missing_historical = len(set(historical_hashes) - cached_historical)
    if missing_historical:
        raise SystemExit(
            f"Abort: {missing_historical} historical code hashes are not in the source cache; "
            "refusing to silently rebuild historical embeddings."
        )

    OUT.mkdir(parents=True)
    working_cache = OUT / "codet5_embeddings_cache.sqlite3"
    shutil.copy2(SOURCE_CACHE, working_cache)
    os.environ["VISUAL_PLATFORM_CODET5_CACHE"] = str(working_cache)
    os.environ["TRANSFORMERS_OFFLINE"] = "1"
    os.environ["HF_HUB_OFFLINE"] = "1"

    # Import only after the private cache environment has been established.
    sys.path.insert(0, str(ROOT / "llm4ad-nbn-zgr-nbn-upload"))
    from visual_platform.nbn.bridge import build_nbn_graph

    progress: list[dict] = []
    def report(item: dict) -> None:
        progress.append(item)
        # Keep Windows terminals readable while preserving full structured data
        # in the final JSON provenance file.
        print(json.dumps(item, ensure_ascii=True), flush=True)

    graph = build_nbn_graph(
        historical + trials,
        OUT,
        distance_metric="codet5p_embedding_cosine",
        progress_callback=report,
    )
    (OUT / "combined_nbn_graph.json").write_text(json.dumps({"graph": graph}, ensure_ascii=False), encoding="utf-8")
    (OUT / "trial_manifest.json").write_text(json.dumps(manifest, indent=2), encoding="utf-8")
    provenance = {
        "historical_graph": str(SOURCE_GRAPH),
        "historical_nodes": len(historical),
        "trial_nodes": len(trials),
        "trial_status_counts": {
            status: sum(item["evaluation_status"] == status for item in manifest)
            for status in sorted({item["evaluation_status"] for item in manifest})
        },
        "cache_policy": "source cache copied to output; source cache unchanged",
        "embedding_cache_path": str(working_cache),
        "graph_build_stats": graph.get("graphBuildStats", {}),
        "progress": progress,
    }
    (OUT / "provenance.json").write_text(json.dumps(provenance, indent=2), encoding="utf-8")
    print(json.dumps({"complete": True, "nodes": len(graph["nodes"]), "edges": len(graph["edges"]), "out": str(OUT)}, indent=2))


if __name__ == "__main__":
    main()
