from __future__ import annotations

import math
from typing import Any

import numpy as np

# ---------------------------------------------------------------------------
# Frozen thresholds for region search (see the plan doc for rationale).
# ---------------------------------------------------------------------------

#: CodeT5 cosine distance below which two solutions are treated as the same
#: family / as duplicates of history. Doubles as the family-fold threshold and
#: the novelty requirement for "different" solutions.
NOVEL_MIN_DIST = 0.02

#: Expansion (anchor neighborhood) ring band: d(n, A) in (RING_LO, RING_HI).
RING_LO = 0.02
RING_HI = 0.30

#: Ship ("different and relatively high-scoring") quantile over all valid
#: history scores. A solution ships when it is novel AND its score >= P75.
SHIP_QUANTILE = 0.75

#: Edge regions with distance below this are rejected as "short edges not worth
#: filling" (both endpoints are near-duplicates, no room in between).
MIN_EDGE_DIST = NOVEL_MIN_DIST

#: Distance buckets covering the expand ring band, used to measure how evenly
#: a neighbourhood is explored (coverage) instead of clustering in one band.
NEIGHBORHOOD_BUCKETS = (
    (0.02, 0.05),
    (0.05, 0.10),
    (0.10, 0.15),
    (0.15, 0.20),
    (0.20, 0.30),
)

#: A "true blank" high-scorer sits at least this far from every better solution;
#: below this it is boxed in by the champion family (gap status).
TRUE_BLANK_GAP = 0.10
BOXED_IN_GAP = 0.05

#: Score sanity limit (mirrors ofec_nbn_bridge / graph sample service).
SCORE_SANITY_LIMIT = 1e6

#: Verdict strings.
VERDICT_FILLED = "FILLED"
VERDICT_SEEDLING = "SEEDLING"
VERDICT_FRACTURE = "FRACTURE"
VERDICT_BUDGET_OUT = "BUDGET_OUT"
VERDICT_CANCELLED = "CANCELLED"


def normalize_valid_score(raw_score: Any) -> float | None:
    """Return the score when it is a usable finite number, else None.

    None / NaN / +-inf / |score| > SCORE_SANITY_LIMIT are treated as invalid
    (the circle-packing evaluator returns -inf for infeasible solutions and the
    runner stores None for parse failures).
    """
    if raw_score is None:
        return None
    try:
        value = float(raw_score)
    except (TypeError, ValueError):
        return None
    if not math.isfinite(value) or abs(value) > SCORE_SANITY_LIMIT:
        return None
    return value


def is_valid_score(raw_score: Any) -> bool:
    return normalize_valid_score(raw_score) is not None


def score_quantiles(scores: list[float], quantiles: tuple[float, ...] = (0.75,)) -> dict[str, float]:
    """Empirical quantiles over a list of finite scores (empty-safe)."""
    finite = [float(s) for s in scores if isinstance(s, (int, float)) and math.isfinite(float(s))]
    if not finite:
        return {f"p{int(q * 100)}": float("nan") for q in quantiles}
    arr = np.asarray(finite, dtype=np.float64)
    out: dict[str, float] = {}
    for q in quantiles:
        out[f"p{int(q * 100)}"] = float(np.quantile(arr, q))
    return out


def _node_score(node: dict[str, Any]) -> float | None:
    return normalize_valid_score(node.get("rawScore", node.get("score", node.get("ofecFitness"))))


def _valid_nodes(nodes: list[dict[str, Any]]) -> list[dict[str, Any]]:
    return [node for node in nodes if _node_score(node) is not None]


