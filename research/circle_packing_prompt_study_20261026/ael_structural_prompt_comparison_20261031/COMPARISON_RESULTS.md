# AEL matched structural/import prompt follow-up

Status: **completed_verified**. Saved baseline: 12 calls. New condition: 12 calls, 1 valid outputs. New best score: 2.109108; target hits >=2.6360: 0.

| Policy | Operator | Baseline valid | New valid | Baseline best | New best |
|---|---|---:|---:|---:|---:|
| uniform | cross | 2/3 | 0/3 | 2.533807 | — |
| uniform | mut | 3/3 | 0/3 | 2.533807 | — |
| nbn_stratified | cross | 1/3 | 0/3 | 1.860415 | — |
| nbn_stratified | mut | 2/3 | 1/3 | 2.109108 | 2.109108 |

Baseline has 11 selected-parent body matches and 4 missing-name exceptions. The new condition has 3 matches and 3 missing-name exceptions.

This compares a joint structural-change/import-completeness prompt intervention against saved prior baseline outcomes. Baseline calls were not repeated. Crossover inputs are matched historical pairs/seeds. Mutation inputs are actual new crossover outputs, so mutation comparisons concern the workflow, not an isolated mutation-prompt effect. The sequential small sample, potentially varying shared-host load and bundled instruction change prevent strong causal or superiority claims. Fingerprint differences do not establish algorithmic diversity without source inspection. Failed fitness stays undefined. No new NBN placement or official-verifier equivalence is claimed.

The allocation amendment in PRE_REGISTRATION_AMENDMENT.json preserves its original prepared version. Model/build/template/context/sampling and evaluator stay pinned. Read PROTOCOL.md, PROMPT_CHANGES.diff, exact call folders and platform history for the complete process. Research results are never repaired or replaced during reporting.

Source inspection: [MECHANISM_REVIEW.md](MECHANISM_REVIEW.md). All three parent-body matches in the new condition are preserved; the only valid packing repeats the matched baseline packing. Changed code by itself did not establish successful structural diversity.
