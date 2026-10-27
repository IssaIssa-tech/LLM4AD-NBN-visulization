"""Create an evidence-bounded analysis of Circle Packing prompt effects.

The repeated 30-candidate study is the main comparison because every
profile/arm has five samples and local raw evaluation files. The earlier pilot
is referenced only as exploratory context. This program does not execute code,
call an LLM, or modify the NBN/source records.
"""
from __future__ import annotations

import csv
import json
import statistics
from collections import Counter, defaultdict
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
RAW = ROOT / "output" / "circle_prompt_preflight_20261025" / "repeated_candidates_raw"
COMBINED = ROOT / "output" / "circle_prompt_preflight_20261025" / "combined_nbn_20261026_v2"
OUT = ROOT / "output" / "circle_prompt_effects_20261026"


def main() -> None:
    if OUT.exists():
        raise SystemExit(f"Refusing to overwrite existing prompt-effects report: {OUT}")
    manifest = json.loads((COMBINED / "trial_manifest.json").read_text(encoding="utf-8"))
    graph = json.loads((COMBINED / "combined_nbn_graph.json").read_text(encoding="utf-8"))["graph"]
    node_by_id = {node["id"]: node for node in graph["nodes"]}
    node_by_index = {int(node["ofecIndex"]): node for node in graph["nodes"]}
    root = next(node for node in graph["nodes"] if node.get("ofecIndex") == node.get("ofecParentIndex"))
    root_index = int(root["ofecIndex"])

    def top_branch(index: int) -> int:
        current = index
        visited: set[int] = set()
        while current != root_index:
            if current in visited:
                raise RuntimeError("cycle in saved NBN")
            visited.add(current)
            parent = int(node_by_index[current]["ofecParentIndex"])
            if parent == root_index:
                return current
            current = parent
        return root_index

    trial_by_id = {row["id"]: row for row in manifest}
    observations: list[dict] = []
    for run_dir in sorted(RAW.glob("repeated_*_20261025")):
        tokens = run_dir.name.split("_")
        profile = tokens[1]
        seed = int(tokens[3])
        evaluation = json.loads((run_dir / "evaluation.json").read_text(encoding="utf-8"))
        for result in evaluation["results"]:
            arm = result["arm"]
            trial_id = f"prompt-{profile}-{seed}-{arm}"
            trial = trial_by_id[trial_id]
            node = node_by_id[trial_id]
            parent = node_by_index[int(node["ofecParentIndex"])]
            observations.append({
                "profile": profile,
                "sampling_seed": seed,
                "arm": arm,
                "trial_id": trial_id,
                "status": result["status"],
                "score": result.get("score"),
                "runtime_seconds": result.get("runtime_seconds"),
                "wall_runtime_seconds": result.get("wall_runtime_seconds"),
                "code_sha256": result["code_sha256"],
                "quality_gate": result.get("quality_gate"),
                "nbn_parent_id": parent["id"],
                "nbn_parent_sample_order": parent["sampleOrder"],
                "nbn_parent_score": parent.get("rawScore"),
                "nbn_top_branch": top_branch(int(parent["ofecIndex"])) if int(parent["ofecIndex"]) != root_index else root_index,
            })

    if len(observations) != 30:
        raise RuntimeError(f"Expected 30 repeated observations, found {len(observations)}")
    OUT.mkdir(parents=True)
    fields = list(observations[0])
    with (OUT / "controlled_prompt_observations.csv").open("w", newline="", encoding="utf-8") as stream:
        writer = csv.DictWriter(stream, fieldnames=fields)
        writer.writeheader()
        writer.writerows(observations)

    grouped: dict[tuple[str, str], list[dict]] = defaultdict(list)
    for row in observations:
        grouped[(row["profile"], row["arm"])].append(row)
    summary: list[dict] = []
    for (profile, arm), rows in sorted(grouped.items()):
        statuses = Counter(row["status"] for row in rows)
        valid = [row for row in rows if row["status"] == "valid"]
        valid_scores = [float(row["score"]) for row in valid]
        summary.append({
            "profile": profile,
            "arm": arm,
            "n": len(rows),
            "valid": statuses["valid"],
            "invalid_geometry": statuses["invalid_geometry"],
            "timeout": statuses["timeout"],
            "other": len(rows) - statuses["valid"] - statuses["invalid_geometry"] - statuses["timeout"],
            "valid_rate": statuses["valid"] / len(rows),
            "mean_valid_score": statistics.mean(valid_scores) if valid_scores else None,
            "best_valid_score": max(valid_scores) if valid_scores else None,
            "unique_code_hashes": len({row["code_sha256"] for row in rows}),
            "valid_nbn_branches": sorted({row["nbn_top_branch"] for row in valid}),
        })
    with (OUT / "controlled_prompt_summary.json").open("w", encoding="utf-8") as stream:
        json.dump(summary, stream, indent=2)

    lines = [
        "# Circle Packing prompt-effects analysis",
        "",
        "## Question from the supervisor",
        "",
        "Which tested prompt condition produced usable Circle Packing algorithms, and what should be used as the evidence-based starting point for the next algorithm design?",
        "",
        "## Evidence included",
        "",
        "Main evidence: a repeated controlled comparison of 30 local-LLM candidates: 2 prompt profiles x 3 arms x 5 recorded sampling seeds. All used `n=26`, the same static screen, isolated geometric evaluator, 20-second limit, and a quality floor of 1.0.",
        "",
        "The two profiles are not single-factor ablations. `baseline` is the original prompt. `contract` combines runtime, all-pairs feasibility, non-trivial-quality, and exact output-contract constraints. Therefore this experiment tests the *combined contract profile*, not the independent effect of each individual constraint.",
        "",
        "## Controlled results",
        "",
        "| Profile | Arm | n | Valid | Invalid geometry | Timeout | Unique code hashes | Valid-score mean / best | Valid NBN branch(es) |",
        "|---|---|---:|---:|---:|---:|---:|---|---|",
    ]
    for row in summary:
        score = "-" if row["mean_valid_score"] is None else f"{row['mean_valid_score']:.12f} / {row['best_valid_score']:.12f}"
        branches = "-" if not row["valid_nbn_branches"] else ", ".join(str(value) for value in row["valid_nbn_branches"])
        lines.append(
            f"| {row['profile']} | {row['arm']} | {row['n']} | {row['valid']} | {row['invalid_geometry']} | "
            f"{row['timeout']} | {row['unique_code_hashes']} | {score} | {branches} |"
        )
    lines += [
        "",
        "## What the data support",
        "",
        "1. Under the tested baseline profile, none of the 15 candidates completed the evaluator: all were timeouts.",
        "2. Under the combined contract profile, M1 parameter tuning still timed out in all five trials. M3 diversity produced four timeouts and one invalid geometry result.",
        "3. Under the combined contract profile, M2 structural modification completed in all five trials, passed the quality floor, and achieved the same valid score (2.579279552688004) in every trial.",
        "4. All five valid M2 trials attach to the same top-level branch of the saved combined CodeT5+ NBN. Thus this condition is currently reliable for feasibility/runtime, but has not demonstrated broad code-region coverage or a score above the historical champion (2.635937208805357).",
        "",
        "## Exploratory context, not pooled with the main comparison",
        "",
        "An earlier five-profile one-sample-per-arm pilot also found that structural modification was the only arm that produced non-zero valid output under its final contract profile: score 2.600306976710351. It is below the historical champion. Because the profiles were explored sequentially and not equally repeated, this pilot is supporting context only; it is not pooled into the controlled statistics above.",
        "",
        "## Design decision justified by the evidence",
        "",
        "Use the **combined contract + M2 structural modification** as the starting condition for the next algorithm-design experiment. Keep the exact contract, 20-second evaluator, quality floor, and full outcome ledger. Do not label M2 as globally best: it is only the best-supported condition among the conditions tested so far.",
        "",
        "The next design must address the remaining weakness: every valid M2 result enters one historical NBN branch. The M2 prompt should therefore preserve its runtime/feasibility contract while explicitly requiring a distinct algorithmic mechanism and evaluating multiple independent samples. M1 and M3 should be redesigned and re-tested separately before comparing them with M2 again.",
        "",
        "## Files produced",
        "",
        "- `controlled_prompt_observations.csv`: every one of the 30 controlled observations, including failures and NBN parent information.",
        "- `controlled_prompt_summary.json`: machine-readable grouped summary used for the table above.",
    ]
    (OUT / "PROMPT_EFFECTS_ANALYSIS.md").write_text("\n".join(lines) + "\n", encoding="utf-8")
    print(json.dumps({"output": str(OUT), "summary": summary}, indent=2))


if __name__ == "__main__":
    main()
