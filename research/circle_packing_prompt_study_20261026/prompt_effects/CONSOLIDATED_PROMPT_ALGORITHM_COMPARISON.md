# Circle Packing: prompt effects, algorithm test and NBN comparison

Date: 2026-10-27. Evidence: saved execution records, protocols, audit, and the versioned exact CodeT5+ graph. The supervisor's requested progression is prompt-effect analysis, selection of useful solutions/prompts, then algorithm design based on those findings.

## Completed comparison

| Condition | Recorded outcome | Supported interpretation |
|---|---|---|
| Exploratory final-contract M2 pilot | valid 2.600306976710351, reproduced twice | Highest recorded score among these new-code studies; exploratory, not pooled with repeated trials |
| Repeated baseline M1/M2/M3 | 15 timeouts | No usable output within the tested budget |
| Repeated contract M1 | 5 timeouts | No usable output within the tested budget |
| Repeated contract M2 | 5 valid at 2.579279552688004 | Reliable tested delivery; equivalent logic across two import-placement hashes |
| Repeated contract M3 | 4 timeouts, 1 invalid geometry | No valid result |
| M2-R | 4 invalid geometry, 1 exception | Repair prompt condition unsuccessful |
| M2-I | 5 exceptions | Sobol implementation delivery failed |
| Code-checked M2 | 5 initial exceptions; repairs: 3 exceptions, 2 static rejection | No full evaluation reached |
| Strict M2-I-P | 5 valid at 2.5902372123245248; 1 unique code | Reliable fixed-patch delivery; controlled improvement over selected M2 baseline |
| M2-I-P-D LLM delivery | 5 byte-exact rejections | Fitness unmeasured; three rejections are comment-only changes |
| Prepared five-seed Sobol algorithm test | 5 valid; mean 2.581170081681577; best 2.5963958373961282 | Seed sensitivity within one frozen algorithm family; no new LLM-generation claim |

The historical archived champion is 2.6359372088053568. It is a provenance reference, not a proven equal-runtime comparison: a separate audit found ten selected high-score historical programs timed out under the current 20-second local evaluator. Prior reports that say 'next' describe their original stage and must be read together with later execution results.

## New NBN evidence

`combined_nbn_m2ipd_20261027/` contains the new graph, viewer, and measured region analysis. It extends the saved 14,035-record graph with five prepared algorithm variants, giving 14,040 nodes and 14,039 edges. All prior nodes were retained, including historical missing/non-finite outcomes and the earlier controlled invalid/timeout trials. Other follow-up failures remain in their ledgers; this graph is a selected comparison cohort, not every experiment ever run.

The build used the existing exact backend and CodeT5+ cosine embeddings. Five added code embeddings were populated during an initial attempt that stopped at backend selection; the successful exact build reused the resulting 14,040 cached embeddings. The prior cache was copied to a separate run folder. No historical cache or graph was overwritten.

| Sobol seed | Score | Exact parent | Parent cosine distance |
|---|---:|---|---:|
| 20261130 | 2.556030886445475 | seed 20261131 | 0.0000106096 |
| 20261131 | 2.585691018316561 | seed 20261134 | 0.0000036955 |
| 20261132 | 2.581517030579852 | seed 20261133 | 0.0000041723 |
| 20261133 | 2.5862156356698685 | seed 20261134 | 0.0000022650 |
| 20261134 | 2.5963958373961282 | historical sample 13690 | 0.0424576402 |

Every added record lies under top-level historical branch sample 13794 (zero-based historical branch index 13793). Pairwise cosine distances between the five variants range from approximately 0.0000023407 to 0.0000162131, computed with explicit float64 renormalization; small numerical differences from backend float32 edge distances are expected. The exact pairwise matrix is saved in `m2ipd_region_analysis.json`.

A branch is operationally the first descendant below the global root. It is a code-space grouping, not proof of a dynamical basin or semantic mechanism. The layout is a cone-tree display with score height; visual gaps alone do not establish unexplored regions. The backend retains its existing score sanitization and tie policy. The full embedding coordinates and tree determine placement, not the displayed projection.

## Evidence-based design decision

Use the combined-contract M2 prompt as the supported executable generation baseline, and retain its strict Sobol patch as the reliable constrained-edit condition. Seed 20261134 is a useful observed setting for the Sobol family, but selecting its maximum after five evaluations is not an independent validation result.

The seed experiment did not address the remaining weakness: structural code-region diversity. All five variants stay in the same historical branch, and the average does not beat the prior fixed-seed Sobol reference. The earlier pilot is also still higher-scoring. Therefore a final superior algorithm has not been established.

The next justified design question is whether one explicitly specified structural mechanism can improve score or yield valid code in a different branch under the same contract. Before generating new candidates, freeze that mechanism, parent choice, prompt, local-model configuration, seeds, evaluator and acceptance criteria. Use the existing experimental records as baselines, retain all outcomes, and compare code mechanisms as well as hashes. This report does not launch or claim results for that future experiment.

## Reproducible artifacts

- `analysis/build_m2ipd_nbn.py`: graph build and measured branch/distance export.
- `analysis/export_m2ipd_viewer.py`: viewer/data export.
- `m2ipd_algorithm_evaluation_20261027/`: frozen manifest, candidate source, evaluator and measured scores.
- `combined_nbn_m2ipd_20261027/m2ipd_region_analysis.json`: parent identities, branch identities, pairwise distances and build stats.
- `RECONCILED_STATUS_AUDIT_20261027.md`: provenance corrections and original delivery diagnosis.
