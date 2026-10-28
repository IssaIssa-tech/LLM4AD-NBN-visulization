"""Launch the isolated hits_1 platform without changing shared environments."""
import argparse,os,runpy,site,sys
from pathlib import Path
root=Path(__file__).resolve().parent
# Read existing research dependencies after this private venv's own packages.
dependency_dir='/home/dyy/llm4ad_env/lib/python3.10/site-packages'
site.addsitedir(dependency_dir)
# Keep the private packages first, then the coherent existing research stack.
# A venv created from a venv otherwise inherits its base Conda stack first.
sys.path.remove(dependency_dir)
private_site=str(Path(sys.prefix)/'lib/python3.10/site-packages')
sys.path.insert(sys.path.index(private_site)+1,dependency_dir)
sys.path.insert(0,str(root))
os.environ['VISUAL_PLATFORM_LOCAL_DATA_DIR']=str(root/'state')
os.environ['VISUAL_PLATFORM_DB']=str(root/'state/platform.sqlite3')
parser=argparse.ArgumentParser();parser.add_argument('--smoke',action='store_true');parser.add_argument('--audit-import',action='store_true');parser.add_argument('--apply-import',action='store_true');args=parser.parse_args()
if args.audit_import or args.apply_import:
    sys.argv=['import_verified_history.py']+(['--apply'] if args.apply_import else [])
    runpy.run_path(str(root/'import_verified_history.py'),run_name='__main__')
elif args.smoke:runpy.run_path(str(root/'platform_history_smoke.py'),run_name='__main__')
else:
    from visual_platform.runtime.app_factory import create_app
    create_app().run(host='127.0.0.1',port=5015,threaded=True,debug=False)