def family_fold(
    nodes: list[dict[str, Any]],
    *,
    fold_threshold: float = NOVEL_MIN_DIST,
) -> dict[str, Any]:
    """Fold an NBN graph's valid-score nodes into families.

    A node joins its parent's family when ``distanceToParent < fold_threshold``;
    otherwise it starts a new family (the family representative is its
    highest-score member, i.e. the first node processed). Parent edges always
    point to a strictly-better (or earlier same-score) node, so processing
    nodes in (score desc, ofecIndex asc) order assigns parents before children.

    Returns:
        {
          "familyOf": {node_id: family_id},
          "families": {family_id: family record},
          "skeleton": [family records sorted by rep score desc],
          "championId": family id of the largest family,
          "validCount": number of valid nodes folded,
        }
    """
    valid = _valid_nodes(nodes)
    by_index: dict[int, dict[str, Any]] = {}
    for node in valid:
        try:
            by_index[int(node.get("ofecIndex", -1))] = node
        except (TypeError, ValueError):
            continue

    ordered = sorted(
        valid,
        key=lambda node: (
            -(float(_node_score(node) or 0.0)),
            int(node.get("ofecIndex", 0) or 0),
        ),
    )

    family_of: dict[str, str] = {}
    families: dict[str, dict[str, Any]] = {}
    counter = 0

    for node in ordered:
        node_id = str(node.get("id") or "")
        if not node_id:
            continue
        parent_index = node.get("ofecParentIndex")
        parent = None
        if isinstance(parent_index, int):
            parent = by_index.get(parent_index)
        parent_id = str(parent.get("id") or "") if parent else None
        distance_to_parent = node.get("distanceToParent")
        try:
            distance_val = float(distance_to_parent)
        except (TypeError, ValueError):
            distance_val = math.inf

        joined_family: str | None = None
        if (
            parent_id
            and parent_id in family_of
            and distance_val < fold_threshold
            and distance_val >= 0.0
        ):
            joined_family = family_of[parent_id]

        if joined_family is None:
            counter += 1
            family_id = f"f{counter:04d}"
            family_of[node_id] = family_id
            families[family_id] = {
                "family_id": family_id,
                "rep_id": node_id,
                "rep_score": _node_score(node),
                "size": 1,
                "parent_family": None,
                "dist_to_parent": None if distance_val is math.inf else distance_val,
                "child_count": 0,
                "is_root": parent_id is None or parent_id == node_id,
                "member_ids": [node_id],
                "valid_count": 1,
            }
        else:
            family_of[node_id] = joined_family
            families[joined_family]["member_ids"].append(node_id)
            families[joined_family]["size"] += 1
            families[joined_family]["valid_count"] += 1

    # Children counts are computed over the whole edge set (valid endpoints).
    for node in valid:
        parent_index = node.get("ofecParentIndex")
        parent = by_index.get(parent_index) if isinstance(parent_index, int) else None
        if parent is None:
            continue
        child_id = str(node.get("id") or "")
        parent_id = str(parent.get("id") or "")
        child_family = family_of.get(child_id)
        parent_family = family_of.get(parent_id)
        if child_family and parent_family and child_family != parent_family:
            families[parent_family]["child_count"] = (
                int(families[parent_family].get("child_count", 0) or 0) + 1
            )
        if child_family and parent_family:
            families[child_family]["parent_family"] = parent_family

    # Champion = largest family (tie: higher rep score).
    champion_id: str | None = None
    for family_id, record in families.items():
        if champion_id is None:
            champion_id = family_id
            continue
        current = families[champion_id]
        if record["size"] > current["size"] or (
            record["size"] == current["size"] and (record["rep_score"] or 0.0) > (current["rep_score"] or 0.0)
        ):
            champion_id = family_id
    if champion_id:
        families[champion_id]["is_champion"] = True

    skeleton = sorted(
        families.values(),
        key=lambda item: (-(item["rep_score"] or 0.0), item["family_id"]),
    )
    return {
        "familyOf": family_of,
        "families": families,
        "skeleton": skeleton,
        "championId": champion_id,
        "validCount": len(valid),
    }


def _family_percentile(rep_score: float, scores: np.ndarray) -> float:
    if scores.size == 0:
        return 0.0
    return float(np.mean(scores <= rep_score))


