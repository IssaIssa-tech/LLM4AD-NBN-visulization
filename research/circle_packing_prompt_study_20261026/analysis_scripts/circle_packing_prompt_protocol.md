# Circle Packing prompt-experiment protocol

## Purpose

Use the large stored Circle Packing history to understand the code fitness
landscape, then test paper-inspired prompt variants with a local LLM.  The
aim is to discover valid, high-quality and diverse algorithms; it is **not**
to claim an improvement before the same evaluator and the recorded results
support it.

## Reference data and provenance

Two reference sources must remain separate:

1. **Historical EoH archive** — canonical sample orders 1--14,000.  It
   contains 8,057 finite evaluator scores, 3,193 non-finite invalid scores,
   310 negative error sentinels, and 2,440 missing scores.  The stored best
   finite score is 2.6359372088053568.
2. **Circle Packing NBN snapshot** — 14,000 nodes and 13,999 nearest-better
   edges, built using CodeT5+ cosine code embeddings.  It is a landscape
   representation of the stored history, not an independent benchmark.

Invalid, missing, and error outcomes are retained in the experimental ledger.
They are evidence about prompt reliability and must never be silently removed.

## Research question

Which paper-inspired prompt / modification style produces the best balance of
validity, fitness, and code diversity when generating Circle Packing
algorithms with the fixed evaluator?

## Prompt arms

All arms use the same function contract and evaluator.  They differ only in
the requested change.

| Arm | Role | Controlled instruction |
|---|---|---|
| M1 | Parameter-tuning mutation | Keep the parent algorithm's overall design. Improve only numeric schedules, iteration budgets, neighbourhood sizes, cooling rates, or other parameters. Explain the intended change briefly in the algorithm description. |
| M2 | Structural mutation | Preserve the entry-point contract but replace one substantial algorithmic component, such as initialization, placement rule, local search, or repair mechanism. Do not merely rename variables or adjust constants. |
| M3 | Diversity / exploration mutation | Produce a valid approach that is materially different from the selected parent family. Prioritise an unexplored algorithmic idea while satisfying every Circle Packing constraint. |

M1, M2, and M3 are evaluated as separate experimental arms.  They are not
combined into one result and their sample counts must be balanced.

## Staged execution

1. **Preflight:** one candidate per arm.  Check that output parsing,
   evaluator logging, and validity recording work.  Do not draw conclusions.
2. **Pilot:** five candidates per arm (15 total) from fixed recorded seeds.
   Report every outcome, including failures.
3. **Main comparison:** only after the pilot is auditable, use an equal,
   pre-registered budget per arm (for example 20 candidates per arm).

## What is recorded for every candidate

- prompt-arm ID and exact prompt text / hash;
- parent seed ID and historical parent score;
- local model and quantisation (`qwen2.5:3b`, Q4_K_M);
- generation timestamp and random seed where available;
- evaluator validity, score, error category, and runtime;
- code fingerprint and NBN placement / nearest-better parent after the graph
  is recomputed or extended.

## Evidence required before saying a prompt is better

A prompt arm may be described as promising only when its recorded results
show at least one of the following relative to the other arms and the
historical baseline:

- a higher valid-solution rate;
- a higher distribution of finite scores, or a score above the stored best;
- a reproducible high-scoring result on the same evaluator; or
- valid algorithms that form a demonstrably distinct code family or enter a
  sparse / previously unrepresented part of the NBN.

The historical archive does not contain a prompt identifier for each old
sample.  Therefore, prompt-level claims begin with the new, fully logged
experiments, not by retrospectively assigning prompts to old records.
