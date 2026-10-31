"""Verify only this researcher's uploaded release/backup; do not extract or execute code."""
import hashlib
import json
import zipfile
from pathlib import Path

root=Path(__file__).resolve().parent
release=root/'preserved_release'
receipt=json.loads((release/'LOCAL_BACKUP.json').read_text())
archive=root/'ael_tracking_and_nbn_backup_20261031.local.zip'
assert archive.resolve().parent==root and release.resolve().parent==root
sha=lambda raw:hashlib.sha256(raw).hexdigest()
assert sha(archive.read_bytes())==receipt['archive_sha256']
with zipfile.ZipFile(archive) as z:
    assert len(z.namelist())==receipt['archive_entries'] and z.testzip() is None
files=json.loads((release/'ARTIFACT_INTEGRITY.json').read_text())['files']
for entry in files:
    path=release/entry['path'];assert path.resolve().is_relative_to(release.resolve())
    assert sha(path.read_bytes())==entry['sha256']
result=dict(passed=True,server_archive=str(archive),server_archive_sha256=receipt['archive_sha256'],
    archive_entries_verified=receipt['archive_entries'],release_directory=str(release),
    release_files_hash_verified=len(files),generation_calls=0,candidate_executions=0)
(root/'SERVER_BACKUP_CHECK.json').write_text(json.dumps(result,indent=2),encoding='utf-8')
print(json.dumps(result))
