# New-instructions platform audit and first implementation slice

Primary server decision: retain hits_1; hits_9 is reachable but no data or jobs were migrated. The new study targets N=26, NBN-based selection of representative historical programs, comparison of parent-selection and prompt strategies using an open-source LLM, structural diversity and feasible scores at least 2.6360, and automatic platform history.

## Existing platform capabilities inspected

- `services/revision_service.py` already stores selected/reference/initial-population nodes, source revisions, prompt, model and method configuration in each revision.
- `runtime/runner_entry.py` hydrates parent records and dispatches prompt generation, seeded EoH or region search.
- `runtime/region_runner.py` already contains regional seed and direction selection; a new region selector should not be added without reconciling these existing mechanisms.
- `runtime/runner_modes.py` persists generated samples; revision events and artifacts already have APIs.
- Our external research folders and standalone NBN viewers are separate from platform revision storage. Their existence does not prove historical data are imported into the active platform database.

## Implemented locally in this slice

- Append-only, per-revision event files, written and fsynced before atomic publication; duplicate event IDs cannot overwrite records.
- Configuration snapshots at revision creation and runner start, including selected-node payloads/NBN references when supplied, source revision links and model/method settings. Changed snapshots record a previous-event link.
- Exact prompt events and corresponding raw response or failed-call events in the timeout-isolated LLM call path.
- Generated-sample events at the shared sample persistence function, including existing code, score, parent metadata and failures when those fields reach that function.
- Read endpoint `/api/revisions/<revision_id>/research-history` and page `/static/research-history.html?revision=REVISION_ID`, with JSON export.
- Structured credential keys are redacted; non-finite values are encoded explicitly instead of invalid browser JSON.

## Verified

Four unit/integration tests cover concurrent appends and duplicate-ID refusal; configuration changes, parent-node metadata, credential redaction and non-finite preservation; Flask history reads and missing-revision handling; mocked LLM success/failure correlation. Modified Python modules passed compilation. No paid or local-model calls are made by these tests.

## Remaining requirements / not claimed complete

- This code is not deployed to the running server/platform yet; a fresh process is needed to load hooks.
- Existing external experiments are not automatically backfilled; their original timestamps and provenance must be retained by any explicit import.
- Exact LLM call IDs are linked to responses/failures, but not yet propagated to evaluated sample IDs through all asynchronous profiler paths. Do not infer linkage from event order.
- Packing-coordinate capture is not yet added to the platform evaluator. Full verifier source/tolerances remain unverified; screenshots establish the mathematical task, not every verifier behavior.
- Parser failures and worker crashes outside the instrumented paths may still lack terminal sample events. Additional integration work is required before claiming complete attempt coverage.
- Strategy changes are captured as revised configurations, not a live edit UI. NBN graph-artifact identity must be frozen alongside selected node IDs for cross-version reproducibility.
- Main platform navigation has not yet been extended; the history page is directly accessible.
- Historical programs still require an active-database import/consistency audit. Existing seed reevaluations do not justify silently excluding complete NBN regions from the new study.
- No new multi-region experimental matrix or LLM search was launched. Histories and challenge-compatible evaluation should be completed before that experiment.

Raw records from prior studies remain preserved. The earlier objective correction remains valid historically; the new explicit target of 2.6360 now applies prospectively to this study.
