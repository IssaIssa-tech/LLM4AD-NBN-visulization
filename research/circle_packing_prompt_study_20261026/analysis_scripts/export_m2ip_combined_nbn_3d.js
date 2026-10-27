// Export the exact 14,035-node M2-I-P combined NBN for the existing 3D viewer.
const fs=require('fs'),path=require('path');
const root=path.resolve(__dirname,'..');
const out=path.join(root,'output','circle_prompt_effects_20261026','combined_nbn_m2ip_20261027');
const graph=JSON.parse(fs.readFileSync(path.join(out,'combined_nbn_m2ip_graph.json'),'utf8')).graph;
const old=JSON.parse(fs.readFileSync(path.join(root,'output','circle_prompt_preflight_20261025','combined_nbn_20261026_v2','trial_manifest.json'),'utf8'));
const added=JSON.parse(fs.readFileSync(path.join(out,'m2ip_trial_manifest.json'),'utf8'));
const trials=[...old,...added], byId=new Map(trials.map(x=>[x.id,x])), index=new Map(graph.nodes.map((n,i)=>[n.id,i]));
const status=x=>x.evaluation_status==='valid'?4:x.evaluation_status==='invalid_geometry'?3:2;
const data={provenance:{source:'combined_nbn_m2ip_graph.json',method:graph.distanceMetric,nbnMode:graph.graphBuildStats.nbnMode,nodes:graph.nodes.length,edges:graph.edges.length,trialCount:trials.length,trialStatusCounts:trials.reduce((a,x)=>((a[x.evaluation_status]=(a[x.evaluation_status]||0)+1),a),{}),m2ipTrialCount:added.length,m2ipUniqueCandidateCount:1},nodes:graph.nodes.map(n=>[n.x,n.y,n.z,byId.has(n.id)?status(byId.get(n.id)):Number.isFinite(n.score)?1:0]),edges:graph.edges.map(e=>[index.get(e.source),index.get(e.target)]),trials:trials.map(t=>{const n=graph.nodes[index.get(t.id)],p=graph.nodes[n.ofecParentIndex];return {...t,nodeIndex:index.get(t.id),x:n.x,y:n.y,z:n.z,parentId:p?.id||null,parentScore:p?.score??null,distanceToParent:n.distanceToParent}})};
fs.writeFileSync(path.join(out,'combined_nbn_3d_data.json'),JSON.stringify(data));console.log(JSON.stringify(data.provenance,null,2));