def _incident_edges(edges: list[dict[str, Any]], node_id: str) -> list[dict[str, Any]]:
    out: list[dict[str, Any]] = []
    for edge in edges:
        source = str(edge.get("source") or "")
        target = str(edge.get("target") or "")
        if source == node_id:
            out.append({"peer": target, "role": "child", "distance": edge.get("distance")})
        elif target == node_id:
            out.append({"peer": source, "role": "parent", "distance": edge.get("distance")})
    return out


def recommend_candidates(
    graph: dict[str, Any],
    *,
    ship_quantile: float = SHIP_QUANTILE,
    fold_threshold: float = NOVEL_MIN_DIST,
    min_edge_dist: float = MIN_EDGE_DIST,
    top_k: int = 20,
) -> dict[str, Any]:
    """Rank regions worth searching: high-scoring non-champion families and
    long parent-child edges.

    Returns a leaderboard payload with:
      - champion / scoreDist / familyCount / validCount,
      - highScoreList: expand regions (anchor = family rep),
      - longEdgeList: edge regions (a = child, b = parent).
    """
    nodes = graph.get("nodes", []) if isinstance(graph, dict) else []
    edges = graph.get("edges", []) if isinstance(graph, dict) else []
    if not isinstance(nodes, list):
        nodes = []
    if not isinstance(edges, list):
        edges = []

    valid = _valid_nodes(nodes)
    scores = np.asarray(
        [float(_node_score(node)) for node in valid],
        dtype=np.float64,
    )
    if scores.size == 0:
        return {
            "champion": None,
            "scoreDist": {"p75": None, "count": 0},
            "familyCount": 0,
            "validCount": 0,
            "highScoreList": [],
            "longEdgeList": [],
        }

    ship_threshold = float(np.quantile(scores, ship_quantile))
    folded = family_fold(nodes, fold_threshold=fold_threshold)
    families = folded["families"]
    skeleton = folded["skeleton"]
    champion_id = folded["championId"]
    champion = families.get(champion_id) if champion_id else None
    id_to_node = {str(node.get("id") or ""): node for node in valid}

    high_score: list[dict[str, Any]] = []
    for record in skeleton:
        if record["family_id"] == champion_id:
            continue
        rep_score = float(record["rep_score"] or 0.0)
        if rep_score < ship_threshold - 1e-12:
            continue
        rep_id = record["rep_id"]
        incident = [
            item
            for item in _incident_edges(edges, rep_id)
            if item["peer"] in id_to_node
        ]
        far_neighbors = [
            item
            for item in incident
            if isinstance(item["distance"], (int, float)) and float(item["distance"]) >= min_edge_dist
        ]
        preferred = max(
            far_neighbors,
            key=lambda item: float(item["distance"]),
            default=None,
        )
        direction_text = "-"
        if preferred is not None:
            direction_text = (
                f"{preferred['peer']} (d={float(preferred['distance']):.5f}, "
                f"{preferred['role']})"
            )
        high_score.append(
            {
                "type": "expand",
                "anchor": rep_id,
                "direction": preferred["peer"] if preferred else None,
                "directionRole": preferred["role"] if preferred else None,
                "directionDistance": preferred["distance"] if preferred else None,
                "reason": (
                    f"rep_score={rep_score:.8f} (P{int(round(_family_percentile(rep_score, scores) * 100))}%), "
                    f"size={record['size']}, 邻居={len(incident)}, 首选方向={direction_text}"
                ),
                "repScore": rep_score,
                "familyId": record["family_id"],
                "familySize": record["size"],
                "percentile": round(_family_percentile(rep_score, scores), 4),
                "neighborCount": len(incident),
            }
        )
    high_score.sort(key=lambda item: (-item["repScore"], item["familySize"], item["familyId"]))
    # Keep a wider candidate pool than the final leaderboard: the service layer
    # ranks these by gap-to-nearest-better afterwards, so slightly lower-scoring
    # but genuinely isolated families are not cut off by the top-k.
    # A wide pool is required: the score-ordered leaderboard is dominated by
    # near-duplicate champion-family members, so genuinely isolated high
    # scorers (small families) rank far below. The service layer computes each
    # candidate's gap-to-nearest-better and re-ranks, so keep enough of them.
    high_score = high_score[: max(top_k * 10, 200)]

    long_edges: list[dict[str, Any]] = []
    for edge in edges:
        source = str(edge.get("source") or "")
        target = str(edge.get("target") or "")
        distance = edge.get("distance")
        if source not in id_to_node or target not in id_to_node:
            continue
        if not isinstance(distance, (int, float)) or not math.isfinite(float(distance)):
            continue
        if float(distance) < min_edge_dist:
            continue
        child_node = id_to_node[source]
        parent_node = id_to_node[target]
        child_score = float(_node_score(child_node) or 0.0)
        parent_score = float(_node_score(parent_node) or 0.0)
        child_family = folded["familyOf"].get(source)
        parent_family = folded["familyOf"].get(target)
        long_edges.append(
            {
                "type": "edge",
                "a": source,
                "b": target,
                "distance": float(distance),
                "reason": (
                    f"d={float(distance):.5f}, 子家族={child_family}(score={child_score:.5f}, "
                    f"size={families.get(child_family, {}).get('size', 1)}), "
                    f"父家族={parent_family}(score={parent_score:.5f}, "
                    f"size={families.get(parent_family, {}).get('size', 1)})"
                ),
                "childFamily": child_family,
                "parentFamily": parent_family,
                "childScore": child_score,
                "parentScore": parent_score,
                "childFamilySize": int(families.get(child_family, {}).get("size", 1) or 1),
                "parentFamilySize": int(families.get(parent_family, {}).get("size", 1) or 1),
            }
        )
    long_edges.sort(key=lambda item: -item["distance"])
    long_edges = long_edges[:top_k]

    return {
        "champion": champion,
        "scoreDist": {
            "p75": ship_threshold,
            "count": int(scores.size),
            "quantiles": score_quantiles(scores.tolist(), (0.25, 0.5, 0.75, 0.9, 0.95, 0.99)),
        },
        "familyCount": len(families),
        "validCount": int(scores.size),
        "highScoreList": high_score,
        "longEdgeList": long_edges,
        "_highScoreTopK": top_k,
    }


