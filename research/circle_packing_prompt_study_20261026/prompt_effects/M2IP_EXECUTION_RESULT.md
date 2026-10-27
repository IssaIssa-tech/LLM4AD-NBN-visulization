# M2-I-P strict code-patch execution result — 2026-10-27

## Question

Does the specified Halton-to-scrambled-Sobol initialization patch improve the
validated M2 Circle Packing heuristic when the local LLM is constrained to
deliver that exact patch?

## Pre-registered condition

Five fixed local-model requests used `qwen2.5:3b` at temperature 0.1. Each
output had to be byte-identical to the pre-registered patched source before it
could proceed to the eight-second precheck and twenty-second `n=26` evaluation.
No repair calls were allowed.

## Results

| Measure | Result |
|---|---:|
| Trials | 5 |
| Exact patch matches | 5 / 5 |
| Valid full evaluations | 5 / 5 |
| Unique generated candidate hashes | 1 |
| Score of each valid evaluation | 2.5902372123245248 |
| Original validated M2 score | 2.579279552688004 |
| Difference from M2 | +0.010957659636520845 |
| Relative difference from M2 | +0.42483412180355895% |
| Historical best score | 2.6359372088053568 |
| Gap to historical best | 0.045699996480832006 |

## Interpretation

The strict patch prompt achieved reliable delivery: every output exactly
matched the allowed Sobol variant and evaluated validly. The Sobol variant
scored higher than the selected M2 baseline for this deterministic evaluator.

The five trials are **not five independent algorithmic scores**: exact-patch
enforcement and the deterministic algorithm produced one unique candidate and
one unique score. They support a code-delivery reliability conclusion and one
controlled algorithm comparison, not a variance estimate or a claim that this
variant is globally best. It remains below the best historical Circle Packing
score.

## Next NBN handling

The five trial records will be represented individually in a new, versioned
combined NBN. Because their code and score are identical, any shared branch or
position is expected and must not be described as five diverse discoveries.

## Evidence

- `M2IP_PATCH_PROTOCOL.md`
- `m2ip_patch_preregistered_run/run_manifest.json`
- `m2ip_patch_execution_20261027/results.json`
- `m2ip_patch_execution_20261027/generation_ledger.jsonl`
