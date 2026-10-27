# M2-I-P-D algorithm-only evaluation — 2026-10-27

## Scope and provenance

Five expected Sobol variants frozen before the earlier LLM delivery test were evaluated once each on the university server. These are prepared source programs, not accepted LLM outputs. The earlier five byte-exact patch rejections remain unchanged. This separately registered evaluation made no LLM calls and no repairs. All executable differences between these five programs were verified by AST comparison to be the Sobol seed literal alone.

The manifest was written before evaluation in `m2ipd_algorithm_evaluation_20261027/algorithm_manifest.json`. The evaluator retained n=26, geometric tolerance 1e-12, a 20-second isolated limit, and a quality floor of 1.0. Unlike the earlier delivery workflow, there was no eight-second precheck. Environment: Python 3.10.20, NumPy 2.2.6, SciPy 1.15.3, university hits_1 host.

## Results

| Sobol seed | Geometry | Sum of radii |
|---|---|---:|
| 20261130 | valid | 2.556030886445475 |
| 20261131 | valid | 2.585691018316561 |
| 20261132 | valid | 2.581517030579852 |
| 20261133 | valid | 2.5862156356698685 |
| 20261134 | valid | 2.5963958373961282 |

All five passed the quality floor. Mean: 2.581170081681577. Median: 2.585691018316561. The best exceeds the previously recorded fixed-seed M2-I-P score 2.5902372123245248 by 0.006158625071603474. The five-seed mean is below that reference. Comparisons use saved prior scores, without contemporaneous reruns of the reference programs.

## Interpretation and decision

Changing Sobol scramble seed affects the achieved score in this bounded search. Five distinct objective values demonstrate different outcomes, but no circle-coordinate records were saved, so geometric packing diversity has not been quantified. These remain one algorithm family with different parameter literals; five hashes are not five structural discoveries.

Seed 20261134 is the best observed parameter setting in this five-seed test. It remains below the earlier exploratory pilot (2.600306976710351) and the archived historical best (2.6359372088053568). The historical reference has not been established as comparable under the current runtime/environment.

Retain this Sobol-initialized bounded search as an evaluated design candidate. These observations do not justify declaring it the final best algorithm or claiming that a prompt discovered it. The remaining supervisor-directed research question is which prompt-generated structural mechanisms improve quality and code-region coverage. An NBN update and structural-diversity conclusion have not been performed for these five variants.

## Evidence

- `m2ipd_algorithm_evaluation_20261027/algorithm_manifest.json`
- `m2ipd_algorithm_evaluation_20261027/algorithm_results.json`
- Five frozen `candidate.py` files and the copied evaluator/runner in that directory.
- `m2ipd_execution_20261027/server_snapshot/`: preserved original LLM delivery records.
- `RECONCILED_STATUS_AUDIT_20261027.md`: audit of prior results and interpretation corrections.
