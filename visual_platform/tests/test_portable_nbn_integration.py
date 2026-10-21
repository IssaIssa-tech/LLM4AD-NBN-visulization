import os
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch
import numpy as np
from visual_platform.nbn import bridge
from visual_platform import portable_nbn

class PortableIntegrationTests(unittest.TestCase):
    def tearDown(self):
        portable_nbn.clear_networks()

    def test_native_backend_and_zgr_layout(self):
        x=np.array([[1.,0.],[0.,1.],[1.,0.],[-1.,0.]])
        scores=[1.,2.,100.,3.]
        samples=[{"id":str(i),"sample_order":i,"score":f,"function":str(i)} for i,f in enumerate(scores)]
        with tempfile.TemporaryDirectory() as tmp, patch.dict(os.environ,{"VISUAL_PLATFORM_NBN_BACKEND":"portable","OFEC_NBN_METHOD":"static"}), patch.object(bridge,"get_codet5_embedding_matrix",return_value=(x,{})), patch.object(bridge,"_compute_exact_nbn",side_effect=AssertionError("exact backend must not run")):
            g=bridge.build_nbn_graph(samples,Path(tmp))
            self.assertEqual(g["graphSource"],"ofec_nbn_portable_cone_tree")
            self.assertEqual(g["graphBuildStats"]["nbnUniqueNodeCount"],3)
            self.assertEqual(g["graphBuildStats"]["layoutMode"],"cone_tree_python")
            self.assertEqual(g["nodes"][2]["ofecFitness"],1.)
            self.assertEqual(g["nodes"][2]["rawScore"],100.)
            self.assertTrue(g["nodes"][2]["isDuplicateEncoding"])
            parents=np.array([n["ofecParentIndex"] for n in g["nodes"]])
            distances=np.array([n["distanceToParent"] for n in g["nodes"]])
            xy=bridge._cone_tree_layout(parents,distances)
            np.testing.assert_allclose([[n["x"],n["y"]] for n in g["nodes"]],xy)
            for n in g["nodes"]:
                self.assertTrue(all(np.isfinite(n[k]) for k in ("x","y","z","zTree")))
            again=bridge.build_nbn_graph(samples,Path(tmp))
            self.assertTrue(again["graphBuildStats"]["nbnHandleReused"])