def _pairwise_distance(vectors: np.ndarray, anchor: np.ndarray) -> np.ndarray:
    anchor = np.asarray(anchor, dtype=np.float32).reshape(1, -1)
    similarity = np.clip(np.dot(vectors, anchor.T), -1.0, 1.0)
    return np.asarray(1.0 - similarity, dtype=np.float32).reshape(-1)


def classify_new_samples(
    new_vectors: np.ndarray,
    scores: list[Any],
    region: dict[str, Any],
    anchor_vectors: dict[str, np.ndarray],
    history_vectors: np.ndarray | None,
    *,
    novel_min_dist: float = NOVEL_MIN_DIST,
    ring_lo: float = RING_LO,
    ring_hi: float = RING_HI,
    ship_threshold: float,
) -> list[dict[str, Any]]:
    """Classify newly generated samples against a region.

    Edge region (lens): d(n,A) < d(A,B) AND d(n,B) < d(A,B).
    Expand region (ring): RING_LO < d(n,A) < RING_HI.
    Novel: min distance to every history vector > novel_min_dist.
    Ship: valid AND novel AND score >= ship_threshold.
    """
    vectors = np.asarray(new_vectors, dtype=np.float32)
    count = vectors.shape[0]
    region_type = str(region.get("type", "") or "").strip()
    a_key = "a"
    b_key = "b"
    a_vec = anchor_vectors.get(a_key)
    b_vec = anchor_vectors.get(b_key)
    if a_vec is None or a_vec.size == 0:
        raise ValueError("classify_new_samples requires an anchor vector 'a'.")
    if region_type == "edge" and (b_vec is None or b_vec.size == 0):
        raise ValueError("classify_new_samples requires an anchor vector 'b' for edge regions.")

    d_a = _pairwise_distance(vectors, a_vec)
    d_b = np.full(count, float("nan"), dtype=np.float32)
    d_ab = float("nan")
    if region_type == "edge":
        d_b = _pairwise_distance(vectors, b_vec)
        d_ab = float(_pairwise_distance(a_vec.reshape(1, -1), b_vec)[0])

    min_d_history = np.full(count, float("inf"), dtype=np.float32)
    if history_vectors is not None and history_vectors.shape[0] > 0:
        history = np.asarray(history_vectors, dtype=np.float32)
        similarity = np.clip(np.dot(vectors, history.T), -1.0, 1.0)
        min_d_history = np.asarray(1.0 - similarity.max(axis=1), dtype=np.float32)

    records: list[dict[str, Any]] = []
    for index in range(count):
        score = normalize_valid_score(scores[index] if index < len(scores) else None)
        valid = score is not None
        d_a_val = float(d_a[index])
        d_b_val = float(d_b[index]) if region_type == "edge" else None
        if region_type == "edge":
            hit = valid and math.isfinite(d_ab) and d_a_val < d_ab and d_b_val < d_ab
        else:
            hit = valid and ring_lo < d_a_val < ring_hi
        min_d = float(min_d_history[index])
        novel = bool(math.isfinite(min_d) and min_d > novel_min_dist) if history_vectors is not None and history_vectors.shape[0] else True
        ship = bool(valid and novel and (score or 0.0) >= ship_threshold)
        records.append(
            {
                "index": index,
                "score": score,
                "valid": valid,
                "d_a": d_a_val,
                "d_b": d_b_val,
                "d_ab": d_ab,
                "hit": bool(hit),
                "min_d_history": min_d,
                "novel": novel,
                "ship": ship,
            }
        )
    return records


