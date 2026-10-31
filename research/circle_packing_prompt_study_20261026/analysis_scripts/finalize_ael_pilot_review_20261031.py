"""Add the completed source-inspection finding to the saved HTML review."""
from pathlib import Path
root=Path(__file__).resolve().parents[1]/'output/ael_operator_pilot_20261031'
p=root/'ael_operator_pilot_review.html';s=p.read_text(encoding='utf-8')
marker='<p id="diversity"></p>'
assert marker in s and 'id="mechanism"' not in s
s=s.replace(marker,marker+'<p id="mechanism"><strong>Source inspection:</strong> all six crossover bodies match one selected historical parent after imports/docstrings are excluded. No valid output improves its better observed parent. All four exceptions are missing-qmc NameErrors. <a href="MECHANISM_REVIEW.md">Read the mechanism assessment</a>.</p>')
p.write_text(s,encoding='utf-8',newline='\n')
