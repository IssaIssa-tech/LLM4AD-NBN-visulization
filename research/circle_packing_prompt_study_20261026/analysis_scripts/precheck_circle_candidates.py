"""Fast, logged precheck gate for generated Circle Packing code.

This script reuses the existing static screen and isolated evaluator, with a
shorter timeout. It is intended to classify implementation/geometry failures
before a future prompt-repair step or full 20-second evaluation. It does not
repair code, call an LLM, or change source candidates.
"""
from __future__ import annotations

import argparse
import json
import sys
from collections import Counter
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "analysis"))
from evaluate_circle_prompt_candidates import evaluate  # noqa: E402


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--candidate-root", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--timeout-seconds", type=int, default=8)
    args = parser.parse_args()
    if args.output.exists():
        raise SystemExit(f"Refusing to overwrite existing precheck report: {args.output}")
    candidates = sorted(args.candidate_root.glob("*/candidate.py"))
    if not candidates:
        raise SystemExit(f"No candidate.py files below {args.candidate_root}")
    results = []
    for candidate in candidates:
        result = evaluate(candidate, timeout_seconds=args.timeout_seconds)
        result["trial_id"] = candidate.parent.name
        results.append(result)
        print(f"{candidate.parent.name}: {result['status']}", flush=True)
    counts = Counter(row["status"] for row in results)
    payload = {
        "purpose": "Fast precheck gate before potential code repair or full Circle Packing evaluation.",
        "timeout_seconds": args.timeout_seconds,
        "candidate_root": str(args.candidate_root),
        "status_counts": dict(sorted(counts.items())),
        "results": results,
    }
    args.output.write_text(json.dumps(payload, indent=2, ensure_ascii=False), encoding="utf-8")
    print(json.dumps({"output": str(args.output), "status_counts": payload["status_counts"]}))


if __name__ == "__main__":
    main()
