from __future__ import annotations

import math
import unittest

import numpy as np

from visual_platform.nbn.region_analysis import (
    NOVEL_MIN_DIST,
    RING_HI,
    RING_LO,
    VERDICT_BUDGET_OUT,
    VERDICT_FILLED,
    VERDICT_FRACTURE,
    VERDICT_SEEDLING,
    anchor_cluster_metrics,
    candidate_child_flags,
    classify_new_samples,
    corridor_comparison,
    exploration_conclusion,
    family_fold,
    final_verdict,
    gap_status,
    min_gap_to_better,
    neighborhood_coverage,
    normalize_valid_score,
    recommend_candidates,
)
from visual_platform.services.region_service import (
    _edge_length_from_graph,
    normalize_region_spec,
)
from visual_platform.runtime.region_runner import (
    _build_region_guidance,
    _region_shape_valid,
)
from visual_platform.runtime.runner_modes import (
    EVALUABILITY_CONSTRAINTS,
    direct_generation_prompt,
)


def _synthetic_nodes() -> tuple[list[dict], list[dict]]:
    scores = [10.0, 9.0, 8.0, 7.0, 6.0, 5.0]
    parents = [0, 0, 1, 2, 3, 4]
    distances = [0.0, 0.05, 0.01, 0.015, 0.4, 0.3]
    nodes = [
        {
            "id": f"n{i}",
            "score": scores[i],
            "rawScore": scores[i],
            "ofecIndex": i,
            "ofecParentIndex": parents[i],
            "distanceToParent": distances[i],
        }
        for i in range(6)
    ]
    edges = [
        {"source": f"n{i}", "target": f"n{parents[i]}", "distance": distances[i]}
        for i in range(1, 6)
    ]
    return nodes, edges


