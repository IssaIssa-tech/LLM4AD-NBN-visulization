# Evidence-based Circle Packing algorithm-design workflow: specification v1

Status: design specification and offline draft plan. No new LLM calls or algorithm-search run has been launched for this workflow.

## Objective and two algorithm levels

The task is to analyze prompt effects, choose useful prompts and solutions, and design an algorithm based on that evidence. This specification describes the higher-level workflow that generates and selects Circle Packing programs. Each generated `pack_circles` function is a lower-level packing algorithm. Testing packing-code edits alone does not implement the higher-level workflow.

The supervisor's message does not specify a particular adaptive selector, population size or ranking rule. The minimal workflow below is our proposed operational design. Its implementation must not be labelled a faithful full EoH reproduction: E1/E2 and a full evolutionary comparison were not evaluated in this study.

## Decisions and evidence

| Decision | Evidence | Status |
|---|---|---|
| Use combined-contract M2 as the first generation option | In the repeated comparison, 5/5 valid; tested M1/M3 conditions yielded none | Supported within tested setup; not universally best |
| Retain the fixed Sobol M2-I-P program as the initial reference | Strict patch delivered identical code five times; valid 2.5902372123245248; later parent checks reproduced this | Supported reference program |
| Use that reference as the parent for the first new batch | Clear executable provenance; change from the historical parent used in the earlier broad M2 comparison | Proposed parent choice, untested prompt-parent combination |
| Keep archived high-score solutions as references until comparable reevaluation | Ten selected archival programs timed out under the present 20-second evaluator | Supported eligibility restriction, not a claim archival programs are poor |
| Do not promote feasible initialization as generally superior | Ten held-out pairs: feasible 3 wins, 7 losses, lower mean | Supported selection decision |
| Keep strict patch as a separate constrained-edit mode | Exact delivery succeeded for one specified patch; later patch conditions failed | Supported for that patch only; not generic reliability |
| Analyze branch coverage after evaluation | Existing cohorts remain in one top-level historical branch | Supported analysis measure; branch selection benefits untested |
| Start with a fixed-parent, five-call batch | Matches scale of prior comparisons and isolates parent changes | Proposed budget/control choice |

## Input and parent eligibility

Maintain an immutable evidence archive containing all prompts, responses, code, evaluation outcomes and provenance, including invalid, timeout, missing, duplicate and non-finite records. Maintain a separate eligible-parent list. Eligibility requires the function contract, valid geometry, a score at least 1.0, and completion under the fixed current evaluator. Archived fitness alone is insufficient.

The first draft plan uses only the fixed M2-I-P reference as its parent. Earlier pilot, historical champion, other prepared variants and failed outputs remain in the evidence archive. A multi-parent or multi-branch policy is a later proposed extension; its benefit has not been measured. The initial parent should receive a current control evaluation when an actual run is registered and executed.

## Prompt selection

Default generation mode is a new, versioned combined-contract M2 template preserving the exact function interface, approved imports, bounded runtime, geometry checks and quality requirement. Request one substantive structural change. Supply the chosen parent source explicitly. Do not present a new template as byte-identical to the previously tested prompt.

The saved earlier prompt requested five CPU seconds and at most one proposal per circle, but its successful output used five proposals and was evaluated with a 20-second limit. Therefore observed success means evaluator validity, not verified compliance with every natural-language instruction. The proposed v1 template explicitly states the actual 20-second evaluator limit and does not invent a tested five-second guarantee.

For v1, choose M2 for all five calls; do not claim adaptive selection. Disable the unsuccessful tested M1/M3 profiles as automatic defaults, while retaining their outcomes. Strict patch mode is only eligible when an explicit patch, parent and guard are separately specified before generation. It is not interchangeable with structural exploration and is not scheduled in the initial draft batch.

## Execution and selection rule

1. Freeze the parent hash, prompt/template hash, model/endpoint/configuration, five sampling seeds, evaluator hash, budget and stopping rule before execution. Mark the draft as registered only after these are checked against the intended server environment.
2. Evaluate the unchanged reference once as the control. If it fails, stop and report the environment/eligibility issue without generating offspring.
3. For each registered seed, make one local-model request. Save request and complete reply metadata, raw response, timestamp and hashes.
4. Extract exactly one complete function-bearing program. Reject ambiguous or incomplete extraction; retain raw replies and extraction reasons.
5. Apply the existing static screen and isolated 20-second geometry evaluator at n=26. Record the quality threshold separately from geometry validity. No automatic repair in v1.
6. Retain every outcome. A valid quality-passing program enters the eligible archive. Flag raw-code duplicates and AST-equivalent code separately; retain individual trial records. Cache or reused evaluations, if introduced later, must be explicitly labelled.
7. Keep an incumbent reference; replace it only with a strictly higher valid score under the same evaluator. On equal fitness retain the incumbent. This is a proposed selection rule, not proof of general superiority. Valid lower-scoring candidates remain available for later analysis.
8. The initial batch keeps the same parent for all five calls, irrespective of interim results. Incumbent updates do not change prompts mid-batch. This is a controlled generation/selection batch, not a completed multi-generation evolutionary algorithm.
9. Stop after five requests, including failed calls. Do not resample failed seeds, tune after looking at outputs, or silently add calls. Report generation failures separately from evaluator failures.
10. After the batch, compute exact CodeT5+ NBN additions where code and comparison fitness provenance permit. Retain code-only failures separately when fitness is unmeasured; do not invent fitness to claim meaningful nearest-better relations. Measure distances and top-level branch coverage, with score-sanitization/tie policy disclosed if failed records are included for visualization.

## Pseudocode

```text
freeze(batch, parent, M2_template, evaluator, seeds)
control = evaluate(parent)
if not eligible(control): stop_with_record()
incumbent = parent
for seed in frozen_seeds:
    reply = local_llm(M2_template, fixed_parent, seed)
    candidate = extract_and_static_screen(reply)
    outcome = evaluate_or_record_failure(candidate)
    archive_all(reply, candidate, outcome)
    if eligible(outcome):
        retain_in_eligible_archive(candidate)
        if outcome.score > incumbent.score: incumbent = candidate
report_prompt_delivery_quality_diversity_and_region_coverage()
```

## Evaluation of the workflow

Primary deliverables: valid/quality-passing rate per request, best and distribution of valid scores, complete failure counts, number of raw and AST-unique programs, exact code distances and branch coverage, and LLM-call/runtime cost. Identical code evaluated repeatedly is delivery evidence, not independent algorithmic discovery. Region coverage is not inferred from cone-tree drawing gaps. Geometric packing diversity requires saved packing coordinates and a defined comparison, not code hashes alone.

The first run will test this new parent/template combination. A claim that the workflow is better than fixed M2 requires a separately registered equal-budget comparison on matched parent/evaluator/model settings. It is not a prerequisite that every design beat historical best. Final reporting must separate observed choices, proposed rules and evaluation results.

## Current implementation boundary

`analysis/plan_prompt_guided_search.py` produces a reviewable draft plan, frozen reference source and new M2 prompt. It checks source syntax and required artifacts, records provenance, and makes no network calls. It does not implement adaptive selection or launch a new search. The external runner and comparative validation remain future work after review of this concrete design.
