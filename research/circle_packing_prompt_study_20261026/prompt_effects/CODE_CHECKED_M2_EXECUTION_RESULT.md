# Code-checked M2 execution result — 2026-10-27

## Scope

This is the pre-registered code-checked M2 condition: five fixed seeds, one
initial M2 generation, an eight-second precheck, at most one error-informed
repair, and a full twenty-second evaluation only after a passing precheck.
It is a test of the delivery workflow, not a new estimate of Circle Packing
search quality.

## Outcomes

| Stage | Count |
|---|---:|
| Trials | 5 |
| Initial precheck: exception | 5 |
| Repair precheck: exception | 3 |
| Repair precheck: static rejection | 2 |
| Reached full evaluation | 0 |
| Valid full evaluations | 0 |

Every initial candidate failed with the same runtime error:

`ValueError: The truth value of an array with more than one element is ambiguous. Use a.any() or a.all()`

Inspection shows the generated programs called Python's scalar `min` on NumPy
vectors when calculating an initial radius. The two statically rejected repairs
also appended a top-level example call such as `pack_circles(5)`, violating the
evaluator's no-top-level-execution rule. The other three repairs retained the
same ambiguous-vector error.

## Interpretation

This condition provides no score comparison because no candidate was eligible
for full evaluation. It does **not** show that the M2 search mechanism is poor.
It shows that, for this local-model run, free generation plus one repair did not
reliably deliver executable code under the evaluator contract.

## Evidence preserved

- `code_checked_m2_execution_20261027/results.json`
- `code_checked_m2_execution_20261027/generation_ledger.jsonl`
- each trial's initial and repaired response, code, and repair prompt
- frozen pre-registration: `CODE_CHECKED_M2_PROTOCOL.md`

## Proposed next controlled condition (not run yet)

The earlier M2-I experiment already included the complete M2 parent program,
so a generic "scaffolded M2-I" rerun would duplicate it. The non-duplicate
successor is an **M2-I-P strict code-patch** condition: provide the validated
M2 source, name the exact Halton-to-Sobol replacement block, and reject any
output that changes code outside that block. This isolates adherence to a
small, fully specified initialization patch from Circle Packing quality. It
must be separately pre-registered and reported; it must not be pooled with the
original free-generation M2 results.
