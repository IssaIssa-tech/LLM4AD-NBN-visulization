"""Describe parent syntax without treating NBN regions as proven mechanisms."""
import ast,hashlib,json
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]
OUT=ROOT/'output/regional_prompt_comparison_draft_20261028'
class Mask(ast.NodeTransformer):
    def visit_FunctionDef(self,node):
        self.generic_visit(node)
        if node.body and isinstance(node.body[0],ast.Expr) and isinstance(node.body[0].value,ast.Constant) and isinstance(node.body[0].value.value,str):node.body.pop(0)
        return node
    def visit_Constant(self,node):
        if isinstance(node.value,(float,int)) and not isinstance(node.value,bool):return ast.copy_location(ast.Constant(value=0),node)
        return node
def main():
    target=OUT/'parent_structure_audit.json'
    if target.exists():raise SystemExit('Existing parent audit')
    manifest=json.loads((OUT/'draft_comparison_manifest.json').read_text());seen=set();rows=[]
    for request in manifest['unique_requests']:
        parent=request['parent']
        if parent['node_id'] in seen:continue
        seen.add(parent['node_id']);source=(OUT/request['request_id']/'parent_candidate.py').read_text();tree=ast.parse(source)
        assert hashlib.sha256(source.encode()).hexdigest()==parent['code_sha256']
        initializers=sorted({n.func.attr for n in ast.walk(tree) if isinstance(n,ast.Call) and isinstance(n.func,ast.Attribute) and isinstance(n.func.value,ast.Name) and n.func.value.id=='qmc'})
        fingerprint=hashlib.sha256(ast.dump(Mask().visit(tree),include_attributes=False).encode()).hexdigest()
        rows.append(dict(node_id=parent['node_id'],region_node_id=parent['region_node_id'],initializers=initializers,literal_masked_ast_sha256=fingerprint))
    report=dict(parents=len(rows),literal_masked_syntax_patterns=len({r['literal_masked_ast_sha256'] for r in rows}),rows=rows,interpretation='Numbers and function docstrings masked for a descriptive syntax check; this is not semantic equivalence, behavioral diversity or proof of distinct algorithms. Different NBN branches need not imply different mechanisms.')
    target.write_text(json.dumps(report,indent=2));print(json.dumps(report,indent=2))
if __name__=='__main__':main()
