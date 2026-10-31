# Second-message preparation: prompts and historical references

Main next paper: **AEL**. Existing experiment baseline: **EoH**. Supplementary prompt references reviewed: **FunSearch** and **MCTS-AHD**.

- `PAPER_PROMPT_CATALOGUE.md`: paper sources, operator meanings, old-label mapping, what already exists, and what remains untested.
- `prompt_catalogue.json` and `templates/`: eight draft Circle Packing prompt adaptations from EoH/AEL/MCTS-AHD. Two further mechanisms are documented with unmet prerequisites rather than represented as ready prompts.
- `PARENT_REFERENCE_REVIEW.md`: all 13 existing reference outcomes and three additional parent options absent from the completed 2026-10-31 parent pool.
- `reference_audit.json`: full source/NBN IDs, code hashes, existing measured outcomes, static source inventories, source-PDF hashes and evidence-file hashes.
- `integrity_check.json`: counts and template/reference integrity checks.

No new LLM call, candidate evaluation, graph rebuild, experimental registration, or university-server job was performed. Original outcome data and the exported history file in the repository root were left unchanged. This is preparation for deciding what to test, not a claim that the supervisor's scientific comparison has been completed.

All original selected source programs already exist under `regional_representatives_20261028/`. They are referenced by path/hash, rather than copied again. The 14,000-record dataset is not duplicated in this package.