def final_verdict(
    segments: list[dict[str, Any]],
    *,
    stopped_fracture: bool = False,
) -> str:
    """Map per-segment stats to a final region verdict.

    Priority: any ship -> FILLED; early FRACTURE stop -> FRACTURE; any
    hit/novel -> SEEDLING; otherwise budget exhausted -> BUDGET_OUT.
    """
    any_ship = any(bool(int(segment.get("ship_count", 0) or 0)) for segment in segments)
    if any_ship:
        return VERDICT_FILLED
    if stopped_fracture:
        return VERDICT_FRACTURE
    any_progress = any(
        bool(int(segment.get("hit_count", 0) or 0) + int(segment.get("novel_count", 0) or 0))
        for segment in segments
    )
    if any_progress:
        return VERDICT_SEEDLING
    return VERDICT_BUDGET_OUT


def corridor_comparison(
    source_graph: dict[str, Any] | None,
    new_graph: dict[str, Any] | None,
    region: dict[str, Any],
) -> dict[str, Any] | None:
    """Best-effort graph-only corridor comparison after a graph rebuild.

    Verifies whether a region's long edge got shorter (filled in) and how many
    nodes in the new graph sit inside the corridor's parent chain.
    """
    if not isinstance(source_graph, dict) or not isinstance(new_graph, dict):
        return None
    region_type = str(region.get("type", "") or "").strip()
    a_id = str(region.get("a", "") or "")
    b_id = str(region.get("b", "") or "")
    if not a_id:
        return None

    source_nodes = source_graph.get("nodes", []) if isinstance(source_graph.get("nodes"), list) else []
    new_nodes = new_graph.get("nodes", []) if isinstance(new_graph.get("nodes"), list) else []
    if not source_nodes or not new_nodes:
        return None

    def _edge_length(graph_nodes: list[dict[str, Any]], child_id: str) -> float | None:
        for node in graph_nodes:
            if str(node.get("id") or "") == child_id:
                value = node.get("distanceToParent")
                if isinstance(value, (int, float)) and math.isfinite(float(value)):
                    return float(value)
                return None
        return None

    def _nearest_better_chain(graph_nodes: list[dict[str, Any]], start_id: str) -> set[str]:
        by_id = {str(node.get("id") or ""): node for node in graph_nodes}
        chain: set[str] = set()
        current = start_id
        for _ in range(6):
            node = by_id.get(current)
            if node is None:
                break
            chain.add(current)
            parent_index = node.get("ofecParentIndex")
            if not isinstance(parent_index, int):
                break
            parent = None
            for candidate in graph_nodes:
                if int(candidate.get("ofecIndex", -1) or -1) == parent_index:
                    parent = candidate
                    break
            if parent is None or str(parent.get("id") or "") == current:
                break
            current = str(parent.get("id") or "")
        return chain

    result: dict[str, Any] = {}
    if region_type == "edge" and b_id:
        before = _edge_length(source_nodes, a_id)
        after = _edge_length(new_nodes, a_id)
        result["edgeBefore"] = before
        result["edgeAfter"] = after
        if before is not None and after is not None:
            result["edgeShrunk"] = bool(after < before * 0.95)
        result["corridorNodeCount"] = len(_nearest_better_chain(new_nodes, a_id))
        result["anchor"] = a_id
        result["direction"] = b_id
    else:
        before = _edge_length(source_nodes, a_id)
        after = _edge_length(new_nodes, a_id)
        result["edgeBefore"] = before
        result["edgeAfter"] = after
        result["corridorNodeCount"] = len(_nearest_better_chain(new_nodes, a_id))
        result["anchor"] = a_id
    return result


