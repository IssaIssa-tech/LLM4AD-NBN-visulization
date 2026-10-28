# Current Circle Packing research evidence

Question: can NBN-guided historical-program selection and prompt design produce structurally diverse high-quality optimizers reaching at least 2.6360? Current answer: not demonstrated.

| Completed condition | Unique LLM calls | Valid | Timeout | Exception | Invalid geometry | Static rejection | Valid scores |
|---|---:|---:|---:|---:|---:|---:|---|
| regional_prompt_comparison_draft_20261028 | 14 | 1 | 3 | 9 | 0 | 1 | [0.3267410733963663] |
| regional_prompt_execution_contract_20261028 | 14 | 1 | 10 | 2 | 1 | 0 | [0.0] |
| bounded_adaptation_pilot_20261028 | 2 | 0 | 0 | 1 | 1 | 0 | [] |
| bounded_feedback_repair_20261028 | 2 | 1 | 0 | 0 | 0 | 1 | [1.5076928592802266] |

Aggregate: 32 unique model calls, {'rejected_static': 2, 'timeout': 13, 'exception': 12, 'valid': 3, 'invalid_geometry': 2}. No target hits. These counts describe sequential exploratory conditions and are not a pooled causal estimate.

## Interpretation

The standard broad comparison and added-checklist comparison each use fourteen unique calls across sixteen analytical slots; shared parent/profile requests are not independent trials. The first yielded one low-score feasible output. The checklist reduced exceptions but increased timeouts and yielded only a zero-radius packing. The two-request bounded pilot followed the loop limits but failed geometry or execution. Its one-feedback-repair follow-up yielded a geometrically valid score of 1.50769 only by removing the required search structure; the other repair was statically rejected. No compliant repair succeeded.

All calls are linked to historical parent 12738 or the other frozen reference nodes in EVIDENCE_INDEX.json and per-condition manifests. The two broad comparisons included quality-only and four-region pools. The small follow-ups use only one historical parent and cannot answer regional selection effects.

The source NBN for these selections is frozen and HNSW-based, with operational top-level branches in code embedding space. It is not asserted to be an exact nearest-better graph or a physical basin decomposition. No new embeddings or NBN positions were computed for these recent candidates. Code hashes alone do not establish mechanism diversity, especially among failing programs.

## Separate earlier and calibration evidence

Earlier repeated M2 scored 2.579279552688004. The strict Halton-to-Sobol patch produced one unique program scoring 2.5902372123245248 across five successful deliveries. Those tests already demonstrate constrained code-delivery capability and should not be repeated under a new name. The archived best is 2.6359372088053568; its score is not automatically comparable to a current-budget execution.

Four prepared-code runtime checks used zero LLM calls: 25/50/100-round historical variants finished in approximately 1.88/2.98/5.38 seconds. The unchanged M2 Halton control finished in 5.09 seconds, score 2.57928. The calibration registration mistakenly labels that control Sobol; its correction and source hash are preserved. These are prepared algorithms, not generated discoveries. The thirteen regional historical-reference diagnostics are also excluded from model-call totals.

## Next comparison design

First check availability of a code-specialized open-source model and freeze its exact digest, quantization, context window, chat/template settings and serving configuration. Reuse one full fourteen-request broad condition, unchanged parents/prompts/evaluator/sampling seeds and generation token cap, as the proposed pilot comparison. Changing model changes tokenizer/template as well as weights and size; describe this as a model-package comparison. Do not claim a pure parameter-count effect or pool old dependent slots as independent replicates.

Before running, verify prompt fit without truncation and preserve prompt-token counts and raw responses. Record actual device/offload allocation and timing. Current model comparisons would be sequential under different shared load; runtime comparisons are descriptive. Keep the same twenty-second research evaluator, no repairs, and the existing failure accounting. Choose a single original prompt condition before seeing new outputs rather than combining whichever old prompt worked best per parent.

Proposed primary model-package outcome: evaluator-valid rate and scores, accompanied by code/geometry/contract compliance. Research outcomes remain target attainment, mechanism diversity and branch coverage when meaningful fitness is available. Only a subsequent adequately replicated selection comparison could support claims of NBN guidance. Stronger-model success is not guaranteed.

No model download or new generation was performed during consolidation. Full official-verifier equivalence remains unresolved. Preserve all unsuccessful outputs and every strategy revision.
