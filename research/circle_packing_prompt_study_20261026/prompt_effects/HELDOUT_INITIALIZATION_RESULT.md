# Held-out initialization validation

The two algorithms were frozen before evaluating ten previously unused Sobol seeds, 20261201–20261210. Both members of every pair were evaluated contemporaneously on the university server, alternating condition order. NumPy seed 2025, original probabilistic acceptance, n=26, the geometry evaluator and a 20-second limit were fixed. No LLM calls, repairs, replacement seeds, parameter tuning or optional stopping occurred. These are prepared-code algorithm comparisons.

| Seed | Original score/status | Feasible score/status | Difference |
|---|---:|---:|---:|
| 20261201 | 2.596872868237 | 2.571422701533 | -0.025450166703 |
| 20261202 | 2.611480717436 | 2.582548885919 | -0.028931831517 |
| 20261203 | 2.619351410171 | 2.594406741011 | -0.024944669160 |
| 20261204 | 2.587656971633 | 2.571378737914 | -0.016278233720 |
| 20261205 | 2.619173509943 | 2.597711798443 | -0.021461711500 |
| 20261206 | 2.612200202910 | 2.605425123249 | -0.006775079661 |
| 20261207 | 2.602495648234 | 2.594336019274 | -0.008159628961 |
| 20261208 | 2.590059999743 | 2.595495685097 | +0.005435685355 |
| 20261209 | 2.578703186538 | 2.584571345183 | +0.005868158645 |
| 20261210 | 2.581771232261 | 2.588356379513 | +0.006585147252 |

## Registered decision

- Valid original: 10/10; valid feasible: 10/10.
- Paired differences available: 10/10.
- Feasible wins/losses/ties: 3/7/0.
- Mean original score among valid outputs: 2.599976574710666.
- Mean feasible score among valid outputs: 2.588565341713522.
- Mean paired difference: -0.011411232997144.
- Median paired difference: -0.012218931340282.
- Registered improvement criterion satisfied: **False**.

The registered criterion requires no lower valid count, positive mean paired difference, and more wins than losses. It is a descriptive decision rule, not a statistical significance test.

## Algorithm-selection implication

This validation does not support replacing original initialization with feasible initialization as a generally better choice. The earlier four-of-five exploratory gain does not establish a reliable improvement on new seeds. Retain the original initialization as the reference and report feasible initialization as a mixed-result alternative.

Keep this cohort separate from the exploratory five seeds. Do not select a new mechanism or winning seed using these results and then describe that selection as independently validated. A best observed score is a descriptive maximum, not a new independent confirmation. The code-region analysis remains the prior result: explored feasible variants stayed in the same historical top-level branch. These twenty validation programs were not added to that graph by this validation.

## Limits and evidence

Ten fixed consecutive seeds, one task size, one NumPy seed and one environment; no random-sampling or broad-generalization claim. Every invalid/timeout result remains in the ledger and is not assigned an invented score. Raw records, hashes, manifest, source, environment and stopping rule are in `heldout_initialization_validation_20261027/`. The existing exploratory graph and reports remain preserved.

Environment: {"python": "3.10.20 (main, Mar 11 2026, 17:46:40) [GCC 14.3.0]", "numpy": "2.2.6", "scipy": "1.15.3", "host": "user-SYS-4029GP-TRTC-EC028B"}.
