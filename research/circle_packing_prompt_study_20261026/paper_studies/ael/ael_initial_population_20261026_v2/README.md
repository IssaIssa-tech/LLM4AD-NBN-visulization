# AEL Circle Packing - initial population manifest

This artefact is a deterministic historical seed selection for the planned AEL adaptation. No LLM generation, candidate evaluation, or population evolution has occurred.

## Registered selection rule

- Historical records considered: 14,000
- Positive-score records considered: 7,854
- Quality pool: distinct-code positive-score records at or above the empirical 95% score quantile (2.630478704583)
- Forced seeds: global historical champion plus the top-scoring representative from every supported top-level NBN branch (at least 20 historical members and 5 positive-score members).
- Remaining seeds: greedy maximum-minimum CodeT5+ cosine distance from already selected seeds, with score then sample order as deterministic tie-breakers.
- Vectors were read directly from the saved private embedding cache; no embeddings were generated and no cache was modified.

## Selected seeds

| AEL rank | Historical sample | Score | Top-level NBN branch | Minimum cosine distance to earlier seeds | Code file |
|---:|---:|---:|---:|---:|---|
| 1 | 12738 | 2.635937208805 | 12737 | - | `seed_code/ael_seed_01_sample_12738.py` |
| 2 | 13794 | 2.635932166033 | 13793 | 0.00896306 | `seed_code/ael_seed_02_sample_13794.py` |
| 3 | 12472 | 2.635923867314 | 12471 | 0.00074363 | `seed_code/ael_seed_03_sample_12472.py` |
| 4 | 12992 | 2.635868764600 | 12991 | 0.00335382 | `seed_code/ael_seed_04_sample_12992.py` |
| 5 | 9708 | 2.635722650500 | 9707 | 0.00430461 | `seed_code/ael_seed_05_sample_09708.py` |
| 6 | 10339 | 2.635888608782 | 13793 | 0.02763793 | `seed_code/ael_seed_06_sample_10339.py` |
| 7 | 9473 | 2.630621980043 | 13793 | 0.02474885 | `seed_code/ael_seed_07_sample_09473.py` |
| 8 | 10950 | 2.630567181373 | 13793 | 0.01988014 | `seed_code/ael_seed_08_sample_10950.py` |
| 9 | 13645 | 2.633272254298 | 13793 | 0.01611594 | `seed_code/ael_seed_09_sample_13645.py` |
| 10 | 8090 | 2.630886291994 | 13793 | 0.01585098 | `seed_code/ael_seed_10_sample_08090.py` |

## Use boundary

These ten programs are initial archival references only. Their stored scores are historical provenance and are not current AEL-run results. Re-evaluate every selected seed under the frozen current evaluator before using it in parent selection or reporting any comparison.
