#!/usr/bin/env python
"""生成"3D 搜索空间图"精简数据（新版本，不覆盖原图 graph_full.json）。

一个文件包含三种划分口径，前端一个页面切换查看：
  1. NBN 山：把 "distanceToParent > 阈值" 的父边剪掉成森林（每棵=一座山）
  2. 球划分：按分数降序做 leader 聚类（d-net，与 tools/cluster.py 同算法）
  3. 爬山轨迹：三次爬山日志里每条 [挖山] 过程（入口 → EOH 生成 → 判死）

用法（日常刷新只需这一条命令，自动找最新图/库/缓存）：
  venv/bin/python tools/build_basin_3d_data.py

输入自动定位规则（也可用参数覆盖）：
  --graph  默认取 .local/runs/ 下最新的 all_* revision 的 graph_full.json
  --db     默认 visual_platform/llm4ad_platform.sqlite3（<repo> 权威副本），无则退 /tmp 工作副本
  --cache  默认 visual_platform/.codet5_embeddings_cache.sqlite3，无则退 /tmp 工作副本
  --valid  有效解快照（<repo>/data/solutions/valid_solutions.json），只用于标记节点，缺了也能出图
  --logs   爬山日志（三条，缺了则轨迹部分为空）

输出：
  --out                        前端数据 static/data/nbn_basins_3d.json
  同目录 nbn_basins_3d.meta.json 可复现元数据（输入路径/hash/参数/统计）

注意：本工具只读（图/库/日志都不改），输出是独立的新版本文件，不覆盖任何原图。
"""

from __future__ import annotations

import argparse
import hashlib
import json
import math
import os
import re
import sqlite3
import sys
import time
from collections import Counter
from pathlib import Path

import numpy as np

REPO_ROOT = Path(__file__).resolve().parents[2]
for candidate in (str(REPO_ROOT), str(REPO_ROOT / "visual_platform")):
    if candidate not in sys.path:
        sys.path.insert(0, candidate)

BASE_DIR = Path(__file__).resolve().parents[1]


def _setup_embedding_cache_env() -> Path | None:
    """嵌入缓存自动定位；必须在 import ofec_nbn_bridge 之前调用（它 import 时读环境变量）。"""
    env = os.environ.get("VISUAL_PLATFORM_CODET5_CACHE", "").strip()
    if env:
        p = Path(env).expanduser()
        if p.exists():
            return p
        print(f"WARN: 指定的嵌入缓存不存在: {p}")
    d_cache = BASE_DIR / ".codet5_embeddings_cache.sqlite3"
    if d_cache.exists():
        os.environ["VISUAL_PLATFORM_CODET5_CACHE"] = str(d_cache)
        return d_cache
    tmp_cache = Path("/tmp/codet5_fast/cache.sqlite3")
    if tmp_cache.exists():
        os.environ["VISUAL_PLATFORM_CODET5_CACHE"] = str(tmp_cache)
        return tmp_cache
    return None


_EMBEDDING_CACHE = _setup_embedding_cache_env()

from visual_platform.nbn.bridge import get_codet5_embedding_matrix
from visual_platform.tools.extract_trajectories import parse_log


def _finite(value: object, default: float | None = None) -> float | None:
    """把非有限浮点（inf/-inf/NaN）清洗成 default，避免浏览器 JSON.parse 拒绝。"""
    if value is None:
        return default
    try:
        f = float(value)
    except (TypeError, ValueError):
        return default
    return f if math.isfinite(f) else default


def _file_fingerprint(path: Path, hash_content: bool) -> dict:
    stat = path.stat()
    fp = {
        "path": str(path),
        "size": stat.st_size,
        "mtime": time.strftime("%Y-%m-%d %H:%M:%S", time.localtime(stat.st_mtime)),
    }
    if hash_content:
        h = hashlib.sha256()
        with open(path, "rb") as fh:
            for chunk in iter(lambda: fh.read(1 << 20), b""):
                h.update(chunk)
        fp["sha256"] = h.hexdigest()
    return fp


