"""Restore preserved histories into a NEW directory; never run candidate programs.

Usage: python restore_ael_tracking_20261031.py --repo-root PATH --destination NEW_PATH
       [--index PATH] [--skip-artifacts]
"""
import argparse,hashlib,importlib.util,json,re,shutil
from pathlib import Path
def sha(raw):return hashlib.sha256(raw).hexdigest()
def canonical(value):return json.dumps(value,sort_keys=True,separators=(',',':'),ensure_ascii=False,allow_nan=False).encode()
def main():
    parser=argparse.ArgumentParser();parser.add_argument('--repo-root',required=True,type=Path);parser.add_argument('--destination',required=True,type=Path);parser.add_argument('--index',type=Path);parser.add_argument('--skip-artifacts',action='store_true');args=parser.parse_args()
    repo=args.repo_root.resolve();study=repo/'research/circle_packing_prompt_study_20261026';index_path=args.index or study/'ael_nbn_analysis_20261031/TRACKING_INDEX.json';index=json.loads(index_path.read_text(encoding='utf-8'))
    dest=args.destination.resolve();assert not dest.exists(),'Restoration target already exists; choose a new directory'
    dest.mkdir(parents=True);event_map={};restored=[]
    for h in index['histories']:
        path=study/h['history_file']
        if not path.exists() and h['role']=='derived_analysis_only_no_generation':
            path=index_path.parent/Path(h['history_file']).name
        assert path.resolve().is_relative_to(study.resolve()) or (h['role']=='derived_analysis_only_no_generation' and path.resolve().parent==index_path.resolve().parent)
        assert sha(path.read_bytes())==h['file_sha256'];snapshot=json.loads(path.read_text(encoding='utf-8'));events=snapshot['events']
        assert sha(canonical(events))==h['canonical_events_sha256'] and len(events)==h['event_count']
        revision=h['revision_id'];assert re.fullmatch(r'[A-Za-z0-9_-]+',revision)
        target=dest/revision/'research_history';target.mkdir(parents=True)
        protected={e['event_id']:e for e in h['events']}
        for e in events:
            assert e['revisionId']==revision and e['id'].isalnum()
            raw=json.dumps(e,ensure_ascii=False,allow_nan=False,sort_keys=True).encode();assert sha(raw)==protected[e['id']]['sha256']
            with (target/(e['id']+'.json')).open('xb') as stream:stream.write(raw)
        event_map[revision]=events;restored.append(dict(revision_id=revision,events=len(events)))
    spec=importlib.util.spec_from_file_location('preserved_history_view',repo/'visual_platform/services/history_view.py');module=importlib.util.module_from_spec(spec);spec.loader.exec_module(module)
    views={revision:module.build_history_view(events) for revision,events in event_map.items()};calls=0
    for attempt in index['programs']:
        rows={r['id']:r for r in views[attempt['origin_revision_id']]['attempts']};row=rows[attempt['call_id']]
        assert row['status']==attempt['evaluation_status'] and row['score']==attempt['score']
        program=row['program'];assert program is not None and sha(program.encode())==attempt['code_sha256']
        recovered=dest/'recovered_programs'/attempt['origin_revision_id']/attempt['call_id'];recovered.mkdir(parents=True)
        (recovered/'candidate.py').write_bytes(program.encode())
        assert sha(canonical(row['request']))==attempt['request_semantic_sha256']
        assert sha(canonical(row['response']))==attempt['response_semantic_sha256']
        prompt=row['request']['messages'][1]['content'];assert sha(prompt.encode())==attempt['prompt_sha256']
        (recovered/'prompt.txt').write_bytes(prompt.encode())
        for name,value in [('request.json',row['request']),('response.json',row['response']),('evaluation_and_lineage.json',dict(status=row['status'],score=row['score'],error=row.get('error'),parents=row['parents'],packing=row.get('packing')))]:
            (recovered/name).write_text(json.dumps(value,indent=2,allow_nan=False),encoding='utf-8')
        calls+=1
    copied=0
    if not args.skip_artifacts:
        for r in index['protected_artifacts']:
            origin=study/r['path'];assert origin.resolve().is_relative_to(study.resolve()) and sha(origin.read_bytes())==r['sha256']
            target=dest/'artifacts'/r['path'];assert target.resolve().is_relative_to(dest);target.parent.mkdir(parents=True,exist_ok=True);shutil.copyfile(origin,target);assert sha(target.read_bytes())==r['sha256'];copied+=1
    result=dict(passed=True,restored_histories=restored,original_events=index['original_event_count'],derived_analysis_events=index['derived_event_count'],total_events=sum(r['events'] for r in restored),generated_programs_restored=calls,source_and_prompt_bytes_match=True,request_and_response_json_values_match=True,failed_fitness_and_parent_links_match=True,protected_artifacts_copied=copied,generation_calls=0,candidate_executions=0)
    (dest/'RESTORE_VERIFICATION.json').write_text(json.dumps(result,indent=2),encoding='utf-8');print(json.dumps(result,indent=2))
if __name__=='__main__':main()
