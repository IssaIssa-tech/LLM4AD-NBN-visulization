# M2-R execution result

## Registered condition

M2-R was a new structural-repair follow-up to the earlier combined-contract M2
prompt. It retained the same local model (`qwen2.5:3b`), temperature (0.1),
maximum output length (1800), `n=26` evaluator, quality floor (1.0), and
20-second isolated evaluation limit. Five sampling seeds were pre-registered
before generation.

## Generation

All five prompts completed on the university host's local Ollama service. The
raw prompts, responses, candidate code, hashes, generation ledger, and
evaluator output are preserved in `m2r_execution_20261026/`.

## Evaluation outcomes

| Trial | Evaluator status | Runtime (seconds) | Score | Recorded issue |
|---|---|---:|---:|---|
| m2r-20261031 | invalid geometry | 1.006 | - | geometric feasibility failed |
| m2r-20261101 | invalid geometry | 0.447 | - | geometric feasibility failed |
| m2r-20261102 | exception | 0.378 | - | `ValueError: too many values to unpack (expected 2)` |
| m2r-20261103 | invalid geometry | 0.438 | - | geometric feasibility failed |
| m2r-20261104 | invalid geometry | 0.447 | - | geometric feasibility failed |

**Summary:** 0/5 valid, 4/5 invalid geometry, 1/5 exception, 0/5 timeout.

## Comparison with the earlier repeated M2 baseline

The prior combined-contract M2 condition produced 5/5 valid candidates with
score 2.579279552688004. M2-R produced 0/5 valid candidates. Under the same
evaluator, M2-R is therefore not a successful replacement for the earlier M2
condition.

This comparison does not prove which sentence of the M2-R addition caused the
failure, because it changed several related structural-repair instructions as
one new condition. It does establish that the complete M2-R prompt condition
should not be selected as the current algorithm-design direction.

## Decision

Keep the original combined-contract M2 condition as the reproducible valid
baseline. Treat M2-R as a fully retained negative result. Do not add M2-R
nodes to the valid-candidate NBN analysis, because it has no valid candidates.
Any later prompt revision should change one identified mechanism at a time and
must be logged as a new condition.
