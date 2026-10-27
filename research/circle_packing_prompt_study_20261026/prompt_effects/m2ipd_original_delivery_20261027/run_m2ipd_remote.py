"""Run strict M2-I-P-D trial outputs with exact patch guards."""
from __future__ import annotations
import hashlib,json,re,sys,urllib.request
from datetime import datetime,timezone
from pathlib import Path
ROOT=Path(__file__).resolve().parent; sys.path.insert(0,str(ROOT))
from evaluate_circle_prompt_candidates import evaluate
def extract(s):
    m=re.search(r'```(?:python)?\s*(.*?)```',s,re.I|re.S); return (m.group(1) if m else s).strip()+'\n'
def gen(prompt,seed,m):
    body=json.dumps({'model':m['model'],'prompt':prompt,'stream':False,'keep_alive':'0','options':{'temperature':m['temperature'],'seed':seed,'num_predict':m['num_predict']}}).encode(); req=urllib.request.Request('http://127.0.0.1:11435/api/generate',data=body,headers={'Content-Type':'application/json'},method='POST')
    with urllib.request.urlopen(req,timeout=600) as r:return json.loads(r.read().decode())
def main():
    m=json.loads((ROOT/'run_manifest.json').read_text()); rows=[]
    for t in m['trials']:
        d=ROOT/t['trial_id']; row={'trial_id':t['trial_id'],'sampling_seed':t['sampling_seed']}
        try:
            ans=gen((d/'prompt.txt').read_text(),t['sampling_seed'],m); response=str(ans.get('response','')); candidate=extract(response); (d/'response.txt').write_text(response); path=d/'candidate.py'; path.write_text(candidate); actual=hashlib.sha256(candidate.encode()).hexdigest(); row.update({'exact_patch_match':actual==t['expected_code_sha256'],'candidate_sha256':actual})
            if not row['exact_patch_match']: row['final']={'status':'rejected_patch_guard','score':None}
            else:
                row['precheck']=evaluate(path,m['precheck_timeout_seconds']); row['final']=evaluate(path,m['full_timeout_seconds']) if row['precheck']['status']=='valid' else {'status':'not_full_evaluated_precheck_failed','score':None}
        except Exception as e: row['final']={'status':'pipeline_error','score':None,'error':f'{type(e).__name__}: {e}'}
        row['timestamp_utc']=datetime.now(timezone.utc).isoformat(); rows.append(row); (ROOT/'generation_ledger.jsonl').open('a').write(json.dumps(row)+'\n'); print(t['trial_id'],row['final']['status'],flush=True)
    (ROOT/'results.json').write_text(json.dumps({'manifest':m,'outcomes':rows},indent=2))
if __name__=='__main__': main()
