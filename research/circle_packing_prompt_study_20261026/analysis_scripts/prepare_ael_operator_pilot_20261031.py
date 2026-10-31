"""Prepare six fixed AEL chains; never executes parents or requests an LLM."""
import json,random,shutil
from pathlib import Path
from ael_pilot_common import NAME,REVISION,MODEL,sha,load,save,write,payload

base=Path(__file__).resolve().parents[1];repo=base/'LLM4AD-NBN-visualization-github'
study=repo/'research/circle_packing_prompt_study_20261026';out=base/'output'/NAME
assert not out.exists(),'Existing pilot: inspect, do not repeat preparation'
parents=sorted(load(base/'output/ael_parent_eligibility_20261031/eligible_parent_options.json')['candidates'],key=lambda p:p['sample_order'])
assert len(parents)==22
prior=load(base/'output/ael_parent_eligibility_20261031/registration.json')['frozen']
templates=study/'paper_prompt_reference_review_20261031/templates'
cross=(templates/'ael_crossover.txt').read_text(encoding='utf-8')
mutation=(templates/'ael_mutation.txt').read_text(encoding='utf-8')
# Common operators; no policy/branch labels in model input. Evaluation provenance
# is supplied in each historical context, not replaced with archived fitness.
cross=cross.replace('Context records identify historical programs and their NBN nodes.', 'Context records identify historical programs.').replace('Historical context, with source IDs, NBN IDs, source hashes, score provenance, descriptions and source code:', 'Two historical parent records, with observed evaluation provenance, descriptions and complete source code:')
mutation=mutation.replace('Context records identify historical programs and their NBN nodes. Treat archived scores as archival provenance, not as measurements under the current budget. Any separate measured diagnostic score must retain its original evaluation provenance. NBN branches describe code-space grouping, not guaranteed physical basins.', 'The supplied parent is the program produced by the immediately preceding crossover. Revise that actual program; no evaluation feedback is supplied.').replace('Historical context, with source IDs, NBN IDs, source hashes, score provenance, descriptions and source code:', 'Actual crossover offspring, with its recorded docstring description and complete source code:')
out.mkdir();write(out/'crossover_template.txt',cross);write(out/'mutation_template.txt',mutation)
graph=load(study/'historical_data/circle_packing_historical_nbn_14000.json');graph=graph.get('graph',graph)
nodes={n['id']:n for n in graph['nodes']}
context={};references={}
for p in parents:
    code=(study/p['original_candidate_path']).read_text(encoding='utf-8').strip()
    assert sha(code.encode())==p['canonical_code_sha256']
    n=nodes[p['node_id']]
    context[p['sample_order']]=dict(source_id=p['node_id'],source_sha256=p['canonical_code_sha256'],observed_score=p['measured_score'],evaluation_provenance=dict(revision='ael-parent-eligibility-20261031',evaluation_id=p['evaluation_id'],n=26,wall_limit_seconds=20,numerical_threads=1,observations=1),archived_description=n.get('algorithm') or '[No archived description recorded]',source_code=code)
    references[p['sample_order']]=dict(id=p['node_id'],nbnNodeId=p['nbn_node_id'],regionNodeId=p['region_node_id'],regionIndex=p['region_index'],sampleOrder=p['sample_order'],codeSha256=p['canonical_code_sha256'],measuredScore=p['measured_score'],evaluationId=p['evaluation_id'],functionPreview=code,sourcePath=p['original_candidate_path'])
manifest=dict(status='prepared_not_executed',name=NAME,execution_revision_id=REVISION,source_platform_revision='circle-history-verified-20261028',source_graph_identity=prior['source_graph_identity'],evaluation=prior['evaluation'],evaluator_hashes=prior['evaluator_hashes'],numerical_threads=prior['numerical_thread_limits'],target_score=2.6360,
    paper=dict(title='Algorithm Evolution Using Large Language Model',pdf_sha256='b642d6a6853828a11d211520823b1e4b1c51048873ee78e6969d6d2dc80f23fb',source='Sections III.E and III.F; Fig.4'),
    model_blob_sha256=MODEL,binary_sha256='76c3242441229aef0ee02f122a2c09d80118487f1104ab1643e27380245e2002',context_size=8192,generation_timeout_seconds=900,
    sampling=dict(temperature=.1,top_k=40,top_p=.9,min_p=0.0,repeat_penalty=1.0,max_tokens=1800,stream=False),
    eligible_population=parents,selection_seeds=[2026103101,2026103102,2026103103],maximum_llm_calls=12,
    stopping_rule='Six prelisted chains; one crossover and at most one mutation each. No repairs, replacements, manual code edits, repeat evaluations or extension until target.',
    mutation_gate='Exactly one extracted program accepted by the existing static contract; independent of crossover fitness/geometry/timeout. No fitness feedback in mutation prompt.',
    adaptations=['Circle Packing N=26 instead of TSP','Historical eligible pool of 22; no full population evolution or survivor selection','Uniform random versus one-parent-per-HNSW-branch selection','One mutation per static-eligible crossover instead of paper probability 0.2','Both crossover and mutation evaluated once for diagnostics','Docstring mechanism description replaces external thought markers','Local Qwen2.5-Coder7B Q4_K_M; explicit 20-second research evaluator'],
    limitations=['Three pairs per policy, descriptive only; parent quality differs; not isolated branch causality','One common AEL template pair, no matched cross-paper comparison in this pilot','Source/AST differences do not establish structural or physical-basin diversity','No new NBN placements or official verifier equivalence claimed','Parent eligibility is one observed execution on the shortlist'],
    template_sha256=dict(crossover=sha(cross.encode()),mutation=sha(mutation.encode())),chains=[])