class RegionAnalysisTest(unittest.TestCase):
    def test_valid_score_normalization(self):
        self.assertEqual(normalize_valid_score(2.6), 2.6)
        self.assertEqual(normalize_valid_score("2.6"), 2.6)
        self.assertIsNone(normalize_valid_score(None))
        self.assertIsNone(normalize_valid_score(float("-inf")))
        self.assertIsNone(normalize_valid_score(float("inf")))
        self.assertIsNone(normalize_valid_score(float("nan")))
        self.assertIsNone(normalize_valid_score(1e208))

    def test_family_fold_deterministic_and_champion(self):
        nodes, _ = _synthetic_nodes()
        folded = family_fold(nodes)
        again = family_fold(nodes)
        self.assertEqual(folded["familyOf"], again["familyOf"])
        # n1/n2/n3 fold together (distances 0.01/0.015 < 0.02), n0 root, n4/n5 separate.
        self.assertEqual(folded["familyOf"]["n1"], folded["familyOf"]["n2"])
        self.assertEqual(folded["familyOf"]["n2"], folded["familyOf"]["n3"])
        self.assertNotEqual(folded["familyOf"]["n0"], folded["familyOf"]["n1"])
        self.assertEqual(folded["validCount"], 6)
        champion = folded["families"][folded["championId"]]
        self.assertEqual(champion["rep_id"], "n1")
        self.assertEqual(champion["size"], 3)
        self.assertTrue(champion.get("is_champion"))

    def test_recommend_candidates_rankings(self):
        nodes, edges = _synthetic_nodes()
        result = recommend_candidates({"nodes": nodes, "edges": edges})
        self.assertEqual(result["scoreDist"]["p75"], 8.75)
        # n0 (score 10 >= P75, non-champion) should be the only high-score expand.
        self.assertEqual([item["anchor"] for item in result["highScoreList"]], ["n0"])
        # Long edges sorted by distance desc.
        long_ids = [(item["a"], item["b"]) for item in result["longEdgeList"]]
        self.assertEqual(long_ids, [("n4", "n3"), ("n5", "n4"), ("n1", "n0")])
        self.assertEqual(result["champion"]["family_id"], folded_champion(result))

    def test_classify_lens_ring_novel_ship(self):
        rng = np.random.default_rng(0)
        emb = rng.normal(size=(6, 256)).astype(np.float32)
        emb /= np.linalg.norm(emb, axis=1, keepdims=True)
        anchor = {"a": emb[0], "b": emb[1]}
        history = emb[2:4]
        midpoint = emb[0] + 0.1 * (emb[1] - emb[0])
        midpoint /= np.linalg.norm(midpoint)
        midpoint = midpoint.reshape(1, -1).astype(np.float32)

        records = classify_new_samples(
            midpoint,
            [8.5],
            {"type": "edge", "a": "n0", "b": "n1"},
            anchor,
            history,
            ship_threshold=7.0,
        )
        self.assertTrue(records[0]["valid"])
        self.assertTrue(records[0]["hit"])
        self.assertTrue(records[0]["novel"])
        self.assertTrue(records[0]["ship"])

        # Invalid (-inf) samples never hit.
        records_invalid = classify_new_samples(
            midpoint,
            [float("-inf")],
            {"type": "edge", "a": "n0", "b": "n1"},
            anchor,
            history,
            ship_threshold=7.0,
        )
        self.assertFalse(records_invalid[0]["valid"])
        self.assertFalse(records_invalid[0]["hit"])
        self.assertFalse(records_invalid[0]["ship"])

        # Expand ring band.
        noise = rng.normal(size=256).astype(np.float32)
        noise -= float(noise.dot(emb[0])) * emb[0]
        noise /= np.linalg.norm(noise)
        ring_vector = emb[0] + 0.5 * noise
        ring_vector = (ring_vector / np.linalg.norm(ring_vector)).reshape(1, -1).astype(np.float32)
        ring_records = classify_new_samples(
            ring_vector,
            [6.0],
            {"type": "expand", "a": "n0"},
            {"a": emb[0]},
            history,
            ship_threshold=7.0,
        )
        self.assertLess(RING_LO, ring_records[0]["d_a"])
        self.assertLess(ring_records[0]["d_a"], RING_HI)
        self.assertTrue(ring_records[0]["hit"])

    def test_final_verdict_priority(self):
        self.assertEqual(
            final_verdict([{"ship_count": 1, "hit_count": 0, "novel_count": 0}]),
            VERDICT_FILLED,
        )
        self.assertEqual(
            final_verdict([{"ship_count": 0, "hit_count": 0, "novel_count": 0}], stopped_fracture=True),
            VERDICT_FRACTURE,
        )
        self.assertEqual(
            final_verdict([{"ship_count": 0, "hit_count": 3, "novel_count": 0}]),
            VERDICT_SEEDLING,
        )
        self.assertEqual(
            final_verdict([{"ship_count": 0, "hit_count": 0, "novel_count": 0}]),
            VERDICT_BUDGET_OUT,
        )

    def test_corridor_comparison(self):
        nodes, _ = _synthetic_nodes()
        result = corridor_comparison(
            {"nodes": nodes},
            {"nodes": nodes},
            {"type": "edge", "a": "n4", "b": "n3"},
        )
        self.assertEqual(result["edgeBefore"], 0.4)
        self.assertIn("corridorNodeCount", result)

    def test_candidate_child_flags(self):
        # Closer to the anchor than to its parent and inside the gap -> candidate.
        self.assertTrue(candidate_child_flags(0.05, 0.09, gap_upper=0.0946))
        # Farther than the parent -> not a candidate.
        self.assertFalse(candidate_child_flags(0.08, 0.05, gap_upper=0.0946))
        # Outside the gap upper bound -> not a candidate.
        self.assertFalse(candidate_child_flags(0.12, 0.20, gap_upper=0.0946))
        # Near-duplicate of the anchor -> not a candidate.
        self.assertFalse(candidate_child_flags(0.005, 0.09, gap_upper=0.0946))
        # Unknown parent distance -> fall back to a fixed closeness bound.
        self.assertTrue(candidate_child_flags(0.05, None))
        self.assertFalse(candidate_child_flags(0.15, None))

    def test_anchor_cluster_metrics(self):
        source_nodes, _ = _synthetic_nodes()
        # In the source graph n3 has no children; in the "new" graph give it one.
        new_nodes = [dict(n) for n in source_nodes]
        new_nodes.append(
            {
                "id": "c1",
                "score": 6.5,
                "rawScore": 6.5,
                "ofecIndex": 99,
                "ofecParentIndex": 3,
                "distanceToParent": 0.03,
            }
        )
        metrics = anchor_cluster_metrics(
            {"nodes": source_nodes},
            {"nodes": new_nodes},
            "n3",
        )
        self.assertIsNotNone(metrics)
        self.assertEqual(metrics["directChildrenBefore"], 1)  # n4 already hangs under n3
        self.assertEqual(metrics["directChildrenAfter"], 2)  # + the new child c1
        self.assertEqual(metrics["directChildrenGrowth"], 1)
        self.assertEqual(metrics["bestChildScore"], 6.5)
        self.assertIsNone(anchor_cluster_metrics({"nodes": source_nodes}, {"nodes": new_nodes}, "missing"))

    def test_neighborhood_coverage(self):
        d_as = [0.03, 0.04, 0.07, 0.11, 0.25]
        result = neighborhood_coverage(d_as)
        self.assertEqual(result["covered"], 4)
        self.assertEqual(result["total"], 5)
        self.assertEqual(result["buckets"]["0.02-0.05"], 2)
        # Everything clustered in one band -> coverage 1.
        clustered = neighborhood_coverage([0.07, 0.08, 0.09, 0.095])
        self.assertEqual(clustered["covered"], 1)

    def test_exploration_conclusion(self):
        # Two consecutive zero-novel, no-improvement segments -> exhausted.
        segments = [
            {"novel_count": 2, "best_score": 2.5},
            {"novel_count": 0, "best_score": 2.5},
            {"novel_count": 0, "best_score": 2.5},
        ]
        self.assertTrue(exploration_conclusion(segments)["exhausted"])
        # A novel or improving segment resets the counter.
        segments2 = [
            {"novel_count": 0, "best_score": 2.5},
            {"novel_count": 1, "best_score": 2.5},
            {"novel_count": 0, "best_score": 2.6},
            {"novel_count": 0, "best_score": 2.6},
        ]
        self.assertFalse(exploration_conclusion(segments2)["exhausted"])

    def test_gap_status(self):
        self.assertEqual(gap_status(0.03), "被围堵")
        self.assertEqual(gap_status(0.12), "真空白")
        self.assertEqual(gap_status(0.07), "中等")
        self.assertEqual(gap_status(None), "unknown")

    def test_min_gap_to_better_ignores_ties(self):
        # Anchor at 2.618 with a tie-scored sibling at 0.043 and a strictly
        # better solution at 0.094: the gap must be 0.094, not 0.043.
        anchor_score = 2.6180682546064302
        scores = [2.6180682546064302, 2.6180682546064302, 2.624414401698106]
        distances = [0.0432, 0.0432, 0.0941]
        gap = min_gap_to_better(anchor_score, scores, distances)
        self.assertAlmostEqual(gap, 0.0941, places=4)
        self.assertEqual(gap_status(gap), "中等")
        # No strictly-better solution -> None (global maximum).
        self.assertIsNone(
            min_gap_to_better(anchor_score, [2.5, 2.6, anchor_score], [0.1, 0.2, 0.0])
        )


