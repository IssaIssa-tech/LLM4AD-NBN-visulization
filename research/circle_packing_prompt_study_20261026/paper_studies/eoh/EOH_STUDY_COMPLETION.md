# EoH paper study - completion record

**Paper:** Fei Liu et al., *Evolution of Heuristics: Towards Efficient Automatic Algorithm Design Using Large Language Model* (ICML 2024).

**Study closure date:** 2026-10-26

## 1. What was learned from the paper

EoH is an automatic heuristic-design framework.  Its population members are
heuristic programs, rather than direct problem solutions.  Each member has a
natural-language heuristic description (a *thought*), executable code, and an
evaluator-derived fitness value.  At each generation EoH uses LLM prompts to
produce new thought-and-code pairs, evaluates feasible programs, and retains a
selected population for the next generation.

The paper uses five operators:

| Paper operator | Role |
|---|---|
| E1 | Exploration from multiple parents, seeking a deliberately different heuristic idea |
| E2 | Exploration by extracting useful shared ideas, then creating a different heuristic |
| M1 | General modification of one selected heuristic |
| M2 | Parameter modification while retaining the main heuristic |
| M3 | Simplification by removing redundant components |

The important methodological lesson for this project is that code must be
evaluated under a fixed evaluator, while prompts, code, thoughts, parents,
runtime, and failures are retained.  A visualisation alone is not evidence that
one operator is better.

## 2. Completed Circle Packing work inspired by EoH

### Historical landscape baseline

- Preserved the 14,000-record Circle Packing historical archive, including
  successful, invalid, missing, non-finite, and error outcomes.
- Built a separate combined graph with the 14,000 historical programs plus 30
  new, fully logged prompt candidates.
- The saved graph has 14,030 nodes and 14,029 **exact nearest-better** edges
  using CodeT5+ embedding cosine distance.  Historical source data and its
  embedding cache were not overwritten.
- The best observed historical score is 2.6359372088053568 (sample 12738).
- The combined graph, 3D viewer, provenance record, and the region-selection
  report are saved under `output/circle_prompt_preflight_20261025/combined_nbn_20261026_v2/`.

### Prompt pilot evidence retained

Two exploratory prompt activities were completed with the local Qwen model and
the same Circle Packing validity checks:

1. A five-profile, three-arm pilot recorded all outcomes.  Its best valid
   result was a structural-mutation candidate with score 2.600306976710351.
   This is below the historical best and is not reported as an improvement.
2. A later controlled repeated comparison produced 30 candidates: 5 valid, 1
   invalid geometry, and 24 timeouts.  The five valid candidates were M2
   structural-mutation trials, each with score 2.579279552688004.  They were
   incorporated into the combined NBN with their calculated parent edges.

All valid, invalid, timeout, and non-finite outcomes remain research data; none
were discarded to make the result appear better.

## 3. NBN interpretation reached

The combined NBN is useful for locating a generated program relative to the
historical code landscape.  It does **not** itself prove solution quality or
that a prompt is superior.  The region-selection analysis identified four
top-level nearest-better branches with adequate historical support.  All five
valid candidates from the repeated comparison attach to the same top-level
branch.  Thus, the current evidence does not show broad exploration across
historical code branches or an improvement over the archive champion.

The 3D cone-tree coordinates are a display layout.  Conclusions in the saved
region report use recorded scores and NBN parentage, rather than visual
appearance alone.

## 4. Accurate status at closure

This EoH study phase is complete as a paper reading, reproducible pilot, and
NBN-based baseline analysis.

It is **not** a full reproduction of the paper's complete multi-generation EoH
experiment.  In particular:

- Circle Packing is an adaptation, not one of the paper's reported benchmarks.
- The local labels M1 and M2 are reversed relative to the paper's M1/M2 naming;
  reports must name both the actual instruction and the paper role.
- The custom three-arm pilot is not the paper's full five-operator,
  population-based evolutionary schedule.
- Thirty prompt candidates are insufficient to claim that any prompt/operator
  is best.

These boundaries protect the project from overstating the results.

## 5. Handover to the next paper

The reusable outputs for the next literature/experiment cycle are:

- the preserved Circle Packing historical archive and exact combined NBN;
- the interactive 3D viewer and provenance files;
- the complete pilot ledger, including failures;
- the region-anchor CSV for a future pre-registered experiment; and
- the fixed evaluator and local-LLM generation records.

If a later project returns to EoH, it should first pre-register an equal-budget
five-operator experiment (E1, E2, M1, M2, M3), fix the seeds/model/evaluator,
and then compare validity, scores, code diversity, and NBN branch coverage.
No such future run is implied by this closure record.
