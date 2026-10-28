"""Freeze graph-defined regional references before any new evaluation."""
import ast,hashlib,json,math
from collections import defaultdict
from datetime import datetime,timezone
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]
SOURCE=ROOT/'LLM4AD-NBN-visualization-github/research/circle_packing_prompt_study_20261026/historical_data/circle_packing_historical_nbn_14000.json'
OUT=ROOT/'output/regional_representatives_20261028'
def sha(s):return hashlib.sha256(s.encode()).hexdigest()
def main():
    if OUT.exists():raise SystemExit('Existing selection; refusing to replace')
    graph=json.loads(SOURCE.read_text(encoding='utf-8'))['graph'];nodes=graph['nodes'];by_index={n['ofecIndex']:n for n in nodes}
    roots=[i for i,n in by_index.items() if n['ofecParentIndex']==i];assert len(roots)==1;root=roots[0]
    memo={root:root}
    def branch(index):
        if index in memo:return memo[index]
        cur=index;trail=[];seen=set()
        while cur not in memo:
            assert cur not in seen,'Cycle in parent tree';seen.add(cur);trail.append(cur)
            parent=by_index[cur]['ofecParentIndex']
            if parent==root:memo[cur]=cur;break
            cur=parent
        value=memo[cur]
        for item in trail:memo[item]=value
        return value
    groups=defaultdict(list)
    for index,node in by_index.items():groups[branch(index)].append(node)
    regions=[]
    for index,members in groups.items():
        positive=[n for n in members if isinstance(n.get('rawScore'),(int,float)) and math.isfinite(n['rawScore']) and n['rawScore']>0]
        if len(members)>=20 and len(positive)>=5:
            regions.append(dict(branch_index=index,branch_node_id=by_index[index]['id'],members=len(members),positive_scores=len(positive),best_archived_score=max(n['rawScore'] for n in positive),positive_nodes=positive))
    regions.sort(key=lambda r:(-r['best_archived_score'],r['branch_index']))
    # Same supported-region thresholds used in earlier region analysis, now on
    # the explicitly frozen imported HNSW graph. Selection is a proposed rule.
    selected_regions=regions[:4];references=[];used=set()
    for region in selected_regions:
        ranked=sorted(region['positive_nodes'],key=lambda n:(n['rawScore'],n['sampleOrder']))
        for role,q in [('high_score',1.0),('median_score',.5),('lower_positive_score',.1)]:
            target=round(q*(len(ranked)-1))
            candidates=sorted(enumerate(ranked),key=lambda pair:(abs(pair[0]-target),pair[1]['sampleOrder']))
            for _,node in candidates:
                code=node['functionPreview'].strip();key=sha(code)
                if key not in used:break
            else:continue
            used.add(key)
            references.append(dict(reference_id=f"branch-{region['branch_index']}-{role}",role=role,region_index=region['branch_index'],region_node_id=region['branch_node_id'],node_id=node['id'],sample_order=node['sampleOrder'],nbn_node_id=node.get('nbnNodeId'),archived_score=node['rawScore'],code_sha256=key,code=code))
    champion=by_index[root];code=champion['functionPreview'].strip()
    if sha(code) not in used:references.append(dict(reference_id='historical-champion-control',role='champion_control',region_index=root,region_node_id=champion['id'],node_id=champion['id'],sample_order=champion['sampleOrder'],nbn_node_id=champion.get('nbnNodeId'),archived_score=champion['rawScore'],code_sha256=sha(code),code=code))
    prior_root=ROOT/'output/ael_paper_study_20261026/ael_initial_population_20261026_v2'
    prior_manifest=prior_root/'initial_population_manifest.json'
    # Link prior records by source-code hash; never claim their old outcomes
    # were measured in the new server environment.
    prior_files=list(prior_root.rglob('*.py'))
    prior_hashes={sha(p.read_text(encoding='utf-8').strip()):str(p.relative_to(ROOT)) for p in prior_files}
    OUT.mkdir()
    for reference in references:
        reference['prior_code_reference']=prior_hashes.get(reference['code_sha256'])
        folder=OUT/reference['reference_id'];folder.mkdir();(folder/'candidate.py').write_text(reference.pop('code'),encoding='utf-8')
    manifest=dict(status='selection_frozen_before_evaluation',registered_utc=datetime.now(timezone.utc).isoformat(),source_graph_sha256=hashlib.sha256(SOURCE.read_bytes()).hexdigest(),source_backend=graph['graphBuildStats'],region_definition='First descendant below unique self-parent root; root treated separately',selection_rule='Regions with >=20 members and >=5 positive archived scores; top four by archived best; choose distinct-code representatives near score ranks 100%, 50%, 10%, plus champion control',selection_rule_status='proposed operational sampling rule, not an empirically optimal strategy',total_graph_regions=len(groups),eligible_regions=len(regions),selected_regions=[{k:v for k,v in r.items() if k!='positive_nodes'} for r in selected_regions],references=references,evaluation_plan=dict(n=26,timeout_seconds=20,geometry_tolerance=1e-12,save_coordinates=True,model_calls=0,purpose='Research-budget diagnostic, not official challenge verification',interpretation='Timeouts or static rejection do not prove region quality; preserve all regions and prior records'))
    (OUT/'selection_manifest.json').write_text(json.dumps(manifest,indent=2),encoding='utf-8')
    print(json.dumps(dict(regions=manifest['selected_regions'],reference_count=len(references),prior_code_matches=sum(bool(r['prior_code_reference']) for r in references)),indent=2))
if __name__=='__main__':main()
