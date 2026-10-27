# Acceptance failure: coordinate diagnosis — 2026-10-27

This instrumented rerun captured the initial and final coordinates of the frozen parent and acceptance-edit programs. Source files were unchanged. Each ran in an isolated subprocess with a 20-second diagnostic timeout. Tracing adds overhead; these are diagnostic observations, not new fitness trials or runtime benchmarks. All coordinates, violating pairs and the analysis script are preserved.

## Observations

| Program | Initial overlapping pairs | Final overlapping pairs | Final boundary violations |
|---|---:|---:|---:|
| Parent Sobol search | 9 | 0 | 0 |
| Radius-increasing-only edit | 9 | 6 | 0 |

All six remaining overlaps in the edited program were present initially. No new overlapping pairs appeared. Circles 14, 15, 16 and 17 (zero-based indices) retain exactly their initial positions and radii. The parent moves every circle and resolves all initial overlaps.

| Remaining pair | Penetration (radius sum minus centre distance) |
|---|---:|
| 14,15 | 0.05325599280154067 |
| 14,16 | 0.08071073760829679 |
| 14,17 | 0.10592975758727363 |
| 15,16 | 0.1034337464371638 |
| 15,17 | 0.005418235259626675 |
| 16,17 | 0.007642879377345729 |

Tolerance: 1e-12. The violations are far larger than numerical tolerance.

## Mechanism supported by the observations

Initialization uses distances to the square boundary to choose radii, but does not enforce pairwise non-overlap. The parent can accept smaller-radius proposals, allowing it to escape this initially infeasible packing in the observed run. The edited rule requires a proposal radius to exceed the current radius. Four circles never change, leaving the observed six initial overlaps unresolved. This establishes the failure pattern; the diagnostic does not log all rejected proposals or separate acceptance effects from the changed RNG stream.

## Evidence-based next design

A next controlled condition can test feasible initialization before monotone acceptance. Retain the fixed Sobol centres and replace only the radius-initialization procedure with a deterministic all-pairs feasible construction. A proposed construction starts all radii at zero, visits circles in a fixed order, and chooses a nonnegative radius bounded by the square boundary and its distance to every other centre minus that centre's currently assigned radius. Considering every centre, including centres whose radii remain zero, is necessary to avoid covering an unassigned centre.

This is a proposed mechanism, not an implemented or successful result. The original parent should remain the concurrent control, and the failed monotone variant remains a negative reference. Any test must record the new source/hash and verify initial feasibility before search, final feasibility, quality and runtime under the fixed evaluator. A subsequent local-LLM implementation test is a separate delivery question.

## Files

- `acceptance_algorithm_test_20261027/geometry_diagnosis.json`: full initial/final coordinates and violations.
- `analysis/diagnose_acceptance_geometry.py`: source-tracing diagnostic.
- `ACCEPTANCE_ALGORITHM_TEST_RESULT.md`: original fixed-evaluator outcome.