for policy in ['uniform','nbn_stratified']:
    for i,seed in enumerate(manifest['selection_seeds'],1):
        rng=random.Random(seed)
        if policy=='uniform':draw=rng.sample(parents,2)
        else:draw=[rng.choice([p for p in parents if p['region_index']==b]) for b in sorted({p['region_index'] for p in parents})]
        draw=sorted(draw,key=lambda p:p['sample_order']);cid=f'{policy}-{i}'
        prompt=cross.replace('{{PARENT_CONTEXTS}}',json.dumps([context[p['sample_order']] for p in draw],ensure_ascii=False,indent=2))
        folder=out/(cid+'-cross');folder.mkdir();write(folder/'prompt.txt',prompt)
        api=payload(manifest,prompt,seed);save(folder/'api_payload.json',api)
        manifest['chains'].append(dict(chain_id=cid,policy=policy,crossover_id=cid+'-cross',mutation_id=cid+'-mut',crossover_seed=seed,mutation_seed=seed+100,parents=[references[p['sample_order']] for p in draw],prompt_sha256=sha(prompt.encode()),payload_sha256=sha(json.dumps(api,sort_keys=True).encode())))
save(out/'manifest.json',manifest)
write(out/'PROTOCOL.md','''# AEL operator pilot — frozen before generation

Question: within the 22 measured eligible historical Circle Packing programs, how do uniform parent sampling and sampling across two frozen HNSW NBN branches affect the quality and diversity of AEL crossover/mutation outputs?

Three paired fixed seeds per policy select six parent pairs. Population order is ascending historical sample order. Uniform uses Python Random(seed).sample(pool,2); stratified uses choice within ascending branch indices 11414 and 13793. Parent prompt order is ascending sample order. No policy or branch label is inserted into the common crossover prompt. Actual measured parent scores retain evaluation provenance. Model/system/sampling settings are common; mutation uses seed+100 and the actual crossover code/docstring without score feedback.

Run crossover, evaluate it once, then mutate if and only if exactly one program was extracted and passed the existing static contract. Invalid geometry, timeout or low fitness do not prevent mutation. Static/extraction failure causes an explicitly recorded dependent skip. No retries, repair prompts, manual source edits, replacement candidates, or adaptive extension. Stop after six chains, at most twelve calls. Context-fit checks use the pinned runtime tokenizer before each request, without generation; context overflow is recorded and never silently truncated.

This adapts AEL Sections III.E/F and Fig.4, not the full paper population experiment. Historical initialization, pool size 22, Circle Packing, local Qwen, NBN stratification, mutation probability one, evaluation of both operators and a code-docstring output format are explicit adaptations. Original paper settings and old results remain preserved separately.

Evaluate N=26 once in the identical hits1 worker/environment used for the parent check, with twenty-second wall limit including startup and four numerical thread limits set to one. Save returned coordinates, stdout, stderr, status and score; independently verify saved geometry/sum without executing again. This research evaluator is not asserted equivalent to the official challenge verifier.

Report status counts, validity, target hits >=2.6360, observed valid scores, offspring-minus-best-parent and mutation-minus-crossover differences where defined, source/AST duplicates and inspected code mechanisms. Three chains per policy and differing parent quality permit descriptive findings, not statistical superiority or causal branch claims. Different initialization seeds in code are not automatically distinct algorithm mechanisms. New NBN placement requires separate measured embedding/graph work and is not implied by this pilot.

Keep all successes, failures, raw requests/responses, selected historical/NBN IDs, generated-parent lineage and configuration/source snapshots in platform history. Preserve the exact manifest and executable scripts by SHA256 before calls. Only this pilot's private model process may be started/stopped; shared files and other users' processes remain untouched.
''')
print(json.dumps(dict(output=str(out),pairs=[dict(id=c['chain_id'],parents=[p['sampleOrder'] for p in c['parents']]) for c in manifest['chains']]),indent=2))
