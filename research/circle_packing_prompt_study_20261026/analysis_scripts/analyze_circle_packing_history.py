"""Produce reproducible descriptive analysis of the supplied Circle Packing history.

This is analysis of historical records only. It does not query an LLM, execute
candidate programs, alter scores, or claim a new experiment has been run.
"""

from __future__ import annotations

import csv
import json
import math
import statistics
import zipfile
from collections import Counter
from pathlib import Path

import matplotlib.pyplot as plt


ROOT = Path(__file__).resolve().parent.parent
HISTORY_ZIP = (
    ROOT / "llm4ad_from_server" / "example" / "tasks" / "circle_packing"
    / "EoH_settings&logs" / "EoH_sample_history.zip"
)
BASIN_ARCHIVE = ROOT / "llm4ad-nbn-zgr-nbn-upload" / "data" / "solutions" / "archive.json"
OUT = ROOT / "output" / "circle_packing_historical_analysis"


def read_values(text: str) -> list[object]:
    decoder = json.JSONDecoder()
    position = 0
    values: list[object] = []
    while position < len(text):
        while position < len(text) and text[position].isspace():
            position += 1
        if position >= len(text):
            break
        try:
            value, position = decoder.raw_decode(text, position)
        except json.JSONDecodeError:
            break
        values.append(value)
    return values


def load_completed_history() -> list[dict[str, object]]:
    by_order: dict[int, dict[str, object]] = {}
    with zipfile.ZipFile(HISTORY_ZIP) as archive:
        for name in archive.namelist():
            if not name.endswith(".json"):
                continue
            for value in read_values(archive.read(name).decode("utf-8")):
                entries = value if isinstance(value, list) else value.get("samples", []) if isinstance(value, dict) else []
                for entry in entries:
                    if isinstance(entry, dict) and isinstance(entry.get("sample_order"), int):
                        by_order[entry["sample_order"]] = entry
    return [by_order[order] for order in range(1, 14_001)]


def classify(value: object) -> tuple[str, float | None]:
    try:
        score = float(value)
    except (TypeError, ValueError):
        return "missing_score", None
    if not math.isfinite(score):
        return "nonfinite_invalid", None
    if score < 0:
        return "negative_error_sentinel", score
    return "finite_evaluator_score", score


