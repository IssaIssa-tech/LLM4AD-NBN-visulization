"""Pre-register a single-component M2-I successor experiment; do not execute it."""
from __future__ import annotations

import hashlib
import json
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
PARENT = ROOT / "output" / "circle_prompt_preflight_20261025" / "repeated_candidates_raw" / "repeated_contract_seed_20261026_20261025" / "m2_structural" / "candidate.py"
OUT = ROOT / "output" / "circle_prompt_effects_20261026" / "m2i_preregistered_run"
SEEDS = [20261105, 20261106, 20261107, 20261108, 20261109]


def main() -> None:
    if OUT.exists():
        raise SystemExit(f"Refusing to overwrite preregistered run: {OUT}")
    parent = PARENT.read_text(encoding="utf-8").strip()
    prompt = f"""You are modifying a tested Circle Packing heuristic.
Return exactly one Python code block and no explanation outside the block.
The code must define only `pack_circles(n: int) -> np.ndarray` and may import
only `numpy`, `math`, or `scipy` submodules. Do not use files, networking,
subprocesses, shell commands, dynamic evaluation, helper functions, or
top-level execution. Return an `(n, 3)` NumPy array of `(x, y, radius)` rows.
All circles must lie inside the unit square and must not overlap. The evaluator
uses n=26 and maximises the sum of radii. Use deterministic behaviour.

This is a single-component structural test named M2-I. Preserve the parent
algorithm's bounded search, all-pairs radius calculation, five proposals per
circle, 500 outer iterations, temperature schedule, and acceptance structure.
Change only the initial centre generator: replace the Halton sequence with a
deterministic scrambled Sobol sequence from `scipy.stats.qmc.Sobol`. Generate a
power-of-two number of Sobol points using `random_base2`, then retain the first
`n` points. Do not add an alternative repair mechanism, additional optimisation
loop, or a zero-radius fallback. Re-check syntax, defined names, boundaries,
non-negative radii, and all-pairs feasibility before answering.

Parent program:
```python
{parent}
```
"""
    OUT.mkdir(parents=True)
    rows = []
    for seed in SEEDS:
        trial_id = f"m2i-{seed}"
        trial_dir = OUT / trial_id
        trial_dir.mkdir()
        prompt_path = trial_dir / "prompt.txt"
        prompt_path.write_text(prompt, encoding="utf-8")
        rows.append({
            "trial_id": trial_id,
            "sampling_seed": seed,
            "prompt_file": str(prompt_path.relative_to(OUT)),
            "prompt_sha256": hashlib.sha256(prompt.encode("utf-8")).hexdigest(),
            "generation_status": "not_started",
        })
    manifest = {
        "purpose": "Pre-registered M2-I Circle Packing successor: change only Halton initialization to deterministic scrambled Sobol initialization. No LLM call or evaluation has occurred.",
        "evidence_baseline": "contract + M2 structural, score 2.579279552688004, 5/5 valid",
        "parent_code_sha256": hashlib.sha256((parent + "\n").encode("utf-8")).hexdigest(),
        "model": "qwen2.5:3b",
        "temperature": 0.1,
        "num_predict": 1800,
        "n_circles": 26,
        "timeout_seconds": 20,
        "quality_floor": 1.0,
        "trials": rows,
    }
    (OUT / "run_manifest.json").write_text(json.dumps(manifest, indent=2), encoding="utf-8")
    (OUT / "README.md").write_text(
        "# M2-I preregistered run\n\n"
        "M2-I changes only the successful M2 baseline's Halton initialization to deterministic scrambled Sobol initialization. It preserves the bounded search and feasibility logic. Five prompts are frozen before generation; no candidate exists yet.\n",
        encoding="utf-8",
    )
    print(json.dumps({"output": str(OUT), "trials": len(rows), "prompt_sha256": rows[0]["prompt_sha256"]}, indent=2))


if __name__ == "__main__":
    main()
