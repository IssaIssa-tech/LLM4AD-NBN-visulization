"""Bounded allocation wait, then one registered run; never repeat a model request."""
import csv,io,json,os,subprocess,sys,time
from datetime import datetime,timezone
from pathlib import Path
base=Path(__file__).resolve().parents[1];root=base/'output/ael_structural_prompt_comparison_20261031'
m=json.loads((root/'manifest.json').read_text(encoding='utf-8'))
key=Path(os.environ['USERPROFILE'])/'.ssh/llm4ad_dyy_10_249_185_134_ed25519'
ssh=['ssh','-T','-o','BatchMode=yes','-o','ConnectTimeout=10','-i',str(key),'-p','8888','dyy@10.249.185.134']
gpu_command='/usr/bin/python3 /home/dyy/issa_nbn_runtime_20261029/ael_structural_prompt_comparison_20261031/ael_pilot_gpu.py '
assert not (root/'readiness_wait.json').exists(),'Existing wait: inspect it before relaunching'
registration=dict(wait_started_utc=datetime.now(timezone.utc).isoformat(),maximum_wait_seconds=600,poll_seconds=30,criteria=m['runtime_expectation'],model_calls_before_wait=0)
(root/'readiness_wait.json').write_text(json.dumps(registration,indent=2),encoding='utf-8')
deadline=time.perf_counter()+600;started=False
try:
    while time.perf_counter()<deadline:
        done=subprocess.run(ssh+['nvidia-smi --query-gpu=index,uuid,memory.free,utilization.gpu --format=csv,noheader,nounits'],capture_output=True,text=True,timeout=20)
        assert done.returncode==0,done.stderr
        rows=[dict(zip(['index','uuid','free_mib','utilization'],[v.strip() for v in values])) for values in csv.reader(io.StringIO(done.stdout))]
        selected=next(r for r in rows if r['uuid']==m['runtime_expectation']['required_gpu_uuid'])
        ready=int(selected['free_mib'])>=m['runtime_expectation']['minimum_free_gpu_mib'] and int(selected['utilization'])==0
        snapshot=dict(utc=datetime.now(timezone.utc).isoformat(),selected_gpu=selected,ready=ready)
        with (root/'allocation_observations.jsonl').open('a',encoding='utf-8') as f:f.write(json.dumps(snapshot)+'\n')
        print('GPU allocation:',selected['free_mib'],'MiB free, utilization',selected['utilization'],'ready='+str(ready),flush=True)
        if ready:
            launch=subprocess.run(ssh+[gpu_command+'start'],capture_output=True,text=True,timeout=120)
            with (root/'service_start_attempts.jsonl').open('a',encoding='utf-8') as f:f.write(json.dumps(dict(returncode=launch.returncode,stdout=launch.stdout,stderr=launch.stderr))+'\n')
            if launch.returncode:
                if 'Same baseline GPU does not meet registered allocation guard' in launch.stderr:
                    time.sleep(30);continue
                raise RuntimeError('Private startup failed before research calls: '+launch.stderr[-2500:])
            started=True;print('PRIVATE MODEL READY; registering and executing the fixed condition',flush=True)
            run=subprocess.run([sys.executable,'-u',str(root/'run_ael_operator_pilot_20261031.py'),'--register','--execute'],cwd=base)
            assert run.returncode==0,'Coordinator stopped; inspect saved files; no retry'
            print('FIXED CONDITION COMPLETED',flush=True);break
        time.sleep(min(30,max(0,deadline-time.perf_counter())))
    else:
        status=dict(status='prepared_wait_expired_no_generation',model_calls=0,reason='Registered GPU allocation criteria remained unmet during the bounded wait',maximum_wait_seconds=600)
        (root/'WAIT_STATUS.json').write_text(json.dumps(status,indent=2),encoding='utf-8');print(json.dumps(status),flush=True)
finally:
    if started and not (root/'service_released.json').exists():
        release=subprocess.run(ssh+[gpu_command+'stop'],input='{}',capture_output=True,text=True,timeout=30)
        (root/'watcher_cleanup.json').write_text(json.dumps(dict(returncode=release.returncode,stdout=release.stdout,stderr=release.stderr),indent=2),encoding='utf-8')
