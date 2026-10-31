# History tracking readiness — 2026-10-31

**Complete for the current Circle Packing platform workflow.** This is a feature-verification result, separate from the scientific quality of any generated packing algorithm. No new research LLM calls were made for this verification.

## Supervisor requirements

| Required history | Implemented and verified behavior |
|---|---|
| Selected historical programs and corresponding NBN nodes | Run configuration, hydrated original source snapshots and source hashes, selected node IDs, NBN IDs, and recorded source-graph identity. Call-specific references are displayed where an explicit link exists. |
| Prompts used or designed | Exact prompts/messages and model requests are preserved with call IDs; raw responses remain available. |
| New programs and evaluation scores | Generated and evaluated source, evaluation IDs, scores, elapsed evaluation time, and actual returned circle coordinates where available. The evaluator runs once; logging does not regenerate a packing. |
| Subsequent prompt or strategy modifications | Configuration snapshots and linked change records preserve earlier values alongside the revised configuration. Changes are captured when an instrumented run uses the changed configuration. |
| Successful and unsuccessful attempts | Valid scores, invalid geometry/nonfinite scores, parsing failures, evaluation exceptions, generation timeouts, and missing outcomes remain explicit. No absent score or call association is invented. |

The Research History header link opens a dedicated review page with experiment selection, searchable attempts, outcome filters, selected programs, changes/configuration, raw events, and complete JSON export. History files are append-only, uniquely identified, and fsynced before publication; duplicate event IDs cannot overwrite an existing record. Credential fields are redacted.

## Verification evidence

- **14 focused unit tests passed** on the private hits_1 deployment. See `history_feature_final_checks.log`.
- The actual direct-generation runner and actual N=26 evaluator were exercised using four synthetic replies: valid grid, invalid packing, evaluator exception, and unparsable text. A separate simulated generation timeout was preserved.
- An actual Celery solo worker received JSON-serialized tasks through an in-memory broker and evaluated valid and invalid programs. This verifies task-context transport and preservation of nonfinite scores before result normalization. An external Redis deployment was not used or tested.
- The asynchronous executor adapter used by EoH/regional execution also evaluated a synthetic program and preserved its originating call association.
- The combined acceptance record contains **8 calls, 43 events, 3 scored outputs and 5 unsuccessful attempts**, two selected historical sources with NBN IDs, and original/revised configurations. `verificationOnly=true`; its scores are diagnostic, not research results.
- Live HTTP API and updated page responded successfully after restarting only the private history application. The existing real GPU study projects **14 unique attempts, 73 preserved events, 7 references, 1 scored output and 13 unsuccessful attempts**.
- Microsoft Edge browser checks passed: status filters, call search, references, graph identity, prompt/configuration history, exact prompt text, complete JSON export, text-safe rendering, desktop/mobile layout and verification labels. The exported raw events exactly matched the input snapshot. See `browser_verification.json`.

## Review locally

- `research_history_review.html`: portable, read-only snapshot of the actual completed 14-attempt study. It includes its original raw events and supports JSON export.
- `tracking_feature_demo.html`: portable demonstration of the eight labelled verification calls, including source snapshots and configuration changes. **Excluded from research results.**
- `history_review_desktop.png`, `tracking_feature_desktop.png`, `tracking_feature_mobile.png`: browser captures.
- `acceptance_result.json`, `acceptance_snapshot.json`, `deployment_verification.json`, `gpu_study_snapshot.json`: machine-readable evidence.

The portable HTML files open directly from disk. They are saved snapshots, not live connections to the university server. The live feature is `/static/research-history.html` on the private platform listening on server loopback port 5015. Local browser access to that listener still requires an independently configured connection; no new SSH tunnel was created here.

## Preservation and limits

Original research runs, scores, and event files were not rewritten. Older runs without an original source snapshot or originating call ID retain that gap explicitly; this feature does not manufacture retrospective provenance. Exact request text remains available where originally recorded. Historical-data coverage is shown by revision, not claimed to include every older external script.

This verification establishes the implemented tracking/review/export workflow. It does not establish that NBN guidance improves solution quality, that any algorithm reaches 2.6360, or that the local evaluator is identical to the challenge's official verifier. Full EoH/regional searches were not rerun; their shared asynchronous adapter was exercised independently. Existing shared server jobs, packages, and other users' files were left intact.
