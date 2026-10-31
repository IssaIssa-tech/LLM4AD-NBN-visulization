"""Audit existing AEL preparation and record source-backed study metadata.

Reads source and old outcomes only. No candidate execution or model calls.
"""
import argparse,ast,hashlib,json,subprocess
from collections import Counter
from pathlib import Path
parser=argparse.ArgumentParser(description=__doc__)
parser.add_argument('--workspace-root',type=Path,default=Path.cwd())
parser.add_argument('--output-dir',type=Path)
parser.add_argument('--paper',type=Path,default=Path('C:/Users/ISSA/Desktop/my research/Algorithm Evolution Using Large Language Model.pdf'))
args=parser.parse_args();ROOT=args.workspace_root.resolve()
REPO=ROOT/'LLM4AD-NBN-visualization-github'
if not REPO.is_dir() and (ROOT/'research/circle_packing_prompt_study_20261026').is_dir():REPO=ROOT
STUDY=REPO/'research/circle_packing_prompt_study_20261026'
AEL=STUDY/'paper_studies/ael'
OUT=args.output_dir or ROOT/'output/ael_method_review_20261031';OUT.mkdir(parents=True,exist_ok=True)
sha=lambda x:hashlib.sha256(x).hexdigest()
load=lambda p:json.loads(p.read_text(encoding='utf-8'))
inventory=[];canonical_sources={}
for path in sorted(AEL.rglob('*')):
    if not path.is_file():continue
    if path.relative_to(AEL).parts[0]=='ael_method_review_20261031':continue
    raw=path.read_bytes();row=dict(path=path.relative_to(STUDY).as_posix(),bytes=len(raw),sha256=sha(raw))
    if path.suffix=='.py':
        source=path.read_text(encoding='utf-8');tree=ast.parse(source)
        row.update(source_sha256=sha(source.strip().encode()),ast_sha256=sha(ast.dump(tree,include_attributes=False).encode()),top_level_functions=[n.name for n in tree.body if isinstance(n,ast.FunctionDef)])
        assert row['top_level_functions']==['pack_circles'],path
        canonical_sources.setdefault(row['source_sha256'],[]).append(row['path'])
    elif path.suffix=='.json':json.loads(raw)
    elif path.suffix=='.md':raw.decode('utf-8')
    inventory.append(row)
manifests=[]
for folder,key,filefield in [('ael_initial_population_20261026','seeds','seed_code_file'),('ael_initial_population_20261026_v2','seeds','seed_code_file'),('runtime_safe_seed_shortlist_20261026','candidates','candidate_code_file')]:
    filename='shortlist_manifest.json' if key=='candidates' else 'initial_population_manifest.json'
    data=load(AEL/folder/filename)
    for item in data[key]:
        path=AEL/folder/item[filefield]
        assert sha(path.read_text(encoding='utf-8').strip().encode())==item['code_sha256'],path
    manifests.append(dict(path=(AEL/folder/filename).relative_to(STUDY).as_posix(),records=len(data[key]),source_graph=data.get('source_graph'),source_graph_nbn_mode=data.get('source_graph_nbn_mode'),all_code_hashes_verified=True))
reevaluation=load(AEL/'ael_initial_population_20261026_v2/seed_reevaluation.json')
seed_manifest=load(AEL/'ael_initial_population_20261026_v2/initial_population_manifest.json')
by_rank={s['ael_seed_rank']:s for s in seed_manifest['seeds']}
for record in reevaluation['results']:
    seed=by_rank[record['ael_seed_rank']];path=AEL/'ael_initial_population_20261026_v2'/seed['seed_code_file']
    source=path.read_text(encoding='utf-8')
    # The old evaluator hashes file bytes; manifests hash stripped LF text.
    variants={sha(path.read_bytes()),sha(source.encode()),sha(source.replace('\n','\r\n').encode())}
    assert record['code_sha256'] in variants
    assert record['historical_id']==seed['historical_id']
    assert record['historical_sample_order']==seed['sample_order']
    assert record['status']=='timeout' and record['score'] is None
