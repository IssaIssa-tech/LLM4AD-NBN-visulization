"""Document a pre-registration engineering amendment; no research calls."""
import json,shutil
from pathlib import Path
from hashlib import sha256
base=Path(__file__).resolve().parents[1];root=base/'output/ael_structural_prompt_comparison_20261031';old=base/'output/ael_operator_pilot_20261031'
assert not (root/'registration.json').exists() and not (root/'runtime_identity.json').exists()
archive=root/'preparation_v1';archive.mkdir()
for name in ['manifest.json','PROTOCOL.md','MATCHING_AUDIT.json','ael_pilot_gpu.py']:shutil.copyfile(root/name,archive/name)
m=json.loads((root/'manifest.json').read_text(encoding='utf-8'));baseline_identity=json.loads((old/'runtime_identity.json').read_text(encoding='utf-8'))
expect=m['runtime_expectation'];expect.update(minimum_free_gpu_mib=7168,minimum_free_after_load_mib=1024,required_gpu_uuid=baseline_identity['gpu']['uuid'])
note=dict(status='pre_registration_engineering_amendment_zero_model_calls',previous_minimum_free_gpu_mib=16384,new_minimum_free_gpu_mib=7168,minimum_free_after_load_mib=1024,baseline_model_buffer_mib=4168.09,baseline_kv_buffer_mib=448.0,baseline_compute_buffer_mib=311.0,baseline_service_log_sha256=sha256((old/'service.log').read_bytes()).hexdigest(),reason='Prior full-offload buffer evidence totals 4927.09MiB. Use the same baseline GPU/model/build/context with a guarded load and >=1GiB remaining; generator timing is not compared.',preserved_preparation='preparation_v1',experiment_outcomes_changed=False,baseline_rerun=False)
m['pre_registration_engineering_amendment']=note
m['limitations'].append('Generator GPU has another resident workload; allocation and headroom are recorded. No generation-timing comparison or exclusive-GPU claim.')
with (root/'manifest.json').open('w',encoding='utf-8',newline='\n') as f:json.dump(m,f,indent=2,allow_nan=False)
protocol=(root/'PROTOCOL.md').read_text(encoding='utf-8').replace('Start only our private service when a GPU has >=16384MiB free and zero reported utilization, as in the prior pilot.', 'A documented pre-registration engineering amendment replaces the conservative 16384MiB startup guard: start only our private service on the same baseline GPU when it has >=7168MiB free and zero reported utilization, and require >=1024MiB free after the complete model/context load. Prior full-offload buffers total 4927.09MiB. Preserve the original prepared protocol and amendment evidence under preparation_v1/ and PRE_REGISTRATION_AMENDMENT.json. This adjusts allocation headroom only, not model/build/context/sampling/evaluation. Another resident workload remains untouched; generator timings are not compared.')
(root/'PROTOCOL.md').write_text(protocol,encoding='utf-8',newline='\n')
p=root/'ael_pilot_gpu.py';s=p.read_text(encoding='utf-8');before="gpu=next((r for r in gpus if int(r['free_mib'])>=16384 and int(r['utilization'])==0),None);assert gpu,'No idle eligible GPU'"
after="gpu=next((r for r in gpus if r['uuid']==m['runtime_expectation']['required_gpu_uuid'] and int(r['free_mib'])>=m['runtime_expectation']['minimum_free_gpu_mib'] and int(r['utilization'])==0),None);assert gpu,'Same baseline GPU does not meet registered allocation guard'"
assert before in s;s=s.replace(before,after)
marker="props=api('/props');save(root/'runtime_props.json',props)"
replacement="post_load_free_mib=int(subprocess.check_output(['nvidia-smi','-i',gpu['uuid'],'--query-gpu=memory.free','--format=csv,noheader,nounits'],text=True).strip())\n    save(root/'post_load_memory_preflight.json',dict(free_mib=post_load_free_mib,minimum_free_mib=m['runtime_expectation']['minimum_free_after_load_mib']))\n    assert post_load_free_mib>=m['runtime_expectation']['minimum_free_after_load_mib'],'Insufficient headroom after full load'\n    "+marker
assert marker in s;s=s.replace(marker,replacement)
start=s.index('    for _ in range(90):');end=s.index("\nif op=='metadata':")
body=s[start:end];s=s[:start]+"    try:\n"+'\n'.join('    '+line for line in body.splitlines())+"\n    except Exception as error:\n        save(root/'startup_failure.json',dict(error=f'{type(error).__name__}: {error}',model_calls=0,own_service_pid=child.pid))\n        if child.poll() is None:\n            assert Path(f'/proc/{child.pid}/cwd').resolve()==root.resolve()\n            os.killpg(child.pid,signal.SIGTERM)\n        raise\n"+s[end:]
p.write_text(s,encoding='utf-8',newline='\n')
audit=json.loads((root/'MATCHING_AUDIT.json').read_text(encoding='utf-8'));audit.update(new_manifest_sha256=sha256((root/'manifest.json').read_bytes()).hexdigest(),pre_registration_engineering_amendment=note)
(root/'MATCHING_AUDIT.json').write_text(json.dumps(audit,indent=2),encoding='utf-8',newline='\n')
(root/'PRE_REGISTRATION_AMENDMENT.json').write_text(json.dumps(note,indent=2),encoding='utf-8',newline='\n')
print('Recorded explicit pre-registration allocation amendment; zero model calls')
