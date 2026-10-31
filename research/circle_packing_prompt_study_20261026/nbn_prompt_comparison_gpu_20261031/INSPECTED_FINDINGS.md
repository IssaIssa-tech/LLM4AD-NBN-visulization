# Inspected preliminary findings — finite GPU study

The research batch finished as registered: fourteen unique model calls, sixteen shared-accounted analytical slots, no retries, repairs or manual candidate edits. Generation succeeded for all fourteen requests. All replies reported normal stop, not the generation token cap; prompts fit the configured context. Thus this batch produced actual algorithm-generation evidence, unlike the earlier serving-timeout condition.

## What the four cells show

- Quality-only parents + standard prompt: 0/4 valid; four execution timeouts.
- Quality-only parents + structural-exploration prompt: 0/4 valid; two exceptions and two static failures.
- NBN-region parents + standard prompt: 0/4 valid; four execution timeouts.
- NBN-region parents + structural-exploration prompt: 1/4 valid, score 2.1026448800851467; two exceptions and one shared static failure.

These cells share the two outputs for historical parent 13794; aggregate unique counts are seven execution timeouts, four exceptions, two static rejections and one valid packing. Do not sum the cell counts as independent model calls.

## Valid program and remaining instruction limitation

The sole valid output comes from historical sample 10486, NBN branch node `c-20261017_165510_f7091449-s10486`, using the structural-exploration prompt. It retains deterministic Latin Hypercube initialization and replaces the historical long annealing search with a single sequential grid-based relocation pass. Grid spacing is 0.05; candidate radius is bounded by square walls and distances to other circles. The saved coordinates pass the existing geometry check and sum-of-radii verification without reexecuting the program.

This is one executable generated mechanism, not a collection of diverse high-quality discoveries. The function docstring remains generic and does not describe the changed mechanism as requested; a code comment does describe the grid. Therefore record the observed mechanism and that instruction-adherence limitation separately from its valid evaluator outcome. No stricter full-prompt compliance rate was pre-registered as the primary geometric-validity measure.

The score is below 2.6360. No target hit occurred. The archived historical score is not a current-budget incumbent, and the previously prepared M2/Sobol results were different experiments; no same-budget parent-improvement claim follows here.

## Failure and timing interpretation

Every unique standard-prompt output (seven programs) exceeded the twenty-second execution limit. The structural prompt produced four distinct runtime errors: a one-dimensional sampling requirement, recursion-depth exhaustion, an array element/sequence mismatch and an invalid array axis. Its two static failures were an unmatched closing parenthesis and an extra top-level `mutate` helper. No source was repaired after inspection.

This suggests that, for the selected parents and these settings, the standard prompt failed to adapt the long historical search to the runtime budget. The structural prompt elicited changes in mechanism but frequently introduced code/contract failures. These are observations about complete prompt packages and this small sample, not isolated sentence effects or a general ranking.

## Conclusion and boundary

The NBN-region/structural-prompt cell contains the only feasible output in this pilot, but the evidence is insufficient to conclude that NBN-guided selection improves quality or structural diversity. There is one output per parent/profile, overlapping groups, and only one feasible result. The supervisor's target remains unmet. The runtime bottleneck is resolved for this batch, and actual generated-program execution and feasibility are now the observed limitations.

All fourteen programs, including unsuccessful ones, remain in the complete history with their parent nodes, prompts, raw replies and outcomes. Embedding placement of these new programs has not been computed; do not claim discovery of a new basin. Invalid/unmeasured fitness must remain explicit rather than becoming fabricated finite scores.

The finite generation batch is closed. The next analytical step is mechanism/representation comparison against the frozen historical data, followed by an evidence-based design decision. Any additional generation, altered runtime budget or repair policy would require a new explicit protocol; no such work was started automatically.
