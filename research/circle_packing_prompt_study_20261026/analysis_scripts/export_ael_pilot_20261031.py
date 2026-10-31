"""Archive completed private pilot records; leave all source files untouched."""
import zipfile
from pathlib import Path
parent=Path(__file__).resolve().parent;root=parent/'ael_operator_pilot_20261031'
with zipfile.ZipFile(parent/'ael_operator_pilot_20261031_records.zip','x',zipfile.ZIP_DEFLATED) as z:
    for p in root.rglob('*'):
        if p.is_file() and '__pycache__' not in p.parts and p.name not in ['execution.lock','history_app.log']:
            z.write(p,p.relative_to(root).as_posix())
print('Exported completed records')
