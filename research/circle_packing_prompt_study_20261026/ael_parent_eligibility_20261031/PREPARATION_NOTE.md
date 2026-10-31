# Preparation and source-identity reconciliation

The original fixed 30-program manifest was saved before registration/execution. Its prepared status is retained unchanged; `registration.json`, `launch.json` and `results.json` separately record the later stages.

A first pre-registration check compared the archived HTTP-export byte hash with the live inner-graph artifact byte hash and stopped on an assertion. No platform revision had been registered and no candidate was executed at that point. The export wraps the graph while the imported artifact stores the inner object, so those two digests have different roles.

The graph was then reconciled read-only: the live input digest equals the archived export hash, and a canonical signature covering all 14,000 program IDs, source hashes, NBN node IDs and nearest-better parent indices matched independently on both sides. Both file identities and the matching signature are preserved in `source_graph_expectation.json`, `source_graph_reconciliation.json` and the frozen registration. The guard was corrected before registration to check those explicit identities. Candidate source, evaluator, tolerance, execution budget and selection order were unchanged.

The earlier exact-graph branch tags in the static shortlist were not copied into the current HNSW graph. Current branch membership was calculated from the frozen graph after matching historical program IDs and source hashes; the original branch index remains a separate metadata field.

The prior-outcome audit inspected 261 result/ledger files in the local output and tracked research bundle. No matching completed outcome was found for the thirty selected code sources under that audit's stated scope. Every candidate in this batch was executed at most once. No LLM call, repair, replacement or source-code edit was used to obtain an eligible result.
