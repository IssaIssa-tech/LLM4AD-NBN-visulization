# Research scope and reconciled status

## Intended objective

Analyze the effects of different prompts, identify useful solutions and prompts,
then design an algorithm based on those findings. The supervisor's message did
not require a superior final Circle Packing score or a new NBN branch as a
condition of completing the analysis. Those are possible measured outcomes,
not guaranteed deliverables.

The recent packing-code ablations investigated narrower mechanisms after the
prompt study. Their results remain useful, including failures. They should not
be presented as completing a higher-level algorithm that selects prompts and
parent solutions. A prompt/parent selection workflow is our proposed way of
operationalizing the instruction; the message alone does not specify its rules.

## What is supported by completed records

| Evidence group | Recorded finding | Permitted use |
|---|---|---|
| Controlled prompt effects | Contract-M2: 5/5 valid at 2.579279552688004; other tested arms: 24 timeouts and one invalid geometry | Select a supported generation baseline within tested conditions |
| Strict M2-I-P delivery | 5/5 accepted outputs, identical code, valid score 2.5902372123245248 | Constrained-edit delivery evidence and one algorithm comparison |
| Other prompt follow-ups | M2-R, M2-I, code-checked M2, M2-I-P-D and acceptance-patch failures retained | Understand failure categories; do not silently discard or pool conditions |
| Prepared-code supporting tests | Seed sensitivity, acceptance diagnosis, feasible-initialization ablations | Analyze specified packing mechanisms; not evidence of successful LLM generation |
| Held-out initialization validation | Both methods 10/10 valid; feasible wins 3/10, lower mean (2.588565 vs 2.599977) | Withdraw general-improvement interpretation of exploratory feasible-initialization gains |
| Exact NBN cohort analyses | Explored variants remain under the same top-level historical branch | Describe observed code-space coverage; no new-region claim |

The earlier pilot score 2.600306976710351 is a separate exploratory result.
The archived historical best 2.6359372088053568 is a provenance reference whose
equal-runtime/environment comparability is unresolved. Neither should be
silently pooled with controlled prompt statistics. Validity, fitness, code
hash diversity, structural diversity and NBN placement are different measures.

## Current deliverable status

- Prompt comparisons and failure records: completed for the registered conditions.
- Supporting packing-code tests and ten-seed validation: completed and preserved.
- NBN viewers: versioned exploratory cohorts, with provenance in their folders.
- Evidence-based choice of useful prompt conditions: baseline evidence available;
  conclusions are limited to the model, parents, evaluator and budgets tested.
- A formal higher-level algorithm that chooses parent solutions and prompts:
  not yet specified, implemented or validated by these studies.

Existing results do not establish an optimal parent-selection policy or prove
that selecting parents by NBN branch will improve generation. Such rules would
be proposed design decisions requiring explicit evaluation. The reference
packing heuristic and a prompt-guided algorithm-design workflow must be named
separately to prevent confusion.

## Appropriate next work

Consolidate the prompt evidence into a design specification: input archive,
eligible parent solutions, prompt options, selection rule, fixed local-model
settings, evaluator, treatment of invalid/timeout/duplicate outputs, retained
population/archive, generation budget, stopping rule and NBN analysis. Label
each decision as observed evidence, implementation requirement or untested
proposal. Do not assume a rank weighting, novelty threshold, adaptation rule
or population size was experimentally established. No new experiment is
authorized or claimed by this documentation correction itself.

## Preservation and interpretation policy

Raw records, negative results and earlier graph versions are retained. Earlier
reports with 'next' or 'selected' describe their original stage; consult the
held-out report and this status note for the current interpretation. The
14,045-node viewer excludes twenty held-out records and other follow-up
ledgers, so it is not an all-results graph or a final-algorithm validation plot.
Prepared feasible variants are researcher-specified programs, not additional
prompt-generated discoveries.

This correction changes scope and interpretation, not raw outcomes or scores.
