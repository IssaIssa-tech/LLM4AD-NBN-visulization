"""Export analysis artifacts only; exclude existing archive vectors and private caches."""
import zipfile
from pathlib import Path
root=Path(__file__).resolve().parent
with zipfile.ZipFile(root.parent/'ael_nbn_analysis_20261031_results.zip','x',zipfile.ZIP_DEFLATED) as z:
    for p in root.rglob('*'):
        if not p.is_file() or any(s.startswith('private_hf_') or s=='__pycache__' for s in p.relative_to(root).parts) or p.name.endswith('.private.npy') or p.name.endswith('.local.zip'):continue
        z.write(p,p.relative_to(root).as_posix())
print('Exported new analysis; original cache/vectors/model weights left in place')
