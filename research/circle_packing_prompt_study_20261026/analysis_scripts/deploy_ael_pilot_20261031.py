"""Extract only the new pilot package; verify paths and never replace old folders."""
import json,sys,zipfile
from pathlib import Path
parent=Path(__file__).resolve().parent
archive=parent/'ael_operator_pilot_20261031_upload.zip';target=parent/'ael_operator_pilot_20261031'
assert not target.exists(),'Existing pilot: inspect rather than overwrite'
with zipfile.ZipFile(archive) as z:
    for n in z.namelist():assert (target/n).resolve().is_relative_to(target)
    target.mkdir()
    for n in z.namelist():
        p=target/n;p.parent.mkdir(exist_ok=True,parents=True)
        with p.open('xb') as f:f.write(z.read(n))
print(json.dumps(dict(status='new_package_extracted',root=str(target))))