def resolve_graph_path(arg: str | None) -> Path:
    if arg:
        path = Path(arg).expanduser()
        if not path.exists():
            raise FileNotFoundError(f"指定的图文件不存在: {path}")
        return path
    runs_dir = BASE_DIR / ".local" / "runs"
    if not runs_dir.exists():
        raise FileNotFoundError(f"找不到运行目录 {runs_dir}，请先构建全量图 revision")
    candidates = sorted(
        (d for d in runs_dir.iterdir() if d.is_dir() and d.name.startswith("all_")),
        key=lambda d: d.name,
    )
    if not candidates:
        raise FileNotFoundError(f"{runs_dir} 下没有 all_* 全量图 revision，请先构建")
    graph = candidates[-1] / "graph_full.json"
    if not graph.exists():
        raise FileNotFoundError(f"最新 revision {candidates[-1].name} 缺少 graph_full.json")
    print(f"自动选用最新全量图: {graph}（revision {candidates[-1].name}）")
    return graph


def resolve_db_path(arg: str | None) -> Path:
    d_db = BASE_DIR / "llm4ad_platform.sqlite3"
    tmp_db = Path("/tmp/codet5_fast/llm4ad_platform.sqlite3")
    if arg:
        path = Path(arg).expanduser()
        if not path.exists():
            raise FileNotFoundError(f"指定的主库不存在: {path}")
        return path
    if d_db.exists():
        return d_db
    if tmp_db.exists():
        print("WARN: 权威主库不存在，退回 /tmp 工作副本，可能略旧")
        return tmp_db
    raise FileNotFoundError("找不到主库（权威副本或 /tmp 工作副本都没有）")


def validate_graph(graph: dict) -> None:
    nodes = graph.get("nodes", [])
    edges = graph.get("edges", [])
    n = len(nodes)
    if n < 2:
        raise ValueError(f"图节点太少: {n}")
    if len(edges) != n - 1:
        print(f"WARN: 边数 {len(edges)} ≠ 节点数-1（{n - 1}），NBN 树可能不完整")
    ids = {nd["id"] for nd in nodes}
    if len(ids) != n:
        raise ValueError(f"节点 id 有重复: {n - len(ids)} 个")
    print(f"图校验通过: {n} 节点 / {len(edges)} 边 / {len(ids)} 唯一 id")


def cut_forest(parents: np.ndarray, dists: np.ndarray, threshold: float) -> np.ndarray:
    """剪长边，返回每个节点的根下标（root[]）。"""
    n = len(parents)
    root = np.full(n, -1, dtype=np.int32)

    def find(i: int) -> int:
        seen: list[int] = []
        j = i
        while True:
            if root[j] != -1:
                r = int(root[j])
                break
            p = int(parents[j])
            if p < 0 or p == j or float(dists[j]) > threshold:
                r = j
                break
            seen.append(j)
            j = p
        root[r] = r
        for k in seen:
            root[k] = r
        return r

    for i in range(n):
        find(i)
    return root


def leader_cluster(emb: np.ndarray, order: np.ndarray, threshold: float) -> tuple[np.ndarray, list[tuple[int, np.ndarray]]]:
    """d-net leader 聚类（与 cluster.py 同算法）。

    emb: (n, d) 已归一化，按 order（分数降序）重排后的矩阵
    order: 原始下标按分数降序的排列
    返回 (basin_of_ordered, [(leader_pos, member_positions), ...])
    """
    n = emb.shape[0]
    assigned = np.zeros(n, dtype=bool)
    clusters: list[tuple[int, np.ndarray]] = []
    basin_of = np.full(n, -1, dtype=np.int32)
    for pos in range(n):
        if assigned[pos]:
            continue
        d = 1.0 - np.clip(emb[pos] @ emb.T, -1.0, 1.0)
        members = np.where((~assigned) & (d < threshold))[0]
        assigned[members] = True
        basin_of[members] = len(clusters)
        clusters.append((int(pos), members))
    return basin_of, clusters


