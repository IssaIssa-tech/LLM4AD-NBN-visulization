"""Prepared-code timing diagnostic; zero LLM calls, no discovery claims."""
import hashlib,json,os,site,subprocess,sys,time
from datetime import datetime,timezone
from pathlib import Path

def sha(path):return hashlib.sha256(path.read_bytes()).hexdigest()
def main():
    root=Path(__file__).resolve().parent;out=root/'prepared_budget_calibration_20261028'
    if out.exists():raise SystemExit('Existing calibration; inspect rather than repeat')
    dep='/home/dyy/llm4ad_env/lib/python3.10/site-packages';site.addsitedir(dep);sys.path.remove(dep)
    sys.path.insert(sys.path.index(str(Path(sys.prefix)/'lib/python3.10/site-packages'))+1,dep)
    sys.path.insert(0,str(root));os.environ['VISUAL_PLATFORM_LOCAL_DATA_DIR']=str(root/'state');os.environ['VISUAL_PLATFORM_DB']=str(root/'state/platform.sqlite3')
    import numpy,scipy
    from visual_platform.services.research_history import append_event,capture_configuration,source_graph_identity
    from visual_platform.repositories.revision_repository import get_revision_record,upsert_revision
    from visual_platform.config import RUNS_DIR
    reference=root/'regional_prompt_execution_contract_20261028/request-2db392b30f2e706d/parent_candidate.py'
    source=reference.read_text();assert source.count('range(40000)')==1
    control=root/'calibration_control_source.py';assert control.exists()
    revision='prepared-budget-calibration-20261028';assert not get_revision_record(revision)
    parent=get_revision_record('circle-history-verified-20261028');assert parent
    out.mkdir();directory=RUNS_DIR/revision
    candidates=[]
    for rounds in [25,50,100]:
        name=f'archived12738-rounds{rounds}';folder=out/name;folder.mkdir()
        path=folder/'candidate.py';path.write_text(source.replace('range(40000)',f'range({rounds})'))
        candidates.append(dict(name=name,path=str(path),source_sha256=sha(path),outer_rounds=rounds,prepared_change='Only outer loop bound changed; cooling schedule left unchanged',origin='archived sample 12738'))
    folder=out/'validated_sobol_control';folder.mkdir();path=folder/'candidate.py';path.write_bytes(control.read_bytes())
    candidates.append(dict(name=folder.name,path=str(path),source_sha256=sha(path),prepared_change='None',origin='Prior M2-I-P validated source; current deployment timing is new'))
    evaluator=root/'regional_representatives_20261028'
    plan=dict(created_utc=datetime.now(timezone.utc).isoformat(),python=sys.version,numpy=numpy.__version__,scipy=scipy.__version__,
        reference_sha256=sha(reference),control_sha256=sha(control),candidates=candidates,timeout_seconds=20,repetitions=1,model_calls=0,
        evaluator_hashes={p.name:sha(p) for p in [evaluator/'evaluate_regional_representatives.py',evaluator/'evaluate_circle_prompt_candidates.py',root/'launch_history_platform.py']},
        limitations='Prepared code; single timing per candidate under current shared load; no general runtime guarantee, score ranking or generated discovery')
    (out/'registration.json').write_text(json.dumps(plan,indent=2))
    config=dict(revision_id=revision,workspace_id=parent['workspace_id'],source_revision_id=parent['revision_id'],source_graph_identity=source_graph_identity(parent['revision_id']),mode='prepared_runtime_calibration',method=plan,prompt='No LLM calls; prepared-code timing only',selected_nodes=[dict(sample_order=12738)])
    upsert_revision(revision,workspace_id=parent['workspace_id'],mode=config['mode'],config=config,lifecycle_status='running')
    directory.mkdir(parents=True,exist_ok=True);capture_configuration(directory,config);append_event(directory,'calibration_registered',plan)
    rows=[]
    for candidate in candidates:
        started=time.perf_counter();append_event(directory,'prepared_evaluation_started',candidate)
        try:
            done=subprocess.run([sys.executable,str(root/'launch_history_platform.py'),'--region-worker',candidate['path']],capture_output=True,text=True,timeout=20)
            result=json.loads(done.stdout) if done.returncode==0 else dict(status='worker_error',score=None,stderr=done.stderr)
        except subprocess.TimeoutExpired:result=dict(status='timeout',score=None)
        row=dict(candidate=candidate,evaluation=result,wall_seconds=time.perf_counter()-started)
        Path(candidate['path']).with_name('evaluation.json').write_text(json.dumps(row,indent=2));append_event(directory,'prepared_evaluation_completed',row)
        rows.append(row);print(candidate['name'],result['status'],result.get('score'),row['wall_seconds'],flush=True)
    (out/'results.json').write_text(json.dumps(dict(registration=plan,results=rows),indent=2))
    append_event(directory,'calibration_completed',dict(evaluations=4,model_calls=0));upsert_revision(revision,lifecycle_status='completed')

if __name__=='__main__':main()
