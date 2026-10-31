# AEL historical-parent eligibility results - 2026-10-31

**Completed historical-program diagnostic. No LLM-generated offspring in this batch.**

Checked all 30 prelisted programs once. Outcomes: `{"timeout": 8, "valid": 22}`. Positive-fitness eligible options: **22**. Eligible options span **2** recorded HNSW branches.

Best observed parent: sample **9180**, score **2.533806569785**. Research-target hits (>=2.6360): **0**. This is a re-evaluated historical program, not a newly discovered or evolved algorithm.

## Every measured outcome

| Shortlist rank | Historical sample | HNSW branch index | Outcome | Measured score | Wall seconds | Eligible positive parent |
|---:|---:|---:|---|---:|---:|---|
| 1 | 9180 | 13793 | valid | 2.533806569785 | 3.004 | yes |
| 2 | 7918 | 11414 | valid | 2.393526620287 | 6.685 | yes |
| 3 | 3221 | 11414 | valid | 2.145813181925 | 0.896 | yes |
| 4 | 11156 | 13793 | valid | 2.373092227528 | 2.121 | yes |
| 5 | 13793 | 13793 | valid | 2.341167275807 | 10.814 | yes |
| 6 | 11877 | 13793 | timeout | unmeasured | 20.026 | no |
| 7 | 11307 | 13793 | timeout | unmeasured | 20.029 | no |
| 8 | 3904 | 11414 | timeout | unmeasured | 20.025 | no |
| 9 | 11062 | 13793 | timeout | unmeasured | 20.026 | no |
| 10 | 9227 | 13793 | timeout | unmeasured | 20.026 | no |
| 11 | 6613 | 13793 | valid | 2.230961723746 | 14.901 | yes |
| 12 | 2581 | 13793 | valid | 2.196828643810 | 0.350 | yes |
| 13 | 12796 | 13793 | timeout | unmeasured | 20.027 | no |
| 14 | 12849 | 13793 | valid | 2.139297480167 | 1.748 | yes |
| 15 | 12852 | 13793 | valid | 2.109107549241 | 2.100 | yes |
| 16 | 7510 | 13793 | valid | 1.972145151721 | 0.892 | yes |
| 17 | 1300 | 13793 | valid | 1.920019738041 | 0.453 | yes |
| 18 | 2058 | 13793 | valid | 1.899140148187 | 0.179 | yes |
| 19 | 2226 | 13793 | valid | 1.883842147957 | 0.167 | yes |
| 20 | 12801 | 13793 | timeout | unmeasured | 20.026 | no |
| 21 | 1042 | 13793 | valid | 1.874027597792 | 2.431 | yes |
| 22 | 3445 | 11414 | valid | 1.860415364520 | 0.351 | yes |
| 23 | 1755 | 13793 | valid | 1.848034448764 | 0.320 | yes |
| 24 | 860 | 13793 | valid | 1.837936441396 | 0.681 | yes |
| 25 | 7692 | 13793 | timeout | unmeasured | 20.027 | no |
| 26 | 679 | 13793 | valid | 1.830491642113 | 0.493 | yes |
| 27 | 929 | 13793 | valid | 1.830491642113 | 0.512 | yes |
| 28 | 947 | 13793 | valid | 1.830491642113 | 0.515 | yes |
| 29 | 1258 | 13793 | valid | 1.830491642113 | 0.477 | yes |
| 30 | 1368 | 13793 | valid | 1.826902161546 | 0.305 | yes |

## Conditions and preservation

- Existing N=26 evaluator/static screen and geometry tolerance 1e-12; twenty-second isolated-worker limit including startup. No source changes, repairs, retries or replacements.
- Workers ran sequentially with OPENBLAS/OMP/MKL/NUMEXPR thread limits fixed at one. This condition is recorded explicitly; timing differences from old shared-load runs are not causal estimates.
- Parent eligibility requires a valid finite score greater than zero. A zero score remains a geometrically valid recorded result but would not be a positive-fitness option.
- All source programs, outcomes, available coordinates, stdout/stderr, start records, ledger and platform events are preserved. Archived scores are unchanged.
- The diagnostic keeps the original frozen 30-program order and stops after those thirty attempts, regardless of target attainment.
- Local search for prior matching completed outcomes inspected 261 result/ledger files and found none for these thirty source identities. This is the stated audit scope, not a claim about inaccessible archives.

## Source graph identity

The archive-export SHA-256 is `c5a38d5dc6f4daeee3903476a3508f8cdd41ac0a5fbd10e394947cd9073802dc`. The live graph artifact stores the inner graph and has a different byte digest, recorded in `registration.json`. The input digest and all 14,000 program/source/NBN-parent identities were reconciled before registration (`source_graph_reconciliation.json`).

The selected shortlist maps to 2 HNSW branches: [11414, 13793]. These are operational code-space groups. Earlier exact-graph labels are retained separately rather than reused as current labels. This check does not establish coverage of all four supported historical HNSW branches or compute any new embedding/NBN placement.

The 22 eligible options are conditional on the earlier static shortlist. This was not an exhaustive runtime scan of all 14,000 historical records and does not establish the best possible executable parent pool. Static loop/import filters can exclude programs that might still finish under the time cap. No conclusion about the quality of an unrepresented branch follows from this shortlist.

## What is now enabled

There are 22 measured positive-fitness historical options available for an AEL parent-selection decision. `eligible_parent_options.json` lists them in score order for review; it does not register an initial population, crossover pair allocation, mutation schedule or generation budget.

The next research step is to freeze the first AEL operator test or full evolutionary configuration, including how NBN-guided parent choice is compared with its declared baseline. Keep model, evaluator, prompt format, call budget and failure accounting explicit. This diagnostic does not establish that a parent-selection policy or prompt is superior.

History revision: `ael-parent-eligibility-20261031`. Full model-generation attempts: zero. Valid coordinates and sums were independently checked from the saved arrays; no candidate was executed again while reporting. Official challenge-verifier equivalence remains unresolved.