def build_ball_partition(
    graph_nodes: list[dict],
    id_index: dict[str, int],
    db_path: Path,
    thresholds: list[float],
) -> tuple[dict[str, dict], np.ndarray]:
    """全量节点球划分：返回 {阈值: {basinOf, basins}} 与嵌入矩阵。"""
    con = sqlite3.connect(str(db_path))
    con.row_factory = sqlite3.Row
    rows = con.execute("select id, score, code from individuals").fetchall()
    con.close()
    by_id = {r["id"]: r for r in rows}
    print(f"球划分: DB 行数 {len(by_id)}")

    samples: list[dict[str, str]] = []
    node_scores = np.zeros(len(graph_nodes), dtype=np.float64)
    missing_code = 0
    for i, nd in enumerate(graph_nodes):
        rec = by_id.get(nd["id"])
        code = str(rec["code"] or "") if rec else ""
        if not code.strip():
            missing_code += 1
        samples.append({"function": code})
        s = rec["score"] if rec and rec["score"] is not None else 0.0
        node_scores[i] = float(s) if s is not None else 0.0
    print(f"球划分: 空代码 {missing_code} 个")

    embeddings, info = get_codet5_embedding_matrix(samples)
    emb = np.asarray(embeddings, dtype=np.float32)
    emb = emb / np.maximum(np.linalg.norm(emb, axis=1, keepdims=True), 1e-12)
    print(f"球划分: 嵌入 {emb.shape} cache={info}")

    # 分数降序（并列按原下标）
    order = np.argsort(-node_scores, kind="stable")
    emb_order = emb[order]

    thresholds_out: dict[str, dict] = {}
    for thr in sorted(set(thresholds)):
        basin_of_ordered, clusters = leader_cluster(emb_order, order, thr)
        basin_of_graph = np.full(len(graph_nodes), -1, dtype=np.int32)
        for pos, graph_idx in enumerate(order):
            basin_of_graph[graph_idx] = int(basin_of_ordered[pos])

        basin_info = []
        for cid, (leader_pos, members) in enumerate(clusters):
            leader_graph = int(order[leader_pos])
            leader_node = graph_nodes[leader_graph]
            basin_info.append(
                {
                    "basin": cid,
                    "size": int(len(members)),
                    "leaderId": leader_node["id"],
                    "leaderScore": _finite(node_scores[leader_graph]),
                    "leaderSummary": (leader_node.get("algorithmSummary") or "")[:60],
                }
            )
        basin_info.sort(key=lambda b: -b["size"])
        thresholds_out[f"{thr:.2f}"] = {
            "basinOf": [int(x) for x in basin_of_graph],
            "basins": basin_info,
        }
        print(f"球划分 t={thr:.2f}: {len(clusters)} 簇，最大 {basin_info[0]['size']}")
    return thresholds_out, emb


