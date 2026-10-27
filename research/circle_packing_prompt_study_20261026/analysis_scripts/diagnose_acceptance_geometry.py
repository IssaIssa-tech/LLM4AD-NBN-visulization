"""Read-only source tracing of initial and final packings in isolated workers."""
import argparse, json, subprocess, sys
from pathlib import Path
import numpy as np

def geometry(a):
    eps=1e-12
    overlaps=[]; boundaries=[]
    for i,(x,y,r) in enumerate(a):
        slack=float(min(r,x-r,y-r,1-x-r,1-y-r))
        if slack < -eps: boundaries.append(dict(circle=i,minimum_slack=slack))
        for j in range(i+1,len(a)):
            gap=float(np.linalg.norm(a[i,:2]-a[j,:2])-r-a[j,2])
            if gap < -eps: overlaps.append(dict(i=i,j=j,gap=gap,penetration=-gap))
    return dict(shape=list(a.shape),finite=bool(np.isfinite(a).all()),overlaps=overlaps,boundary_violations=boundaries,
        overlap_count=len(overlaps),boundary_violation_count=len(boundaries),radius_sum_diagnostic=float(a[:,2].sum()),coordinates=a.tolist())

def worker(path):
    from evaluate_circle_prompt_candidates import static_screen
    screen=static_screen(path)
    if not screen['ok']: raise ValueError(screen)
    source=path.read_text(); initial=None
    # Observe the first iteration header, after initialization has completed.
    line=next(i for i,s in enumerate(source.splitlines(),1) if s.strip()=='for iteration in range(500):')
    def trace(frame,event,arg):
        nonlocal initial
        if event=='line' and frame.f_code.co_filename==str(path) and frame.f_lineno==line and initial is None:
            initial=np.array(frame.f_locals['circles'],copy=True)
        return trace
    scope={'__name__':'geometry_diagnostic','np':np}
    exec(compile(source,str(path),'exec'),scope)
    sys.settrace(trace)
    try: final=np.asarray(scope['pack_circles'](26),dtype=float)
    finally: sys.settrace(None)
    if initial is None: raise ValueError('Initialization trace point not captured')
    first=geometry(initial); last=geometry(final)
    before={(x['i'],x['j']) for x in first['overlaps']}; after={(x['i'],x['j']) for x in last['overlaps']}
    return dict(initial=first,final=last,remaining_initial_overlap_pairs=sorted(before&after),new_overlap_pairs=sorted(after-before),
        unchanged_circles=[int(i) for i in range(26) if np.array_equal(initial[i],final[i])])

def main():
    parser=argparse.ArgumentParser(); parser.add_argument('--worker',type=Path); args=parser.parse_args()
    if args.worker:
        print(json.dumps(worker(args.worker))); return
    root=Path(__file__).resolve().parent; out=root/'geometry_diagnosis.json'
    if out.exists(): raise SystemExit('Existing diagnosis; refusing overwrite')
    records=[]
    for name in ('parent_candidate.py','expected_candidate.py'):
        try:
            result=subprocess.run([sys.executable,str(Path(__file__).resolve()),'--worker',str(root/name)],capture_output=True,text=True,timeout=20)
            row=dict(program=name,exit_code=result.returncode)
            if result.returncode==0: row['diagnosis']=json.loads(result.stdout)
            else: row['error']=result.stderr[-3000:]
        except subprocess.TimeoutExpired: row=dict(program=name,status='diagnostic_timeout',timeout_seconds=20)
        records.append(row)
    out.write_text(json.dumps(dict(purpose='Instrumented diagnostic rerun, not a new algorithm trial or fitness record',tolerance=1e-12,records=records),indent=2))
    for row in records:
        d=row.get('diagnosis')
        print(row['program'],json.dumps(dict(initial_overlaps=d['initial']['overlap_count'],final_overlaps=d['final']['overlap_count'],boundary_violations=d['final']['boundary_violation_count'],remaining_initial_pairs=d['remaining_initial_overlap_pairs'],new_pairs=d['new_overlap_pairs'])) if d else row)

if __name__=='__main__': main()
