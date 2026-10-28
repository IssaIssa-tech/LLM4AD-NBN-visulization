"""Prepare identical prompts for a new model package; no inference."""
import hashlib,json,shutil
from pathlib import Path
root=Path(__file__).resolve().parents[1];source=root/'output/regional_prompt_comparison_draft_20261028';out=root/'output/coder7b_comparison_draft_20261028'
if out.exists():raise SystemExit('Existing draft; inspect rather than overwrite')
m=json.loads((source/'draft_comparison_manifest.json').read_text(encoding='utf-8'));out.mkdir();mapping={}
for r in m['unique_requests']:
    old=r['request_id'];prompt=(source/old/'prompt.txt').read_text(encoding='utf-8')
    payload=dict(model='qwen2.5-coder:7b',temperature=.1,num_predict=1800,sampling_seed=r['sampling_seed'],prompt=prompt)
    digest=hashlib.sha256(json.dumps(payload,sort_keys=True).encode()).hexdigest();new='request-'+digest[:16];mapping[old]=new
    folder=out/new;folder.mkdir();(folder/'prompt.txt').write_text(prompt,encoding='utf-8');shutil.copyfile(source/old/'parent_candidate.py',folder/'parent_candidate.py')
    r.update(request_id=new,comparison_baseline_request_id=old,request_sha256=digest)
for slot in m['analytical_slots']:slot['request_id']=mapping[slot['request_id']]
m.update(status='draft_not_registered_not_executed',execution_revision_id='coder7b-comparison-20261028',previous_condition='regional-prompt-comparison-20261028',amendment='Change model package only; retain original broad-comparison prompt text, parent pools, sampling seeds and evaluator',
    execution_gate='Runner currently pins old model and endpoint; do not execute this draft with it. Complete download/digest verification, choose resource allocation, freeze context/template and device settings, verify prompt fit, then register new runner before calls.')
m['budget']['model']='qwen2.5-coder:7b'
m['before_execution']=['Model download and full digest verified','No shared job disruption; explicit serving/device configuration frozen','Prompt token counts and context fit checked without truncation','New model-aware runner audited and frozen; original runner is pinned to qwen2.5:3b','Platform history registration and evaluator equality verified']
(out/'draft_comparison_manifest.json').write_text(json.dumps(m,indent=2),encoding='utf-8')
(out/'PREPARATION_STATUS.md').write_text('''# Coder 7B comparison preparation

Draft only: fourteen unique new-model requests, sixteen analytical slots with shared calls explicit. Uses the first broad comparison's exact prompt text and seven unique historical references, not the later checklist/repair prompts. The source condition was chosen before new-model outputs exist. Pair each new request with its saved baseline ID. No repairs, retries, resampling or candidate edits. The twenty-second research evaluator and 1800-token generation cap remain proposed unchanged. Different tokenizers/templates mean this is a model-package comparison, not a pure size effect.

A private CPU-only download service was started at hits_1 loopback 11436 with its model cache under /mnt/data/dyy/llm4ad_nbn_research_20261013/platform_history_20261028/coder7b_preparation_20261028/models. GPU visibility is -1. Other Ollama services and jobs were not changed. Download is preparation, not an experimental call. No GPU allocation is assumed from free-memory readings.

The old runner pins qwen2.5:3b and endpoint 11435. Do not pass this draft to that runner as an experiment. A new model-aware execution configuration must be implemented, checked and frozen after installation and resource checks. Exact model digest, template, context fit, serving device and environmental snapshot are still registration gates. No inference or benchmark has started. Do not infer a faster runtime or better score in advance.
''',encoding='utf-8')
print(out)
