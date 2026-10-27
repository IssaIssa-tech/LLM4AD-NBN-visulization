"""Register and run the fixed-parent M2 workflow; retain every call outcome."""
import argparse, ast, hashlib, json, os, platform, re, shutil, sys, urllib.request
from datetime import datetime, timezone
from pathlib import Path

def now(): return datetime.now(timezone.utc).isoformat()
def sha(text): return hashlib.sha256(text.encode()).hexdigest()
def ast_hash(text): return sha(ast.dump(ast.parse(text),include_attributes=False))
def eligible(result,floor): return result.get('status')=='valid' and result.get('score',float('-inf'))>=floor
def improves(result,incumbent,floor): return eligible(result,floor) and result['score']>incumbent['score']
def extract(text):
    blocks=re.findall(r'```(?:python)?\s*\n(.*?)```',text,re.S|re.I)
    if not blocks: blocks=[text]
    complete=[]
    for block in blocks:
        try:
            code=block.strip()+'\n';tree=ast.parse(code)
            if any(isinstance(n,ast.FunctionDef) and n.name=='pack_circles' for n in tree.body):complete.append(code)
        except SyntaxError:pass
    if len(complete)!=1:raise ValueError(f'Expected one complete program, found {len(complete)}')
    return complete[0]

def prepare():
    root=Path(__file__).resolve().parents[1];base=root/'output/circle_prompt_effects_20261026'
    draft=base/'prompt_guided_design_v1';out=base/'prompt_guided_workflow_v1_execution'
    if out.exists():raise SystemExit('Existing execution directory; inspect instead of repeating')
    plan=json.loads((draft/'draft_plan.json').read_text())
    assert sha((draft/'parent_candidate.py').read_text())==plan['parent']['code_sha256']
    assert sha((draft/'prompt_M2_v1.txt').read_text())==plan['prompt']['sha256']
    out.mkdir()
    for name in ('parent_candidate.py','prompt_M2_v1.txt','draft_plan.json'):shutil.copy2(draft/name,out)
    shutil.copy2(root/'analysis/evaluate_circle_prompt_candidates.py',out)
    shutil.copy2(__file__,out/'run_prompt_guided_workflow.py')
    print(out)

def register(root):
    if (root/'manifest.json').exists():raise SystemExit('Already registered; inspect existing manifest')
    plan=json.loads((root/'draft_plan.json').read_text());config=plan['proposed_model']
    # Read-only model availability and identity check. No generation here.
    with urllib.request.urlopen(config['endpoint'].replace('/api/generate','/api/tags'),timeout=15) as response:tags=json.load(response)
    matches=[m for m in tags.get('models',[]) if m.get('name')==config['name'] or m.get('model')==config['name']]
    if len(matches)!=1:raise SystemExit('Configured model not uniquely available')
    import numpy,scipy
    manifest=dict(status='registered_not_started',registered_utc=now(),draft=plan,model_identity=matches[0],
        environment=dict(python=sys.version,numpy=numpy.__version__,scipy=scipy.__version__,host=platform.node()),
        evaluator_bytes_sha256=hashlib.sha256((root/'evaluate_circle_prompt_candidates.py').read_bytes()).hexdigest(),
        runner_sha256=sha(Path(__file__).read_text()),stopping_rule='Five fixed one-call requests; no repair or replacement; fixed parent',
        extraction_rule='Exactly one parseable function-bearing block, followed by unchanged static screen',
        archival_rule='Save every request, reply, status, duplicate annotation and selection decision',
        preflight_rule='Stop before generation if parent is not valid/quality passing; log failure',
        actual_run_status='Determined by run_started.json, progress.json and results.json; this manifest is immutable')
    assert manifest['evaluator_bytes_sha256']==plan['evaluation']['evaluator_sha256']
    assert sha((root/'parent_candidate.py').read_text())==plan['parent']['code_sha256']
    assert sha((root/'prompt_M2_v1.txt').read_text())==plan['prompt']['sha256']
    (root/'manifest.json').write_text(json.dumps(manifest,indent=2))
    print('Registered model',matches[0].get('name'),'digest',matches[0].get('digest'),flush=True)

