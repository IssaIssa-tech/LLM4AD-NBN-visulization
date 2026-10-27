# Circle Packing algorithm design from prompt and landscape evidence

Date: 2026-10-27. This report consolidates completed experiments for the supervisor's instruction to analyze prompt effects, select useful solutions/prompts, and design an algorithm based on evidence. This is an EoH-inspired Circle Packing prompt/algorithm study, not a full EoH reproduction or an executed AEL evolutionary run.

## Prompt evidence

The repeated two-profile, three-arm, five-seed comparison produced 30 candidates. The combined-contract M2 condition alone returned five valid solutions, all at 2.579279552688004. The other conditions yielded 24 timeouts and one invalid geometry result. The combined contract changes several instructions together, so it is not an ablation of individual prompt sentences. M2 code had two hashes with equivalent logic.

M2-R produced four invalid geometries and one exception; M2-I produced five exceptions. Code-checked M2 with one repair never reached full evaluation. Strict M2-I-P delivered the same exact Sobol-patched program in five requests; each evaluated valid at 2.5902372123245248. This supports delivery reliability and one controlled algorithm comparison, not five diverse discoveries.

Later M2-I-P-D delivery failed five byte-exact checks; three differences were comments only. The subsequent acceptance-rule delivery test failed five AST checks because all outputs deleted the best-proposal update and retained the original acceptance condition. These are retained negative prompt results. Prepared algorithm tests are explicitly separate from local-LLM success claims.

## What the algorithm tests established

- Five prepared Sobol seed variants were valid; scores ranged from 2.556030886445475 to 2.5963958373961282. They stayed in one NBN top-level historical branch.
- Removing probabilistic acceptance made the fixed-seed output invalid. Coordinate diagnosis found nine initial overlapping pairs; six remained among four unchanged circles. The original parent resolved all nine.
- A 2x2 initialization/acceptance comparison showed that feasible initialization restored validity under monotone acceptance, but its score was only 2.4489024587636323. Feasible initialization with original acceptance scored 2.5943804351303266 at Sobol seed 2025, versus parent 2.5902372123245248.
- Across the five matched Sobol seeds 20261130–20261134, feasible initialization was valid in all five and improved four scores. Mean increased from 2.581170081681577 to 2.5951188746156824; mean paired gain was 0.013948792934105558. Controls were saved earlier evaluations, not interleaved contemporaneous runs.

## Selected candidate design

1. Use scrambled Sobol centres.
2. Assign feasible radii deterministically in fixed order, bounded by unit-square boundaries and distance to every other centre minus its current radius, including unassigned zero-radius centres.
3. Retain the original bounded 500-pass search with five proposals per circle, all-pairs radius constraints and probabilistic acceptance.
4. Validate the final packing using the fixed evaluator before accepting its objective.

This component design was specified by the researcher using observed failure and score evidence. It must not be attributed to successful LLM generation. The local model remains the source of the original executable M2 parent and the successful fixed Sobol patch condition.

Best observed feasible setting: Sobol seed 20261134, score 2.605215496668259. This exceeds the separate exploratory pilot score 2.600306976710351 but remains below archived historical best 2.6359372088053568. The historical environment and runtime comparability are unresolved. Choosing the maximum over observed seeds is not held-out validation.

## New exact NBN analysis

The versioned `combined_nbn_feasible_20261027/` graph contains 14,045 nodes and 14,044 edges: 14,000 historical records, 35 earlier prompt trials, five prepared original-initialization Sobol variants, and five prepared feasible-initialization variants. Other failed follow-ups remain in complete experiment ledgers; this graph is a selected visualization cohort, not the complete study ledger.

Build used exact nearest-better computation with CodeT5+ cosine embeddings, 14,040 cached embeddings and five new embeddings in a private copied cache. Earlier graphs and cache were retained.

All feasible variants and matched controls remain under historical top-level branch sample 13794 (old zero-based branch index 13793). Distances from the feasible variants to their matched controls range from 0.009190223806486153 to 0.009207236067617752. Distances within the five feasible variants range from about 0.0000022783 to 0.0000174269. These are normalized embedding cosine distances, not distances between physical circle packings.

Four feasible variants attach to better-scoring feasible variants. The highest-scoring one attaches to historical sample 7174 at parent distance 0.04574108123779297; that parent has archived score 2.605710649414161. The group represents a code modification within an existing top-level branch, not a newly established region. A branch is operationally the first descendant of the global root and is not proof of a dynamical attraction basin. Cone-tree layout appearance does not determine novelty.

## Decision and remaining validation

The completed evidence supports feasible initialization plus the original probabilistic acceptance rule as a promising candidate design for the explored seeds. It does not establish a general best algorithm, broad structural diversity, or a new NBN region.

The next validation should freeze a previously unused algorithm-seed cohort and evaluate both initialization conditions for each seed under the same server environment, retaining all outcomes and paired differences. Hold model generation separate from that evaluation. Do not tune the design using this validation cohort and then describe it as held out. No unseen-seed run was launched as part of this report.

## Evidence map

- `PROMPT_EFFECTS_ANALYSIS.md`: repeated prompt comparison.
- `M2IP_EXECUTION_RESULT.md`: successful strict Sobol patch delivery.
- `RECONCILED_STATUS_AUDIT_20261027.md`: provenance corrections and inventory.
- `M2_ACCEPTANCE_EXECUTION_RESULT.md`: failed structural-patch delivery.
- `ACCEPTANCE_GEOMETRY_DIAGNOSIS.md`: measured initial/final overlap pattern.
- `FEASIBLE_INITIALIZATION_RESULT.md`: factorial comparison.
- `MATCHED_INITIALIZATION_RESULT.md`: paired five-seed comparison.
- `combined_nbn_feasible_20261027/feasible_region_analysis.json`: exact parents, branches and distances.
- `combined_nbn_feasible_20261027/combined_nbn_feasible_3d.html`: updated viewer, with prepared feasible variants labelled separately.