def build_trajectories(
    graph_nodes: list[dict],
    id_index: dict[str, int],
    logs: list[Path],
    sessions: list[str],
) -> tuple[dict, np.ndarray, np.ndarray]:
    """从日志解析爬山轨迹，映射到图节点。"""
    # revision -> [(sample_order, graph_index)]，sample_order 从 id 后缀 -sN 取
    # （图里的 sampleOrder 是跨 revision 的全局序号，不能用）
    rev_nodes: dict[str, list[tuple[int, int]]] = {}
    for i, nd in enumerate(graph_nodes):
        rev = nd.get("sourceRevisionId", "")
        m = re.search(r"-s(\d+)$", nd.get("id", ""))
        if rev and m:
            rev_nodes.setdefault(rev, []).append((int(m.group(1)), i))
    for v in rev_nodes.values():
        v.sort()

    traj_of = np.full(len(graph_nodes), -1, dtype=np.int32)
    order_in_traj = np.full(len(graph_nodes), -1, dtype=np.int32)
    traj_list: list[dict] = []

    all_tr = []
    for log, session in zip(logs, sessions):
        if log.exists():
            all_tr.extend(parse_log(log, session, len(all_tr)))

    for t in all_tr:
        entry_idx = id_index.get(t.entry_id, -1)
        registered: list[int] = []
        if t.revision:
            rev_list = rev_nodes.get(t.revision, [])
            max_so = rev_list[-1][0] if rev_list else 0
            # 日志"共 C"是计数器（=已插入数+1），所以本段节点为 s(start)..s(cum_end-1)
            start = max(t.cum_start, 1)
            end = (t.cum_end if t.cum_end is not None else max_so + 1) - 1
            end = min(end, max_so)
            for so, idx in rev_list:
                if start <= so <= end:
                    registered.append(idx)
        path: list[int] = []
        if entry_idx >= 0:
            path.append(entry_idx)
        path.extend(registered)
        for step, idx in enumerate(path):
            if traj_of[idx] == -1:  # 入口可能被多条轨迹共用，颜色归第一条
                traj_of[idx] = t.index
                order_in_traj[idx] = step

        # 新高点链：入口 + 每次严格刷新纪录的节点（分数单调上升，画出来干净）
        best_path: list[int] = []
        best_so_far = -float("inf")
        for idx in path:
            s = float(graph_nodes[idx].get("rawScore"))
            if s is None:
                s = graph_nodes[idx].get("score")
            if s is None:
                s = graph_nodes[idx].get("ofecFitness")
            try:
                s = float(s)
            except (TypeError, ValueError):
                s = 0.0
            if s > best_so_far:
                best_so_far = s
                best_path.append(idx)

        traj_list.append(
            {
                "index": t.index,
                "session": t.session,
                "entry": t.entry_id,
                "entryScore": t.entry_score,
                "best": t.best_score,
                "evaluated": t.evaluated,
                "verdict": t.verdict,
                "completed": t.completed,
                "nodeCount": len(path),
                "path": path,
                "bestPath": best_path,
            }
        )

    # 核对：新高点链终点分数应等于日志 best（未完成轨迹无 best）
    for t in traj_list:
        if t["best"] is not None:
            end_score = float(graph_nodes[t["bestPath"][-1]].get("rawScore") or graph_nodes[t["bestPath"][-1]].get("score") or 0)
            if abs(end_score - t["best"]) > 2e-4:
                print(f"  !! 轨迹 #{t['index']} bestPath 终点 {end_score:.6f} != 日志 best {t['best']:.6f}")
    print(f"轨迹: {len(traj_list)} 条，覆盖节点 {int((traj_of >= 0).sum())}，新高点链平均 {np.mean([len(t['bestPath']) for t in traj_list]):.1f} 点")
    return {"list": traj_list}, traj_of, order_in_traj


