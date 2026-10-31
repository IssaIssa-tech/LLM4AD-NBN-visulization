"""Extract only this new condition; never replace an existing shared-server folder."""
import json,zipfile
from pathlib import Path
parent=Path(__file__).resolve().parent;name='ael_structural_prompt_comparison_20261031';root=parent/name
assert not root.exists(),'Existing condition: inspect rather than overwrite'
with zipfile.ZipFile(parent/(name+'_upload.zip')) as z:
    for n in z.namelist():assert (root/n).resolve().is_relative_to(root)
    root.mkdir()
    for n in z.namelist():
        p=root/n;p.parent.mkdir(exist_ok=True,parents=True)
        with p.open('xb') as f:f.write(z.read(n))
print(json.dumps(dict(status='new_condition_deployed',root=str(root))))
