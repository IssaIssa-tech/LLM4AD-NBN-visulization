"""Export new exact graph with explicit feasible-variant provenance."""
import json,math
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]
BASE=ROOT/'output/circle_prompt_effects_20261026'
OUT=BASE/'combined_nbn_feasible_20261027'
graph=json.loads((OUT/'combined_nbn_feasible_graph.json').read_text())['graph']
old=json.loads((BASE/'combined_nbn_m2ipd_20261027/combined_nbn_3d_data.json').read_text())
report=json.loads((OUT/'feasible_region_analysis.json').read_text())
trials=old['trials']+report['variants']; by_id={t['id']:t for t in trials}
nodes=graph['nodes']; index={n['id']:i for i,n in enumerate(nodes)}
def category(n):
    t=by_id.get(n['id'])
    if not t:return int(isinstance(n.get('rawScore'),(float,int)) and math.isfinite(n['rawScore']))
    if t.get('provenance')=='prepared_feasible_variant':return 6
    if t.get('provenance')=='prepared_algorithm_variant':return 5
    return {'valid':4,'invalid_geometry':3}.get(t['evaluation_status'],2)
for t in trials:
    i=index[t['id']];n=nodes[i];t.update(nodeIndex=i,x=n['x'],y=n['y'],z=n['z'])
data=dict(provenance=dict(nodes=len(nodes),edges=len(graph['edges']),promptCount=35,preparedCount=10,method=graph['distanceMetric']),nodes=[[n['x'],n['y'],n['z'],category(n)] for n in nodes],edges=[[index[e['source']],index[e['target']]] for e in graph['edges']],trials=trials)
assert len(nodes)==14045 and sum(n[3]==6 for n in data['nodes'])==5
assert all(0<=a<len(nodes) and 0<=b<len(nodes) for a,b in data['edges'])
(OUT/'combined_nbn_3d_data.json').write_text(json.dumps(data))
html=(BASE/'combined_nbn_m2ipd_20261027/combined_nbn_m2ipd_3d.html').read_text(encoding='utf-8')
html=html.replace('NBN + Sobol seed variants','NBN + feasible initialization')
html=html.replace('35 earlier prompt trials + 5 evaluated prepared algorithm variants','35 earlier prompt trials + 10 evaluated prepared algorithm variants')
html=html.replace('Orange: valid prompt outputs. Green: prepared Sobol seed variants.','Orange: valid prompt outputs. Green: seed variants. Pink: feasible initialization.')
html=html.replace('All five prepared variants remain','All five feasible-initialization variants remain')
html=html.replace('[.26,.91,.61]]','[.26,.91,.61],[1,.35,.75]]')
html=html.replace('prepared algorithm variant — valid</div>','prepared Sobol variant — valid</div><div class="row"><span class="sw" style="background:#ff59bf"></span>prepared feasible initialization — valid</div>')
html=html.replace("?0x42e79c:0xffb13b","?0x42e79c:t.provenance==='prepared_feasible_variant'?0xff59bf:0xffb13b")
html=html.replace("document.querySelector('#valid').checked];","document.querySelector('#valid').checked,document.querySelector('#valid').checked];")
(OUT/'combined_nbn_feasible_3d.html').write_text(html,encoding='utf-8')
print('Validated graph references; exported 14045 nodes, 45 experiment records')
