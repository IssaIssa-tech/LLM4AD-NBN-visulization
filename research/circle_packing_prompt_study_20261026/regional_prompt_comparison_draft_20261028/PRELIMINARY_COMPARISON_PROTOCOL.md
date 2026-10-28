# Draft preliminary parent-selection × prompt comparison

Status: concrete draft prepared; no model requests have been made, no trial has been registered as executed, and no results are claimed. The model identity, evaluator hash/environment and platform-history bindings must be checked before registration.

## Research question

Under a common local-model and generated-program evaluation budget, how do historical-parent selection and prompt design affect feasible score, code structure and NBN coverage? Research target: at least 2.6360. This target is neither guaranteed nor asserted as an officially verified score without the full challenge verifier.

## Parent policy resolving the diagnostic timeouts

The selected historical programs are archival **textual references**. They are not scored incumbents in the current 20-second environment. Their source code, source graph/node identity, archived score and diagnostic status remain available. A reference may inform LLM design even when its own lengthy search did not finish under the diagnostic budget. Do not compare new scores to its archival score as if both were measured under identical conditions.

Inspection found 20,000–40,000-round searches in several high-score references, with multiple nested proposals per circle. Increasing the historical execution limit without a new condition would change the study. This draft instead retains the existing 20-second limit for **all newly generated programs**, preserving every selected region. This is a research-efficiency condition, not a rule established by the challenge website. No reference program is shortened or otherwise edited.

This is a different policy from the earlier fixed-parent/incumbent workflow; that old protocol and its outcomes remain unchanged. If a later study aims to measure improvement over a freshly evaluated historical parent, it must establish a comparable parent/offspring budget separately.

## Two selection strategies

1. Quality-only: the top four distinct source-code hashes by positive finite archived score, with sample-order tie-breaking. No NBN region condition.
2. NBN-region: the best archived positive-score representative of each of the four supported top-level branches selected in the frozen regional manifest (support: at least 20 members and five positive-score records).

The source graph SHA-256 is frozen in the manifest; its backend is HNSW-based. A region is the first descendant below the global root. These are operational code-space groups, not proven physical attraction basins.

| Selection strategy | Historical sample orders |
|---|---|
| Quality-only top four distinct code records | 12738, 13794, 13970, 12472 |
| Four supported NBN-region high-score representatives | 13794, 10493, 11415, 10486 |

The overlapping reference is sample 13794. The groups are not independent random samples. Parent selection changes both program content and archived-score distribution; any outcome describes the full strategy, not an isolated causal effect of a branch label.

## Two prompt profiles

- `contract_M2`: fixed program contract, bounded deterministic computation, geometry and research-runtime conditions, and one substantive structural change from the supplied parent.
- `contract_M2_structural_exploration`: the same common contract and structural-change requirement, plus an explicit request to depart from the reference's search/proposal pattern, describe the mechanism in a function docstring, and use supplied NBN grouping as context.

The second profile is a combined prompt package, not a single-sentence ablation. Both state the same target and research runtime. Both include exact reference code and explicitly label the parent score as archived. Full prompt text and SHA-256 are saved per unique request.

## Planned calls and failure policy

Four parents per selection strategy × two prompts = sixteen analytical slots. Sampling seed is deterministically `202600000 + historical_sample_order`. A shared parent receives the same seed for each prompt profile across strategies. Model/configuration and prompt are identical for those shared slots, so fourteen unique requests suffice. Reuse must be explicit in the analytical table; shared responses are not independent replications. Each strategy still has eight defined slots, with shared-call cost disclosed. No physical duplicate call is planned merely to fill a table.

Proposed local model: qwen2.5:3b, temperature 0.1, maximum generation length 1800. No repairs, replacement calls, adaptive parent changes or optional stopping. This small pilot has one sample per parent/profile; it cannot establish a robust prompt ranking. Preserve generation failures, truncation metadata, extraction failures, invalid geometry, non-finite output, exceptions, timeouts, duplicates and successes.

Before running, freeze actual model digest and endpoint, evaluator source hash and environment, registered trial order, history revision and source artifact IDs. Verify request hashes and IDs, detect repeated request identities, and include all unique calls in the ledger. No candidate source patching is permitted within this condition.

## Measurements

Report outcomes per slot and unique request: valid rate, count reaching 2.6360 under the named evaluator, score distribution among valid outputs, complete failure counts, runtime and call cost. Invalid results have no invented finite fitness. Preserve exact `(26,3)` packing outputs, code, raw replies, prompts, parent node references, and any subsequent strategy revision as new history events.

Measure code SHA-256 and AST duplicates separately. After generation, embed programs using the frozen CodeT5+ configuration and compare distances/placement against a named graph. Fitness-unmeasured failures must not receive invented scores for meaningful nearest-better claims; any sanitized visualization must disclose that policy. Structural diversity requires code-mechanism inspection as well as numerical representation. Plot appearance alone is insufficient.

`parent_structure_audit.json` describes seven unique references. All have different number-masked AST fingerprints, but this is syntax, not proof of seven algorithms. The quality-only pool includes LatinHypercube, Sobol and Halton initializers; the four region-selected high-score references all use LatinHypercube. Thus the NBN strategy cannot be assumed to maximize initializer or mechanism diversity.

## Registration gate

This draft resolves representation and budget policy transparently but does not claim verifier equivalence. Confirm the common evaluator as a research condition and complete platform-history/model/evaluator checks before executing. A separate higher-runtime or official-verifier experiment must use a new registered condition. The prior thirteen reference diagnostics and every earlier study remain preserved.
