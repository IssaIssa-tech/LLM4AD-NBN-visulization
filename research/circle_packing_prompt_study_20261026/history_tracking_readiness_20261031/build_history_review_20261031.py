"""Package read-only API snapshots for offline review, without a server tunnel."""
import argparse,base64,json
from pathlib import Path
parser=argparse.ArgumentParser();parser.add_argument('--static-dir',type=Path);parser.add_argument('--output-dir',type=Path);args=parser.parse_args()
root=Path.cwd()
static=args.static_dir or next(p for p in [root/'llm4ad_from_server/visual_platform/static',root/'visual_platform/static'] if p.is_dir())
out=args.output_dir or (Path(__file__).resolve().parent if (Path(__file__).resolve().parent/'gpu_study_snapshot.json').is_file() else root/'output/history_feature_verification_20261031')
template=(static/'research-history.html').read_text(encoding='utf-8')
css=(static/'research-history.css').read_text(encoding='utf-8')
js=(static/'research-history.js').read_text(encoding='utf-8')
for source,target in [('gpu_study_snapshot.json','research_history_review.html'),('acceptance_snapshot.json','tracking_feature_demo.html')]:
    raw=(out/source).read_bytes();json.loads(raw)
    encoded=base64.b64encode(raw).decode('ascii')
    embedded="window.HISTORY_SNAPSHOT=JSON.parse(new TextDecoder().decode(Uint8Array.from(atob('"+encoded+"'),c=>c.charCodeAt(0))));"
    html=template.replace('<link rel="stylesheet" href="/static/research-history.css">','<style>'+css+'</style>').replace('<script src="/static/research-history.js"></script>','<script>'+embedded+'</script><script>'+js+'</script>')
    (out/target).write_text(html,encoding='utf-8')
    print(target)
