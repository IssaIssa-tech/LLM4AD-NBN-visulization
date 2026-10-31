"""Frozen rendering and strict response extraction for the finite AEL operator pilot."""
import ast,hashlib,json,re
from pathlib import Path

NAME='ael_operator_pilot_20261031'
REVISION='ael-operator-pilot-20261031'
H1='/mnt/data/dyy/llm4ad_nbn_research_20261013/platform_history_20261028'
H9='/home/dyy/issa_nbn_runtime_20261029'
MODEL='60e05f2100071479f596b964f89f510f057ce397ea22f2833a0cfe029bfc2463'
SYSTEM='You are Qwen, created by Alibaba Cloud. You are a helpful assistant.'
def sha(data):return hashlib.sha256(data).hexdigest()
def load(path):return json.loads(Path(path).read_text(encoding='utf-8'))
def save(path,value):
    with Path(path).open('x',encoding='utf-8',newline='\n') as f:json.dump(value,f,indent=2,allow_nan=False)
def write(path,text):
    with Path(path).open('x',encoding='utf-8',newline='\n') as f:f.write(text)
def extract(response):
    text=response['choices'][0]['message']['content']
    blocks=re.findall(r'```(?:python)?\s*\n(.*?)```',text,re.S)
    if len(blocks)!=1:raise ValueError('Expected exactly one Python code block')
    return blocks[0].strip()+'\n'
def description(code):
    tree=ast.parse(code)
    fn=next((n for n in tree.body if isinstance(n,ast.FunctionDef) and n.name=='pack_circles'),None)
    return (ast.get_docstring(fn) if fn else None) or '[No function-docstring description recorded; use the actual code below.]'
def payload(manifest,prompt,seed):
    return dict(model='qwen2.5-coder-7b-q4km',messages=[dict(role='system',content=SYSTEM),dict(role='user',content=prompt)],seed=seed,**manifest['sampling'])
def mutation_prompt(root,code):
    template=(Path(root)/'mutation_template.txt').read_text(encoding='utf-8')
    context=json.dumps(dict(description=description(code),source_code=code),ensure_ascii=False,indent=2)
    return template.replace('{{PARENT_CONTEXTS}}',context)
