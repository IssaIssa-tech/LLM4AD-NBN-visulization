"""Freeze the finite supervisor-directed GPU comparison, without model calls."""
import copy,hashlib,json,shutil
from datetime import datetime,timezone
from pathlib import Path
root=Path(__file__).resolve().parents[1];source=root/'output/coder7b_comparison_draft_20261028';out=root/'output/nbn_prompt_comparison_gpu_20261031'
if out.exists():raise SystemExit('Existing condition; inspect rather than overwrite')
manifest=json.loads((source/'draft_comparison_manifest.json').read_text(encoding='utf-8'));out.mkdir();mapping={}
sampling=dict(temperature=.1,top_k=40,top_p=.9,min_p=0.0,repeat_penalty=1.0,max_tokens=1800,stream=False)
for request in manifest['unique_requests']:
    old=request['request_id'];prompt=(source/old/'prompt.txt').read_text(encoding='utf-8')
    payload=dict(model='qwen2.5-coder-7b-q4km',messages=[dict(role='system',content='You are Qwen, created by Alibaba Cloud. You are a helpful assistant.'),dict(role='user',content=prompt)],seed=request['sampling_seed'],**sampling)
    digest=hashlib.sha256(json.dumps(dict(condition='nbn_prompt_comparison_gpu_20261031',payload=payload),sort_keys=True).encode()).hexdigest();new='request-'+digest[:16];mapping[old]=new
    folder=out/new;folder.mkdir();(folder/'prompt.txt').write_text(prompt,encoding='utf-8');shutil.copyfile(source/old/'parent_candidate.py',folder/'parent_candidate.py')
    (folder/'api_payload.json').write_text(json.dumps(payload,indent=2),encoding='utf-8')
    request.update(request_id=new,failed_serving_condition_request_id=old,request_sha256=digest,payload_sha256=hashlib.sha256(json.dumps(payload,sort_keys=True).encode()).hexdigest())
for slot in manifest['analytical_slots']:slot['request_id']=mapping[slot['request_id']]
manifest.update(status='prepared_not_executed',execution_revision_id='nbn-prompt-comparison-gpu-20261031',created_utc=datetime.now(timezone.utc).isoformat(),
    previous_condition='coder7b-comparison-20261028',amendment='Working hits9 GPU llama.cpp serving package; exact historical parents and user-prompt text retained; hits1 evaluator unchanged',
    serving=dict(runtime='llama.cpp b6780',generator_host='hits_9',evaluator_host='hits_1',context_size=8192,parallelism=1,cpu_threads=4,model_blob_sha256='60e05f2100071479f596b964f89f510f057ce397ea22f2833a0cfe029bfc2463',sampling=sampling),
    stopping_rule='Exactly fourteen unique registered attempts; sixteen slots explicitly reuse shared responses. No repair, manual patch, replacement request or adaptive extension.',
    inference_limit='Preliminary descriptive 2x2 comparison with one output per parent/profile and overlap; no strong causal ranking, guaranteed 2.6360 result, or proof of basin structure. Serving package differs from prior runs.')
manifest['budget'].update(model_calls=14,repair_calls=0,generation_timeout_seconds=900,per_generated_program_seconds=20)
manifest['before_execution']=['Verify model and runtime identity','Pin idle GPU and private generation service','Verify all prompt/parent hashes against original comparison','Register complete configuration and graph identity in platform history before requests']
(out/'draft_comparison_manifest.json').write_text(json.dumps(manifest,indent=2),encoding='utf-8')
(out/'PROTOCOL.md').write_text('''# Finite NBN selection × prompt comparison — 2026-10-31

Research question: whether selection of historical Circle Packing N=26 programs using NBN regions, together with prompt strategy, helps discover structurally diverse high-quality optimizers reaching 2.6360 under the named research evaluator.

Factors: quality-only top-four distinct archived programs versus the best representative of each of four supported NBN branches; standard M2 contract versus structural-exploration prompt. Use the exact saved original user prompts and parent source, paired deterministic sampling seeds, one response per parent/profile. Four cells of four analytical slots use fourteen unique requests because one parent overlaps; shared outcomes are not independent replications. Region definitions and HNSW graph identity are frozen, not asserted as physical attraction basins. Archived scores are textual context, not comparable twenty-second incumbents.

Generation uses verified Qwen2.5-Coder 7B Q4_K_M weights in private llama.cpp b6780 GPU serving on hits_9. Explicit common sampling: temperature 0.1, top_k 40, top_p 0.9, min_p 0, repeat_penalty 1, max_tokens 1800, context 8192. Runtime template/system prompt and exact weights/build hashes are recorded. Cross-package differences prevent interpreting this as a pure size ablation relative to earlier runs. Within this condition, generation configuration is identical across selection/prompt factors.

Keep evaluation on hits_1 using the existing twenty-second isolated worker, same source hashes and numpy/scipy environment. No repair, retries, replacement candidates, manual patches or extra rounds. Preserve generation errors, extraction/static failures, exceptions, invalid geometry, nonfinite outputs, timeouts, duplicates and successes. Record full prompts/responses, selected historical/NBN node identity, packing coordinates when available, scores and every event in platform history. No unavailable packing or fitness is invented.

Primary descriptive measures: valid fraction, error counts, valid score distribution and target hits per cell and unique call. Record source and AST duplicates separately from inspected mechanism diversity. Compare new code with historical embeddings/NBN only under a separately identified frozen representation; invalid/unmeasured programs remain in history without invented ranked fitness. No new NBN placement is implied merely by generation.

Stop after the fourteen attempts, regardless of target attainment. Report preliminary positive or negative findings without extending until success. Then connect supported parent/prompt choices to algorithm design; if evidence cannot select a reliable choice, state that limitation. No superiority or official challenge-verifier equivalence is assumed. Existing epsilon and twenty-second budget are research settings.
''',encoding='utf-8')
print(out)
