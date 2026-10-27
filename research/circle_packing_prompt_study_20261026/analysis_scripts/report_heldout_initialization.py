"""Summarize frozen validation results without altering source outcomes."""
import json,statistics
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]
BASE=ROOT/'output/circle_prompt_effects_20261026'
data=json.loads((BASE/'heldout_initialization_validation_20261027/results.json').read_text())
rows=data['matched_results'];assert len(rows)==10
deltas=[r['score_difference'] for r in rows if r['score_difference'] is not None]
valid={k:sum(r[k]['status']=='valid' for r in rows) for k in ('original','feasible')}
wins=sum(d>0 for d in deltas);losses=sum(d<0 for d in deltas);ties=sum(d==0 for d in deltas)
means={k:statistics.mean(r[k]['score'] for r in rows if r[k]['status']=='valid') for k in valid}
support=valid['feasible']>=valid['original'] and bool(deltas) and statistics.mean(deltas)>0 and wins>losses
table=['| Seed | Original score/status | Feasible score/status | Difference |','|---|---:|---:|---:|']
for row in rows:
    show=lambda k:f"{row[k]['score']:.12f}" if row[k]['status']=='valid' else row[k]['status']
    delta='unmeasured' if row['score_difference'] is None else f"{row['score_difference']:+.12f}"
    table.append(f"| {row['sobol_seed']} | {show('original')} | {show('feasible')} | {delta} |")
text=f'''# Held-out initialization validation

The two algorithms were frozen before evaluating ten previously unused Sobol seeds, 20261201–20261210. Both members of every pair were evaluated contemporaneously on the university server, alternating condition order. NumPy seed 2025, original probabilistic acceptance, n=26, the geometry evaluator and a 20-second limit were fixed. No LLM calls, repairs, replacement seeds, parameter tuning or optional stopping occurred. These are prepared-code algorithm comparisons.

{chr(10).join(table)}

## Registered decision

- Valid original: {valid['original']}/10; valid feasible: {valid['feasible']}/10.
- Paired differences available: {len(deltas)}/10.
- Feasible wins/losses/ties: {wins}/{losses}/{ties}.
- Mean original score among valid outputs: {means['original']:.15f}.
- Mean feasible score among valid outputs: {means['feasible']:.15f}.
- Mean paired difference: {statistics.mean(deltas):+.15f}.
- Median paired difference: {statistics.median(deltas):+.15f}.
- Registered improvement criterion satisfied: **{support}**.

The registered criterion requires no lower valid count, positive mean paired difference, and more wins than losses. It is a descriptive decision rule, not a statistical significance test.

## Algorithm-selection implication

{'The validation supports the feasible initialization choice on this fixed held-out cohort. It does not establish universal superiority.' if support else 'This validation does not support replacing original initialization with feasible initialization as a generally better choice. The earlier four-of-five exploratory gain does not establish a reliable improvement on new seeds. Retain the original initialization as the reference and report feasible initialization as a mixed-result alternative.'}

Keep this cohort separate from the exploratory five seeds. Do not select a new mechanism or winning seed using these results and then describe that selection as independently validated. A best observed score is a descriptive maximum, not a new independent confirmation. The code-region analysis remains the prior result: explored feasible variants stayed in the same historical top-level branch. These twenty validation programs were not added to that graph by this validation.

## Limits and evidence

Ten fixed consecutive seeds, one task size, one NumPy seed and one environment; no random-sampling or broad-generalization claim. Every invalid/timeout result remains in the ledger and is not assigned an invented score. Raw records, hashes, manifest, source, environment and stopping rule are in `heldout_initialization_validation_20261027/`. The existing exploratory graph and reports remain preserved.

Environment: {json.dumps(data['environment'])}.
'''
out=BASE/'HELDOUT_INITIALIZATION_RESULT.md'
if out.exists():raise SystemExit('Existing report; refusing overwrite')
out.write_text(text,encoding='utf-8');print(text)