class RegionServiceTest(unittest.TestCase):
    def test_normalize_region_spec(self):
        self.assertEqual(
            normalize_region_spec({"type": "edge", "a": "x", "b": "y"}),
            {"type": "edge", "a": "x", "b": "y"},
        )
        self.assertEqual(
            normalize_region_spec({"type": "expand", "a": "x"}),
            {"type": "expand", "a": "x"},
        )
        self.assertIsNone(normalize_region_spec({"type": "edge", "a": "x"}))
        self.assertIsNone(normalize_region_spec({"type": "edge", "a": "x", "b": "x"}))
        self.assertIsNone(normalize_region_spec({"type": "circle", "a": "x"}))
        self.assertIsNone(normalize_region_spec(None))

    def test_region_shape_valid(self):
        self.assertTrue(_region_shape_valid({"type": "edge", "a": "x", "b": "y"}))
        self.assertTrue(_region_shape_valid({"type": "expand", "a": "x"}))
        self.assertFalse(_region_shape_valid({"type": "edge", "a": "x"}))
        self.assertFalse(_region_shape_valid({"type": "edge", "a": "x", "b": "x"}))

    def test_edge_length_from_graph(self):
        nodes, edges = _synthetic_nodes()
        self.assertEqual(_edge_length_from_graph({"nodes": nodes, "edges": edges}, "n4", "n3"), 0.4)
        self.assertEqual(_edge_length_from_graph({"nodes": nodes, "edges": edges}, "n1", "n0"), 0.05)
        # Without edges the fallback reads distanceToParent from node records.
        self.assertEqual(_edge_length_from_graph({"nodes": nodes, "edges": []}, "n4", "n3"), 0.4)
        bare_nodes = [dict(node) for node in nodes]
        for node in bare_nodes:
            node.pop("distanceToParent", None)
        self.assertIsNone(_edge_length_from_graph({"nodes": bare_nodes, "edges": []}, "n4", "n3"))


