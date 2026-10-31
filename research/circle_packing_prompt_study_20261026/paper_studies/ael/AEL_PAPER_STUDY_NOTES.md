# AEL paper study notes

**Paper:** Fei Liu, Xialiang Tong, Mingxuan Yuan, and Qingfu Zhang, *Algorithm Evolution Using Large Language Model* (2023 preprint).

**Status:** Reading and method extraction started on 2026-10-26.  No AEL candidate has been generated or evaluated in this project yet.

**Reading clarification, 2026-10-31:** Section III.D permits either existing or LLM-generated initial algorithms; the reported experiment chooses LLM-generated initialization. Statements below about that choice describe the experimental configuration, not a restriction of the general framework. AEL remains the next main paper. See the [current prompt-source review](../../paper_prompt_reference_review_20261031/PAPER_PROMPT_CATALOGUE.md) for prepared, unexecuted adaptations and supplementary sources.

## 1. Central idea

Algorithm Evolution using Large Language Model (AEL) treats an optimisation
algorithm as an evolutionary individual.  Each individual consists of:

1. a short natural-language algorithm description;
2. executable code in a predefined input/output format; and
3. a fitness value obtained by running that code on a set of evaluation
   instances.

The LLM is used to create and revise algorithms.  It is not used as a direct
solver for individual problem instances.

## 2. Evolutionary procedure reported in the paper

1. **Initialization:** create and evaluate a population of algorithms.  The
   paper lets the LLM create the initial algorithms, rather than starting from
   expert-designed ones.
2. **Selection:** select parent algorithms from the current population.  In the
   reported experiments, parents are selected with equal probability.
3. **Crossover:** give the LLM multiple parent descriptions and code blocks;
   request a new algorithm motivated by the parents but distinct from them.
4. **Mutation:** give the LLM one parent description and code block; request a
   revised version of that algorithm.
5. **Evaluation:** execute every created code program on a fixed set of
   instances to obtain its fitness.
6. **Population management:** add offspring, then remove the worst algorithms
   to reduce the population from `(s + 1)N` to `N`.

The paper's individual representation and explicit program contract are
important: an LLM response is not an experimental result until the code has
passed the specified evaluator.

## 3. Reported TSP demonstration

The paper demonstrates AEL on constructive travelling-salesman heuristics.  A
program implements `select_next_node(current_node, destination_node,
unvisited_nodes, distance_matrix)`.  Fitness is the average gap to a Gurobi
solution over 64 randomly generated TSP instances of size 50; lower is better.

Reported AEL settings for this demonstration:

| Setting | Value |
|---|---:|
| Population size `N` | 10 |
| Number of generations `Ng` | 10 |
| Crossover probability | 1.0 |
| Mutation probability | 0.2 |
| Crossover parents `l` | 2 |
| Offspring per crossover `s` | 1 |
| LLMs reported | GPT-3.5-turbo and GPT-4 |

These are the paper's TSP settings.  They are not results or defaults for our
Circle Packing work or our local Qwen model.

## 4. Difference from the completed EoH study

| Aspect | AEL paper | EoH paper studied previously |
|---|---|---|
| Main operators | Initialization, crossover, mutation | Initialization plus E1, E2, M1, M2, M3 prompt strategies |
| Parent selection reported | Equal-probability selection | Rank-weighted selection in the reported experiments |
| Population update | Add offspring, delete worst to keep `N` | Select the best `N` after feasible new heuristics are added |
| Paper demonstration | Constructive TSP next-node rule | TSP, bin packing, and flow-shop scheduling |

Both papers evolve algorithms rather than direct solutions, but their prompt
operators and population-management rules should not be merged or renamed.

## 5. Implication for this project

The supervisor-directed Circle Packing archive can be useful as landscape
context and as a source of reproducible reference programs.  However, an AEL
experiment on Circle Packing would be an **adaptation** because the paper's
implemented program contract is a TSP next-node selection rule.

Before executing any AEL adaptation, we must pre-register:

- the Circle Packing individual representation and exact function contract;
- a fixed evaluator, score direction, tolerance, and timeout;
- whether initialization is LLM-only, as in the paper, or seeded from archival
  programs (a stated deviation);
- population size, number of generations, crossover and mutation budgets;
- local model name and decoding settings; and
- a ledger that preserves every candidate, including invalid, timeout,
  duplicate, missing, and non-finite outcomes.

The prior EoH-derived Circle Packing pilot is useful historical context but is
not an AEL run and must not be relabelled as one.

## 6. Proposed next reading-stage deliverable

Create an AEL literature-matrix entry and a one-page experimental decision:

1. **Faithful paper reproduction:** use the paper's constructive TSP interface
   and reported settings, if its full TSP evaluator/instance generator is
   available.
2. **Transparent Circle Packing adaptation:** use the Circle Packing evaluator
   and state every departure from the TSP-specific AEL demonstration before
   any generation is run.

No experiment is launched until that decision is made.
