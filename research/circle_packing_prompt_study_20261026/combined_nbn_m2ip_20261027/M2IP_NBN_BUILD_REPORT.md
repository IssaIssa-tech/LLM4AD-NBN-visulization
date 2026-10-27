# Exact combined NBN update with M2-I-P trials

## Inputs

- Prior exact combined NBN: 14,030 nodes (14,000 historical + 30 earlier prompt trials).
- Added records: five valid M2-I-P strict Sobol-patch trials.
- Distance metric: CodeT5+ embedding cosine.
- NBN rule: exact nearest-better neighbor.

## Build result

| Measure | Value |
|---|---:|
| Nodes | 14,035 |
| Edges | 14,034 |
| Cached embeddings reused | 14,030 |
| New embeddings generated | 5 |
| All prompt trials | 35 |
| Valid prompt trials | 10 |
| Invalid-geometry prompt trials | 1 |
| Timeout prompt trials | 24 |

The five M2-I-P records are retained individually. They have identical code and
score by design, so their shared placement/branch is expected; it is not
evidence of five diverse discoveries.

## Files

- `combined_nbn_m2ip_graph.json`: complete exact graph.
- `combined_nbn_3d_data.json`: compact viewer data.
- `combined_nbn_m2ip_3d.html`: interactive 3D viewer.
- `m2ip_trial_manifest.json`: five added trial records.
