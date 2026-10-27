# Code-checked M2 protocol

## Motivation from observed data

The 8-second precheck reproduced every recorded failure category:

- M2-I: 5/5 exception;
- M2-R: 4/5 invalid geometry and 1/5 exception; and
- the successful M2 baseline candidate: valid within the same gate.

The purpose of this protocol is to address **implementation reliability**
before a costly full evaluation. It is a new prompt pipeline and must be
reported separately from the original one-call M2 condition.

## Fixed first-stage generation

Generate one candidate using the frozen combined-contract M2 structural prompt
and record the complete request, sampling seed, response, code hash, and
model configuration.

## Fast precheck

Run `analysis/precheck_circle_candidates.py` with an 8-second isolated limit.
It performs the existing AST contract screen, executes `pack_circles(26)`, and
applies the existing shape, finiteness, boundary, and all-pairs geometry checks.

| Precheck outcome | Next action |
|---|---|
| valid | Send the exact same code to the full 20-second evaluation. No repair prompt. |
| static rejection, exception, wrong shape, non-finite output, invalid geometry, or timeout | Issue exactly one repair prompt. |

## One allowed repair prompt

The repair request must include the original candidate code and its recorded
precheck status/error. It must say:

> Return a minimal corrected version of this exact candidate. Preserve its
> intended algorithmic mechanism and its one structural change. Fix only the
> recorded failure: `<RECORDED_STATUS_OR_ERROR>`. Return exactly one
> `pack_circles(n)` function under the original contract. Do not add a new
> mechanism, an unbounded loop, tests, prose, or top-level execution. Re-check
> all defined names, `(n, 3)` shape, finite values, square boundaries, and
> all-pairs non-overlap before answering.

Run the repaired code through the same 8-second precheck. Whether it passes or
fails, do not make a second repair call.

## Full evaluation and reporting

Only a code version that passes the precheck proceeds to the unchanged
20-second evaluation. Log:

- first-stage prompt/code/hash and precheck status;
- whether a repair was used, its prompt/code/hash, and repair precheck status;
- full-evaluation outcome, score, and runtime; and
- total LLM calls per trial (one or two).

Compare this code-checked M2 condition against the original M2 baseline using
equal sampling seeds and the same evaluator. Do not call it better solely
because it repairs syntax/runtime errors: it must improve the recorded valid
rate, score, or code-region diversity under the stated two-call budget.
