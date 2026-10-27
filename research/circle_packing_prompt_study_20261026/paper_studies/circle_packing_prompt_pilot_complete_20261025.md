# Circle Packing prompt pilot — complete record

Date: 2026-10-25  
Problem: Circle Packing (`n = 26`)  
Model: local Qwen2.5 3B on the university server (GPU-backed)  
Evaluator: static contract screen, then isolated Python evaluation with a 20-second limit and geometric feasibility checks.

## Purpose

This is an exploratory, controlled prompt-engineering pilot guided by the EoH workflow and the supervisor's advice: use the large Circle Packing history to investigate prompts that can reach unexplored code regions while preserving **all** outcomes (valid, invalid, exception, timeout, and static rejection).

It is not yet a full comparative experiment: each profile generated one candidate per arm, so it cannot establish that one prompt or operator is superior.

## Arms

- **M1** — parameter-tuning mutation from a high-score historical seed.
- **M2** — structural mutation from a high-score historical seed.
- **M3** — diversity-oriented mutation from a high-score historical seed.

## Complete outcome table

| Prompt profile | M1 | M2 | M3 | Valid / 3 |
|---|---|---|---|---:|
| Baseline | timeout | timeout | timeout | 0 |
| Runtime-constrained | timeout | invalid geometry | exception (`p` undefined) | 0 |
| Runtime + validity repair | timeout | valid, score 0.000000 | exception (`qmc` undefined) | 1 |
| Runtime + validity + quality | static rejection | static rejection | static rejection | 0 |
| Runtime + validity + quality + exact contract | timeout | **valid, score 2.600306976710351** | timeout | **1** |

All candidates, prompts, model responses, code hashes, and evaluator records remain in the associated run folders on the research server. Failures are research data, not discarded samples.

## Promising result

The final profile required exactly one top-level entry function, `pack_circles(n)`, prohibited top-level test code, emphasized geometric validity and runtime, applied a quality floor of 1.0, and used low-temperature generation.

Its M2 candidate:

- passed the static contract;
- returned a feasible `(26, 3)` packing;
- achieved score **2.600306976710351**;
- ran in **4.37 s** on the first evaluation (4.62 s wall time);
- passed the quality gate; and
- reproduced twice with the same score (4.38 s and 4.24 s evaluation runtime).

The candidate code SHA-256 is `2f4ff9ca91d6c70f505be7d56e852d6eb4229787b2bc29d90102b4571d0c1667`.

## Comparison with the historical landscape

The canonical Circle Packing historical cohort contains 14,000 sample orders: 8,057 finite scores, 3,193 non-finite invalid outcomes, 310 negative-error sentinels, and 2,440 missing outcomes. The best historical finite score is **2.6359372088053568**.

Therefore the M2 score is **0.0356302320950058 below** the historical best (about **1.35% lower**). It is a strong valid pilot candidate under this evaluator, but it must **not** be described as better than the historical best.

## NBN interpretation boundary

The saved Circle Packing NBN snapshot has 14,000 nodes and 13,999 nearest-better edges, based on CodeT5+ cosine embeddings. Its retained graph JSON does not include the original embedding vectors. Consequently, this new candidate cannot honestly be placed into that exact NBN yet. Any future placement requires rerunning the same embedding/nearest-better pipeline (or a clearly labelled proxy analysis).

## Next experiment — pre-registered before looking for more results

Use the final **runtime + validity + quality + exact contract** profile as a candidate prompt condition and compare it against the baseline with multiple independent samples per arm (recommended: 5 per M1/M2/M3 profile). Hold fixed:

1. `n = 26`, evaluator, 20-second limit, quality threshold, seed selection policy, and local model version;
2. the complete ledger of prompts, raw outputs, code, hashes, static outcomes, runtime, feasibility, and score;
3. analysis of validity rate, timeout/error rate, score distribution among valid solutions, novelty/region after proper NBN embedding, and diversity.

This will turn the successful pilot observation into a defensible Circle Packing experiment aligned with the supervisor's feedback.
