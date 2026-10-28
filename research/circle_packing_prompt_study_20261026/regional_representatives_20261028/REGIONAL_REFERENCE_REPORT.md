# Regional historical references: selection and execution checks

The selected programs are references from the frozen imported HNSW NBN. This is not a new algorithm-generation experiment. The operational regions are first descendants under the unique global root, with that root treated separately. The chosen sampling rule is proposed, not an empirically optimal selection strategy.

Source graph SHA-256: `c5a38d5dc6f4daeee3903476a3508f8cdd41ac0a5fbd10e394947cd9073802dc`.
Region support thresholds: at least 20 members and five positive archived scores. Select the four supported regions with highest archived best score. Within each, select distinct-code programs nearest the 100th, 50th and 10th positive-score rank percentiles. Include the historical champion separately. Every reference was frozen before evaluation.

## All outcomes

| Region / role | Historical sample | Archived score | Current outcome | Current score |
|---|---:|---:|---|---:|
| branch-13793-high_score | 13794 | 2.635932166033 | timeout | unmeasured |
| branch-13793-median_score | 2908 | 2.123754173526 | valid | 2.123754173526 |
| branch-13793-lower_positive_score | 7476 | 0.927074832681 | timeout | unmeasured |
| branch-10492-high_score | 10493 | 2.635917766431 | timeout | unmeasured |
| branch-10492-median_score | 12130 | 2.629123045318 | timeout | unmeasured |
| branch-10492-lower_positive_score | 9320 | 2.593520022592 | timeout | unmeasured |
| branch-11414-high_score | 11415 | 2.635908415115 | timeout | unmeasured |
| branch-11414-median_score | 13158 | 1.854685784009 | valid | 1.854685784009 |
| branch-11414-lower_positive_score | 7713 | 0.661056563267 | valid | 0.661056563267 |
| branch-10485-high_score | 10486 | 2.635806185232 | timeout | unmeasured |
| branch-10485-median_score | 6534 | 2.621171786882 | timeout | unmeasured |
| branch-10485-lower_positive_score | 13402 | 2.604538440535 | timeout | unmeasured |
| historical-champion-control | 12738 | 2.635937208805 | timeout | unmeasured |

Outcome counts: {"timeout": 10, "valid": 3}.

## Interpretation

Current measured coverage: valid programs were found in two of the four selected regions. Samples 2908, 13158 and 7713 returned valid scores 2.123754173526148, 1.8546857840094024 and 0.6610565632673218 respectively. Geometric validity is distinct from solution quality. No reference reached 2.6360 under this diagnostic. All four high-score representatives and the separate historical champion timed out; their archived fitness remains unchanged.

No external random-seed override was injected; the programs' own seed behavior was retained. This is a single diagnostic execution per reference, not a new reproducibility or variance estimate. No import, environment repair or code modification was applied to a selected program during evaluation.

The 20-second limit is a frozen research-budget diagnostic, not a rule established from the official challenge verifier. The approved-import static screen and isolated worker save actual coordinates for returned arrays, including invalid/non-finite results. Missing coordinates on timeouts or exceptions remain missing. The diagnostic namespace contains NumPy as np, matching the earlier standalone research evaluator; it does not reconstruct an arbitrary historical environment.

The historical stored score is not overwritten. A timeout or rejection does not prove that a region is poor, and a changed score does not establish that the archived result was wrong. Different dependencies, entry-point wrappers, runtime budgets or hardware can affect execution. Prior reevaluations are retained as separate provenance rather than silently reused as current results.

Regions of this HNSW snapshot differ from the earlier exact rebuilt graph. Reports must identify the graph used; old branch labels must not be carried over automatically. A top-level branch is a code-space grouping, not proof of a physical attraction basin.

## What this enables next

Use these measured outcomes to define execution-eligible parent pools under the stated budget, while preserving references from every selected region. Do not launch prompts until the parent-selection comparison, prompt variants, model identity, equal call budget, seed allocation and failure policy are registered. If a selected region has no eligible reference, record that limitation and decide explicitly whether to expand its frozen reference pool or change the common evaluator budget; do not silently remove it.

The current target is score at least 2.6360 plus structural diversity, as stated in the new instructions. Official verifier compatibility remains unresolved; current scores are research-evaluator outcomes only. No LLM call was made in this step.

## Reproducibility

Environment: `{"python": "3.10.20 (main, Mar 11 2026, 17:46:40) [GCC 14.3.0]", "numpy": "1.26.4", "scipy": "1.15.3"}`.
Platform history revision: `regional-reference-check-20261028`.
Selection manifest, source code hashes, graph/node IDs, per-reference outputs, full coordinates where available, ledger and environment are preserved alongside this report. The original datasets and prior studies remain unchanged.