def run(root):
    sys.path.insert(0,str(root))
    from evaluate_circle_prompt_candidates import evaluate
    manifest=json.loads((root/'manifest.json').read_text());plan=manifest['draft'];config=plan['proposed_model']
    # Exclusive marker prevents accidental concurrent or repeated runs.
    with (root/'run_started.json').open('x') as stream:json.dump(dict(started_utc=now(),pid=os.getpid()),stream)
    assert hashlib.sha256((root/'evaluate_circle_prompt_candidates.py').read_bytes()).hexdigest()==manifest['evaluator_bytes_sha256']
    parent=(root/'parent_candidate.py').read_text();prompt=(root/'prompt_M2_v1.txt').read_text()
    assert sha(parent)==plan['parent']['code_sha256'] and sha(prompt)==plan['prompt']['sha256']
    floor=plan['evaluation']['quality_floor'];timeout=plan['evaluation']['timeout_seconds']
    control=evaluate(root/'parent_candidate.py',timeout)
    (root/'parent_control.json').write_text(json.dumps(control,indent=2))
    if not eligible(control,floor):
        (root/'results.json').write_text(json.dumps(dict(status='stopped_parent_ineligible',control=control,calls=0),indent=2));return
    incumbent=dict(id='parent',score=control['score'],code_sha256=sha(parent))
    raw_seen={sha(parent):'parent'};ast_seen={ast_hash(parent):'parent'};rows=[]
    for seed in plan['proposed_sampling_seeds']:
        trial_id=f'm2-v1-{seed}';folder=root/trial_id;folder.mkdir()
        row=dict(trial_id=trial_id,sampling_seed=seed,parent_sha256=sha(parent),incumbent_before=dict(incumbent),request_attempted=False)
        try:
            request=dict(model=config['name'],prompt=prompt,stream=False,keep_alive='0',options=dict(temperature=config['temperature'],num_predict=config['num_predict'],seed=seed))
            (folder/'request.json').write_text(json.dumps(request,indent=2));row['request_attempted']=True
            req=urllib.request.Request(config['endpoint'],data=json.dumps(request).encode(),headers={'Content-Type':'application/json'})
            with urllib.request.urlopen(req,timeout=600) as response:reply=json.load(response)
            (folder/'raw_reply.json').write_text(json.dumps(reply,indent=2));response_text=reply.get('response','')
            (folder/'response.txt').write_text(response_text);row['done_reason']=reply.get('done_reason')
            try:code=extract(response_text)
            except ValueError as error:
                row['evaluation']=dict(status='extraction_failure',score=None,error=str(error))
            else:
                path=folder/'candidate.py';path.write_text(code);rh=sha(code);ah=ast_hash(code)
                row.update(code_sha256=rh,ast_sha256=ah,raw_duplicate_of=raw_seen.get(rh),ast_duplicate_of=ast_seen.get(ah))
                raw_seen.setdefault(rh,trial_id);ast_seen.setdefault(ah,trial_id)
                row['evaluation']=evaluate(path,timeout)
                row['quality_passing']=eligible(row['evaluation'],floor)
                if improves(row['evaluation'],incumbent,floor):incumbent=dict(id=trial_id,score=row['evaluation']['score'],code_sha256=rh)
        except Exception as error:row['evaluation']=dict(status='generation_or_pipeline_error',score=None,error=f'{type(error).__name__}: {error}')
        row.update(completed_utc=now(),incumbent_after=dict(incumbent));rows.append(row)
        with (root/'ledger.jsonl').open('a') as stream:stream.write(json.dumps(row)+'\n')
        (root/'progress.json').write_text(json.dumps(dict(completed_trials=len(rows),incumbent=incumbent,outcomes=rows),indent=2))
        print(trial_id,row['evaluation']['status'],row['evaluation'].get('score'),flush=True)
    assert len(rows)==plan['budget_calls']
    (root/'results.json').write_text(json.dumps(dict(status='complete',completed_utc=now(),manifest=manifest,parent_control=control,outcomes=rows,incumbent=incumbent),indent=2))

def self_test():
    code='def pack_circles(n):\n    return n\n'
    assert extract('```python\nx=1\n```\n```python\n'+code+'```')==code
    for text in ('```python\nx=1\n```','```python\n'+code+'```\n```python\n'+code+'```'):
        try:extract(text)
        except ValueError:pass
        else:raise AssertionError('Ambiguous/incomplete output accepted')
    assert ast_hash(code)==ast_hash('# comment\n'+code)
    assert not improves(dict(status='invalid_geometry',score=99),dict(score=2),1)
    assert not improves(dict(status='valid',score=2),dict(score=2),1)
    assert improves(dict(status='valid',score=3),dict(score=2),1)
    print('Extraction ambiguity, AST duplicate and incumbent selection checks passed; zero network calls')

if __name__=='__main__':
    parser=argparse.ArgumentParser();parser.add_argument('action',choices=['prepare','register','run','self-test']);args=parser.parse_args()
    root=Path(__file__).resolve().parent
    if args.action=='prepare':prepare()
    elif args.action=='register':register(root)
    elif args.action=='run':run(root)
    else:self_test()
