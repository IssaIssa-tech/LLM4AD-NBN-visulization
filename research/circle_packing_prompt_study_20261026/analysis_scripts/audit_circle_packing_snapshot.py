"""Describe the preserved Circle Packing NBN snapshot without altering it.

The snapshot contains a scored/validity-labelled historical landscape.  This
audit is deliberately descriptive: it identifies the data available for study,
but does not claim a new prompt has improved the historical baseline.
"""

from __future__ import annotations

import argparse
import json
import math
import statistics
from collections import Counter
from pathlib import Path
from typing import Any


def finite(value: Any) -> bool:
    return isinstance(value, (int, float)) and math.isfinite(float(value))


def basin_table(snapshot: dict[str, Any], threshold: str, limit: int = 10) -> list[dict[str, Any]]:
    basins = snapshot.get("nbn", {}).get(threshold, {}).get("basins", [])
    selected = sorted(
        (basin for basin in basins if isinstance(basin, dict)),
        key=lambda basin: (-int(basin.get("size") or 0), -float(basin.get("rootScore") or float("-inf"))),
    )[:limit]
    return [
        {
            "basin_id": basin.get("basin"),
            "size": basin.get("size"),
            "root_id": basin.get("rootId"),
            "root_score": basin.get("rootScore"),
            "root_summary": basin.get("rootSummary"),
        }
        for basin in selected
    ]


def markdown(audit: dict[str, Any]) -> str:
    counts = audit["counts"]
    lines = [
        "# Circle Packing historical NBN: baseline audit",
        "",
        "## Scope",
        "",
        f"- Snapshot generated: `{audit['snapshot']['generated_at']}`.",
        f"- Stored NBN nodes/edges: {counts['nodes']:,} / {counts['edges']:,}.",
        f"- Validity-labelled candidates: {counts['valid']:,}; records flagged non-valid: {counts['non_valid']:,}.",
        f"- Unique valid candidates: {counts['unique_valid']:,}.",
        f"- Valid finite-score range: {audit['fitness']['minimum']:.8f} to {audit['fitness']['maximum']:.8f}; median {audit['fitness']['median']:.8f}.",
        "",
        "This is a preserved historical snapshot. It is suitable for landscape description and for selecting future test regions; it is not evidence that a new prompt has improved the baseline.",
        "",
        "## Provenance limits",
        "",
        "- The snapshot preserves node score, validity flag, source/origin, operator and NBN relationships.",
        "- Its local raw Circle-history ZIP retains code records but not reliable per-record scores for all candidates. Therefore no new comparison should be launched from that ZIP alone.",
        "- Future prompt runs require the original scored evaluator/data source (or a fresh, deterministic Circle Packing evaluator) and must save candidate-level outcomes.",
        "",
        "## Historical generation coverage",
        "",
        "| Operator / source label | Records |",
        "|---|---:|",
    ]
    for name, value in audit["operator_counts"]:
        lines.append(f"| {name or '(not recorded)'} | {value:,} |")
    lines += ["", "## NBN structure", ""]
    for threshold, data in audit["basins"].items():
        lines += [
            f"### Threshold {threshold}",
            "",
            f"The snapshot reports {data['basin_count']:,} basins at this threshold. The largest basins are listed only to orient exploration; basin size is not itself a quality ranking.",
            "",
            "| Basin | Size | Root score | Root ID |",
            "|---:|---:|---:|---|",
        ]
        for basin in data["largest"]:
            root_score = basin["root_score"]
            score_text = f"{float(root_score):.8f}" if finite(root_score) else "not recorded"
            lines.append(f"| {basin['basin_id']} | {basin['size']:,} | {score_text} | `{basin['root_id']}` |")
        lines.append("")
    lines += [
        "## Evidence-based next experiment",
        "",
        "1. Keep this snapshot unchanged as the historical baseline.",
        "2. Obtain access to the original scored Circle Packing workspace/evaluator before generating candidates.",
        "3. Define a small, registered prompt set from the literature: a controlled baseline prompt, a novelty/diversity prompt, a structural-recombination prompt, and a parameter-refinement prompt.",
        "4. For each prompt, record the exact prompt text/hash, parent/region, model settings, code, validity status/reason, score, diversity representation, and random seeds.",
        "5. Compare prompts by validity rate, best/median score, unique-code rate, and which NBN regions/basins receive new candidates—not by a screenshot alone.",
    ]
    return "\n".join(lines) + "\n"


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--snapshot", type=Path, required=True)
    parser.add_argument("--meta", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()

    snapshot = json.loads(args.snapshot.read_text(encoding="utf-8"))
    meta = json.loads(args.meta.read_text(encoding="utf-8"))
    nodes = [node for node in snapshot.get("nodes", []) if isinstance(node, dict)]
    valid = [node for node in nodes if node.get("valid") == 1 and finite(node.get("score"))]
    scores = [float(node["score"]) for node in valid]
    if not scores:
        raise ValueError("No finite valid scores are available in this snapshot.")

    audit = {
        "snapshot": {
            "path": str(args.snapshot.resolve()),
            "generated_at": snapshot.get("generatedAt"),
            "metadata_generated_at": meta.get("generatedAt"),
        },
        "counts": {
            "nodes": len(nodes),
            "edges": len(snapshot.get("edges", [])),
            "valid": len(valid),
            "non_valid": len(nodes) - len(valid),
            "unique_valid": sum(node.get("valid") == 1 and node.get("unique") == 1 for node in nodes),
            "trajectories": len(snapshot.get("trajectories", {}).get("list", [])),
        },
        "fitness": {
            "minimum": min(scores),
            "maximum": max(scores),
            "median": statistics.median(scores),
            "mean": statistics.fmean(scores),
        },
        "operator_counts": Counter(str(node.get("op") or "") for node in nodes).most_common(),
        "origin_counts": Counter(str(node.get("origin") or "") for node in nodes).most_common(),
        "basins": {
            threshold: {
                "basin_count": len(snapshot.get("nbn", {}).get(threshold, {}).get("basins", [])),
                "largest": basin_table(snapshot, threshold),
            }
            for threshold in ("0.02", "0.05")
        },
    }
    args.output.mkdir(parents=True, exist_ok=True)
    (args.output / "circle_packing_baseline_audit.json").write_text(json.dumps(audit, indent=2, ensure_ascii=False), encoding="utf-8")
    (args.output / "circle_packing_baseline_audit.md").write_text(markdown(audit), encoding="utf-8")
    print(json.dumps({"ok": True, "output": str(args.output), "counts": audit["counts"]}, indent=2))


if __name__ == "__main__":
    main()
