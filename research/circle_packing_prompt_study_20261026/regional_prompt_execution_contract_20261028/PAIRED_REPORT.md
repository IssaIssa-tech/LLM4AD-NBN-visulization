# Execution-contract prompt comparison

All fourteen new requests completed. Every request, response and terminal outcome is present in the downloaded platform history. Original outcomes remain unchanged. Analysis did not execute candidate code.

| Outcome | Previous prompt | Added checklist |
|---|---:|---:|
| valid | 1 | 1 |
| timeout | 3 | 10 |
| exception | 9 | 2 |
| invalid_geometry | 0 | 1 |
| rejected_static | 1 | 0 |

Previous valid score: 0.3267410733963663. New valid score: 0.0. Neither condition reached 2.6360. The zero-score packing passes the current geometry check because all radii are zero; it is a degenerate feasible output, not useful optimization progress.

| Selection | Original prompt profile | Valid | Timeout | Exception | Invalid |
|---|---|---:|---:|---:|---:|
| quality_only_top4 | contract_M2 | 0 | 3 | 1 | 0 |
| quality_only_top4 | contract_M2_structural_exploration | 0 | 3 | 0 | 1 |
| nbn_region_top4 | contract_M2 | 1 | 3 | 0 | 0 |
| nbn_region_top4 | contract_M2_structural_exploration | 0 | 3 | 1 | 0 |

Each cell contains four analytical slots; two requests are shared across selection strategies. Fourteen unique requests underlie sixteen slots. These are descriptive outcomes, not independent replicated evidence of a strategy ranking.

## Source inspection

- Seven previous missing-qmc exceptions and the previous top-level-example rejection do not recur. This does not isolate which checklist sentence caused the change.
- Ten timeouts retain nested iterative searches. Their outer literal loop limits span 3,000–40,000. Source structure is consistent with excessive work, but is not a measured runtime beyond the twenty-second cutoff.
- One exception indexes a 26-row array with the search iteration counter, eventually reaching index 26. Another combines incompatible three-coordinate and two-coordinate arrays.
- The sole valid program initializes zero radii and updates local x/y/radius variables without writing the improvements back to its returned circles array. Saved coordinates confirm all radii remain zero.
- All fourteen responses report normal stop rather than token-limit truncation. Fourteen distinct code hashes are not evidence of useful structural diversity.

## Research conclusion

The checklist did not improve useful feasible score in this pilot. Exceptions fell from nine to two while timeouts increased from three to ten. These counts cannot establish that NBN selection is ineffective: execution and optimization correctness dominate, there is one sample per parent/profile, and the archival parents are long-running textual references rather than comparable current-budget incumbents.

Do not change the registered budget or silently repair these candidates. Before another broad generation batch, audit the historical reference context and small-model ability to produce an executable, bounded program. A proposed next diagnostic should separately test a complete executable reference and a precise work-budget contract with a small fixed number of requests, then decide whether a larger paired selection study is warranted. Register that protocol before calls; any change of model or runtime must be explicit.

No new NBN placement, official-verifier equivalence, or final algorithm superiority is claimed. Retain the unsuccessful outputs and current twenty-second research condition in the experiment history.
