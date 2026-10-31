# AEL operator pilot: measured outcomes

Completed 12 model calls across six pre-registered chains. 8 valid outputs; best valid score 2.533807; 0 outputs reached 2.6360. No retries, manual candidate patches, or repeated evaluations were used.

| Selection | Operator | Calls | Valid | Best valid score | Target hits |
|---|---|---:|---:|---:|---:|
| uniform | cross | 3 | 2 | 2.533807 | 0 |
| uniform | mut | 3 | 3 | 2.533807 | 0 |
| nbn_stratified | cross | 3 | 1 | 1.860415 | 0 |
| nbn_stratified | mut | 3 | 2 | 2.109108 | 0 |

| Call | Outcome | Score | Δ best observed parent |
|---|---|---:|---:|
| uniform-1-cross | valid | 1.972145 | 0.000000 |
| uniform-1-mut | valid | 1.972145 | 0.000000 |
| uniform-2-cross | valid | 2.533807 | 0.000000 |
| uniform-2-mut | valid | 2.533807 | 0.000000 |
| uniform-3-cross | exception | — | — |
| uniform-3-mut | valid | 2.139297 | -0.201870 |
| nbn_stratified-1-cross | valid | 1.860415 | -0.059604 |
| nbn_stratified-1-mut | valid | 1.860415 | -0.059604 |
| nbn_stratified-2-cross | exception | — | — |
| nbn_stratified-2-mut | valid | 2.109108 | 0.000000 |
| nbn_stratified-3-cross | exception | — | — |
| nbn_stratified-3-mut | exception | — | — |

Scores and geometry were independently checked from saved returned arrays. Failed attempts retain undefined fitness. Historical parent scores are single observations under the same evaluation environment; archive scores are not substituted as current fitness.

There are 9 distinct stripped sources, 9 distinct ASTs, and 5 exact coordinate-set fingerprints among valid outputs. These counts measure syntax and saved packings, not independent algorithm mechanisms or physical basins. `VERIFIED_SUMMARY.json` also reports comparisons to parent function ASTs with import/docstring nodes omitted; this normalization is only a syntactic diagnostic, not a proof of semantic equivalence.

Source inspection found that all six crossover bodies match one selected historical parent under that normalization. Eleven of twelve total outputs match a historical body; the remaining modified body fails before optimization. All four exceptions are missing-`qmc` NameErrors. Three mutations are exact source duplicates of crossover; two add the missing import without changing the computational body. None of the eight valid outputs improves on its better observed parent. See [MECHANISM_REVIEW.md](MECHANISM_REVIEW.md) for the source-based assessment and interpretation boundaries.

The two selection policies use different historical programs and parent quality. Three seeds per policy support descriptive results only. This pilot uses one common AEL crossover/mutation prompt pair, not a matched comparison with EoH or other papers. No new NBN embedding or placement is claimed. The bounded operator test is complete; the supervisor's broader research question and a full AEL population study are not declared complete.

All parent IDs/NBN nodes, full prompts/responses, generated code, both parent links for crossover, generated-parent lineage for mutation, coordinates, errors, runtime identities and configuration are saved in this folder and the platform export. The fixed protocol and source scripts remain unchanged.
