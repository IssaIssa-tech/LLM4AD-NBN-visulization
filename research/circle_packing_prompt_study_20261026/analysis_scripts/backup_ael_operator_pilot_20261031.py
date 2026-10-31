"""Copy the new completed case only, verify bytes, and reuse existing data paths."""
import shutil
from pathlib import Path
from ael_pilot_common import NAME,load,sha
base=Path(__file__).resolve().parents[1];source=base/'output'/NAME
study=base/'LLM4AD-NBN-visualization-github/research/circle_packing_prompt_study_20261026'
target=study/NAME;assert not target.exists(),'Existing backup; inspect rather than overwrite'
target.mkdir()
files=load(source/'ARTIFACT_INTEGRITY.json')['files']
for record in files:
    origin=source/record['path'];dest=target/record['path'];assert dest.resolve().is_relative_to(target)
    assert sha(origin.read_bytes())==record['sha256']
    dest.parent.mkdir(exist_ok=True,parents=True);shutil.copyfile(origin,dest)
    assert sha(dest.read_bytes())==record['sha256']
shutil.copyfile(source/'ARTIFACT_INTEGRITY.json',target/'ARTIFACT_INTEGRITY.json')
names=['ael_pilot_common.py','ael_pilot_gpu.py','ael_pilot_history.py','prepare_ael_operator_pilot_20261031.py','run_ael_operator_pilot_20261031.py','report_ael_operator_pilot_20261031.py','deploy_ael_pilot_20261031.py','test_ael_history_20261031.py','reload_history_for_ael_20261031.py','export_ael_pilot_20261031.py','merge_ael_pilot_records_20261031.py','verify_ael_live_20261031.py','verify_ael_gpu_release_20261031.py','finalize_ael_pilot_review_20261031.py','make_ael_pilot_browser_check_20261031.py','check_ael_operator_pilot_20261031.mjs','backup_ael_operator_pilot_20261031.py']
for name in names:
    dest=study/'analysis_scripts'/name;assert not dest.exists()
    shutil.copyfile(base/'analysis'/name,dest)
print('Backed up',len(files)+1,'evidence/review files and',len(names),'scripts; no historical dataset copy')
