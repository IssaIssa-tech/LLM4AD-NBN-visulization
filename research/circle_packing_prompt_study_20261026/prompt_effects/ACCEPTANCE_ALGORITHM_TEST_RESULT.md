# Algorithm-only acceptance ablation result — 2026-10-27

The previously frozen intended edit was evaluated separately from the five failed local-LLM delivery trials. No additional generation, repair, seed tuning or source changes were performed. The prospective manifest is `acceptance_algorithm_test_20261027/manifest.json`.

| Program | Outcome | Score | Evaluator runtime |
|---|---|---:|---:|
| Sobol M2-I-P parent | valid | 2.5902372123245248 | 4.357 s |
| Frozen radius-increasing-only acceptance edit | invalid geometry | unscored | 4.091 s |

Both programs passed the static screen and returned shape (26, 3). The fixed n=26 evaluator used a 20-second isolated limit and all-pairs overlap/boundary checks. The parent reproduced its earlier score in the same server environment.

## Decision

Reject this frozen acceptance edit as a replacement at the tested deterministic setting. Retain the valid parent. This is one prepared algorithm comparison, not five successful LLM outputs or evidence of general inferiority over every possible seed. The original five AST rejections remain unchanged.

## Interpretation boundary

The edit changes acceptance and the consumption of random numbers, so subsequent proposals need not match the parent. Source inspection suggests an additional concern: initial radii are based on boundary distances and do not enforce pairwise feasibility. Restricting acceptance to radius increases may leave initial overlaps unresolved. This is a plausible explanation, not a measured diagnosis: packing coordinates and violating pairs were not saved by this evaluator.

No invalid output was assigned a fitness score. The next design should address feasibility explicitly before attempting monotone radius improvement. Any repair or revised initialization would be a new condition requiring a frozen design and fresh evaluation; no such condition was executed here.

## Evidence

- `acceptance_algorithm_test_20261027/results.json`
- `acceptance_algorithm_test_20261027/ledger.jsonl`
- Frozen parent, edited source, evaluator, runner and manifest in the same folder.
- `M2_ACCEPTANCE_EXECUTION_RESULT.md`: separate failed LLM-delivery experiment.
