"""Freeze the saved 24-program cohort and four original histories; no executions."""
import hashlib,json,shutil
from pathlib import Path
base=Path(__file__).resolve().parents[1];out=base/'output/ael_nbn_analysis_20261031';assert not out.exists()
study=base/'LLM4AD-NBN-visualization-github/research/circle_packing_prompt_study_20261026'
sha=lambda raw:hashlib.sha256(raw).hexdigest()
load=lambda p:json.loads(p.read_text(encoding='utf-8'))
cases=['ael_operator_pilot_20261031','ael_structural_prompt_comparison_20261031'];programs=[];histories=[]
for case in ['ael_parent_eligibility_20261031',*cases]:
    root=base/'output'/case
    if (root/'ARTIFACT_INTEGRITY.json').exists():
        inventory=load(root/'ARTIFACT_INTEGRITY.json')
        for row in inventory['files']:assert sha((root/row['path']).read_bytes())==row['sha256'],(case,row['path'])
    else:
        assert case=='ael_parent_eligibility_20261031'
        saved=load(root/'results.json');assert saved['results']==[json.loads(line) for line in (root/'ledger.jsonl').read_text(encoding='utf-8').splitlines()]
        reg=load(root/'registration.json')['frozen'];assert sha((root/'manifest.json').read_bytes())==reg['manifest_sha256']
        for r in saved['results']:
            source=(study/r['candidate']['original_candidate_path']).read_text(encoding='utf-8').strip()
            assert sha(source.encode())==r['candidate']['canonical_code_sha256']
    filename='platform_history.json';history=load(root/filename)
    histories.append(dict(revision_id=history['revisionId'],local_path=f'{case}/{filename}',repo_path=f'{case}/{filename}',file_sha256=sha((root/filename).read_bytes()),event_count=len(history['events']),canonical_events_sha256=sha(json.dumps(history['events'],sort_keys=True,separators=(',',':'),ensure_ascii=False).encode())))
    if case not in cases:continue
    outcomes=load(root/'results.json')['results'];view={a['id']:a for a in history['view']['attempts']}
    for r in outcomes:
        call=r['call_id'];source=root/call/'candidate.py';assert source.is_file()
        code=source.read_text(encoding='utf-8');assert sha(code.encode())==r['code_sha256']
        assert view[call]['status']==r['status'] and view[call]['score']==r.get('score')
        programs.append(dict(id=f"generated:{history['revisionId']}:{call}",origin_revision_id=history['revisionId'],call_id=call,case=case,operator=r['operator'],selection_policy=r['policy'],evaluation_status=r['status'],score=r.get('score'),code_sha256=sha(code.encode()),embedding_source_sha256=sha(code.strip().encode()),source_file=f'{case}/{call}/candidate.py',parents=view[call]['parents'],evaluation_id=r.get('evaluation_id'),history_file=f'{case}/{filename}'))
prep=base/'output/ael_structural_prompt_comparison_20261031/preparation_history_final.json';h=load(prep)
histories.append(dict(revision_id=h['revisionId'],local_path='ael_structural_prompt_comparison_20261031/preparation_history_final.json',repo_path='ael_structural_prompt_comparison_20261031/preparation_history_final.json',file_sha256=sha(prep.read_bytes()),event_count=len(h['events']),canonical_events_sha256=sha(json.dumps(h['events'],sort_keys=True,separators=(',',':'),ensure_ascii=False).encode())))
assert len(programs)==24 and sum(h['event_count'] for h in histories)==205
parents=load(base/'output/ael_parent_eligibility_20261031/results.json')['results']
registration=load(base/'output/ael_parent_eligibility_20261031/registration.json')['frozen']
for case in cases:
    reg=load(base/'output'/case/'registration.json')['frozen'];assert reg['evaluator_hashes']==registration['evaluator_hashes'] and reg['numpy']==registration['numpy'] and reg['scipy']==registration['scipy']
