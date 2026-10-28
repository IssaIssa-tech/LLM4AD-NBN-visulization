# Preliminary registered comparison results

Fourteen unique requests completed. Sixteen analytical slots include shared responses; they are not sixteen independent generations.

Unique outcomes: {'rejected_static': 1, 'timeout': 3, 'exception': 9, 'valid': 1}. No result reached 2.6360.

| Parent strategy | Prompt | Slots | Valid | Timeout | Exception | Static rejection |
|---|---|---:|---:|---:|---:|---:|
| quality_only_top4 | contract_M2 | 4 | 1 | 1 | 1 | 1 |
| quality_only_top4 | contract_M2_structural_exploration | 4 | 0 | 1 | 3 | 0 |
| nbn_region_top4 | contract_M2 | 4 | 0 | 2 | 2 | 0 |
| nbn_region_top4 | contract_M2_structural_exploration | 4 | 0 | 0 | 4 | 0 |

## Failure inspection

Seven exceptions report missing `qmc`; the saved programs use it without importing it. Two report too many values to unpack. One static rejection contains top-level example execution, contrary to the prompt contract. Three programs exceeded the fixed twenty-second research execution budget. All model replies report `done_reason=stop`, rather than length truncation.

The single valid packing has sum of radii 0.3267410733963663. It is geometrically feasible under this evaluator but low quality. Fourteen different code hashes and fourteen AST fingerprints describe syntactic differences, not evidence of fourteen useful mechanisms or diverse high-quality solutions.

## Interpretation and next condition

This pilot does not support selecting a superior prompt or parent-selection strategy. One sample per parent/profile, overlapping parents, widespread execution failure, and a budget different from archival evaluation prevent strong ranking or parent-improvement claims. NBN groups are from a frozen HNSW code-space graph, not proven physical basins. The target is not achieved, and official-verifier equivalence remains unverified.

Preserve this condition unchanged. A proposed next condition should test an explicit self-contained-import/interface requirement and bounded-work instruction against the existing prompt while retaining the same parent pools and evaluator. Any repair policy requires separate registration, its own model-call accounting, and preservation of pre-repair failures. Do not silently fix and replace these results.

No embeddings or new NBN placements were calculated in this analysis. Failures have no invented finite scores. Do not add them as fitness-ranked discoveries to the old viewer.

Analysis reads saved artifacts only; no LLM requests or candidate reevaluations were performed.
