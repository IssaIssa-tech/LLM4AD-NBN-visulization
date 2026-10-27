# AEL Circle Packing - initial population manifest

This artefact is a deterministic historical seed selection for the planned AEL adaptation. No LLM generation, candidate evaluation, or population evolution has occurred.

## Registered selection rule

- Historical records considered: 14,000
- Positive-score records considered: 7,854
- Quality pool: distinct-code positive-score records at or above the empirical 95% score quantile (2.630478704583)
- Seed 1: global historical champion.
- Seeds 2-10: greedy maximum-minimum CodeT5+ cosine distance from already selected seeds, with score then sample order as deterministic tie-breakers.
- Vectors were read directly from the saved private embedding cache; no embeddings were generated and no cache was modified.

## Selected seeds

| AEL rank | Historical sample | Score | Top-level NBN branch | Minimum cosine distance to earlier seeds | Code file |
|---:|---:|---:|---:|---:|---|
| 1 | 12738 | 2.635937208805 | 12737 | - | `seed_code/ael_seed_01_sample_12738.py` |
| 2 | 10339 | 2.635888608782 | 13793 | 0.03192591 | `seed_code/ael_seed_02_sample_10339.py` |
| 3 | 9473 | 2.630621980043 | 13793 | 0.02557984 | `seed_code/ael_seed_03_sample_09473.py` |
| 4 | 8090 | 2.630886291994 | 13793 | 0.02185881 | `seed_code/ael_seed_04_sample_08090.py` |
| 5 | 10950 | 2.630567181373 | 13793 | 0.02026593 | `seed_code/ael_seed_05_sample_10950.py` |
| 6 | 13645 | 2.633272254298 | 13793 | 0.01998955 | `seed_code/ael_seed_06_sample_13645.py` |
| 7 | 8752 | 2.633782369618 | 13793 | 0.01916755 | `seed_code/ael_seed_07_sample_08752.py` |
| 8 | 10667 | 2.635724584827 | 13793 | 0.01609119 | `seed_code/ael_seed_08_sample_10667.py` |
| 9 | 9675 | 2.634188676439 | 13793 | 0.01581097 | `seed_code/ael_seed_09_sample_09675.py` |
| 10 | 8876 | 2.635635991380 | 13793 | 0.01517322 | `seed_code/ael_seed_10_sample_08876.py` |

## Use boundary

These ten programs are initial archival references only. Their stored scores are historical provenance and are not current AEL-run results. Re-evaluate every selected seed under the frozen current evaluator before using it in parent selection or reporting any comparison.
