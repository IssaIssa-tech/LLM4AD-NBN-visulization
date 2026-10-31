"""Freeze a 30-program historical eligibility diagnostic, without execution."""
import ast,hashlib,json,zipfile
from datetime import datetime,timezone
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]
BASE=ROOT/'LLM4AD-NBN-visualization-github/research/circle_packing_prompt_study_20261026'
SOURCE=BASE/'paper_studies/ael/runtime_safe_seed_shortlist_20261026'
OUT=ROOT/'output/ael_parent_eligibility_20261031'
if OUT.exists():raise SystemExit('Existing eligibility preparation; inspect instead of replacing')
sha=lambda data:hashlib.sha256(data).hexdigest()
original=json.loads((SOURCE/'shortlist_manifest.json').read_text())
graph_path=BASE/'historical_data/circle_packing_historical_nbn_14000.json'
graph_bytes=graph_path.read_bytes();graph=json.loads(graph_bytes)['graph'];by_id={n['id']:n for n in graph['nodes']};by_index={n['ofecIndex']:n for n in graph['nodes']}
root=next(n['ofecIndex'] for n in graph['nodes'] if n['ofecIndex']==n['ofecParentIndex'])
def branch(index):
    seen=set()
    while index!=root:
        assert index not in seen;seen.add(index);parent=by_index[index]['ofecParentIndex']
        if parent==root:return by_index[index]
        index=parent
    return by_index[index]
candidates=[];archive_sources={};variants={}
for item in original['candidates']:
    source=SOURCE/item['candidate_code_file'];raw=source.read_bytes();text=source.read_text(encoding='utf-8');node=by_id[item['historical_id']]
    assert sha(text.strip().encode())==item['code_sha256']==sha(node['functionPreview'].strip().encode())
    ast.parse(text);region=branch(node['ofecIndex']);identifier='sample-'+str(item['sample_order'])
    path=f'candidates/{identifier}.py';archive_sources[path]=raw
    for digest in {sha(raw),sha(text.encode()),sha(text.strip().encode()),sha(text.replace('\n','\r\n').encode())}:variants.setdefault(digest,set()).add(identifier)
    candidates.append(dict(candidate_id=identifier,shortlist_rank=item['shortlist_rank'],sample_order=item['sample_order'],node_id=item['historical_id'],nbn_node_id=node['nbnNodeId'],region_node_id=region['id'],region_index=region['ofecIndex'],archived_score=item['historical_raw_score'],archived_score_role='archived_provenance_not_current_fitness',canonical_code_sha256=item['code_sha256'],transport_bytes_sha256=sha(raw),candidate_file=path,original_candidate_path=source.relative_to(BASE).as_posix(),original_shortlist_branch_index=item['top_level_nbn_branch_index']))
assert len(candidates)==30 and len({c['canonical_code_sha256'] for c in candidates})==30
# Look for completed outcomes by code identity, not just folder name.
matches=[];scanned=0;seen_files=set()
def inspect(value,path):
    if isinstance(value,dict):
        digest=value.get('code_sha256')
        if digest in variants and 'status' in value and any(k in value for k in ('score','runtime_seconds','wall_runtime_seconds')):
            matches.append(dict(path=str(path.relative_to(ROOT)),candidate_ids=sorted(variants[digest]),status=value['status'],score=value.get('score'),matched_code_hash=digest))
        for child in value.values():inspect(child,path)
    elif isinstance(value,list):
        for child in value:inspect(child,path)
for location in [ROOT/'output',BASE]:
    for path in location.rglob('*'):
        if not path.is_file() or path.suffix not in ('.json','.jsonl') or path.stat().st_size>2_000_000:continue
        if any(part.startswith('browser_profile_') for part in path.parts) or 'research_history' in path.parts:continue
        if not any(token in path.name.lower() for token in ('result','evaluation','outcome','precheck','ledger')):continue
        if path in seen_files:continue
        seen_files.add(path);scanned+=1
        try:
            text=path.read_text(encoding='utf-8-sig')
            if path.suffix=='.jsonl':
                for line in text.splitlines():
                    if line.strip():inspect(json.loads(line),path)
            else:inspect(json.loads(text),path)
        except (ValueError,UnicodeError):continue
OUT.mkdir()
audit=dict(scanned_result_files=scanned,scope='Local output and tracked research bundle; result/evaluation/outcome/precheck/ledger JSON or JSONL <=2MB; raw event folders excluded',source_hash_variants='file bytes, LF text, stripped LF text, reconstructed CRLF text',matching_completed_outcomes=matches)
(OUT/'PRIOR_OUTCOME_AUDIT.json').write_text(json.dumps(audit,indent=2),encoding='utf-8')
if matches:raise SystemExit('Prior outcome matches found; inspect and reconcile before execution')
manifest=dict(status='prepared_fixed_diagnostic_not_executed',prepared_utc=datetime.now(timezone.utc).isoformat(),execution_revision_id='ael-parent-eligibility-20261031',purpose='AEL historical-parent eligibility check; no LLM generation and no claim of an evolved algorithm',source_platform_revision='circle-history-verified-20261028',source_graph_sha256=sha(graph_bytes),source_graph_backend=graph['graphBuildStats'],source_graph_path=graph_path.relative_to(BASE).as_posix(),source_shortlist_manifest=SOURCE.relative_to(BASE).as_posix()+'/shortlist_manifest.json',source_shortlist_sha256=sha((SOURCE/'shortlist_manifest.json').read_bytes()),mapping_policy='Historical program ID and stripped-source hash verified against the current frozen HNSW graph. Preserve the earlier shortlist branch separately; do not copy its exact-graph branch label into HNSW.',candidates=candidates,execution_order=[c['candidate_id'] for c in candidates],evaluation=dict(task_n=26,timeout_seconds=20,geometry_epsilon=1e-12,evaluator='Unchanged existing regional reference worker and static_screen/valid_circles implementation',execution='Sequential isolated subprocesses; 20-second cap includes worker startup; one execution per unique source',numerical_threads=dict(OPENBLAS_NUM_THREADS='1',OMP_NUM_THREADS='1',MKL_NUM_THREADS='1',NUMEXPR_NUM_THREADS='1'),eligibility='status valid, finite score >0; zero scores remain valid results but are not positive-fitness parent options',repairs=0,retries=0,target=2.6360),stopping_rule='Stop after all 30 prelisted candidates regardless of outcomes; no replacements, repairs, source edits, or LLM calls',prior_outcome_audit=audit,interpretation=['A single diagnostic execution establishes only observed completion/validity under this condition','Archived scores remain unchanged; do not pool them as current fitness','Explicit single-thread numerical settings are frozen for this diagnostic; prior shared-load timings are not causal comparisons','Source graph is HNSW operational code-space structure, not a proof of physical basins','Official challenge-verifier equivalence is unresolved'])
raw=json.dumps(manifest,indent=2).encode();(OUT/'manifest.json').write_bytes(raw)
with zipfile.ZipFile(OUT/'candidate_upload.zip','w',zipfile.ZIP_DEFLATED) as z:
    z.writestr('manifest.json',raw)
    for name,source in archive_sources.items():z.writestr(name,source)
print(json.dumps(dict(candidates=len(candidates),result_files_scanned=scanned,previous_outcome_matches=len(matches),source_graph_sha256=manifest['source_graph_sha256'],regions=sorted({c['region_index'] for c in candidates}),manifest_sha256=sha(raw)),indent=2))
