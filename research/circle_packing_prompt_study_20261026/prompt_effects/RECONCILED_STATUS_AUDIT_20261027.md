# Reconciled research status — 2026-10-27

This audit reads the local experiment reports and protocols, evaluator and M2-I-P-D preparation/runner source, execution JSON records, and downloaded M2-I-P-D raw candidates. It does not represent a rerun of any experiment or independent validation of every historical score or NBN edge.

## Completed work

- Exploratory prompt pilot: final-contract M2 achieved 2.600306976710351 and was reproduced twice. This is a separate exploratory observation, not part of the later repeated comparison.
- Controlled prompt comparison: 30 candidates, two profiles × three arms × five sampling seeds. Contract M2 produced five valid evaluations at 2.579279552688004. Its two code hashes differ in import placement; they do not establish two distinct algorithm designs. Other arms produced 24 timeouts and one invalid geometry outcome.
- M2-R: five evaluations, four invalid geometry and one exception.
- M2-I: five exceptions.
- Code-checked M2: five initial exceptions; repairs produced three exceptions and two static rejections. None reached full evaluation.
- M2-I-P: five exact outputs, five valid full evaluations at 2.5902372123245248, one unique candidate. This improves the selected repeated M2 baseline, but not the earlier pilot or the historical archived best (2.6359372088053568).
- Saved combined NBN report: 14,035 records and 14,034 edges, comprising 14,000 historical records, 30 controlled prompt trials, and five M2-I-P trials. This is a selected visualization cohort, not the complete ledger of every follow-up experiment.

## M2-I-P-D: completed generation, no quality evaluation

The downloaded server snapshot is preserved under `m2ipd_execution_20261027/server_snapshot/`, including prompts, responses, candidates, manifest, ledger, runner, evaluator and results. The server ledger records completion of the fifth trial at 2026-10-27 19:26:02 CST.

All five failed the registered byte-exact patch guard. No precheck or full fitness evaluation was performed. Geometric validity and fitness are therefore **unmeasured**, rather than established as zero valid packings.

- Seeds 20261130 and 20261131: extracted candidates contain only the four-line initialization snippet, omitting the function and remaining program. The extractor selects the first fenced code block; raw responses must be consulted before attributing omission solely to generation.
- Seeds 20261132–20261134: full candidates differ from expected source only in the initialization comment: `Scrambled Sobol initialization` became `Scrambled Sobol sequence initialization`. Executable source otherwise matches in the inspected text diff. They still fail the original byte-exact rule.

The five hashes are different, partly because the requested seed literals differ. This is not evidence of five structurally different algorithms. Seed diversity, packing-output diversity and code-mechanism diversity require separate measurements.

The manifest uses the same integer for LLM sampling seed and Sobol seed. Consequently the request conditions vary in both respects, although the intended algorithm change is Sobol initialization alone. The inherited parent docstring also requests all seeds equal 2025 while the new instruction specifies a different Sobol seed. This ambiguity should be documented before a future condition is designed.

The runner saves response text but omits full Ollama response metadata, including completion/truncation fields. The raw text remains available; metadata cannot be reconstructed from the ledger.

## Separate AEL work already present

`output/ael_paper_study_20261026/` already contains paper notes, a Circle Packing adaptation protocol, historical initial-population manifests, a ten-seed re-evaluation audit (all timeout at 20 seconds), and a thirty-program static runtime shortlist. The shortlist README explicitly says runtime eligibility remains unverified. These preparation artifacts are not an executed AEL evolutionary experiment.

## Corrections to earlier chat summaries

- “M2-I-P is the best verified result” was too broad: the earlier pilot scored higher. M2-I-P improves the chosen repeated M2 baseline.
- “M2-I-P-D has zero valid solutions” should read “zero candidates admitted to evaluation; validity unmeasured.”
- Earlier server checks interpolated PowerShell `$p` inside remote shell text incorrectly. Their `RUNNING` output did not establish a live process. Direct directory inspection and the downloaded completed results establish the current status.
- Historical best scores are archived references. The separate historical-seed timeout audit shows that equal evaluator/runtime comparability cannot be assumed.

## Remaining work

Preserve and report this completed negative patch-compliance result. Before another experiment, resolve whether the next objective is byte-exact LLM delivery, algorithm evaluation across Sobol seeds, or structural algorithm diversity. Changing seeds alone does not demonstrate new code mechanisms or new NBN regions. Any exploratory evaluation of comment-only variants must be separately labelled and must retain the original rejected outcomes. No new trial, revised eligibility rule, score or NBN placement was created by this audit.