class RegionPromptTest(unittest.TestCase):
    def test_edge_guidance_contains_goal_and_constraints(self):
        anchor = {"id": "a1", "score": 2.6, "algorithm": "constructive", "functionPreview": "def pack_circles(n):\n    pass"}
        direction = {"id": "b1", "score": 2.5, "algorithm": "greedy", "functionPreview": "def pack_circles(n):\n    pass"}
        text = _build_region_guidance(
            {"type": "edge", "a": "a1", "b": "b1"},
            anchor,
            [direction],
            d_ab=0.12,
            user_prompt="focus on spiral placement",
            champion_block="[AVOID -- the dominant family]\nplateaus",
        )
        self.assertIn("REGION GOAL", text)
        self.assertIn("AVOID", text)
        self.assertNotIn("ROUND FEEDBACK", text)
        self.assertIn("pack_circles", text)
        self.assertIn("Mandatory evaluability hard constraints", text)
        self.assertIn("focus on spiral placement", text)

    def test_expand_guidance_uses_ring_band(self):
        anchor = {"id": "a1", "score": 2.6, "algorithm": "constructive", "functionPreview": "def pack_circles(n):\n    pass"}
        text = _build_region_guidance(
            {"type": "expand", "a": "a1"},
            anchor,
            [],
            d_ab=None,
            user_prompt="",
            champion_block="",
        )
        self.assertIn("REGION GOAL", text)
        self.assertIn(f"{RING_LO:.2f}", text)
        self.assertIn(f"{RING_HI:.2f}", text)
        self.assertIn("BEAT it", text)
        self.assertIn("not bound by it", text)
        self.assertNotIn("ROUND FEEDBACK", text)

    def test_direct_generation_relation_directive_and_constraints(self):
        from llm4ad.base.code import TextFunctionProgramConverter

        template = "import numpy as np\ndef pack_circles(n: int) -> np.ndarray:\n    pass"
        template_function = TextFunctionProgramConverter.text_to_function(template)
        refs = [
            {
                "id": "anchor-1",
                "sampleOrder": 1,
                "rawScore": 2.618,
                "operator": "expert",
                "algorithm": "anchor algo",
                "functionPreview": "def pack_circles(n):\n    pass",
            }
        ]
        text = direct_generation_prompt(
            "Task description.",
            template_function,
            user_prompt="",
            reference_nodes=refs,
            attempt_index=1,
            total_attempts=10,
            relation_directive="[arm2] combine the common backbone",
        )
        self.assertIn("[RELATION DIRECTIVE]", text)
        self.assertIn("[arm2] combine the common backbone", text)
        self.assertIn("Hard time limit ~10 seconds", text)
        self.assertIn("random seed to 2025", text)
        self.assertIn("no top-level loops/calls/print", text)
        # Constraints are independent of the relation directive.
        self.assertIn(EVALUABILITY_CONSTRAINTS[:40], text)


def folded_champion(result: dict) -> str:
    return result["champion"]["family_id"]


if __name__ == "__main__":
    unittest.main(verbosity=2)