manifest=dict(status='prepared_analysis_only',analysis_revision_id='ael-nbn-analysis-20261031',generation_calls=0,candidate_executions=0,cohort=dict(generated_programs=24,generated_valid=9,generated_failed=15,historical_diagnostic_records=30,historical_valid=22,historical_timeouts=8),source_graph_identity=registration['source_graph_identity'],source_graph_reconciliation=registration['graph_source_reconciliation'],historical_graph_repo_path='historical_data/circle_packing_historical_nbn_14000.json',historical_cache='/mnt/data/dyy/llm4ad_nbn_research_20261013/runs/m2ip_exact_nbn_20261027/visual_platform/.codet5_embeddings_cache.sqlite3',embedding_model_path='/mnt/data/dyy/llm4ad_nbn_research_20261013/private_codet5_env_20261027/model',embedding_python='/mnt/data/dyy/llm4ad_nbn_research_20261013/private_codet5_env_20261027/bin/python',histories=histories,programs=programs,historical_diagnostics=[dict(candidate=r['candidate'],evaluation_status=r['evaluation']['status'],score=r['evaluation'].get('score'),evaluation_id=r['evaluation_id']) for r in parents],evaluation_provenance=dict(evaluator_hashes=registration['evaluator_hashes'],python=registration['python'],numpy=registration['numpy'],scipy=registration['scipy'],numerical_threads=registration['numerical_thread_limits'],budget_seconds=20),analysis_rules=dict(archive_context='Fixed 14000-node archived HNSW graph; nearest historical code matches are similarity associations, not new NBN edges',measured_nbn='Exact cosine nearest neighbor among strictly greater measured fitness. Only the 22 valid historical diagnostics and nine valid generated evaluations are eligible. Equal fitness is not better; retain all maximum-score roots.',unscored='Keep 23 failed/timeout records in analysis/history without numeric fitness or nearest-better edges',historical_regions='First descendant below the frozen historical HNSW root; a code-space proxy, not a proven physical basin',projection='Fit PCA on cached historical vectors only; project generated vectors into that same fitted transform. Height in archive view is PCA, not fitness.',representation_check='Verify model assets; recompute declared historical anchors and compare against cache before using new vectors; report token truncation and similarity limitations',duplicate_policy='Retain each experiment record; reuse embedding work by stripped-source hash, report source/AST/body/packing identities separately'))
out.mkdir();(out/'INPUT_MANIFEST.json').write_text(json.dumps(manifest,indent=2,allow_nan=False),encoding='utf-8',newline='\n')
paper=Path('C:/Users/ISSA/Desktop/my research/Nearest-Better_Network_for_Visualizing_and_Analyzing_Combinatorial_Optimization_Problems_A_Potential_Unified_Tool.pdf')
(out/'METHOD.md').write_text('''# AEL generated-program NBN analysis and history preservation

Analyze the 24 saved programs from the two completed AEL batches, including all 15 failures. Reuse the 30 historical-parent diagnostic results, including eight timeouts. No optimization program is generated, repaired or executed during this work.

Preserve and verify four original histories (205 events): parent diagnostic, original AEL pilot, revised-prompt preparation and revised-prompt execution. Original event identities, prompts, source snapshots, lineage and scores remain unchanged. A separate preservation index links the existing files by hash; the 14,000-record archive is not copied into another Git dataset.

The paper's definition in Eq.(1), PDF page 3 / printed page 1197, uses f(y)>f(x). The measured comparison therefore uses strictly greater observed fitness and leaves all equal-maximum programs as roots. Do not add equal-fitness convenience links merely to force a single tree. Preserve the pre-existing historical HNSW graph and its own construction conventions as a separately identified archived context.

For all 24 generated sources, compute CodeT5+ cosine nearest historical matches using the exact verified historical cache/model representation. Count positional association with frozen HNSW branches separately from an actual new NBN parent. Use source/AST/body identity, distance-to-parent and distance-to-nearest-archive distributions to examine copying and region concentration. A nearest code match alone does not prove functional equivalence or a physical basin. Historical sampling is biased; low coverage is not proof of an unexplored optimization basin.

Archived fitness and present 20-second fitness are not silently combined. Build an exact measured-only NBN using the 22 valid historical diagnostics and nine valid generated evaluation records. Keep all 54 records inspectable; 23 records with unavailable/invalid fitness have no fitness-based parent. Include all tied maxima as roots. Report record-level and source/packing deduplication counts separately.

Verify that new embeddings are compatible with the read-only historical cache by recomputing historical anchor programs. Record model/tokenizer hashes, environment, preprocessing, max token length, anchor errors and cache coverage. Preserve the 14,000 historical vectors without re-embedding or modifying the source cache. Store newly computed vectors and the PCA transform as reproducibility artifacts. Full returned-coordinate checks and original errors remain linked to their recorded outcomes.

Create an interactive 3D review of archived context and the measured NBN with visibly distinct edge meanings, score provenance and failed statuses. Preserve all analysis outputs in a separate revision and link each analyzed node to its original experiment call. Completion means measured analysis and a restorable tracking backup, not reaching 2.6360 or validating the paper's general landscape theory for code embeddings.
''',encoding='utf-8',newline='\n')
(out/'PAPER_SOURCE.json').write_text(json.dumps(dict(path=str(paper),sha256=sha(paper.read_bytes()),definition='Eq.(1), PDF page 3 / printed page 1197: strictly better f(y)>f(x)',application='CodeT5 cosine over programs is this research adaptation, not a distance asserted by the paper'),indent=2),encoding='utf-8')
print(json.dumps(dict(programs=24,historical_records=30,original_events=205,output=str(out))))
