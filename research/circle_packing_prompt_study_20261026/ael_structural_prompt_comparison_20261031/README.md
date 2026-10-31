# AEL matched structural/import prompt comparison — completed 2026-10-31

This separately registered follow-up reused the twelve saved baseline outcomes and made **twelve new model calls** with the same six historical pairs, stage seeds, model/build/chat template and evaluator. The changed operator instructions jointly require substantive computational changes and complete imports. They are researcher-designed AEL-inspired adaptations, not verbatim paper prompts or a full population evolution.

| Measure | Saved baseline | Revised prompt pair |
|---|---:|---:|
| Model calls | 12 existing, not rerun | 12 new |
| Valid outputs | 8 | 1 |
| Exceptions | 4 | 9 |
| Invalid geometry | 0 | 2 |
| Best valid score | 2.5338065697852596 | 2.109107549240501 |
| Hits >=2.6360 | 0 | 0 |
| Exact normalized selected-parent body matches | 11/12 | 3/12 |

The normalization omits imports/docstrings and measures syntactic copying, not semantic novelty. The only valid new output retains a historical body and exactly repeats its matched baseline packing. The revised pair therefore changed more code without demonstrating a valid novel improvement. The original pair remains a provisional working delivery baseline within these cases; no general or statistical superiority is claimed.

Open `ael_structural_comparison_review.html` locally for the completed comparison, filters, parent/NBN provenance and links to exact prompts, responses and programs. GitHub source view does not execute HTML. Read `COMPARISON_RESULTS.md`, `MECHANISM_REVIEW.md`, `COMPARISON_SUMMARY.json` and `MECHANISM_DIAGNOSTICS.json` for measured results, independent saved-array checks and inspection of all twelve generated sources.

`manifest.json`, `registration.json`, `PROTOCOL.md`, `PROMPT_CHANGES.diff` and `MATCHING_AUDIT.json` preserve the exact design, source identities and paired request checks. `preparation_v1/` retains the initial prepared allocation guard. `PRE_REGISTRATION_AMENDMENT.json` records the pre-registration memory-headroom adjustment based on the prior service's buffer log. The bounded availability check is preserved in `readiness_wait.json` and `allocation_observations.jsonl`. At actual startup, the GPU had 24,253MiB free, the same as baseline startup, and 19,027MiB remained after loading; the original conservative guard would also have passed. Generator timings are not compared.

The preparation-only history has six events and zero model requests; its final export and verification are separate from the actual executed condition. The execution history has eighty events and twelve real requests, including six two-parent crossover links and six generated-parent mutation links. `LIVE_HISTORY_VERIFICATION.json` and `PREPARATION_HISTORY_VERIFICATION.json` verify equality with the deployed APIs. All failures, invalid returned coordinates, raw requests/responses, source, stdout/stderr and undefined failed fitness remain intact. No candidate was manually patched, replaced or executed again during reporting.

`GPU_RELEASE_VERIFICATION.json` confirms release of this condition's private model process. `BROWSER_VERIFICATION.json` and the preview record desktop/mobile and filter checks. Baseline source records and the 14,000-program archive are reused by path/hash, not uploaded again as another dataset. Browser profiles, caches and execution locks are excluded from Git.

The bundled prompt intervention, earlier rather than concurrently randomized baseline, small sample and changing mutation inputs limit causal interpretation. No new NBN placement or official challenge-verifier equivalence is asserted. This finite comparison is complete; no extra search is running, and the broader supervisor-directed discovery objective remains open.
