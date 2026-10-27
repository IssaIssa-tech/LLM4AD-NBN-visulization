# Registered direction: AEL adaptation for Circle Packing

**Decision date:** 2026-10-26

## Decision

This project will study AEL using **Circle Packing**, rather than attempting a
TSP reproduction.  The reason is evidential: the project already has a large,
preserved Circle Packing archive and an exact CodeT5+ nearest-better network
(NBN) built from it.  This offers a stronger historical baseline and a better
way to inspect where new program candidates lie in code space.

This is an **adaptation of AEL**, not a claim of an exact replication of the
paper's constructive-TSP experiment.

## What remains fixed

- Task contract: `pack_circles(n: int) -> np.ndarray` returning an `(n, 3)`
  array of circle centres and radii in the unit square.
- Evaluation task: `n = 26` with the existing static screen, isolated
  execution, geometric feasibility checks, score calculation, and fixed
  timeout.
- Score direction: higher feasible sum of radii is better.
- Evidence policy: retain every code response and outcome: valid score,
  invalid geometry, static rejection, exception, timeout, duplicate, missing,
  and non-finite result.
- Local LLM policy: use only the configured local model; record its exact name,
  endpoint, decoding parameters, sampling seed, timestamp, and response hash.

## AEL components mapped to Circle Packing

| AEL component | Circle Packing implementation |
|---|---|
| Individual | Brief algorithm thought, `pack_circles` code, evaluator fitness, provenance |
| Initial population | A pre-registered selection from the historical archive, rather than LLM-only initialization |
| Crossover | Local LLM receives two parent thoughts and programs, then produces one new Circle Packing heuristic |
| Mutation | Local LLM receives one parent thought and program, then produces a bounded revision |
| Evaluation | Existing Circle Packing evaluator, unchanged for all candidates |
| Population management | Combine incumbent and feasible offspring, then retain the best `N` under the fixed score rule |
| NBN analysis | Rebuild/extend the exact CodeT5+ NBN after the run; use it to analyse code-region coverage, not to assign fitness |

## Explicit deviations from the paper

1. The original demonstration evolves constructive TSP next-node policies;
   this study evolves complete Circle Packing functions.
2. The paper initializes its population with LLM-generated algorithms.  This
   adaptation initializes from the historical Circle Packing archive, so that
   the large available data are used transparently rather than ignored.
3. The original paper evaluates average TSP gap over 64 TSP50 instances.
   This adaptation uses the existing Circle Packing feasibility-and-score
   evaluator.  Results cannot be compared numerically with the paper's TSP
   results.
4. The local model is not GPT-3.5-turbo or GPT-4.  Its configuration must be
   recorded before any AEL generation call.

## Required pre-registration before execution

No AEL candidate should be generated until the following are written to a run
manifest:

1. population size `N`, number of generations, crossover/mutation budget, and
   stopping rule;
2. deterministic historical-initial-population selection rule, including the
   exact IDs, scores, and code hashes of all initial programs;
3. parent-selection rule;
4. exact crossover and mutation prompt templates;
5. local model/endpoint, temperature, maximum generation length, and sampling
   seeds;
6. evaluator executable, timeout, numerical tolerance, and score direction;
7. raw-output, duplicate, validity, runtime, and NBN-analysis fields.

## First practical action

Create the initial-population manifest from the 14,000 historical records.
The selection should balance high observed score with distinct NBN branches;
it must be calculated and saved before the LLM is called.  The previous
EoH-style pilot remains a separate completed study and is not included as an
AEL generation.
