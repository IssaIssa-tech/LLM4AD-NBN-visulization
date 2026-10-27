# M2-I-P strict code-patch protocol

## Motivation

The earlier M2-I trials attempted a Sobol initialization change but all failed
to produce evaluation-ready code. The later code-checked M2 condition also
failed before evaluation. This condition tests local-model adherence to one
small, explicit code patch rather than asking it to redesign a heuristic.

## Fixed parent and permitted change

The validated contract-M2 parent program is fixed by SHA-256 in
`m2ip_patch_preregistered_run/run_manifest.json`.

The only permitted change is replacement of the three-line Halton initialization
block by the specified four-line deterministic scrambled-Sobol block. The
parent's imports, bounded search, all-pairs radius calculation, five proposals
per circle, 500 iterations, temperature schedule, and acceptance logic remain
unchanged.

## Trials and evaluation

- Five fixed sampling seeds: 20261120–20261124.
- Local model: `qwen2.5:3b`, temperature 0.1, `num_predict=1800`.
- No repair call: the condition measures one-pass patch compliance.
- An output whose SHA-256 does not exactly equal the pre-registered patched
  source is recorded as `rejected_patch_guard` and is not evaluated.
- Exact outputs receive the existing 8-second precheck. Only a valid precheck
  proceeds to the unchanged 20-second Circle Packing evaluation at `n=26`.

## Interpretation rule

This is a prompt-delivery reliability condition. Its results must be reported
separately from both the original free-generation M2 baseline and the earlier
M2-I condition. If exact outputs evaluate, their score measures the specified
Sobol initialization variant; if they fail the patch guard, no conclusion about
Circle Packing solution quality is justified.
