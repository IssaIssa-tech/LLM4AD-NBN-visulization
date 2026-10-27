# Feasible initialization × acceptance: 2x2 algorithm ablation

Date: 2026-10-27. Four prepared programs were frozen in a manifest before evaluation, with one evaluation per condition, zero LLM calls, no repair or tuning, fixed seed 2025, n=26 and the existing 20-second isolated geometry evaluator. These are algorithm experiments, not successful LLM prompt outputs.

| Initialization | Acceptance | Geometry | Score |
|---|---|---|---:|
| Original boundary-based radii | Original probabilistic rule | valid | 2.5902372123245248 |
| Original boundary-based radii | Radius increases only | invalid | unscored |
| Deterministic feasible radii | Original probabilistic rule | valid | 2.5943804351303266 |
| Deterministic feasible radii | Radius increases only | valid | 2.4489024587636323 |

The feasible construction keeps the existing Sobol centres, starts with zero radii, and assigns radii in fixed order, bounded by the square and distance to every other centre minus its current radius. Considering unassigned centres with zero radius prevents an assigned circle from covering them. Subsequent assignments respect earlier radii. The source is preserved verbatim with its hash. Initial coordinates were not separately traced in this evaluation; final feasibility is measured directly by the evaluator.

## Findings

1. The original conditions reproduce the earlier valid parent and invalid monotone result.
2. Feasible initialization plus monotone acceptance returns a valid packing, resolving the observed final-feasibility failure at this deterministic setting. Its score is substantially lower than the parent.
3. Feasible initialization with original acceptance improves the parent by 0.0041432228058018 in this run. This is one controlled deterministic comparison, not an estimate of typical improvement across seeds.
4. The best new score remains below the separately tested Sobol seed 20261134 (2.5963958373961282), the earlier exploratory pilot (2.600306976710351), and the archived historical champion. Conditions and provenance differ, so these references are not pooled.

## Design decision

Retain the original probabilistic acceptance rule as the supported choice at this setting. Keep feasible initialization plus original acceptance as a candidate structural variant. Do not select monotone acceptance merely because it now returns valid geometry: its measured objective is worse.

Before declaring a final algorithm, test the initialization effect across a fixed matched set of Sobol seeds, retaining identical evaluator and acceptance settings. The original and feasible initialization variants must use the same seed in each pair. This would address whether the small improvement is consistent. A local-LLM implementation experiment and exact NBN placement are separate questions; neither was performed for these new variants.

## Interpretation limits

One deterministic setting, no independent repeats across algorithm seeds. Removing probabilistic acceptance changes RNG draw consumption as well as the acceptance mechanism. This 2x2 test separates the two specified source components, but does not imply all future generated heuristics behave similarly. Invalid output receives no score. All four outcomes are retained.

Evidence: `feasible_initialization_test_20261027/manifest.json`, `results.json`, `ledger.jsonl`, four frozen programs, evaluator and runner; `analysis/test_feasible_initialization.py` reproduces preparation and execution with overwrite guards.
