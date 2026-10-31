"""Back up this new condition and relevant scripts only; do not duplicate the archive."""
import json,shutil
from pathlib import Path
from hashlib import sha256
base=Path(__file__).resolve().parents[1];root=base/'output/ael_structural_prompt_comparison_20261031'
study=base/'LLM4AD-NBN-visualization-github/research/circle_packing_prompt_study_20261026';target=study/root.name
assert not target.exists(),'Existing research backup; inspect rather than replace'
target.mkdir();inventory=[]
for p in sorted(root.rglob('*')):
    rel=p.relative_to(root)
    if not p.is_file() or any(part.startswith('browser_profile_') or part=='__pycache__' for part in rel.parts) or p.name=='execution.lock':continue
    dest=target/rel;assert dest.resolve().is_relative_to(target);dest.parent.mkdir(exist_ok=True,parents=True)
    raw=p.read_bytes();shutil.copyfile(p,dest);assert sha256(raw).hexdigest()==sha256(dest.read_bytes()).hexdigest()
    inventory.append(dict(path=rel.as_posix(),bytes=len(raw),sha256=sha256(raw).hexdigest()))
data=dict(files=inventory,scope='New condition only; frozen baseline referenced by existing path/hash. Excludes browser profiles, cache, execution lock and this inventory.')
for folder in [root,target]:(folder/'ARTIFACT_INTEGRITY.json').write_text(json.dumps(data,indent=2),encoding='utf-8',newline='\n')
names=['prepare_ael_structural_comparison_20261031.py','amend_ael_structural_memory_preflight_20261031.py','deploy_ael_structural_comparison_20261031.py','run_ael_structural_when_ready_20261031.py','report_ael_structural_comparison_20261031.py','record_ael_structural_preparation_20261031.py','finalize_ael_structural_preparation_20261031.py','export_ael_structural_comparison_20261031.py','check_ael_structural_comparison_20261031.mjs','backup_ael_structural_comparison_20261031.py','merge_ael_structural_records_20261031.py','verify_ael_structural_live_20261031.py','summarize_ael_structural_mechanisms_20261031.py']
for name in names:
    dest=study/'analysis_scripts'/name;assert not dest.exists();shutil.copyfile(base/'analysis'/name,dest)
print('Backed up',len(inventory)+1,'files and',len(names),'new scripts')