def _direct_nbn_children(
    graph: dict[str, Any] | None,
    anchor_id: str,
) -> tuple[dict[str, Any] | None, list[dict[str, Any]]]:
    """Return (anchor node, list of its direct NBN children) in a graph."""
    if not isinstance(graph, dict):
        return None, []
    nodes = graph.get("nodes") if isinstance(graph.get("nodes"), list) else []
    anchor = None
    by_index: dict[int, dict[str, Any]] = {}
    for node in nodes:
        node_id = str(node.get("id") or "")
        if node_id == anchor_id:
            anchor = node
        try:
            by_index[int(node.get("ofecIndex", -1))] = node
        except (TypeError, ValueError):
            continue
    if anchor is None:
        return None, []
    anchor_index = anchor.get("ofecIndex")
    if not isinstance(anchor_index, int):
        return anchor, []
    children = [
        node
        for node in nodes
        if node.get("ofecParentIndex") == anchor_index
        and str(node.get("id") or "") != anchor_id
    ]
    return anchor, children


def anchor_cluster_metrics(
    source_graph: dict[str, Any] | None,
    new_graph: dict[str, Any] | None,
    anchor_id: str,
) -> dict[str, Any] | None:
    """Topology-only cluster metrics for an expand anchor, comparing the source
    graph against the rebuilt graph after a region run.

    Returns direct-NBN-children counts before/after (the visible "cluster" in
    the cone-tree layout), the children's scores in the new graph, and the best
    score found directly below the anchor. None when the anchor is absent from
    either graph.
    """
    source_anchor, source_children = _direct_nbn_children(source_graph, anchor_id)
    new_anchor, new_children = _direct_nbn_children(new_graph, anchor_id)
    if source_anchor is None or new_anchor is None:
        return None

    def _score(node: dict[str, Any]) -> float | None:
        return normalize_valid_score(node.get("rawScore", node.get("score", node.get("ofecFitness"))))

    new_child_records = [
        {
            "id": str(node.get("id") or ""),
            "score": _score(node),
            "distanceToParent": node.get("distanceToParent"),
        }
        for node in new_children
    ]
    new_child_records.sort(
        key=lambda item: -(item["score"] if item["score"] is not None else -1e18)
    )
    best_child_score = max(
        (float(record["score"]) for record in new_child_records if record["score"] is not None),
        default=None,
    )
    return {
        "anchor": anchor_id,
        "directChildrenBefore": len(source_children),
        "directChildrenAfter": len(new_children),
        "directChildrenGrowth": len(new_children) - len(source_children),
        "bestChildScore": best_child_score,
        "newChildren": new_child_records[:20],
    }


