# Selected baseline algorithm for the next Circle Packing design

## Selection evidence

The repeated prompt comparison selected the combined-contract M2 structural
condition as the current baseline:

- 5 of 5 generated candidates were geometrically valid under the fixed
  20-second evaluator;
- each received score **2.579279552688004**;
- each passed the non-trivial quality floor of 1.0; and
- M1 and M3 did not produce a valid candidate in the same repeated comparison.

The M2-R follow-up then produced 0 of 5 valid candidates. Therefore the
original combined-contract M2 output is retained as the baseline; M2-R is not
selected.

## Actual code family observed

The five valid M2 outputs contain two different SHA-256 code hashes, but their
algorithmic logic is the same; the difference is import placement. The shared
mechanism is:

1. deterministic Halton-sequence initialization of circle centres;
2. conservative initial radii based on distance to the square boundary;
3. 500 bounded optimisation passes;
4. for each circle, five candidate position moves, using a mix of exploratory
   random moves and local moves under a cosine temperature schedule;
5. radius calculation against the boundary and every other circle; and
6. acceptance of a proposed circle when it improves its radius, with a
   temperature-controlled exploratory acceptance rule.

This is best described as a **Halton-initialised bounded stochastic local
search with all-pairs radius expansion**.

## What may and may not be claimed

Supported:

- It is the most reliable condition among the prompt conditions tested so far.
- It produced valid non-zero Circle Packing output in the controlled five-seed
  repeated comparison.
- It is a practical executable baseline for the next algorithm design.

Not supported:

- It does not beat the historical best score, 2.635937208805357.
- It does not establish that structural modification is always better than the
  other prompt families.
- It has not shown a different high-quality NBN branch; all five valid outputs
  attach to one top-level historical branch.

## Next design rule

Any proposed successor must preserve the fixed function contract and 20-second
evaluator. It should change **one** clearly specified component of this
baseline at a time, keep a full outcome ledger, and be compared against the
baseline's five-seed result. A successor is not selected unless it improves
the recorded validity, score, or demonstrated code-region diversity under the
same evaluation conditions.

## Stable code references

- Four matching outputs:
  `../circle_prompt_preflight_20261025/repeated_candidates_raw/repeated_contract_seed_20261026_20261025/m2_structural/candidate.py`
  (and seeds 20261027 through 20261029).
- Equivalent-logic output with imports inside the function:
  `../circle_prompt_preflight_20261025/repeated_candidates_raw/repeated_contract_seed_20261030_20261025/m2_structural/candidate.py`.
