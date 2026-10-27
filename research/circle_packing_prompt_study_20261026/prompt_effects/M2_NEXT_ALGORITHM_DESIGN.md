# Next Circle Packing algorithm design: evidence-based M2 condition

## Why this condition is selected

The controlled 30-candidate comparison found that the combined contract plus
M2 structural modification was the only tested condition that produced valid,
non-trivial Circle Packing output in every repeat (5/5 valid; score
2.579279552688004).  This selects the condition as a starting point for the
next design. It does **not** establish that M2 is globally best or that it
beats the historical champion.

## Fixed requirements retained from the successful condition

- Return exactly one Python function: `pack_circles(n: int) -> np.ndarray`.
- Module level may contain only approved imports, an optional docstring, and
  that one function.
- Use deterministic bounded computation and finish for `n=26` within the
  fixed 20-second evaluator limit.
- Return an `(n, 3)` finite array of `(x, y, radius)` values.
- Enforce unit-square boundaries, non-negative radii, and all-pairs
  non-overlap before returning.
- Avoid an all-zero fallback; target a strictly positive sum of radii and keep
  the quality floor of 1.0.
- Save prompt, model configuration, sampling seed, raw response, code hash,
  static-screen outcome, runtime, geometry outcome, and score for every run.

## New requirement motivated by the NBN result

All five valid M2 candidates attach to one historical CodeT5+ NBN branch.
The next M2 prompt must therefore ask for a **specific, bounded, structural
change** rather than a restatement of the prior successful pattern. The prompt
must describe the proposed mechanism in a short thought before giving code.

Suitable structural mechanisms to test one at a time include:

1. deterministic candidate-site construction followed by bounded radius
   expansion;
2. bounded relocation/repair moves after an initial feasible placement; or
3. a different deterministic initialization coupled with a feasibility-preserving
   local refinement schedule.

These are candidate mechanisms, not claimed improvements. One mechanism per
prompt condition is required so that later outcomes can be attributed to a
known prompt change.

## Proposed prompt condition: M2-R (structural repair)

Use the existing M2 structural prompt and exact output contract, then add:

> Replace one substantive component of the parent heuristic with a bounded,
> deterministic feasibility-preserving mechanism. State the single component
> you changed in at most two sentences. Use no unbounded loops, no optimisation
> budget above 500 rounds, and no nested all-pairs search inside a large
> iteration budget. Before returning, apply a deterministic all-pairs boundary
> and overlap repair. Do not return an all-zero solution.

This is a new, separately labelled prompt condition. It must not be pooled
with the earlier `contract + M2` results.

## Minimal next experiment

1. Freeze the full M2-R prompt text, parent reference, model, temperature,
   maximum output length, five sampling seeds, evaluator, and timeout in a
   manifest before calling the local LLM.
2. Generate five independent M2-R candidates with the local LLM.
3. Evaluate all five with the unchanged 20-second evaluator.
4. Compare only against the earlier repeated `contract + M2` condition:
   validity rate, score distribution among valid candidates, unique-code
   count, runtime, and NBN branch placement.
5. Retain all outcomes. A result is not called better unless the recorded
   comparison supports that statement.

## Decision gate after M2-R

- If M2-R improves score or produces valid candidates in a different NBN
  branch, use its successful mechanism as the next algorithm-design family.
- If it only repeats the existing branch/score, keep it as a reliable baseline
  and redesign a single different M2 mechanism.
- If it fails feasibility or runtime, record the failure and revise only the
  identified failure source; do not silently replace the condition.
