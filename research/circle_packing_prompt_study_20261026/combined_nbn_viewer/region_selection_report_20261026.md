# Circle Packing NBN: region-selection report

## Scope and provenance

This report is derived only from `combined_nbn_graph.json` and `trial_manifest.json` in this folder.
The graph has 14,030 nodes and 14,029 exact nearest-better edges using the CodeT5+ embedding cosine method.
A *region* below means a top-level branch of that saved nearest-better tree. It is an operational semantic-NBN grouping, not proof of a physical or causal fitness basin.

## Historical data observed

- Historical nodes: 14,000
- Numeric finite historical scores: 8,367
- Positive-score historical nodes: 7,854
- Best historical score: 2.635937208805 (sample 12738)
- Prompt outcomes retained: valid 5, invalid geometry 1, timeout 24

## Candidate historical anchor regions for the next controlled prompt batch

Selection rule: at least 20 historical nodes and at least 5 positive-score nodes; then rank by the best observed score in each distinct top-level NBN branch. This is a reproducible prioritization rule, not evidence that any selected region will improve the best score.

| Rank | Branch index | Historical nodes | Positive-score nodes | Best observed score | Anchor sample | Anchor ID |
|---:|---:|---:|---:|---:|---:|---|
| 1 | 13793 | 10415 | 5933 | 2.635932166033 | 13794 | `c-20261017_165510_f7091449-s13794` |
| 2 | 12471 | 293 | 237 | 2.635923867314 | 12472 | `c-20261017_165510_f7091449-s12472` |
| 3 | 12991 | 1265 | 601 | 2.635868764600 | 12992 | `c-20261017_165510_f7091449-s12992` |
| 4 | 9707 | 2018 | 1075 | 2.635722650500 | 9708 | `c-20261017_165510_f7091449-s9708` |

The same anchors are available in `region_anchor_candidates_20261026.csv` for use in a controlled prompt protocol.

## Observed placement of valid prompt trials

These are the five actually evaluated valid trials. Parent links are calculated by the combined NBN; they are not manually chosen and do not establish a performance improvement.

| Trial | Arm | Seed | Trial score | NBN parent sample | Parent score | Parent top-level branch |
|---|---|---:|---:|---:|---:|---:|
| `prompt-contract-20261026-m2_structural` | m2_structural | 20261026 | 2.579279552688 | 5770 | 2.624120521194 | 13793 |
| `prompt-contract-20261027-m2_structural` | m2_structural | 20261027 | 2.579279552688 | 5770 | 2.624120521194 | 13793 |
| `prompt-contract-20261028-m2_structural` | m2_structural | 20261028 | 2.579279552688 | 5770 | 2.624120521194 | 13793 |
| `prompt-contract-20261029-m2_structural` | m2_structural | 20261029 | 2.579279552688 | 5770 | 2.624120521194 | 13793 |
| `prompt-contract-20261030-m2_structural` | m2_structural | 20261030 | 2.579279552688 | 12076 | 2.626032665882 | 13793 |

## Decision for the next experiment

Use the saved anchor CSV to choose reference algorithms from several distinct branches. For each branch, run a pre-specified number of prompt trials with the same evaluator, time limit, local LLM model, and recorded seed. Retain valid, invalid-geometry, timeout, missing, and non-finite outcomes. Compare best score, valid rate, and branch coverage against this baseline; do not claim improvement until the evaluations are complete.

## Limitations

- CodeT5+ embedding distance measures code semantics, not direct geometric-solution distance.
- Cone-tree coordinates are only a display layout; the report uses tree parentage and recorded scores instead.
- The 30 prompt candidates are too few to support a conclusion about prompt effectiveness.
