"""Derive a separately saved compatible embedding attempt; retain the failed probe."""
from pathlib import Path
root=Path(__file__).resolve().parent;s=(root/'embed_ael_nbn_sources_20261031.py').read_text(encoding='utf-8')
s=s.replace("root=Path(__file__).resolve().parent;assert root.name=='ael_nbn_analysis_20261031'","analysis_root=Path(__file__).resolve().parent;assert analysis_root.name=='ael_nbn_analysis_20261031'\nroot=analysis_root/'representation_512';root.mkdir()")
for name in ['INPUT_MANIFEST.json','MODEL_ASSETS.json','INPUT_AUDIT.json']:
    s=s.replace(f"(root/'{name}')",f"(analysis_root/'{name}')")
s=s.replace("root/'historical_vectors.private.npy'","analysis_root/'historical_vectors.private.npy'")
s=s.replace("root.parent/row['source_file']","analysis_root.parent/row['source_file']")
s=s.replace('anchor_samples=[1,947,3445,7918,9180,12852,13793,14000]',"anchor_samples=sorted({1,14000,*[d['candidate']['sample_order'] for d in m['historical_diagnostics']],*[round(1+i*13999/31) for i in range(32)]})")
s=s.replace('1024','512')
(root/'embed_ael_nbn_reconciled_20261031.py').write_text(s,encoding='utf-8',newline='\n')