def main() -> None:
    OUT.mkdir(parents=True, exist_ok=True)
    rows = load_completed_history()
    points: list[tuple[int, float]] = []
    best_so_far: list[tuple[int, float]] = []
    current_best = -math.inf
    classes = Counter()
    for row in rows:
        order = int(row["sample_order"])
        label, score = classify(row.get("score"))
        classes[label] += 1
        if label == "finite_evaluator_score" and score is not None:
            points.append((order, score))
            current_best = max(current_best, score)
        best_so_far.append((order, current_best if math.isfinite(current_best) else math.nan))

    # Fixed 1,000-sample windows make temporal comparison transparent.
    windows: list[dict[str, object]] = []
    for start in range(1, 14_001, 1_000):
        end = min(start + 999, 14_000)
        window = rows[start - 1:end]
        counts = Counter()
        finite: list[float] = []
        for row in window:
            label, score = classify(row.get("score"))
            counts[label] += 1
            if label == "finite_evaluator_score" and score is not None:
                finite.append(score)
        windows.append({
            "sample_orders": f"{start}-{end}",
            "records": len(window),
            "finite_evaluator_score": counts["finite_evaluator_score"],
            "nonfinite_invalid": counts["nonfinite_invalid"],
            "negative_error_sentinel": counts["negative_error_sentinel"],
            "missing_score": counts["missing_score"],
            "finite_rate": len(finite) / len(window),
            "median_finite_score": statistics.median(finite) if finite else None,
            "best_finite_score": max(finite) if finite else None,
        })

    with (OUT / "sample_windows.csv").open("w", newline="", encoding="utf-8") as stream:
        writer = csv.DictWriter(stream, fieldnames=list(windows[0]))
        writer.writeheader()
        writer.writerows(windows)

    basin_payload = json.loads(BASIN_ARCHIVE.read_text(encoding="utf-8"))
    basins = sorted(basin_payload["basins"], key=lambda basin: float(basin["best"]), reverse=True)
    basin_rows = [{
        "basin_id": basin["basin_id"],
        "historical_best_score": basin["best"],
        "member_count": basin["member_count"],
        "unique_count": basin["unique_count"],
        "distance_from_champion": basin["dist_champion"],
        "representative_id": basin["best_id"],
    } for basin in basins]
    with (OUT / "basin_summary.csv").open("w", newline="", encoding="utf-8") as stream:
        writer = csv.DictWriter(stream, fieldnames=list(basin_rows[0]))
        writer.writeheader()
        writer.writerows(basin_rows)

    # This is a compact summary of the 51 stored basin representatives, not a
    # replacement for the interactive 30,476-node NBN view.
    fig_basin, axis_basin = plt.subplots(figsize=(10, 7), constrained_layout=True)
    distances = [float(row["distance_from_champion"]) for row in basin_rows]
    scores = [float(row["historical_best_score"]) for row in basin_rows]
    sizes = [35 + 28 * math.log10(int(row["member_count"]) + 1) for row in basin_rows]
    colours = [math.log10(int(row["member_count"]) + 1) for row in basin_rows]
    scatter = axis_basin.scatter(distances, scores, s=sizes, c=colours, cmap="viridis", alpha=0.82, edgecolors="white", linewidths=0.5)
    for row in basin_rows:
        if row["basin_id"] in {"m001", "m003", "m010", "m022"}:
            axis_basin.annotate(row["basin_id"], (float(row["distance_from_champion"]), float(row["historical_best_score"])), xytext=(5, 5), textcoords="offset points", weight="bold")
    axis_basin.set(
        title="Historical Circle Packing basin representatives",
        xlabel="stored code-space distance from champion",
        ylabel="stored best score (higher is better)",
    )
    colour_bar = fig_basin.colorbar(scatter, ax=axis_basin)
    colour_bar.set_label("log10(stored basin member count + 1)")
    fig_basin.savefig(OUT / "basin_score_distance_summary.png", dpi=180)
    plt.close(fig_basin)

    xs, ys = zip(*points)
    best_x, best_y = zip(*best_so_far)
    fig, (axis_score, axis_status) = plt.subplots(2, 1, figsize=(12, 8), constrained_layout=True)
    axis_score.scatter(xs, ys, s=5, alpha=0.22, color="#2878b5", label="finite evaluator score")
    axis_score.plot(best_x, best_y, color="#c83e4d", linewidth=2, label="best score so far")
    axis_score.set(title="Historical Circle Packing score trajectory (samples 1-14,000)", xlabel="sample order", ylabel="sum of radii (higher is better)")
    axis_score.legend(loc="lower right")
    labels = [window["sample_orders"] for window in windows]
    bottom = [0] * len(windows)
    colours = {
        "finite_evaluator_score": "#2a9d8f",
        "nonfinite_invalid": "#e76f51",
        "negative_error_sentinel": "#9d4edd",
        "missing_score": "#adb5bd",
    }
    for label, display in [
        ("finite_evaluator_score", "finite score"),
        ("nonfinite_invalid", "invalid (-inf/non-finite)"),
        ("negative_error_sentinel", "negative error sentinel"),
        ("missing_score", "missing score"),
    ]:
        values = [window[label] for window in windows]
        axis_status.bar(labels, values, bottom=bottom, color=colours[label], label=display)
        bottom = [a + b for a, b in zip(bottom, values)]
    axis_status.set(title="Recorded evaluation outcomes by 1,000-sample window", xlabel="sample-order window", ylabel="records")
    axis_status.tick_params(axis="x", rotation=45)
    axis_status.legend(ncol=2, fontsize=9)
    fig.savefig(OUT / "historical_score_and_outcomes.png", dpi=180)
    plt.close(fig)

    finite_scores = [score for _, score in points]
    best_order, best_score = max(points, key=lambda point: point[1])
    report = [
        "# Circle Packing historical-data analysis",
        "",
        "This report describes supplied historical records only. No new candidate was generated or evaluated.",
        "",
        "## Completed historical archive",
        "",
        f"- Records included: **{len(rows):,}** (sample orders 1-14,000).",
        f"- Finite evaluator scores: **{classes['finite_evaluator_score']:,}** ({classes['finite_evaluator_score'] / len(rows):.1%}).",
        f"- Invalid non-finite scores: **{classes['nonfinite_invalid']:,}** ({classes['nonfinite_invalid'] / len(rows):.1%}).",
        f"- Negative error sentinels: **{classes['negative_error_sentinel']:,}** ({classes['negative_error_sentinel'] / len(rows):.1%}).",
        f"- Missing scores: **{classes['missing_score']:,}** ({classes['missing_score'] / len(rows):.1%}).",
        f"- Best finite historical score: **{best_score:.12f}** at sample **{best_order:,}**.",
        f"- Median finite score: **{statistics.median(finite_scores):.12f}**.",
        "",
        "## Basin reference archive",
        "",
        f"- Historical basin representatives available with code: **{len(basin_rows)}**.",
        "- The top rows in `basin_summary.csv` are ordered by their stored historical score.",
        "- Basin score is historical provenance only; re-evaluate a seed before using it as a current-run comparison point.",
        "- `basin_score_distance_summary.png` shows the trade-off between stored score, distance from the champion, and basin size for the 51 available code representatives.",
        "",
        "## What this supports next",
        "",
        "The trajectory and outcome ledger provide a real baseline for the pilot prompt study. A later prompt run must retain the same outcome categories, save the full prompt and code, and compare arms under a fixed local-model and evaluator configuration.",
    ]
    (OUT / "HISTORICAL_ANALYSIS.md").write_text("\n".join(report) + "\n", encoding="utf-8")
    print(f"Wrote historical analysis to {OUT}")


if __name__ == "__main__":
    main()
