"""Create an additive release and a verified local ZIP; leave frozen cases unchanged."""
import hashlib
import json
import shutil
import zipfile
from pathlib import Path

base = Path(__file__).resolve().parents[1]
out = base / 'output/ael_nbn_analysis_20261031'
repo = base / 'LLM4AD-NBN-visualization-github'
study = repo / 'research/circle_packing_prompt_study_20261026'
release = study / out.name
restore = base / 'output/ael_tracking_restore_check_20261031'
backup = base / 'output/ael_tracking_and_nbn_backup_20261031.local.zip'
assert not release.exists() and not backup.exists(), 'Existing release/backup: inspect rather than duplicate'
sha = lambda raw: hashlib.sha256(raw).hexdigest()
load = lambda name: json.loads((out / name).read_text(encoding='utf-8'))
for name in ['ANALYSIS_VERIFICATION.json','RESTORE_CHECK.json','BROWSER_VERIFICATION.json','FINAL_LIVE_HISTORY_CHECK.json']:
    assert load(name)['passed']

script_names = [
    'prepare_ael_nbn_analysis_20261031.py','audit_ael_tracking_nbn_inputs_20261031.py',
    'embed_ael_nbn_sources_20261031.py','diagnose_ael_embedding_compatibility_20261031.py',
    'prepare_ael_reconciled_embedding_20261031.py','embed_ael_nbn_reconciled_20261031.py',
    'analyze_ael_nbn_20261031.py','register_ael_nbn_analysis_20261031.py',
    'export_ael_nbn_analysis_20261031.py','build_ael_nbn_viewer_20261031.py',
    'restore_ael_tracking_20261031.py','build_ael_tracking_index_20261031.py',
    'check_ael_nbn_viewer_20261031.mjs','verify_ael_nbn_analysis_20261031.py',
    'report_ael_nbn_analysis_20261031.py','verify_ael_live_history_20261031.py',
    'package_ael_nbn_analysis_20261031.py','verify_ael_server_backup_20261031.py',
]
scripts = []
for name in script_names:
    source = base / 'analysis' / name
    destination = study / 'analysis_scripts' / name
    assert source.is_file() and not destination.exists(), name
    shutil.copyfile(source,destination)
    scripts.append(dict(path='analysis_scripts/'+name,sha256=sha(source.read_bytes()),bytes=source.stat().st_size))
(out / 'ANALYSIS_SCRIPTS.json').write_text(json.dumps(dict(scripts=scripts),indent=2),encoding='utf-8',newline='\n')

# Include exact restored tracking, sources/results, analysis vectors and scripts in the local backup.
# Do not recursively include browser profiles, older ZIPs, model weights, or the source cache.
analysis_files = [p for p in sorted(out.rglob('*')) if p.is_file()
                  and not any(part.startswith('browser_profile_') or part.startswith('private_hf') or part=='__pycache__' for part in p.relative_to(out).parts)
                  and not p.name.endswith('.local.zip')
                  and p.name not in ['LOCAL_BACKUP.json','ARTIFACT_INTEGRITY.json','SERVER_BACKUP_CHECK.json']]
entries = []
with zipfile.ZipFile(backup,'x',zipfile.ZIP_DEFLATED,compresslevel=6) as archive:
    for source in sorted(restore.rglob('*')):
        if source.is_file():
            name='restored_tracking/'+source.relative_to(restore).as_posix()
            archive.write(source,name);entries.append(name)
    for source in analysis_files:
        name='nbn_analysis/'+source.relative_to(out).as_posix()
        archive.write(source,name);entries.append(name)
    for record in scripts:
        source=study/record['path'];name=record['path']
        archive.write(source,name);entries.append(name)
with zipfile.ZipFile(backup) as archive:
    assert archive.testzip() is None and len(archive.namelist())==len(set(entries))
private_names=['historical_vectors.private.npy','historical_metadata.json','historical_vector_order.json']
local=dict(passed=True,local_archive=str(backup),archive_sha256=sha(backup.read_bytes()),
    archive_bytes=backup.stat().st_size,archive_entries=len(entries),zip_crc_verified=True,
    original_events=205,derived_events=28,generated_programs=24,protected_existing_artifacts=616,
    included='Verified restored histories and artifacts, recovered generated sources/prompts/outcomes, analysis outputs, historical vectors/metadata/order, and analysis scripts',
    excluded='Existing 14000-program source archive, model weights, source cache, browser profiles, older ZIPs; this post-archive receipt and the final release integrity/server receipts',
    historical_source_archive_reused=load('TRACKING_INDEX.json')['historical_archive_reference'],
    intermediate_files=[dict(path=n,sha256=sha((out/n).read_bytes()),bytes=(out/n).stat().st_size,in_local_zip=True,in_github_release=False) for n in private_names])
(out/'LOCAL_BACKUP.json').write_text(json.dumps(local,indent=2),encoding='utf-8',newline='\n')

release.mkdir()
allowed={'.json','.md','.png','.html','.txt','.npz'}
for source in sorted(out.rglob('*')):
    if not source.is_file():continue
    rel=source.relative_to(out)
    if any(part.startswith('browser_profile_') or part.startswith('private_hf') or part=='__pycache__' for part in rel.parts):continue
    if source.name in private_names or source.name.endswith('.local.zip'):continue
    if source.suffix not in allowed and source.name not in ['.gitignore','.gitattributes']:continue
    target=release/rel;target.parent.mkdir(parents=True,exist_ok=True);shutil.copyfile(source,target)
manifest=[dict(path=p.relative_to(release).as_posix(),sha256=sha(p.read_bytes()),bytes=p.stat().st_size) for p in sorted(release.rglob('*')) if p.is_file() and p.name!='ARTIFACT_INTEGRITY.json']
(release/'ARTIFACT_INTEGRITY.json').write_text(json.dumps(dict(files=manifest),indent=2),encoding='utf-8',newline='\n')
print(json.dumps(dict(local_backup=local['local_archive'],archive_bytes=local['archive_bytes'],archive_entries=len(entries),sha256=local['archive_sha256'],release_files=len(manifest)+1,scripts=len(scripts))))
