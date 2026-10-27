# M2-I execution result

## Registered change

M2-I preserved the successful combined-contract M2 baseline and requested one
specific structural change only: replace Halton initialization with a
deterministic scrambled Sobol initialization. The bounded 500-iteration
search, five proposals per circle, all-pairs radius calculation, evaluator,
20-second limit, and five-seed budget were held fixed.

## Outcome

All five local-Qwen generations completed, but no candidate completed the
Circle Packing evaluator successfully.

| Trial | Status | Runtime (seconds) | Recorded error |
|---|---|---:|---|
| m2i-20261105 | exception | 1.683 | `NameError: name 'r' is not defined` |
| m2i-20261106 | exception | 1.646 | `NameError: name 'r' is not defined` |
| m2i-20261107 | exception | 0.388 | `TypeError: Sobol.__init__() got an unexpected keyword argument 'n'` |
| m2i-20261108 | exception | 1.594 | `NameError: name 'r' is not defined` |
| m2i-20261109 | exception | 1.622 | `ValueError: could not broadcast input array from shape (67108864,2) into shape (26,2)` |

**Summary:** 0/5 valid, 5/5 exception, 0/5 timeout, 0/5 invalid geometry.

## Comparison and conclusion

The M2 baseline remains the only selected condition: it had 5/5 valid
candidates at score 2.579279552688004. M2-I did not produce an evaluable
candidate and is therefore not a successful successor.

This does not show that Sobol initialization is bad for Circle Packing. It
shows that this particular local-LLM prompt condition did not reliably
implement the required Sobol change under the exact code contract. The failure
mode is implementation reliability, not an observed fitness comparison.

All prompts, responses, candidate files, generation ledger, and evaluator
records are preserved in `m2i_execution_20261026/`. No invalid M2-I candidate
is added to the valid-candidate NBN comparison.

## Next decision

Do not run another broad prompt variation automatically. The evidence now
supports retaining the M2 baseline as the executable algorithm. A later
successor should either use a constrained code-edit/patch workflow that can
verify the single intended change before evaluation, or test a new prompt
condition after explicitly deciding which reliability failure it addresses.
