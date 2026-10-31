# Finite NBN selection and prompt comparison — GPU study

Fourteen registered unique requests finished. Sixteen analytical slots share two responses across parent-selection groups; they are not sixteen independent trials.

| Selection | Prompt | Valid / 4 | Target hits | Best valid score | Outcomes |
|---|---|---:|---:|---:|---|
| quality_only_top4 | contract_M2 | 0 | 0 | None | {'timeout': 4} |
| quality_only_top4 | contract_M2_structural_exploration | 0 | 0 | None | {'exception': 2, 'rejected_static': 2} |
| nbn_region_top4 | contract_M2 | 0 | 0 | None | {'timeout': 4} |
| nbn_region_top4 | contract_M2_structural_exploration | 1 | 0 | 2.1026448800851467 | {'rejected_static': 1, 'exception': 2, 'valid': 1} |

Unique-call outcomes: {'timeout': 7, 'exception': 4, 'rejected_static': 2, 'valid': 1}. Valid scores: [2.1026448800851467]. Target hits: 0.

The study used fixed Qwen2.5-Coder 7B Q4_K_M weights and a pinned llama.cpp GPU runtime on hits_9. Evaluation remained on hits_1 with the registered worker/dependencies and twenty-second limit. No repair, replacement call or manual candidate patch was permitted. See registration.json, the manifest and exact saved prompts for provenance.

This is a preliminary descriptive comparison, one sample per parent/profile. Parent groups overlap and differ in code as well as archived quality. Prompt profiles are complete instruction packages. A higher valid count alone cannot establish a robust ranking, broad generalization or causal benefit from an NBN label.

Unique source/AST hashes are inspection aids, not proof of meaningful mechanism diversity. Inspect successful program mechanisms and scored-program embedding/NBN placement before drawing a diversity conclusion. No new NBN placement is claimed by this report. Missing or invalid fitness remains unranked. The frozen historical graph is HNSW-based, not an exact or physical basin guarantee.

The 2.6360 target is checked against the named research evaluator. Its timeout/tolerance settings and full official-verifier equivalence remain separately qualified. Report the outcome even if no target hit occurs; do not extend the batch until success. Connect supported prompt/parent choices to algorithm design only where the evidence permits.
