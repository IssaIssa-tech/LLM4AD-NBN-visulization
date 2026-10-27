# AEL Circle Packing initial-population re-evaluation audit

**Date:** 2026-10-26

## Result

All 10 selected historical initial-population programs timed out when
re-evaluated locally with the current isolated evaluator and a **20-second**
limit per candidate.

| Outcome | Count |
|---|---:|
| timeout | 10 |
| valid | 0 |
| invalid geometry | 0 |
| exception | 0 |
| static rejection | 0 |

The complete machine-readable record is `seed_reevaluation.json` in this
folder.  It contains every timeout and the historical ID, sample order,
archived score, and NBN branch for each seed.

## Interpretation boundary

The selected programs remain high-score **historical** records.  Their saved
scores have not been changed.  This audit only establishes that they did not
complete under this project's present local evaluator/time limit.

The historical scores may have been measured with a different runtime budget,
hardware configuration, dependency version, or evaluator environment.  This
audit cannot identify which factor caused the difference without a controlled
environment comparison.

## Consequence for the planned AEL adaptation

Do not generate crossover or mutation offspring from this population yet.
Parent programs must first be executable under the same fixed evaluation
environment that will score their offspring; otherwise the comparison would be
unfair and scientifically unclear.

## Required decision before continuation

Choose and record one of the following before any AEL generation:

1. Use the original/historical evaluator environment and its documented time
   budget for both parents and offspring; or
2. Keep the current 20-second local evaluator and select a new initial
   population from programs that pass it; or
3. Establish a new justified runtime budget, then re-evaluate all seed and
   offspring programs using that exact same budget.

No AEL offspring has been generated.  All ten timeout results are retained as
data.
