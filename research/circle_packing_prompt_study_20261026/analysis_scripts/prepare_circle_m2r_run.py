"""Pre-register, but do not execute, five M2-R Circle Packing generations."""
from __future__ import annotations

import hashlib
import json
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
SOURCE_PROMPT = ROOT / "output" / "circle_prompt_preflight_20261025" / "repeated_candidates_raw" / "repeated_contract_seed_20261026_20261025" / "m2_structural" / "prompt.txt"
OUT = ROOT / "output" / "circle_prompt_effects_20261026" / "m2r_preregistered_run"
SEEDS = [20261031, 20261101, 20261102, 20261103, 20261104]

M2R_INSERT = """

M2-R structural-repair requirement (new experimental condition):
Replace exactly one substantial algorithmic component with a bounded,
deterministic, feasibility-preserving mechanism. The changed component must be
one of: deterministic candidate-site construction, bounded relocation/repair,
or deterministic initialization plus feasibility-preserving local refinement.
Use one mechanism, not a mixture. Do not use an unbounded loop, a search budget
above 500 rounds, or a nested all-pairs search inside a large iteration budget.
Before returning, apply a deterministic all-pairs boundary and overlap repair.
Do not return an all-zero or near-zero-radius solution. The goal is to test a
structurally distinct, executable candidate; no performance claim is expected.
""".strip()


def main() -> None:
    if OUT.exists():
        raise SystemExit(f"Refusing to overwrite preregistered run: {OUT}")
    base = SOURCE_PROMPT.read_text(encoding="utf-8")
    marker = "\n\nParent program:\n```python\n"
    if marker not in base:
        raise RuntimeError("Unexpected source prompt structure; cannot safely insert M2-R requirement.")
    prompt = base.replace(marker, f"\n\n{M2R_INSERT}{marker}", 1)
    OUT.mkdir(parents=True)
    rows = []
    for seed in SEEDS:
        trial_id = f"m2r-{seed}"
        trial_dir = OUT / trial_id
        trial_dir.mkdir()
        prompt_path = trial_dir / "prompt.txt"
        prompt_path.write_text(prompt, encoding="utf-8")
        rows.append({
            "trial_id": trial_id,
            "sampling_seed": seed,
            "prompt_file": str(prompt_path.relative_to(OUT)),
            "prompt_sha256": hashlib.sha256(prompt.encode("utf-8")).hexdigest(),
            "generation_status": "not_started_endpoint_unavailable",
        })
    manifest = {
        "purpose": "Pre-registered M2-R Circle Packing follow-up. No LLM call or candidate evaluation has occurred.",
        "derived_from_evidence": "output/circle_prompt_effects_20261026/PROMPT_EFFECTS_ANALYSIS.md",
        "comparison_baseline": "contract + m2_structural, 5 repeated candidates, qwen2.5:3b, temperature 0.1, num_predict 1800",
        "new_condition": "M2-R structural repair; append one bounded deterministic structural mechanism requirement to the earlier successful combined contract + M2 prompt.",
        "model": "qwen2.5:3b",
        "endpoint_requirement": "An approved execution host with a reachable local Ollama endpoint. This workstation had neither 127.0.0.1:11435 nor 127.0.0.1:11436 available when preregistered.",
        "temperature": 0.1,
        "num_predict": 1800,
        "n_circles": 26,
        "evaluator": "static screen + isolated Circle Packing geometric evaluation",
        "timeout_seconds": 20,
        "quality_floor": 1.0,
        "trials": rows,
    }
    (OUT / "run_manifest.json").write_text(json.dumps(manifest, indent=2), encoding="utf-8")
    (OUT / "README.md").write_text(
        "# M2-R preregistered run\n\n"
        "Five M2-R prompts have been frozen before model access. They must be generated only on an approved host with the recorded local model endpoint, then evaluated using the unchanged 20-second evaluator. No files in this folder are generated algorithms yet.\n",
        encoding="utf-8",
    )
    print(json.dumps({"output": str(OUT), "trials": len(rows), "prompt_sha256": rows[0]["prompt_sha256"]}, indent=2))


if __name__ == "__main__":
    main()
