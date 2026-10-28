# Bounded adaptation pilot: two requests

Both registered requests completed. Neither timed out or produced a valid score. Original programs and outcomes are preserved; this analysis did not execute or edit candidate code.

## Work-limit compliance and correctness are separate

Both sources contain one 100-round outer loop, one three-proposal loop, and scans bounded by n. There are no while loops, restarts, recursion or optimizer calls. Both include complete numpy/qmc imports and write accepted updates to the circles array. These observations support compliance with the prescribed loop structure, not compliance with every optimization instruction.

- `request-1f5a502788743e8a`: invalid geometry, worker runtime 0.73957 seconds. Inspection of saved coordinates finds exactly one overlapping pair: zero-based rows 21 and 23, clearance -0.0774779752. The source initializes radii from boundary distances alone, without checking pairwise feasibility. It only accepts proposals that increase a circle's radius, so an initially overlapping circle may remain unchanged. It does not establish a feasible incumbent or verify the final packing. This explains a plausible mechanism for the observed overlap; no corrected-code counterfactual was run.
- `request-e344667942f9535e`: exception in 0.33742 seconds: `NameError: name 'circircles' is not defined`. The distance formula misspells `circles`. Separate inspection finds that `_` names both the outer round and inner proposal counter, so proposal cooling uses an overwritten counter, and `best_r` is never updated after selecting a best proposal. Fixing the typo alone would not establish algorithm correctness or feasibility. No repair was performed.

## Interpretation

The precise work instructions yielded bounded source structures and eliminated timeouts in these two outputs. The sample is too small to generalize reliability, compare prompt profiles, or rank NBN parent-selection strategies. Neither output reaches 2.6360; neither is a high-quality feasible discovery. Comments claiming annealing or validity are not implementation evidence.

This pilot isolates runtime as an addressable issue while exposing remaining program-correctness and feasible-initialization failures. The next proposed condition should use explicit evaluation feedback and a separately registered, fixed repair-call budget, preserving the initial failure and all repaired outputs as distinct records. Repair must target the demonstrated fault, retain the work limits and prohibit silent source edits. Validate actual geometry after generation; do not treat a successful code edit as an optimization improvement.

Before registering that condition, inspect the previous M2-R and code-checked repair protocols to identify what would be new. Do not repeat their completed experiments or silently pool their results. A new repair pilot would measure repair of these specific bounded outputs; it would not establish the ultimate NBN-guidance hypothesis.

All two requests, responses, terminal outcomes and the completion marker were checked in downloaded platform history. No NBN embedding or placement was performed, and invalid outputs were assigned no finite score. The official verifier remains unverified.
