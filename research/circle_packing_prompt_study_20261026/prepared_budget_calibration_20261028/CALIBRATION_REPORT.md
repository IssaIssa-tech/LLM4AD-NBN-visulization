# Prepared-code budget calibration

Four prepared programs were evaluated once in the current deployment, with the unchanged twenty-second research evaluator. No LLM calls were made. Registration, source files, coordinates and platform events are preserved.

| Prepared program | Wall seconds including worker startup | Score | Geometry |
|---|---:|---:|---|
| Historical sample 12738, outer rounds 25 | 1.8761 | 2.3901152479 | valid |
| Historical sample 12738, outer rounds 50 | 2.9804 | 2.4100613117 | valid |
| Historical sample 12738, outer rounds 100 | 5.3785 | 2.4163442447 | valid |
| Unchanged M2 Halton control, 500 rounds | 5.0944 | 2.5792795527 | valid |

## Correction to registration labels

The directory name `validated_sobol_control` and its registered origin description incorrectly say Sobol. The supplied file is `m2ipd_preregistered_run/parent_candidate.py`, which explicitly initializes `qmc.Halton(d=2, seed=2025)`. Its recorded source hash identifies the actual code, which was executed unchanged. The result matches the earlier M2 baseline, not the Sobol-patch result. Preserve the original registration and outcome paths; use this correction when interpreting them. The labeling mistake does not require rerunning the same code.

## Scope and implication

The three historical variants alter only `range(40000)` to the registered smaller outer-loop bound. Their cooling schedule is unchanged. They are prepared calibration variants, not LLM-generated discoveries, and cannot establish the best shortened algorithm. Single observations under shared server load provide no universal timing guarantee. These measurements do not justify applying the same numerical cap to arbitrary generated programs, whose inner work may differ.

For a subsequent constrained adaptation pilot, a 100-round cap on this specific historical search structure has measured headroom under the current evaluator. Prompt compliance must also preserve or explicitly bound proposal and pairwise loops. An unconstrained newly generated search cannot inherit this runtime assurance. The useful M2 control further demonstrates that a feasible nonzero result can be produced in this environment; the previous zero scores and timeouts are not evidence of a universally broken evaluator.

Next register a small bounded adaptation condition before new generation, distinguishing researcher-prescribed work limits from LLM-selected optimization changes. Retain the same evaluator, disclose changed prompt scope, and preserve all failures. Do not infer that the target 2.6360 has been achieved or that an NBN selection strategy has won. None of these calibration scores reaches the target.