def candidate_child_flags(
    d_a: float,
    d_parent: float | None,
    *,
    gap_upper: float | None = None,
    fallback_upper: float = 0.10,
) -> bool:
    """Online "likely to hang under the anchor" test for an expand sample.

    A sample is a candidate NBN child of the anchor when it is closer to the
    anchor than to the anchor's parent (i.e. on the anchor's side of the gap)
    and stays within the gap upper bound. When the parent distance is unknown
    (e.g. after the anchor drifted), fall back to a fixed closeness bound.
    """
    if not math.isfinite(float(d_a)) or float(d_a) <= NOVEL_MIN_DIST:
        return False
    upper = gap_upper if gap_upper is not None and math.isfinite(float(gap_upper)) else fallback_upper
    if float(d_a) >= float(upper):
        return False
    if d_parent is not None and math.isfinite(float(d_parent)):
        return float(d_a) < float(d_parent)
    return True


def neighborhood_coverage(
    d_as: list[float],
    buckets: tuple[tuple[float, float], ...] = NEIGHBORHOOD_BUCKETS,
) -> dict[str, Any]:
    """Bucket the anchor distances of neighbourhood members and report how many
    distance bands were actually explored."""
    counts: dict[str, int] = {}
    for lo, hi in buckets:
        counts[f"{lo:.2f}-{hi:.2f}"] = 0
    for value in d_as:
        try:
            d = float(value)
        except (TypeError, ValueError):
            continue
        for lo, hi in buckets:
            if lo <= d < hi:
                counts[f"{lo:.2f}-{hi:.2f}"] += 1
                break
    covered = sum(1 for count in counts.values() if count > 0)
    return {
        "buckets": counts,
        "covered": covered,
        "total": len(buckets),
    }


def exploration_conclusion(
    segments: list[dict[str, Any]],
    *,
    zero_novel_threshold: int = 2,
) -> dict[str, Any]:
    """Decide whether a neighbourhood looks exhausted.

    Consecutive segments with zero novel samples AND no best-score improvement
    are treated as evidence that the neighbourhood has been explored and no
    higher-score signal remains (an empirical conclusion, not a proof).
    """
    consecutive_zero_novel = 0
    prev_best: float | None = None
    for segment in segments:
        best = segment.get("best_score")
        best = float(best) if isinstance(best, (int, float)) else None
        novel = int(segment.get("novel_count", 0) or 0)
        improved = (
            prev_best is not None
            and best is not None
            and best > prev_best + 1e-12
        )
        if novel == 0 and not improved:
            consecutive_zero_novel += 1
        else:
            consecutive_zero_novel = 0
        if best is not None:
            prev_best = best
    exhausted = consecutive_zero_novel >= zero_novel_threshold
    return {
        "conclusion": "已探明（连续零新颖且无提升，无更高分信号）" if exhausted else "仍有空间",
        "exhausted": exhausted,
        "consecutiveZeroNovel": consecutive_zero_novel,
        "threshold": zero_novel_threshold,
    }


def gap_status(gap: float | None) -> str:
    """Classify a high-scorer's gap to the nearest better solution."""
    if gap is None:
        return "unknown"
    if gap < BOXED_IN_GAP:
        return "被围堵"
    if gap >= TRUE_BLANK_GAP:
        return "真空白"
    return "中等"


def min_gap_to_better(
    anchor_score: float,
    scores: Any,
    distances: Any,
) -> float | None:
    """Minimum semantic distance from the anchor to a STRICTLY better solution.

    Tie scores (score == anchor) are NOT better: they are duplicate/sibling
    solutions and would otherwise report a fake zero/close gap. Returns None
    when no strictly-better solution exists (global maximum).
    """
    mask = np.asarray(scores, dtype=np.float64) > float(anchor_score) + 1e-12
    if not mask.any():
        return None
    return float(np.asarray(distances, dtype=np.float64)[mask].min())