def main() -> None:
    parser = argparse.ArgumentParser(
        description="生成 3D 搜索空间图精简数据（NBN 山 + 球 + 爬山轨迹）；默认自动找最新图/库/缓存"
    )
    parser.add_argument(
        "--graph",
        type=str,
        default=None,
        help="全量 NBN 图文件；默认取 .local/runs/ 下最新的 all_* revision",
    )
    parser.add_argument(
        "--out",
        type=str,
        default=str(REPO_ROOT / "visual_platform" / 'static/data/nbn_basins_3d.json'),
    )
    parser.add_argument("--db", type=str, default=None, help="主库；默认 <repo> 权威副本，退 /tmp")
    parser.add_argument("--thresholds", nargs="+", type=float, default=[0.02, 0.03, 0.04, 0.05, 0.06])
    parser.add_argument("--ball-thresholds", nargs="+", type=float, default=[0.02, 0.05, 0.10])
    parser.add_argument(
        "--valid",
        type=str,
        default=str(REPO_ROOT / 'data/solutions/valid_solutions.json'),
        help="有效解快照（用于标记每个节点是否有效/唯一）",
    )
    parser.add_argument(
        "--logs",
        nargs="+",
        default=[str(REPO_ROOT / 'logs/climb_run.log'), str(REPO_ROOT / 'logs/climb_nbn.log'), str(REPO_ROOT / 'logs/climb_nbn04.log')],
    )
    parser.add_argument(
        "--sessions",
        nargs="+",
        default=["ball-0.05-15000", "nbn-0.05-4000", "nbn-0.04-6000"],
    )
    args = parser.parse_args()

    graph_path = resolve_graph_path(args.graph)
    db_path = resolve_db_path(args.db)
    print(f"主库: {db_path}")
    print(f"嵌入缓存: {_EMBEDDING_CACHE or '未找到（将现场嵌入，很慢）'}")

    graph = json.loads(graph_path.read_text(encoding="utf-8"))
    validate_graph(graph)
    nodes = graph["nodes"]
    n = len(nodes)
    id_index = {node["id"]: i for i, node in enumerate(nodes)}

    valid_ids: set[str] = set()
    valid_path = Path(args.valid)
    if valid_path.exists():
        valid_data = json.loads(valid_path.read_text(encoding="utf-8"))
        for item in valid_data.get("codes", []):
            if item.get("id"):
                valid_ids.add(str(item["id"]))
    print(f"有效解标记: {len(valid_ids)} 个节点 id 命中快照")

    parents = np.array([int(x.get("ofecParentIndex", -1)) for x in nodes], dtype=np.int32)
    dists = np.array([float(x.get("distanceToParent", 0.0)) for x in nodes], dtype=np.float64)

    # 基础节点数组
    slim_nodes = []
    for i, node in enumerate(nodes):
        score = node.get("rawScore")
        if score is None:
            score = node.get("score")
        if score is None:
            score = node.get("ofecFitness")
        score = _finite(score, 0.0) or 0.0
        nid = node["id"]
        so_match = re.search(r"-s(\d+)$", nid)
        slim_nodes.append(
            {
                "id": nid,
                "x": _finite(node.get("x"), 0.0),
                "y": _finite(node.get("y"), 0.0),
                "z": _finite(node.get("z"), 0.0),
                "zTree": _finite(node.get("zTree"), 0.0),
                "score": score,
                "so": int(so_match.group(1)) if so_match else 0,
                "rev": node.get("sourceRevisionId", ""),
                "origin": node.get("originKind", ""),
                "op": node.get("operator", ""),
                "valid": 1 if score > 0 else 0,
                "unique": 1 if nid in valid_ids else 0,
            }
        )

    edge_index_pairs = []
    for e in graph["edges"]:
        si = id_index.get(e["source"])
        ti = id_index.get(e["target"])
        if si is not None and ti is not None:
            edge_index_pairs.append([si, ti])

    # ---- NBN 山 ----
    nbn_out: dict[str, dict] = {}
    for thr in sorted(set(args.thresholds)):
        root_arr = cut_forest(parents, dists, thr)
        root_ids = sorted(np.unique(root_arr))
        root_index = {int(r): k for k, r in enumerate(root_ids)}
        sizes = Counter(int(r) for r in root_arr)
        basin_info = []
        for r in root_ids:
            rn = nodes[int(r)]
            basin_info.append(
                {
                    "basin": int(root_index[int(r)]),
                    "size": sizes[int(r)],
                    "rootId": rn.get("id"),
                    "rootScore": _finite(rn.get("score")),
                    "rootSummary": (rn.get("algorithmSummary") or "")[:60],
                }
            )
        basin_info.sort(key=lambda b: -b["size"])
        basin_of = [int(root_index[int(r)]) for r in root_arr]
        nbn_out[f"{thr:.2f}"] = {"basinOf": basin_of, "basins": basin_info}
        print(f"NBN t={thr:.2f}: {len(root_ids)} 座山，最大 {basin_info[0]['size']}")

    # ---- 球划分 ----
    ball_out, _ = build_ball_partition(nodes, id_index, db_path, args.ball_thresholds)

    # ---- 爬山轨迹 ----
    traj_out, traj_of, order_in_traj = build_trajectories(
        nodes, id_index, [Path(x) for x in args.logs], args.sessions
    )

    payload = {
        "generatedFrom": graph_path.name,
        "generatedAt": time.strftime("%Y-%m-%d %H:%M:%S"),
        "validCount": sum(1 for x in slim_nodes if x["valid"]),
        "uniqueValidCount": sum(1 for x in slim_nodes if x["unique"]),
        "nodeCount": n,
        "edgeCount": len(edge_index_pairs),
        "nbn": nbn_out,
        "ball": {"thresholds": ball_out},
        "trajectories": {
            **traj_out,
            "trajOf": [int(x) for x in traj_of],
            "orderInTraj": [int(x) for x in order_in_traj],
        },
        "nodes": slim_nodes,
        "edges": edge_index_pairs,
    }
    out_path = Path(args.out)
    out_path.parent.mkdir(parents=True, exist_ok=True)
    out_path.write_text(
        json.dumps(payload, ensure_ascii=False, separators=(",", ":"), allow_nan=False),
        encoding="utf-8",
    )

    # ---- 自检 ----
    reloaded = json.loads(out_path.read_text(encoding="utf-8"))
    assert len(reloaded["nodes"]) == n
    for kind, th in [("nbn", reloaded["nbn"]), ("ball", reloaded["ball"]["thresholds"])]:
        for t, info in th.items():
            assert len(info["basinOf"]) == n
            assert sum(b["size"] for b in info["basins"]) == n
    raw = out_path.read_bytes()
    assert b"Infinity" not in raw and b"NaN" not in raw
    print(f"自检通过: JSON 可解析、无非有限浮点、三种划分数组完整")

    # ---- 可复现元数据 ----
    meta = {
        "generatedAt": payload["generatedAt"],
        "command": "venv/bin/python tools/build_basin_3d_data.py"
        + (f" --graph {args.graph}" if args.graph else "")
        + (f" --db {args.db}" if args.db else ""),
        "inputs": {
            "graph": _file_fingerprint(graph_path, hash_content=True),
            "db": _file_fingerprint(db_path, hash_content=False),
            "validSnapshot": (
                _file_fingerprint(valid_path, hash_content=False) if valid_path.exists() else None
            ),
            "climbLogs": [
                _file_fingerprint(Path(x), hash_content=True) for x in args.logs if Path(x).exists()
            ],
            "embeddingCache": str(_EMBEDDING_CACHE) if _EMBEDDING_CACHE else None,
        },
        "params": {
            "nbnThresholds": sorted(set(args.thresholds)),
            "ballThresholds": sorted(set(args.ball_thresholds)),
            "sessions": args.sessions,
        },
        "outputStats": {
            "nodeCount": n,
            "nbnMountains": {t: len(v["basins"]) for t, v in reloaded["nbn"].items()},
            "ballClusters": {t: len(v["basins"]) for t, v in reloaded["ball"]["thresholds"].items()},
            "trajectories": len(reloaded["trajectories"]["list"]),
            "trajectoryNodes": int(sum(1 for x in reloaded["trajectories"]["trajOf"] if x >= 0)),
        },
    }
    meta_path = out_path.with_name(out_path.stem + ".meta.json")
    meta_path.write_text(json.dumps(meta, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"已写出: {out_path} ({out_path.stat().st_size / 1e6:.1f} MB)")
    print(f"元数据: {meta_path}")


if __name__ == "__main__":
    main()
