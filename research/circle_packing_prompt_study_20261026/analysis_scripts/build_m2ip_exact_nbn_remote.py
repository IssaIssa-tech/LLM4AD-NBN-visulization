"""Build a separate exact CodeT5 NBN with the five valid M2-I-P trials."""
from __future__ import annotations

import json
from pathlib import Path

from visual_platform.nbn.bridge import build_nbn_graph


ROOT = Path(__file__).resolve().parent


def main() -> None:
    base = json.loads((ROOT / "combined_nbn_graph.json").read_text(encoding="utf-8"))["graph"]
    samples = []
    for node in base["nodes"]:
        samples.append({
            "id": node["id"], "sample_order": node["mergedSampleOrder"],
            "origin_sample_order": node["sampleOrder"], "score": node.get("rawScore"),
            "function": node.get("functionPreview", ""), "operator": node.get("operator", ""),
            "algorithm": node.get("algorithm", ""), "source_kind": node.get("sourceKind", ""),
            "source_label": node.get("sourceLabel", ""), "origin_kind": node.get("originKind", ""),
        })
    results = json.loads((ROOT / "results.json").read_text(encoding="utf-8"))["outcomes"]
    manifest = []
    for offset, result in enumerate(results, start=1):
        trial_id = result["trial_id"]
        code = (ROOT / trial_id / "candidate.py").read_text(encoding="utf-8").strip()
        record = {"id": f"prompt-m2ip-20261027-{trial_id}", "sample_order": len(samples) + 1,
                  "origin_sample_order": len(samples) + 1, "score": result["final"]["score"],
                  "function": code, "operator": "m2ip_strict_sobol_patch",
                  "algorithm": "Validated M2 with strict Halton-to-scrambled-Sobol initialization patch",
                  "source_kind": "prompt_trial", "source_label": "M2-I-P strict patch trial",
                  "origin_kind": "prompt_trial", "generation": result["sampling_seed"]}
        samples.append(record)
        manifest.append({"id": record["id"], "trial_id": trial_id, "sampling_seed": result["sampling_seed"],
                         "evaluation_status": result["final"]["status"], "score": record["score"],
                         "exact_patch_match": result["exact_patch_match"]})
    graph = build_nbn_graph(samples, ROOT / "build_artifacts", distance_metric="codet5p_embedding_cosine")
    (ROOT / "combined_nbn_m2ip_graph.json").write_text(json.dumps({"graph": graph}, ensure_ascii=False), encoding="utf-8")
    (ROOT / "m2ip_trial_manifest.json").write_text(json.dumps(manifest, indent=2), encoding="utf-8")
    print(json.dumps({"nodes": len(graph["nodes"]), "edges": len(graph["edges"]), "stats": graph.get("graphBuildStats", {})}, indent=2))


if __name__ == "__main__":
    main()
