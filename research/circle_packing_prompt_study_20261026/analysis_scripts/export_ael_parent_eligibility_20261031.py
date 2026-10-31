"""Package completed diagnostic records, referring to existing source programs."""
import json,zipfile
from pathlib import Path
deployment=Path(__file__).resolve().parent;root=deployment/'ael_parent_eligibility_20261031'
results=json.loads((root/'results.json').read_text());assert results['status']=='completed' and len(results['results'])==30
target=deployment/'ael_parent_eligibility_results_20261031.zip'
assert not target.exists(),'Existing export; reuse instead of replacing'
with zipfile.ZipFile(target,'x',zipfile.ZIP_DEFLATED) as archive:
    for path in root.rglob('*'):
        if path.is_file() and path.relative_to(root).parts[0]!='candidates':archive.write(path,path.relative_to(root))
print(json.dumps(dict(path=str(target),bytes=target.stat().st_size,programs=30,source_program_policy='Sources are already preserved in the original shortlist; source hashes and original paths are included.')))
