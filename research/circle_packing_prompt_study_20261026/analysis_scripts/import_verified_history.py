"""Import audited canonical rows into the isolated platform without overwrites."""
import argparse,hashlib,json,math,shutil,sqlite3,sys
from datetime import datetime,timezone
from pathlib import Path

def digest(path):return hashlib.sha256(path.read_bytes()).hexdigest()
def main():
    parser=argparse.ArgumentParser();parser.add_argument('--apply',action='store_true');args=parser.parse_args()
    root=Path(__file__).resolve().parent
    # This script is deployed under the isolated installation root.
    sys.path.insert(0,str(root))
    from visual_platform.config import RUNS_DIR
    from visual_platform.runtime.database import DB_PATH,init_db_schema,get_connection
    from visual_platform.repositories import workspace_repository as wr,revision_repository as rr,individual_repository as ir,artifact_repository as ar
    from visual_platform.services.research_history import append_event,capture_configuration
    assets=root/'history_sources_20261028';audit=json.loads((assets/'audit.json').read_text())
    graph_path=assets/'circle_packing_historical_nbn_14000.json';archive=assets/'EoH_sample_history_complete.zip'
    assert digest(graph_path)==audit['source_graph_sha256']
    assert digest(archive)==audit['archive_sha256']
    graph=json.loads(graph_path.read_text())['graph']
    rows=[json.loads(line) for line in (assets/'canonical_programs.jsonl').read_text().splitlines()]
    assert len(rows)==14000 and len({r['id'] for r in rows})==14000
    by_id={n['id']:n for n in graph['nodes']}
    for row in rows:
        node=by_id[row['id']]
        assert row['sample_order']==node['sampleOrder']
        assert row['function']==node['functionPreview'].strip()
        assert hashlib.sha256(row['function'].encode()).hexdigest()==row['provenance']['code_sha256']
        assert row['score']==node.get('rawScore')
    init_db_schema();revision='circle-history-verified-20261028';directory=RUNS_DIR/revision
    with get_connection() as conn:
        existing=conn.execute('SELECT COUNT(*) AS n FROM individuals').fetchone()['n']
        collisions=sum(conn.execute('SELECT 1 FROM individuals WHERE id=?',(r['id'],)).fetchone() is not None for r in rows)
        revision_exists=conn.execute('SELECT 1 FROM revisions WHERE revision_id=?',(revision,)).fetchone() is not None
    print(json.dumps(dict(preflight=True,existing_individuals=existing,colliding_ids=collisions,revision_exists=revision_exists,canonical_rows=len(rows),apply=args.apply)),flush=True)
    if collisions or revision_exists or directory.exists():raise SystemExit('Existing import/colliding IDs: refusing overwrite')
    if not args.apply:return
    backup=root/'state'/'before_history_import.sqlite3'
    if backup.exists():raise SystemExit('Backup exists; inspect before proceeding')
    with sqlite3.connect(str(DB_PATH)) as source,sqlite3.connect(str(backup)) as target:source.backup(target)
    directory.mkdir(parents=True);(directory/'samples').mkdir()
    workspace=wr.create_workspace('Circle Packing N=26 — verified historical cohort',description='14,000 graph-mapped historical records; archived scores, not fresh evaluations.')
    config=dict(revision_id=revision,workspace_id=workspace,mode='history_import',log_dir=str(directory/'samples'),
        source_graph_sha256=audit['source_graph_sha256'],source_archive_sha256=audit['archive_sha256'],
        historical_import=dict(audit=audit,reevaluated=False),method={},prompt='',selected_nodes=[])
    rr.upsert_revision(revision,workspace_id=workspace,mode='history_import',config=config,lifecycle_status='running',graph_status='none')
    capture_configuration(directory,config)
    append_event(directory,'history_import_started',dict(sourceGraphSha256=audit['source_graph_sha256'],archiveSha256=audit['archive_sha256'],cohortSize=14000,originalBackend=audit['source_backend']))
    for row in rows:row.update(revision_id=revision,workspace_id=workspace)
    ir.insert_individuals_bulk(rows)
    frozen=directory/'historical_graph_frozen.json'
    frozen.write_text(json.dumps(graph,ensure_ascii=False),encoding='utf-8')
    artifact=ar.upsert_artifact(revision,artifact_type='graph',artifact_role='full',format_name='json',storage_uri=str(frozen),status='ready',input_digest=audit['source_graph_sha256'],content_digest=digest(frozen),metadata=dict(nodeCount=14000,edgeCount=13999,distanceMetric=graph.get('distanceMetric'),nbnMode=audit['source_backend'].get('nbnMode'),sourceGraphSha256=audit['source_graph_sha256'],scoreProvenance='archived_not_reevaluated'))
    config.update(source_graph_artifact_id=artifact,source_graph_content_sha256=digest(frozen))
    rr.upsert_revision(revision,config=config,lifecycle_status='completed',graph_status='ready')
    wr.update_workspace_revision(workspace,revision)
    # This deployment had no active research workspace; don't switch an existing one.
    if wr.get_active_workspace() is None:wr.activate_workspace(workspace)
    with get_connection() as conn:
        records=conn.execute('SELECT id,code,score,raw_payload FROM individuals WHERE revision_id=?',(revision,)).fetchall()
    assert len(records)==14000
    for record in records:
        node=by_id[record['id']];assert record['code']==node['functionPreview'].strip();assert record['score']==node.get('rawScore')
        payload=json.loads(record['raw_payload']);assert payload['provenance']['original_node_id']==record['id']
    verification=dict(revisionId=revision,workspaceId=workspace,graphArtifactId=artifact,importedPrograms=len(records),verifiedCodeNodeMappings=len(records),sourceGraphSha256=audit['source_graph_sha256'],frozenGraphContentSha256=digest(frozen),archiveSha256=audit['archive_sha256'],scoreClasses=audit['score_classes'],archiveRecordsRetained=audit['raw_archive_records'],canonicalScoresReevaluated=False,sourceBackend=audit['source_backend'],completedUtc=datetime.now(timezone.utc).isoformat(),backupPath=str(backup))
    append_event(directory,'history_import_completed',verification)
    capture_configuration(directory,config)
    (root/'history_import_verification.json').write_text(json.dumps(verification,indent=2));print(json.dumps(verification,indent=2),flush=True)
if __name__=='__main__':main()
