# AEL operator pilot — completed 2026-10-31

Six pre-registered crossover→mutation chains produced twelve real local-model responses: **eight valid outputs and four exceptions**. Best score: **2.5338065697852596**; target **2.6360** was not reached. No valid output improved its better measured parent.

Read `RESULTS.md` and `MECHANISM_REVIEW.md`, or open `ael_operator_pilot_review.html` locally. The self-contained review provides policy/outcome filters, parent IDs, NBN node IDs and mutation lineage, with links to exact requests, responses and candidate code. GitHub's source view does not execute the HTML.

All six crossover computational bodies match one selected historical parent under a recorded AST comparison excluding imports/docstrings. Five mutations retain those bodies; the sixth adds an overlap adjustment but fails before optimization. Four failures are missing-`qmc` NameErrors; none is output-token truncation. Raw failures remain intact. See the mechanism review for distinctions between source, AST, body and packing fingerprints.

This is a small AEL adaptation: two parent-selection policies, three seeds each, one common AEL crossover/mutation prompt pair, local Qwen2.5-Coder 7B Q4_K_M, and the unchanged twenty-second N=26 hits1 research evaluator with numerical threads capped at one. Mutation uses actual crossover source without evaluation feedback. It is not the paper's full population evolution, a matched cross-paper comparison, or proof that either selection policy is superior.

`manifest.json` and `registration.json` freeze design, sources, graph identity, runtime and script hashes before generation. Each call folder retains exact prompt/request, raw response, extracted program, static screen, isolated evaluation, coordinates when returned, stdout/stderr and outcome. `platform_history.json` contains eighty-four events; `LIVE_HISTORY_VERIFICATION.json` confirms equality with the deployed API, six two-parent crossover links and six generated-parent mutation links.

`VERIFIED_SUMMARY.json` checks saved coordinates/scores without rerunning programs. `BROWSER_VERIFICATION.json` and the preview document desktop/mobile checks. Fifteen focused history tests passed; `HISTORY_TEST_VERIFICATION.json` records the command and observed result. `GPU_RELEASE_VERIFICATION.json` confirms release of this pilot's private model process. Other shared-server work was not stopped or modified.

No new NBN placement is computed or claimed. Historical sources and the 14,000-record graph are reused by existing source path/hash. Browser profiles, transport ZIPs and execution locks are excluded from Git. Frozen evidence bytes are preserved by `.gitattributes`.

The next proposal is a separately registered matched prompt comparison addressing parent-code copying and complete imports, using these frozen parent pairs/model/evaluator. It has **not** been executed. The pilot stops here regardless of target attainment; the broader supervisor-directed investigation remains open.
