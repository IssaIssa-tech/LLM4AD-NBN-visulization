# Paper-based prompt review for the supervisor's second message

Review date: 2026-10-31. Status: **source review and draft prompt library; no new generation or evaluation**.

**Main next paper: AEL (Algorithm Evolution Using Large Language Model).** EoH is the existing experimental baseline. FunSearch and MCTS-AHD were consulted as supplementary prompt sources in response to the request for different papers; this is not a switch to full reproductions of those methods.

The message asks us to examine prompts from different papers and different historical program choices, then observe how those choices affect results. History tracking is implemented. Completing that software feature does not complete the requested scientific comparison.

## What the original papers actually provide

These are readings of the supplied papers, not completed reproductions of four methods. The paper methods overlap; different paper names do not automatically provide independent prompt mechanisms.

| Source | Source location in supplied PDF | Prompt mechanism | Circle Packing use and current boundary |
|---|---|---|---|
| [EoH](https://arxiv.org/abs/2401.02051) | Section 3.4, PDF p.4 | E1 seeks a new form from multiple parents; E2 extracts a common idea and adds new parts; M1 revises one heuristic; M2 changes its parameters; M3 removes redundant components. | Five clearly named reference families. Prior local labels need the mapping below. A new operator-specific template is an adaptation, not an already measured result. |
| [AEL](https://arxiv.org/abs/2311.15249) | Sections III.E and III.F, PDF p.5 | Crossover supplies several parent descriptions and code, seeking a distinct offspring; mutation revises one parent. | Two-parent crossover offers a useful contrast to the recent single-parent prompts. The inspected AEL folder contains reading/adaptation/seed preparation records, not a completed AEL generation comparison. |
| [FunSearch](https://doi.org/10.1038/s41586-023-06924-6) | Methods: Prompt building, PDF p.9; Extended Data Fig.1, PDF p.12 | Best-shot prompting orders sampled implementations by score, assigns versioned names, and asks for a new function body. | This is a program-completion representation. Using our chat model, a full packing function, or parents from different NBN branches would be stated adaptations. Versioned context must remain separate from the single-function evaluator payload. |
| [MCTS-AHD](https://arxiv.org/html/2501.08603v3) | Section 3.1; Appendix E.1, PDF pp.21-24 | e2 combines a base program with a reference program's useful ideas. s1 uses genuine related programs along an evolution-tree path. | An explicit BASE/DONOR e2-style prompt can be drafted from archived code. An NBN nearest-better path is not recorded evolutionary ancestry; it cannot silently substitute for the s1 path. Reading prompts does not implement MCTS. |

Exact local PDF paths, SHA-256 identities and page locators are saved in `reference_audit.json`. Prompt files in `templates/` are our paraphrased Circle Packing adaptations, not verbatim quotations or published Circle Packing prompts.

AEL initialization clarification: Section III.C (PDF p.4) allows existing algorithms or LLM-created ones; the reported experiment chooses LLM-created initialization. Historical seeding is therefore a difference from that experimental configuration, not a claim that the AEL framework forbids existing programs. III.D covers selection. The section locator was corrected during the full AEL reading continuation; the interpretation and original experimental records are unchanged.

## Correct the naming before comparing anything

The early `analysis/circle_packing_prompt_protocol.md` and `analysis/run_circle_prompt_preflight.py` establish what the local labels actually requested. The EoH paper's original operator meanings were checked on its complete prompt-strategy page.

| Earlier local label | Actual local request | Relationship to EoH |
|---|---|---|
| M1 / `m1_parameter` | Numerical tuning with the main design retained | Corresponds to the **paper's M2 role**, with our task-specific restrictions. |
| M2 / `m2_structural` / `contract_M2` | Replace one substantive algorithmic component | Falls within the **paper's broader M1 revision role**; our one-component instruction is narrower. |
| M3 / `m3_diversity` in the early pilot | A materially different approach from one parent | A custom novelty instruction. It is **not paper M3**, which is simplification; it is not a faithful multi-parent E1 either. |
| `contract_M2_structural_exploration` | Structural change plus an explicit novelty request and NBN branch context | A complete custom prompt package, not a separately published operator. |
| M2-R / M2-I / M2-I-P / M2-I-P-D | Repair, initialization or strict-patch follow-ups | Local research variants, not additional independent papers. |

Keep all original labels and raw records. Add paper-role metadata when analysing them; do not rename historical outputs and imply a different prompt was executed.

## What the inspected experiments already establish

- The repeated EoH-inspired study and constrained Sobol-patch studies already exist. Their original findings remain in the study records; they should not be repeated merely under a corrected label.
- The completed GPU comparison used **seven distinct historical parents**, two custom structural prompt profiles, and **14 unique requests** shared across 16 analytical slots. That is a parent-selection/custom-prompt comparison, not a four-paper comparison.
- Its single geometrically valid generated output scored **2.1026448800851467**. There were seven execution timeouts, four exceptions and two static failures. It did not establish target attainment or superiority of a selection rule.
- The three existing valid historical references identified in `PARENT_REFERENCE_REVIEW.md` were absent from that named comparison's parent pool. Their recorded mechanisms and scores can inform which alternatives to examine.
- The inspected AEL records contain prepared historical seeds and their checks. Preparation is not an AEL offspring-generation result. No completed FunSearch best-shot or MCTS-AHD e2/s1 comparison was identified in the inspected study records.

Evidence paths and file hashes are listed in `reference_audit.json`. The underlying research reports remain unchanged.

## Draft library: what is ready to review

`prompt_catalogue.json` distinguishes paper source, operator, parent requirements, adaptation, template path and execution status. Every new template is marked **unexecuted**.

| Template IDs | Context needed | Current preparation status |
|---|---|---|
| `eoh_e1_new_form`, `eoh_e2_shared_idea` | At least two distinct parent programs, identities and provenance | Draft prompt text. Pair selection remains to be specified; using two parents differs from the paper experiment's reported five-parent setting. |
| `eoh_m1_revision`, `eoh_m2_parameters`, `eoh_m3_simplification` | One parent program and its provenance | Draft text using the paper's operator meanings. These are not new outcome records. |
| `ael_crossover`, `ael_mutation` | Two parents for crossover; one for mutation | Draft text. Historical seeding and the N=26 contract are explicit adaptations. |
| `mcts_e2_base_donor` | Explicit BASE and DONOR programs with separate provenance | Draft text following the source prompt's base/reference transfer idea. No claim of an MCTS selection schedule. |
| `funsearch_best_shot` | Two implementations with comparable measured fitness and a versioned completion adapter | Source mechanism documented; adapter and response-to-function normalization are not prepared here. Archived scores must not be used as comparable current-budget measurements. |
| `mcts_s1_lineage` | At least two distinct programs with recorded evolutionary lineage | Source mechanism documented; the required eligible path has not been selected. NBN edges alone are insufficient. |

The shared function/output requirements reuse the existing research interface. The draft single-block format stores the short method description inside a docstring, unlike papers that request a description outside the code. That formatting choice is an adaptation required for our current extraction screen.

## Practical interpretation of the second message

1. Use the supplied papers to obtain identifiable prompt mechanisms, with exact provenance.
2. Examine different historical program mechanisms and NBN identities, including alternatives beyond the latest high-score parent pool.
3. Then specify a controlled comparison of the selected prompts and parents. Model, evaluator, budgets, score provenance and failure accounting must be explicit before execution.
4. Use the tracking feature to preserve every attempt and strategy change. Assess quality and structural diversity from results, not from a different filename or visual position alone.

This review completes the reading/preparation portion. The additional paper-based prompt/parent combinations still need an agreed experimental design and actual measurements. No new packing result, parent fitness, experiment registration, model call, graph rebuild or server job is claimed by this review.
