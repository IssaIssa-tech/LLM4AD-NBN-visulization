"""Archive current condition records, preserving existing server files."""
import zipfile
from pathlib import Path
parent=Path(__file__).resolve().parent;name='ael_structural_prompt_comparison_20261031';root=parent/name
with zipfile.ZipFile(parent/(name+'_records.zip'),'x',zipfile.ZIP_DEFLATED) as z:
    for p in root.rglob('*'):
        if p.is_file() and '__pycache__' not in p.parts and p.name!='execution.lock':z.write(p,p.relative_to(root).as_posix())
print('Exported current condition records without changing sources')
