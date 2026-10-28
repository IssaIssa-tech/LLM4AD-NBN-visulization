"""Prepare a canonical graph-mapped import while preserving every ZIP record."""
import argparse,ast,hashlib,json,math
from collections import Counter,defaultdict
from pathlib import Path
from zipfile import ZipFile
ROOT=Path(__file__).resolve().parents[1]
SOURCE=ROOT/'LLM4AD-NBN-visualization-github/research/circle_packing_prompt_study_20261026/historical_data'
OUT=ROOT/'output/historical_import_20261028'
def sha(data):return hashlib.sha256(data).hexdigest()
def clean(value):
    if isinstance(value,float) and not math.isfinite(value):return {'nonfinite':str(value)}
    if isinstance(value,dict):return {k:clean(v) for k,v in value.items()}
    if isinstance(value,list):return [clean(v) for v in value]
    return value
def normalized(source):
    source=str(source or '').strip()
    try:ast.parse(source);return source
    except SyntaxError:return source.replace('\\n','\n').replace('\\t','\t').replace('\\"','"')
def main():
    global OUT
    parser=argparse.ArgumentParser();parser.add_argument('--archive',type=Path);parser.add_argument('--output',type=Path);args=parser.parse_args()
    if args.output:OUT=args.output.resolve()
    if OUT.exists():raise SystemExit('Existing audit; refusing overwrite')
    graph_path=SOURCE/'circle_packing_historical_nbn_14000.json';zip_path=args.archive or SOURCE/'EoH_sample_history_14000.zip'
    graph_file=json.loads(graph_path.read_text(encoding='utf-8'));graph=graph_file['graph']
    nodes=graph['nodes'];assert len(nodes)==14000 and len({n['id'] for n in nodes})==14000
    assert {n['sampleOrder'] for n in nodes}==set(range(1,14001))
    by_order=defaultdict(list);raw=[];parse_issues=[]
    decoder=json.JSONDecoder()
    with ZipFile(zip_path) as archive:
        for name in archive.namelist():
            if not name.endswith('.json'):continue
            text=archive.read(name).decode('utf-8');position=0;value_index=0
            while text[position:].strip():
                while position<len(text) and text[position].isspace():position+=1
                try:value,end=decoder.raw_decode(text,position)
                except json.JSONDecodeError as error:
                    parse_issues.append(dict(entry=name,offset=position,error=str(error),unparsed_chars=len(text)-position));break
                position=end;value_index+=1
                entries=value if isinstance(value,list) else value.get('samples',[]) if isinstance(value,dict) else []
                for index,item in enumerate(entries):
                    record=dict(entry=name,json_value=value_index,item_index=index,record=item)
                    raw.append(record)
                    if isinstance(item,dict) and isinstance(item.get('sample_order'),int):by_order[item['sample_order']].append(record)
    canonical=[];mapping=[];mismatches=[];counts=Counter()
    for node in nodes:
        order=node['sampleOrder'];code=str(node.get('functionPreview') or '').strip();assert code
        code_digest=sha(code.encode());matches=[r for r in by_order[order] if sha(normalized(r['record'].get('function')).encode())==code_digest]
        if not matches:mismatches.append(order)
        score=node.get('rawScore');status='missing_or_nonfinite_in_graph' if score is None else 'negative_sentinel' if score<0 else 'finite_archived_score'
        counts[status]+=1
        refs=[dict(entry=r['entry'],json_value=r['json_value'],item_index=r['item_index']) for r in matches]
        provenance=dict(source_graph_sha256=sha(graph_path.read_bytes()) if not canonical else canonical[0]['provenance']['source_graph_sha256'],original_node_id=node['id'],nbn_node_id=node.get('nbnNodeId'),ofec_index=node.get('ofecIndex'),ofec_parent_index=node.get('ofecParentIndex'),source_run_id=node.get('sourceRunId'),code_sha256=code_digest,archive_matches=refs,score_status=status,reevaluated=False)
        canonical.append(dict(id=node['id'],sample_order=order,function=code,algorithm=node.get('algorithm',''),operator=node.get('operator',''),score=score,source_kind='historical',origin_kind='historical',provenance=provenance))
        mapping.append(dict(sample_order=order,node_id=node['id'],nbn_node_id=node.get('nbnNodeId'),code_sha256=code_digest,matching_archive_records=len(matches)))
    assert not mismatches,f'Graph/archive code mismatches: {mismatches[:20]}'
    ids={n['id'] for n in nodes};assert all(e['source'] in ids and e['target'] in ids for e in graph['edges'])
    report=dict(graph_nodes=len(nodes),graph_edges=len(graph['edges']),source_graph_sha256=sha(graph_path.read_bytes()),archive_sha256=sha(zip_path.read_bytes()),raw_archive_records=len(raw),unique_archive_sample_orders=len(by_order),orders_with_multiple_records=sum(len(v)>1 for v in by_order.values()),canonical_import_records=len(canonical),graph_archive_code_mismatches=mismatches,parse_issues=parse_issues,score_classes=dict(counts),source_backend=graph.get('graphBuildStats'),score_policy='Canonical code and rawScore from preserved graph; all ZIP records retained separately; no fresh evaluation',source_files=dict(graph=graph_path.name,archive=zip_path.name))
    OUT.mkdir()
    for name,records in [('raw_archive_records.jsonl',raw),('canonical_programs.jsonl',canonical)]:
        with (OUT/name).open('w',encoding='utf-8') as stream:
            for record in records:stream.write(json.dumps(clean(record),ensure_ascii=False,allow_nan=False)+'\n')
    (OUT/'program_node_mapping.json').write_text(json.dumps(mapping,indent=2),encoding='utf-8')
    (OUT/'audit.json').write_text(json.dumps(report,indent=2),encoding='utf-8');print(json.dumps(report,indent=2))
if __name__=='__main__':main()
