"""Index existing immutable records and new NBN links without duplicating datasets."""
import hashlib,json,subprocess
from pathlib import Path
base=Path(__file__).resolve().parents[1];repo=base/'LLM4AD-NBN-visualization-github';study=repo/'research/circle_packing_prompt_study_20261026';out=base/'output/ael_nbn_analysis_20261031'
sha=lambda raw:hashlib.sha256(raw).hexdigest()
canonical=lambda value:json.dumps(value,sort_keys=True,separators=(',',':'),ensure_ascii=False,allow_nan=False).encode()
load=lambda p:json.loads(p.read_text(encoding='utf-8'))
m=load(out/'INPUT_MANIFEST.json');event_index=load(out/'ORIGINAL_EVENT_INDEX.json');analysis=load(out/'NBN_ANALYSIS.json');artifact=load(out/'PLATFORM_ANALYSIS_VERIFICATION.json')['artifact_id'];histories=[];programs=[];all_event_ids=set()
for h in m['histories']:
    source=study/h['repo_path'];snapshot=load(source);protected=[e for e in event_index['events'] if e['revision_id']==h['revision_id']]
    assert len(protected)==h['event_count'] and sha(source.read_bytes())==h['file_sha256']
    for event in protected:assert event['event_id'] not in all_event_ids;all_event_ids.add(event['event_id'])
    histories.append(dict(revision_id=h['revision_id'],role='original_experiment_or_preparation',history_file=h['repo_path'],file_sha256=h['file_sha256'],canonical_events_sha256=h['canonical_events_sha256'],event_count=h['event_count'],events=protected))
derived=load(out/'analysis_history.json');derived_events=[]
for e in derived['events']:
    raw=json.dumps(e,ensure_ascii=False,allow_nan=False,sort_keys=True).encode()
    derived_events.append(dict(revision_id=e['revisionId'],event_id=e['id'],event_type=e['eventType'],timestamp_utc=e['timestampUtc'],sha256=sha(raw),bytes=len(raw)))
histories.append(dict(revision_id=derived['revisionId'],role='derived_analysis_only_no_generation',history_file='ael_nbn_analysis_20261031/analysis_history.json',file_sha256=sha((out/'analysis_history.json').read_bytes()),canonical_events_sha256=sha(canonical(derived['events'])),event_count=len(derived['events']),events=derived_events))
views={h['revision_id']:load(study/h['repo_path'])['view'] for h in m['histories']}
for p in m['programs']:
    row=next(r for r in views[p['origin_revision_id']]['attempts'] if r['id']==p['call_id']);meta=next(r for r in analysis['programs'] if r['id']==p['id']);source=study/p['source_file'];assert sha(source.read_bytes())==p['code_sha256']
    prompt=source.parent/'prompt.txt';response=source.parent/'raw_response.json';request=source.parent/'api_payload.json'
    assert sha(canonical(load(request)))==sha(canonical(row['request'])) and sha(canonical(load(response)))==sha(canonical(row['response']))
    parents=[]
    for parent in row['parents']:
        if parent.get('originCallId'):
            origin=parent.get('originRevisionId') or p['origin_revision_id'];resolved=f"generated:{origin}:{parent['originCallId']}"
            producer=next(q for q in m['programs'] if q['id']==resolved);assert parent['codeSha256']==producer['code_sha256']
            assert sha(parent['recordedSource'].encode())==producer['code_sha256']
            parents.append(dict(kind='generated_parent',recorded_id=parent['id'],origin_call_id=parent['originCallId'],resolved_origin_revision_id=origin,revision_resolution='explicit' if parent.get('originRevisionId') else 'same recorded experiment containing the originating call',resolved_analysis_node_id=resolved,code_sha256=parent['codeSha256']))
        else:
            assert parent.get('nbnNodeId') is not None and sha(parent['functionPreview'].encode())==parent['codeSha256']
            parents.append(dict(kind='historical_parent',historical_id=parent['id'],nbn_node_id=parent['nbnNodeId'],historical_region_index=parent['regionIndex'],code_sha256=parent['codeSha256'],source_graph_artifact_id=m['source_graph_identity']['artifactId']))
    programs.append(dict(analysis_node_id=p['id'],origin_revision_id=p['origin_revision_id'],call_id=p['call_id'],evaluation_status=p['evaluation_status'],score=p['score'],code_sha256=p['code_sha256'],source_file=p['source_file'],prompt_sha256=sha(prompt.read_bytes()),request_semantic_sha256=sha(canonical(row['request'])),response_semantic_sha256=sha(canonical(row['response'])),parents=parents,nearest_historical=meta['nearest_historical'],measured_nbn_artifact_id=artifact,measured_nbn_node_id=p['id'],fitness_ranked=p['evaluation_status']=='valid',truncation=meta['truncation']))
# Preserve original tracked case files and selected source programs by reference/hash.
case_names=['ael_parent_eligibility_20261031','ael_operator_pilot_20261031','ael_structural_prompt_comparison_20261031'];prefix='research/circle_packing_prompt_study_20261026/'
tracked=subprocess.check_output(['git','-C',str(repo),'ls-files','-z','--',*[prefix+n for n in case_names]]).decode().split('\0');paths={name[len(prefix):] for name in tracked if name}
paths.update(d['candidate']['original_candidate_path'] for d in m['historical_diagnostics'])
protected=[]
for name in sorted(paths):
    path=study/name;protected.append(dict(path=name,sha256=sha(path.read_bytes()),bytes=path.stat().st_size))
index=dict(schema_version=1,scope='The two AEL batches, their historical eligibility check, follow-up preparation, and derived NBN analysis. Older unrelated studies are not silently included.',original_event_count=205,derived_event_count=len(derived['events']),generated_program_count=24,generated_valid=9,generated_failed=15,historical_diagnostic_count=30,histories=histories,programs=programs,protected_artifacts=protected,source_graph_identity=m['source_graph_identity'],historical_archive_reference=dict(path=m['historical_graph_repo_path'],sha256=m['source_graph_identity']['inputDigest'],included_in_tracking_copy=False,reason='Existing tracked 14000-record archive is reused; no duplicate dataset or model weights'),restore_instructions='Use restore_ael_tracking_20261031.py with the existing repository and a new destination. Event records, candidate source and prompt bytes are verified. Requests/responses are also checked for JSON-value equality. Candidate programs are never executed.')
(out/'TRACKING_INDEX.json').write_text(json.dumps(index,indent=2,allow_nan=False),encoding='utf-8',newline='\n')
print('Preservation index:',len(histories),'histories,',205+len(derived['events']),'events,',len(programs),'generated programs,',len(protected),'existing artifacts referenced')
