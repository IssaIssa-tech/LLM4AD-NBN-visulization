# Circle Packing prompt-effects analysis

## Question from the supervisor

Which tested prompt condition produced usable Circle Packing algorithms, and what should be used as the evidence-based starting point for the next algorithm design?

## Evidence included

Main evidence: a repeated controlled comparison of 30 local-LLM candidates: 2 prompt profiles x 3 arms x 5 recorded sampling seeds. All used `n=26`, the same static screen, isolated geometric evaluator, 20-second limit, and a quality floor of 1.0.

The two profiles are not single-factor ablations. `baseline` is the original prompt. `contract` combines runtime, all-pairs feasibility, non-trivial-quality, and exact output-contract constraints. Therefore this experiment tests the *combined contract profile*, not the independent effect of each individual constraint.

## Controlled results

| Profile | Arm | n | Valid | Invalid geometry | Timeout | Unique code hashes | Valid-score mean / best | Valid NBN branch(es) |
|---|---|---:|---:|---:|---:|---:|---|---|
| baseline | m1_parameter | 5 | 0 | 0 | 5 | 1 | - | - |
| baseline | m2_structural | 5 | 0 | 0 | 5 | 1 | - | - |
| baseline | m3_diversity | 5 | 0 | 0 | 5 | 1 | - | - |
| contract | m1_parameter | 5 | 0 | 0 | 5 | 2 | - | - |
| contract | m2_structural | 5 | 5 | 0 | 0 | 2 | 2.579279552688 / 2.579279552688 | 13793 |
| contract | m3_diversity | 5 | 0 | 1 | 4 | 4 | - | - |

## What the data support

1. Under the tested baseline profile, none of the 15 candidates completed the evaluator: all were timeouts.
2. Under the combined contract profile, M1 parameter tuning still timed out in all five trials. M3 diversity produced four timeouts and one invalid geometry result.
3. Under the combined contract profile, M2 structural modification completed in all five trials, passed the quality floor, and achieved the same valid score (2.579279552688004) in every trial.
4. All five valid M2 trials attach to the same top-level branch of the saved combined CodeT5+ NBN. Thus this condition is currently reliable for feasibility/runtime, but has not demonstrated broad code-region coverage or a score above the historical champion (2.635937208805357).

## Exploratory context, not pooled with the main comparison

An earlier five-profile one-sample-per-arm pilot also found that structural modification was the only arm that produced non-zero valid output under its final contract profile: score 2.600306976710351. It is below the historical champion. Because the profiles were explored sequentially and not equally repeated, this pilot is supporting context only; it is not pooled into the controlled statistics above.

## Design decision justified by the evidence

Use the **combined contract + M2 structural modification** as the starting condition for the next algorithm-design experiment. Keep the exact contract, 20-second evaluator, quality floor, and full outcome ledger. Do not label M2 as globally best: it is only the best-supported condition among the conditions tested so far.

The next design must address the remaining weakness: every valid M2 result enters one historical NBN branch. The M2 prompt should therefore preserve its runtime/feasibility contract while explicitly requiring a distinct algorithmic mechanism and evaluating multiple independent samples. M1 and M3 should be redesigned and re-tested separately before comparing them with M2 again.

## Files produced

- `controlled_prompt_observations.csv`: every one of the 30 controlled observations, including failures and NBN parent information.
- `controlled_prompt_summary.json`: machine-readable grouped summary used for the table above.
