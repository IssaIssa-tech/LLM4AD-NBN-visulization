"""Run focused history tests in our private platform environment."""
import site,sys,unittest
from pathlib import Path
root=Path(__file__).resolve().parent
dep='/home/dyy/llm4ad_env/lib/python3.10/site-packages';site.addsitedir(dep);sys.path.remove(dep)
private=str(Path(sys.prefix)/'lib/python3.10/site-packages');sys.path.insert(sys.path.index(private)+1,dep);sys.path.insert(0,str(root))
suite=unittest.TestSuite(unittest.defaultTestLoader.loadTestsFromName('visual_platform.tests.'+name) for name in ['test_history_view','test_research_history','test_packing_history'])
result=unittest.TextTestRunner(verbosity=2).run(suite);raise SystemExit(not result.wasSuccessful())
