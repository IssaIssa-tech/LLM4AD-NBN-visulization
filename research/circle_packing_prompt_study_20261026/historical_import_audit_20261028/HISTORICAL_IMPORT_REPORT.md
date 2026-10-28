# Verified historical import — 2026-10-28

## Result

The isolated hits_1 platform database now contains 14,000 canonical historical programs with their original NBN node IDs. Every database code string, archived raw score and source-node correspondence was checked against the preserved graph after insertion. No existing individual IDs collided; the database had zero individuals before import. A SQLite backup was made before writes.

- Revision: `circle-history-verified-20261028`.
- Workspace: `bd1c9a6c-74c9-4e65-9ee7-6694ae27f668`.
- Graph artifact: `artifact:circle-history-verified-20261028:graph:full:fd1b32d0dfbdb9d0`.
- Imported graph: 14,000 nodes, 13,999 edges.
- Canonical source/code/node mappings verified: 14,000/14,000.
- Scores: 8,057 finite nonnegative archived scores, 310 negative sentinels, 5,633 graph values that are missing or non-finite. The graph alone cannot distinguish all missing values from non-finite values; source ZIP records remain preserved.
- Reevaluated programs: zero. No new LLM calls were made.

## Source versions and preservation

Two different local ZIP files were found. They are not interchangeable:

| Source | SHA-256 | Parsed records | Unique sample orders | Parse issue |
|---|---|---:|---:|---|
| Previously bundled ZIP (`EoH_settings&logs` source) | `8a205689e32601e43b427b8c9271d83d6412d19c5c8eb9f1df7d0ee86ee07cfe` | 14,094 | 14,069 | Truncated trailing fragment in samples_14001~14200.json |
| Complete local ZIP (`EoH_settings_logs` source) | `7c4275825c9b133fd04439b1c679c02cae6c5b4423ebe661a1a4869a3f01c93d` | 14,096 | 14,071 | None |

Each has 25 orders with multiple records. All 14,000 graph programs match at least one normalized source program in both ZIPs. The complete ZIP was selected for import provenance; both original byte streams were preserved. Normalization is documented in the audit script: parse as source first, otherwise decode literal newline/tab/quote escapes for comparison. Canonical imported code comes from the unchanged graph, not a rewritten ZIP program. Every source-match reference retains archive member, JSON-value index and item index.

The canonical cohort is defined by the saved graph's sample orders 1–14,000. Extra orders are supplemental records, not silently merged into that graph. Repeated source records are not asserted to be independent experiments. Full parsed records remain in server-side JSONL files, and original ZIPs preserve any unparseable trailing bytes. These measured counts apply to these specific ZIP versions; older chat references to other totals must not substitute for a versioned source audit.

## Frozen graph identity and limits

Original graph SHA-256: `c5a38d5dc6f4daeee3903476a3508f8cdd41ac0a5fbd10e394947cd9073802dc`.
Unwrapped platform graph-content SHA-256: `e589c4fbad72923d79e17280ddba2453e650da6eec7eca35668f0dc2d5ec36da`.
These differ because the original file wraps the graph with cache metadata, while the platform artifact stores the graph object alone. The original source file remains intact.

The imported snapshot's own metadata reports `hnsw_static`, backend `libnbn_portable`, layout `pca3`, 13,820 unique encodings and 180 duplicate samples. It must not be described as an exact nearest-better rebuild. Later exact cone-tree study graphs are separate versioned artifacts. Region selection must name the graph version and backend used.

New platform revisions now record the source graph artifact ID, content digest, input digest and metadata. Absolute readable graph files are hash-checked before identity capture; a content mismatch fails rather than silently changing provenance. Missing graph artifacts are explicitly recorded as missing.

## Platform verification and preservation

The revision, historical node-code lookup, research-history endpoint and graph-content endpoint each returned HTTP 200. The import's start/completion events and configuration snapshots are stored in the revision history. Only our isolated platform process was restarted to load the provenance hook. Shared data, existing research jobs, old graph versions and original archives were not removed or overwritten.

Nine local tests pass, including graph-file tampering detection. The audit and importer refuse to overwrite existing output directories or colliding imported IDs. The importer is not a general transactional import API: a failed partial import must be inspected, not blindly repeated. The pre-import backup and explicit revision records are retained for recovery.

## Next research step

Select representative historical programs from explicitly defined regions of a named frozen graph, retain high/medium/low and failed records in the archive, and verify the execution eligibility of proposed parents under a frozen research budget. Compare parent-selection and prompt strategies under equal local-LLM budgets. The challenge verifier remains unverified beyond the supplied screenshots, so no challenge-compatible score claim should be made yet. No regional generation experiment was launched during this import.
