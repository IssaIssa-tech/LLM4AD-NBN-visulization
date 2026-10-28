"""Describe all fixed regional-reference checks without dropping failures."""
import json
from collections import Counter
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1];OUT=ROOT/'output/regional_representatives_20261028'
def main():
    data=json.loads((OUT/'results.json').read_text());manifest=data['manifest']
    counts=Counter(row['evaluation']['status'] for row in data['results'])
    lines=['# Regional historical references: selection and execution checks','',
        'The selected programs are references from the frozen imported HNSW NBN. This is not a new algorithm-generation experiment. The operational regions are first descendants under the unique global root, with that root treated separately. The chosen sampling rule is proposed, not an empirically optimal selection strategy.','',
        f"Source graph SHA-256: `{manifest['source_graph_sha256']}`.",
        'Region support thresholds: at least 20 members and five positive archived scores. Select the four supported regions with highest archived best score. Within each, select distinct-code programs nearest the 100th, 50th and 10th positive-score rank percentiles. Include the historical champion separately. Every reference was frozen before evaluation.','',
        '## All outcomes','',
        '| Region / role | Historical sample | Archived score | Current outcome | Current score |','|---|---:|---:|---|---:|']
    for row in data['results']:
        r=row['reference'];e=row['evaluation'];score=f"{e['score']:.12f}" if e['status']=='valid' else 'unmeasured'
        lines.append(f"| {r['reference_id']} | {r['sample_order']} | {r['archived_score']:.12f} | {e['status']} | {score} |")
    lines+=['','Outcome counts: '+json.dumps(dict(counts))+'.','',
        '## Interpretation','',
        'The 20-second limit is a frozen research-budget diagnostic, not a rule established from the official challenge verifier. The approved-import static screen and isolated worker save actual coordinates for returned arrays, including invalid/non-finite results. Missing coordinates on timeouts or exceptions remain missing. The diagnostic namespace contains NumPy as np, matching the earlier standalone research evaluator; it does not reconstruct an arbitrary historical environment.','',
        'The historical stored score is not overwritten. A timeout or rejection does not prove that a region is poor, and a changed score does not establish that the archived result was wrong. Different dependencies, entry-point wrappers, runtime budgets or hardware can affect execution. Prior reevaluations are retained as separate provenance rather than silently reused as current results.','',
        'Regions of this HNSW snapshot differ from the earlier exact rebuilt graph. Reports must identify the graph used; old branch labels must not be carried over automatically. A top-level branch is a code-space grouping, not proof of a physical attraction basin.','',
        '## What this enables next','',
        'Use these measured outcomes to define execution-eligible parent pools under the stated budget, while preserving references from every selected region. Do not launch prompts until the parent-selection comparison, prompt variants, model identity, equal call budget, seed allocation and failure policy are registered. If a selected region has no eligible reference, record that limitation and decide explicitly whether to expand its frozen reference pool or change the common evaluator budget; do not silently remove it.','',
        'The current target is score at least 2.6360 plus structural diversity, as stated in the new instructions. Official verifier compatibility remains unresolved; current scores are research-evaluator outcomes only. No LLM call was made in this step.','',
        '## Reproducibility','',
        f"Environment: `{json.dumps(data['environment'])}`.",
        f"Platform history revision: `{data['platform_revision_id']}`.",
        'Selection manifest, source code hashes, graph/node IDs, per-reference outputs, full coordinates where available, ledger and environment are preserved alongside this report. The original datasets and prior studies remain unchanged.']
    target=OUT/'REGIONAL_REFERENCE_REPORT.md'
    if target.exists():raise SystemExit('Existing report; refusing overwrite')
    target.write_text('\n'.join(lines)+'\n',encoding='utf-8');print(json.dumps(dict(counts=counts,report=str(target)),indent=2))
if __name__=='__main__':main()