pdf=args.paper
paper=dict(title='Algorithm Evolution Using Large Language Model',authors=['Fei Liu','Xialiang Tong','Mingxuan Yuan','Qingfu Zhang'],arxiv='2311.15249v1',local_pdf=str(pdf),sha256=sha(pdf.read_bytes()),pages=11,reviewed_body_pages=list(range(1,10)),reference_pages=[10,11],visually_checked_method_and_results_pages=[3,4,5,6,7,8,9])
settings=dict(population_size=10,generations=10,crossover_probability=1.0,mutation_probability=0.2,crossover_parents=2,offspring_per_crossover=1,models=['GPT-3.5-turbo','GPT-4'],fitness_instances=64,fitness_problem='random TSP50',fitness_direction='minimize average gap to Gurobi')
review=load(STUDY/'paper_prompt_reference_review_20261031/reference_audit.json')
runtime_options=[{k:r[k] for k in ('sample_order','node_id','nbn_node_id','region_index','diagnostic_status','diagnostic_score','code_sha256','source_path')} for r in review['additional_parent_options']]
shortlist=load(AEL/'runtime_safe_seed_shortlist_20261026/shortlist_manifest.json')
audit=dict(status='AEL_method_review_and_existing_work_audit_complete',new_llm_calls=0,new_candidate_evaluations=0,paper=paper,paper_settings=settings,
    input_snapshot_git_commit=subprocess.check_output(['git','-C',str(REPO),'rev-parse','HEAD'],text=True).strip(),input_worktree_status=subprocess.check_output(['git','-C',str(REPO),'status','--porcelain','--',str(AEL)],text=True).strip(),inventory_scope='Existing AEL preparation excluding the method-review package itself',
    ael_folder_inventory=inventory,files_read=len(inventory),python_sources_parsed=sum('source_sha256' in r for r in inventory),unique_python_sources=len(canonical_sources),manifests_verified=manifests,
    existing_seed_recheck=dict(records=len(reevaluation['results']),outcomes=dict(Counter(r['status'] for r in reevaluation['results'])),timeout_seconds=reevaluation['timeout_seconds'],all_source_identities_verified=True),
    existing_static_shortlist=dict(records=len(shortlist['candidates']),status='static_only_in_this_AEL_folder',runtime_completion_not_established_by_static_filter=True),
    separate_regional_options=dict(status='previous_diagnostics_not_new_AEL_population',references=runtime_options,source_graph_sha256=review['source_graph_sha256'],backend=review['graph_backend'],region_count=len({r['region_index'] for r in runtime_options})),
    implementation_status=dict(ael_generation_result_found_in_existing_ael_folder=False,platform_modes_observed=['direct_ai','prompt_gen','real','seeded_eoh','region_search'],full_ael_population_schedule_verified=False),
    decision_already_recorded='Circle Packing N=26 adaptation with local/open-source LLM and historical programs; do not ask again whether to switch to TSP',
    before_live_run=['register operator pilot versus full population evolution','establish eligible initial parents under one evaluator/environment','freeze graph identity and region assignment','freeze actual model and request settings','specify budgets, lineage, failure accounting and stopping rule'])
(OUT/'AEL_READINESS_AUDIT.json').write_text(json.dumps(audit,indent=2),encoding='utf-8')
(OUT/'PAPER_SETTINGS.json').write_text(json.dumps(dict(paper=paper,reported_settings=settings,settings_role='paper_reference_only_not_an_executed_Circle_Packing_configuration'),indent=2),encoding='utf-8')
catalogue=load(STUDY/'paper_prompt_reference_review_20261031/prompt_catalogue.json')
profiles=[]
for identifier in ('ael_crossover','ael_mutation'):
    item=next(p for p in catalogue['templates'] if p['id']==identifier)
    path=STUDY/'paper_prompt_reference_review_20261031'/item['template_path']
    assert sha(path.read_text(encoding='utf-8').encode())==item['template_sha256']
    profiles.append(dict(id=identifier,operator=item['paper_operator'],minimum_parent_programs=item['minimum_parents'],template_path=path.relative_to(REPO).as_posix(),template_sha256=item['template_sha256'],status='existing_draft_reused_unexecuted'))
initial=OUT/'ael_initialization_draft.txt'
if not initial.is_file():initial=AEL/'ael_method_review_20261031/ael_initialization_draft.txt'
profiles.insert(0,dict(id='ael_initialization',operator='initialization',minimum_parent_programs=0,template_path='research/circle_packing_prompt_study_20261026/paper_studies/ael/ael_method_review_20261031/ael_initialization_draft.txt',template_sha256=sha(initial.read_text(encoding='utf-8').encode()),status='new_draft_unexecuted',usage='Alternative initialization route only; existing historical-seeding direction is unchanged'))
pack=dict(status='reading_preparation_only_not_registered_for_execution',paper_pdf_sha256=paper['sha256'],source_locations=dict(initialization='Section III.C, PDF p.4; Fig.4, PDF p.6',crossover='Section III.E, PDF p.5; Fig.4, PDF p.6',mutation='Section III.F, PDF p.5; Fig.4, PDF p.6'),profiles=profiles,
    complete_schedule='Initialize evaluated population; sample parents; crossover; optionally mutate crossover offspring; evaluate resulting program; collect generation; retain best N; repeat',
    adaptation=dict(task='Circle Packing in a unit square, N=26',llm_policy='local/open-source',score='maximize valid sum of radii',format='One code block; method description in docstring instead of paper start/end markers',nbn_guidance='Research extension, not an original AEL component'),
    pending_execution_choices=['eligible measured parent population','pilot versus complete evolutionary schedule','fixed local model/runtime and prompt-fit check','generation, mutation and evaluation budgets','stopping and failure/survivor policies'],new_model_calls=0,new_evaluations=0)
(OUT/'AEL_PROMPT_PACK.json').write_text(json.dumps(pack,indent=2),encoding='utf-8')
print(json.dumps({k:audit[k] for k in ('files_read','python_sources_parsed','unique_python_sources','existing_seed_recheck','existing_static_shortlist','new_llm_calls','new_candidate_evaluations')},indent=2))
