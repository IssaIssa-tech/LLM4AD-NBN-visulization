# Matched-seed initialization comparison — 2026-10-27

Five prepared feasible-initialization variants were frozen before evaluation. The original probabilistic acceptance rule, NumPy seed 2025, n=26, existing geometry checks and 20-second isolated evaluator were held fixed. Sobol scramble seeds match the previously evaluated original-initialization variants. No LLM calls, repairs, adaptive seed selection or control reruns occurred. Controls are reused earlier server results rather than interleaved contemporaneous evaluations.

| Sobol seed | Original initialization | Feasible initialization | Difference |
|---|---:|---:|---:|
| 20261130 | 2.556030886445475 | 2.5967375699635373 | +0.04070668351806228 |
| 20261131 | 2.585691018316561 | 2.5792269505615675 | -0.006464067754993419 |
| 20261132 | 2.581517030579852 | 2.5960479367965945 | +0.01453090621674269 |
| 20261133 | 2.5862156356698685 | 2.598366419088454 | +0.012150783418585664 |
| 20261134 | 2.5963958373961282 | 2.605215496668259 | +0.008819659272130576 |

Both cohorts have five valid outputs. Feasible initialization improves four of five matched scores. Original mean: 2.581170081681577. Feasible mean: 2.5951188746156824. Mean paired difference: +0.013948792934105558; median paired difference: +0.012150783418585664.

## Design decision

Select feasible initialization with the original probabilistic acceptance rule as the promising algorithm design for the tested seed cohort. Keep the one worsening seed visible. The best observed setting is Sobol seed 20261134 at 2.605215496668259, exceeding the separately recorded earlier exploratory pilot score 2.600306976710351. It remains 0.030721712137097956 below the archived historical best; historical environment/runtime comparability remains unresolved.

This is evidence for a component choice in the tested prepared algorithm family, not proof of general superiority or a successful local-LLM generation result. Five previously explored fixed seeds form a small exploratory cohort. Selecting the best after looking at results does not independently validate that setting. A held-out fixed seed cohort would be needed to assess generalization beyond these seeds. These new programs have not yet been placed in the exact CodeT5+ NBN, and no claim of a new code region or broad structural diversity is made.

The proposed algorithm is: scrambled-Sobol centre initialization; deterministic feasible radius assignment against all centres and previously assigned radii; the original bounded 500-pass, five-proposal search with all-pairs radius calculation and probabilistic acceptance. The output continues to require independent geometry validation.

## Preserved evidence

`matched_initialization_test_20261027/` contains manifest, five candidate programs, frozen earlier control records, evaluator, runner, ledger and results. Candidate and control hashes identify provenance. `analysis/test_matched_initialization.py` prepares and executes with overwrite guards. The previous factorial test and negative acceptance results remain separate.

## Next evidence required

Extend the exact NBN with the new prepared variants and inspect their measured parent/branch placement. Treat this as analysis of the selected design, not as a substitute for fitness evaluation. Before more prompt generation, document the algorithm decision and distinguish researcher-specified components from LLM-delivered changes.
