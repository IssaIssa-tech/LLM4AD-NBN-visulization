"""Export versioned viewer with prepared variants identified separately."""
import json
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]
base=ROOT/'output/circle_prompt_effects_20261026'
out=base/'combined_nbn_m2ipd_20261027'
graph=json.loads((out/'combined_nbn_m2ipd_graph.json').read_text())['graph']
old=json.loads((base/'combined_nbn_m2ip_20261027/combined_nbn_3d_data.json').read_text())
analysis=json.loads((out/'m2ipd_region_analysis.json').read_text())
trials=old['trials']+analysis['variants']
by_id={t['id']:t for t in trials}
index={n['id']:i for i,n in enumerate(graph['nodes'])}
nodes=graph['nodes']
def category(n):
    t=by_id.get(n['id'])
    if not t: return 1 if n.get('rawScore') is not None and isinstance(n.get('rawScore'),(float,int)) else 0
    if t.get('provenance')=='prepared_algorithm_variant': return 5
    return {'valid':4,'invalid_geometry':3}.get(t['evaluation_status'],2)
for t in trials:
    i=index[t['id']]; n=nodes[i]
    t.update(nodeIndex=i,x=n['x'],y=n['y'],z=n['z'])
data=dict(provenance=dict(nodes=len(nodes),edges=len(graph['edges']),promptCount=35,preparedCount=5,method=graph['distanceMetric']),nodes=[[n['x'],n['y'],n['z'],category(n)] for n in nodes],edges=[[index[e['source']],index[e['target']]] for e in graph['edges']],trials=trials)
(out/'combined_nbn_3d_data.json').write_text(json.dumps(data))
html=(base/'combined_nbn_m2ip_20261027/combined_nbn_m2ip_3d.html').read_text(encoding='utf-8')
html=html.replace('NBN + M2-I-P —','NBN + Sobol seed variants —')
start=html.index("document.querySelector('#summary').innerHTML=")
end=html.index(';',start)
html=html[:start]+"document.querySelector('#summary').innerHTML=`${P.nodes.toLocaleString()} nodes · ${P.edges.toLocaleString()} exact nearest-better edges<br>35 earlier prompt trials + 5 evaluated prepared algorithm variants<br>Orange: valid prompt outputs. Green: prepared Sobol seed variants.<br>All five prepared variants remain in the same top-level historical branch.`"+html[end:]
html=html.replace('prompt valid solutions</label>','valid solutions and prepared variants</label>')
html=html.replace('</div>\n<script type="module">','<div class="row"><span class="sw" style="background:#42e79c"></span>prepared algorithm variant — valid</div></div>\n<script type="module">')
html=html.replace('[1,.60,.08]]','[1,.60,.08],[.26,.91,.61]]')
html=html.replace("document.querySelector('#valid').checked];","document.querySelector('#valid').checked,document.querySelector('#valid').checked];")
html=html.replace('color:0xffb13b,wireframe:true','color:t.provenance===\'prepared_algorithm_variant\'?0x42e79c:0xffb13b,wireframe:true')
(out/'combined_nbn_m2ipd_3d.html').write_text(html,encoding='utf-8')
print('Exported',len(nodes),'nodes;',len(trials),'experiment records')
