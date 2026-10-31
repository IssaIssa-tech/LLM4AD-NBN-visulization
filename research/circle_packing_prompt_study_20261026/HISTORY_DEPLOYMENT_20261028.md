# Platform research-history integration and isolated deployment

**Historical deployment note (2026-10-28).** The feature was subsequently completed and verified on 2026-10-31. Consult [the current readiness report](history_tracking_readiness_20261031/HISTORY_TRACKING_READINESS.md) for the structured review interface, 14 passing tests, full runner/evaluator acceptance check, actual Celery in-memory worker test, browser/export checks, and current limitations. The statements below describe the earlier deployment stage.

Primary server: hits_1. Private installation:
`/mnt/data/dyy/llm4ad_nbn_research_20261013/platform_history_20261028/`.
HTTP listener: server loopback `127.0.0.1:5015`; original jobs and installations were not stopped or replaced.

## Implemented

- Exact prompt/response call IDs now travel as response metadata in direct prompt-generation runs; saved samples include call ID and selected node IDs.
- The existing evaluation callable is wrapped to capture its actual returned packing once, before original geometry checking. Initial candidate execution is not repeated for logging. Raw coordinates, shape, finiteness and evaluated-source hash are recorded even for invalid/non-finite packings. Exceptions and no-score outcomes remain explicit; no unavailable coordinates are fabricated.
- A separate evaluation ID links evaluation start, packing output and completion. Existing evaluator verdicts are retained; scores reaching 2.6360 are labelled against the existing evaluator, not asserted to match the unseen official verifier.
- Seeded-EoH and regional executor adapters transfer the sampling-thread call ID explicitly to asynchronous jobs. Their profiler sample records include that ID. Seed records have no originating LLM call ID.
- Celery tasks transport the history context explicitly rather than depending on worker environment inheritance. That code path is implemented but has not been exercised against a live broker in this deployment.
- History page and JSON export are available at `/static/research-history.html?revision=REVISION_ID` and `/api/revisions/REVISION_ID/research-history`. A Research History link was added to the platform header.

## Verification

Eight local tests passed: append concurrency, immutability, configuration changes, redaction, non-finite preservation, HTTP access, request/failure linkage, packing capture, serialization and explicit asynchronous context transfer. (Some tests combine multiple assertions.)

The server synthetic smoke test used an actual isolated Circle Packing evaluator and a mocked LLM response. It produced seven linked events, one 26-circle output, and HTTP 200 responses for the history endpoint and page. Its grid score 2.123333333333333 is synthetic diagnostic data, not a research candidate or benchmark result. Verification revision: `history-smoke-d19ba9e4a3c1`. Model calls: zero. Test environment: Python 3.10.20, NumPy 1.26.4. A previous successful synthetic revision is retained separately.

The private deployment uses a snapshot of our platform/framework source and a private venv containing Celery/Redis client dependencies. Existing research dependencies are read from `/home/dyy/llm4ad_env/`; no shared packages were modified. Initial deployment attempts exposed NumPy/Pandas and eager-import incompatibilities; these were resolved through dependency ordering and the private framework snapshot. The full platform generation path has not yet been tested with a real LLM or live Celery broker after deployment. It must not be described as a completed regional experiment.

## Access and remaining work

The server listener was verified with HTTP 200. Automatic approval review blocked launching a hidden local SSH forwarding process; no tunnel was created by that attempt. From a user terminal, access can be forwarded with:

```powershell
ssh -N -o ExitOnForwardFailure=yes -i "$env:USERPROFILE\.ssh\codex_hits1_dyy_ed25519" -p 8000 -L 127.0.0.1:5015:127.0.0.1:5015 dyy@10.249.47.6
```

Then open `http://127.0.0.1:5015/static/research-history.html?revision=history-smoke-d19ba9e4a3c1`.

The isolated database is intentionally new. Historical-data import/consistency auditing and immutable source-graph identity snapshots remain to be completed before a multi-region experiment. Existing external-run folders are not silently backfilled. Challenge verifier source/tolerance equivalence is still unverified. The new deployment dependency versions must be frozen for the next study rather than pooling old scores across environments.
