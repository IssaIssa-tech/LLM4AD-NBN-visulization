# Historical-program alternatives: existing evidence only

Source graph: `c5a38d5dc6f4daeee3903476a3508f8cdd41ac0a5fbd10e394947cd9073802dc`; backend `hnsw_static`. NBN branches are operational code-space groups.

The following rows reuse the 2026-10-28 reference checks. No program was executed again. Scores and timeouts remain separate from archived fitness.

| Historical sample | Branch index | Role | Existing diagnostic outcome | Existing diagnostic score | In latest 14-call parent pool? |
|---|---:|---|---|---:|---|
| 13794 | 13793 | high_score | timeout | unmeasured | yes |
| 2908 | 13793 | median_score | valid | 2.123754173526148 | no |
| 7476 | 13793 | lower_positive_score | timeout | unmeasured | no |
| 10493 | 10492 | high_score | timeout | unmeasured | yes |
| 12130 | 10492 | median_score | timeout | unmeasured | no |
| 9320 | 10492 | lower_positive_score | timeout | unmeasured | no |
| 11415 | 11414 | high_score | timeout | unmeasured | yes |
| 13158 | 11414 | median_score | valid | 1.8546857840094024 | no |
| 7713 | 11414 | lower_positive_score | valid | 0.6610565632673218 | no |
| 10486 | 10485 | high_score | timeout | unmeasured | yes |
| 6534 | 10485 | median_score | timeout | unmeasured | no |
| 13402 | 10485 | lower_positive_score | timeout | unmeasured | no |
| 12738 | 12737 | champion_control | timeout | unmeasured | yes |

## Additional options to examine

The existing valid references absent from the latest comparison are samples **2908, 13158, and 7713**. This is a reading-stage shortlist, not a registered parent-selection policy or an executed generation experiment.

- **2908**: unscrambled Sobol initialization, annealing-style single-circle moves, scheduled boundary padding and radius scaling. Source explicitly uses a 1,000-round outer loop.
- **13158**: jittered grid initialization, 500 rounds of repulsive position adjustment, then 100 rounds of greedy radius expansion.
- **7713**: unscrambled Halton initialization, scheduled random relocation and boundary/overlap force calculations over 5,000 rounds. Its diagnostic score was low despite geometric validity.

These mechanism descriptions were checked against the saved source. They identify differences to inspect, not proof of meaningful structural diversity in successful generated descendants. The three records span **two** NBN branches, not three. The other two selected branches retain their timeout outcomes and are not silently removed.

Full historical/NBN IDs, source hashes, source paths, recorded outcomes and static call inventories are in `reference_audit.json`. The existing source files are referenced rather than copied again.
