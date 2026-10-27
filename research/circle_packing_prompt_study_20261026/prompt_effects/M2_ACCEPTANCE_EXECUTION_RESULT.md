# Acceptance-rule ablation: local-model delivery result

Completed: 2026-10-27 22:50:38 CST. Five registered local-Qwen requests completed; all returned the same candidate hash and `done_reason=stop`. All failed the registered AST patch guard. No candidate was admitted to fitness evaluation. Validity and fitness of the generated code remain unmeasured.

## Intended edit

Keep the fixed Sobol parent program and replace only:

```python
if best_r > r or np.random.random() < np.exp((best_r - r)/temperature):
```

with:

```python
if best_r > r:
```

## Observed executable changes

Each generated program instead deleted:

```python
if current_r > best_r:
    best_r = current_r
    best_pos = (new_x, new_y, current_r)
```

It retained the original probabilistic acceptance condition and placed that condition inside the proposal loop. This is not a comment/formatting mismatch. The variables `best_r` and `best_pos` remain initialized to zero and None without their original updating block. Static inspection therefore indicates the retained assignment guarded by `best_pos is not None` cannot update a circle through that path. This is a source-code diagnosis, not an executed geometry or fitness result.

## Counts and control

- Requests: 5; unique generated hashes: 1.
- AST matches: 0/5; full candidate evaluations: 0/5.
- Contemporaneous parent control: valid, score 2.5902372123245248, evaluator runtime about 4.83 seconds.
- No repair or replacement calls were made.

The result demonstrates failure to deliver the specified edit under this prompt/local-model condition. It does not test whether radius-increasing-only acceptance improves the algorithm. The raw reply metadata, prompts, generated programs, ledger, expected program and parent reference evaluation are preserved in `m2_acceptance_execution_20261027/`.

## Decision

Retain all five rejections as completed data. Do not rerun this prompt unchanged or include these programs as evaluated NBN additions. An algorithm-only evaluation of the frozen expected edit would answer a separate question and must be registered and labelled separately before execution. The current run alone supports no claim of improved quality or structural diversity.
