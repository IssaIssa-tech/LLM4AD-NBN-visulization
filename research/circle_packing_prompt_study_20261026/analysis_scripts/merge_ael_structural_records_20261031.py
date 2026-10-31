"""Merge downloaded evidence without replacing any existing local result."""
import json,zipfile
from pathlib import Path
from ael_pilot_common import sha,save
NAME='ael_structural_prompt_comparison_20261031'
base=Path(__file__).resolve().parents[1];out=base/'output'/NAME;records=[]
for host in ['hits1','hits9']:
    archive=base/'output'/f'{NAME}_{host}_records.zip'
    with zipfile.ZipFile(archive) as z:
        for name in z.namelist():
            target=out/name;assert target.resolve().is_relative_to(out)
            raw=z.read(name);record=dict(host=host,path=name,sha256=sha(raw))
            if not target.exists():
                target.parent.mkdir(exist_ok=True,parents=True)
                with target.open('xb') as f:f.write(raw)
                record['action']='added'
            elif sha(target.read_bytes())==sha(raw):record['action']='already_identical_not_duplicated'
            else:
                # Registration wrappers differ locally/remotely; JSON whitespace
                # variants are verified and retained only when materially different.
                equal=name.endswith('.json') and json.loads(target.read_bytes())==json.loads(raw)
                if equal:record['action']='same_json_value_existing_local_bytes_preserved'
                else:
                    assert name=='registration.json','Unexpected conflicting recorded file: '+name
                    with (out/(host+'_registration.json')).open('xb') as f:f.write(raw)
                    record['action']='distinct_registration_wrapper_saved'
            records.append(record)
save(out/'DOWNLOAD_MERGE_AUDIT.json',records);print('Verified',len(records),'remote archive entries without replacing local records')
