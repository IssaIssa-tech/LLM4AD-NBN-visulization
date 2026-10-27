"""Prepare a five-seed code-checked M2 experiment without generation."""
from __future__ import annotations

import hashlib
import json
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
SOURCE_PROMPT = ROOT / "output" / "circle_prompt_preflight_20261025" / "repeated_candidates_raw" / "repeated_contract_seed_20261026_20261025" / "m2_structural" / "prompt.txt"
OUT = ROOT / "output" / "circle_prompt_effects_20261026" / "code_checked_m2_preregistered_run"
SEEDS = [20261110, 20261111, 20261112, 20261113, 20261114]


def main() -> None:
    if OUT.exists():
        raise SystemExit(f"Refusing to overwrite preregistered run: {OUT}")
    prompt = SOURCE_PROMPT.read_text(encoding="utf-8")
    OUT.mkdir(parents=True)
    trials = []
    for seed in SEEDS:
        trial_id = f"code-checked-m2-{seed}"
        directory = OUT / trial_id
        directory.mkdir()
        path = directory / "initial_prompt.txt"
        path.write_text(prompt, encoding="utf-8")
        trials.append({
            "trial_id": trial_id,
            "sampling_seed": seed,
            "initial_prompt_file": str(path.relative_to(OUT)),
            "initial_prompt_sha256": hashlib.sha256(prompt.encode("utf-8")).hexdigest(),
            "generation_status": "not_started",
        })
    manifest = {
        "purpose": "Pre-registered code-checked M2 condition: one M2 generation, an 8-second precheck, one repair only on a failure, then unchanged 20-second evaluation.",
        "comparison_baseline": "original combined-contract M2, five repeated seeds, 5/5 valid at score 2.579279552688004",
        "model": "qwen2.5:3b",
        "temperature": 0.1,
        "num_predict": 1800,
        "n_circles": 26,
        "precheck_timeout_seconds": 8,
        "full_timeout_seconds": 20,
        "quality_floor": 1.0,
        "maximum_llm_calls_per_trial": 2,
        "trials": trials,
    }
    (OUT / "run_manifest.json").write_text(json.dumps(manifest, indent=2), encoding="utf-8")
    print(json.dumps({"output": str(OUT), "trials": len(trials)}, indent=2))


if __name__ == "__main__":
    main()
