#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""生成 MDS 语义空间 3D 数据（static/data/mds3d_data.json + .meta.json）。

为什么：锥形树布局的 (x,y) 不是语义距离；本工具用 Landmark MDS 把
CodeT5 语义距离矩阵降到 3 维——图上两点距离 ≈ 语义距离（保真度见 meta），
z 用分数高度。配合 static/mds3d.html 查看。

输入：
  - static/data/nbn_basins_3d.json  节点元数据（id/score/rev/origin/op/valid/unique）+ NBN 边
  - visual_platform/llm4ad_platform.sqlite3  个体代码
  - .codet5_embeddings_cache.sqlite3  嵌入缓存（sha256(code.strip()) -> 256 维 L2 归一化向量）

方法（Landmark MDS，内存友好）：
  1. 唯一码 = 按 code hash 去重（约 16433 个），重复代码共享同一坐标；
  2. 地标 = 按分数分层采样 ~1500 个唯一码；
  3. 地标间经典 MDS（双中心化 + 特征分解）-> 3 维；
  4. 其余唯一码：到地标的距离向量 -> 投影嵌入（out-of-sample）；
  5. 全部 29957 节点映射到所属唯一码坐标。

输出（mds3d_data.json）：
  nodes[]      {id,x,y,z,score,rev,origin,op,valid,unique,parent}
  trajectories {list,trajOf,orderInTraj}  # 21 条爬山轨迹（bestPath 用 MDS 坐标画）
  entryChains  [{entry,chain:[...]}]      # 21 个入口的 NBN 父链（点选高亮用）
  fidelity     {rho2,stress2,rho3,stress3} # 保真度（随机配对抽样）
  meta         同目录 .meta.json（输入/参数/统计，可复现）
"""

from __future__ import annotations

import argparse
import hashlib
import json
import sqlite3
import sys
import time
from pathlib import Path

import numpy as np

REPO_ROOT = Path(__file__).resolve().parents[2]


def _load_vecs(code_hashes: list[str], cache_path: str) -> dict[str, np.ndarray]:
    """直接从嵌入缓存 sqlite 读向量（不依赖 ofec_nbn_bridge，避免拉起 torch）。"""
    con = sqlite3.connect(cache_path)
    out: dict[str, np.ndarray] = {}
    try:
        chunk = 900
        for start in range(0, len(code_hashes), chunk):
            batch = code_hashes[start : start + chunk]
            placeholders = ",".join("?" for _ in batch)
            rows = con.execute(
                f"SELECT code_hash, dim, vector FROM embeddings WHERE code_hash IN ({placeholders})",
                batch,
            ).fetchall()
            for ch, dim, blob in rows:
                v = np.frombuffer(blob, dtype=np.float32).reshape(-1)
                if v.size == int(dim):
                    out[str(ch)] = v
    finally:
        con.close()
    return out

BASE_DIR = REPO_ROOT / "visual_platform"
DEFAULT_SRC = BASE_DIR / "static/data/nbn_basins_3d.json"
DEFAULT_DB = BASE_DIR / "llm4ad_platform.sqlite3"
DEFAULT_CACHE = BASE_DIR / ".codet5_embeddings_cache.sqlite3"
DEFAULT_OUT = BASE_DIR / "static/data/mds3d_data.json"

N_LANDMARKS = 1500
K_DIMS = 3
P1_FLOOR = True  # z 用 P1 作为分数下限（避免低分离群压扁高分带）


def _finite(x: float, fallback: float = 0.0) -> float:
    try:
        v = float(x)
        return v if np.isfinite(v) else fallback
    except (TypeError, ValueError):
        return fallback


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--src", default=str(DEFAULT_SRC))
    ap.add_argument("--db", default=str(DEFAULT_DB))
    ap.add_argument("--cache", default=str(DEFAULT_CACHE))
    ap.add_argument("--out", default=str(DEFAULT_OUT))
    ap.add_argument("--landmarks", type=int, default=N_LANDMARKS)
    ap.add_argument("--dims", type=int, default=K_DIMS)
    ap.add_argument("--spread", type=float, default=1.0,
                    help="距离幂次拉伸：D'=D^spread（<1 拉开密集区、单调保序；1=不拉伸）")
    args = ap.parse_args()

    t0 = time.time()
    src_path, db_path, cache_path, out_path = map(Path, (args.src, args.db, args.cache, args.out))

    data = json.load(open(src_path, encoding="utf-8"))
    nodes = data["nodes"]
    edges = data["edges"]
    n = len(nodes)
    print(f"节点 {n}，边 {len(edges)}")

    # ---- 代码 -> 嵌入 ----
    con = sqlite3.connect(str(db_path))
    rows = con.execute("select id, code from individuals").fetchall()
    con.close()
    code_by_id = {r[0]: (r[1] or "").strip() for r in rows}
    sources = [code_by_id[nd["id"]] for nd in nodes]
    hashes = [hashlib.sha256(s.encode("utf-8")).hexdigest() for s in sources]
    vecs = _load_vecs(hashes, str(cache_path))
    emb = np.stack([vecs[h] for h in hashes])  # 29957×256，重复代码共享向量

    # ---- 唯一码 ----
    uniq_hash_to_idx: dict[str, int] = {}
    uniq_node_idx: list[int] = []  # 每个唯一码的第一个节点下标
    for i, h in enumerate(hashes):
        if h not in uniq_hash_to_idx:
            uniq_hash_to_idx[h] = len(uniq_node_idx)
            uniq_node_idx.append(i)
    nu = len(uniq_node_idx)
    print(f"唯一码 {nu}")
    emb_u = emb[uniq_node_idx]  # nu×256
    scores_u = np.array([nodes[i]["score"] for i in uniq_node_idx], dtype=np.float64)

    # ---- 地标选择：按分数分层 + 少量随机 ----
    rng = np.random.default_rng(20260816)
    order = np.argsort(scores_u, kind="stable")
    n_lm = min(args.landmarks, nu)
    stride = max(1, nu // n_lm)
    lm_sel = set(order[::stride][:n_lm].tolist())
    if len(lm_sel) < n_lm:
        extras = rng.choice([i for i in range(nu) if i not in lm_sel],
                            size=n_lm - len(lm_sel), replace=False)
        lm_sel |= set(extras.tolist())
    lm = np.array(sorted(lm_sel))
    print(f"地标 {len(lm)}")

    # ---- 地标经典 MDS ----
    E_lm = emb_u[lm]
    S_lm = np.clip(E_lm @ E_lm.T, -1.0, 1.0)
    D_lm_raw = 1.0 - S_lm
    # 幂次拉伸：D' = D^spread（<1 拉开密集区，单调保序）。压缩的是"距离的绝对大小"，
    # 排序关系不变 → Spearman ρ 基本不变，视觉上核心不再挤成一坨。
    D_lm = D_lm_raw ** args.spread
    nL = len(lm)
    J = np.eye(nL) - np.ones((nL, nL)) / nL
    B = -0.5 * J @ (D_lm ** 2) @ J
    w, V = np.linalg.eigh(B)
    k = min(args.dims, nL - 1)
    top = np.argsort(w)[::-1][:k]
    Lw = np.maximum(w[top], 0)
    U_k = V[:, top]
    Y_lm = U_k * np.sqrt(Lw)[None, :]  # 地标坐标 nL×k
    print(f"地标 MDS 特征值: {Lw.tolist()}")

    # ---- 全量唯一码投影 ----
    # b_i = -0.5 (d² - colmean(D_lm²) - μ_i + mean(D_lm²)) ; y = b_i @ U_k @ Λ_k^{-1/2}
    D_lm2 = D_lm ** 2
    col_mean = D_lm2.mean(axis=0)          # 地标 j 到各地标的平均距离²
    global_mean = D_lm2.mean()
    dist_all = 1.0 - np.clip(emb_u @ E_lm.T, -1.0, 1.0)  # nu×nL 原始语义距离
    d2_all = (dist_all ** args.spread) ** 2               # 幂拉伸后的"距离²"
    mu = d2_all.mean(axis=1, keepdims=True)
    b_all = -0.5 * (d2_all - col_mean[None, :] - mu + global_mean)
    inv_sqrt = 1.0 / np.sqrt(Lw)
    Y_all = b_all @ (U_k * inv_sqrt[None, :])  # nu×k
    # 地标自己的坐标用精确 MDS 结果（与投影一致；小差异无害）
    print(f"全量投影完成: {Y_all.shape}")

    # 朝向对齐：让冠军在原点、整体分布正负均衡（仅视觉习惯）
    champ_node = int(np.argmax([nodes[i]["score"] for i in uniq_node_idx]))
    Y_all = Y_all - Y_all[champ_node]
    # 让 x 方向方差最大（可选），保持稳定即可——不做，保持特征分解顺序

    # ---- 保真度验证（随机配对抽样，唯一码间）----
    rng2 = np.random.default_rng(7)
    npair = 8000
    a = rng2.integers(0, nu, npair)
    b = rng2.integers(0, nu, npair)
    keep = a != b
    a, b = a[keep], b[keep]
    sem = 1.0 - np.clip((emb_u[a] * emb_u[b]).sum(axis=1), -1.0, 1.0)  # 原始语义距离
    mds3 = np.linalg.norm(Y_all[a] - Y_all[b], axis=1)
    mds2 = np.hypot(*(Y_all[a] - Y_all[b]).T[:2])
    from scipy.stats import spearmanr
    rho2 = float(spearmanr(sem, mds2).statistic)
    rho3 = float(spearmanr(sem, mds3).statistic)
    # stress：对"原始语义距离"和对"拉伸后目标"分别算（拉伸必然抬高对原始距离的 stress）
    stress2 = float(np.sqrt(np.sum((mds2 - sem) ** 2) / np.sum(sem ** 2)))
    stress3 = float(np.sqrt(np.sum((mds3 - sem) ** 2) / np.sum(sem ** 2)))
    sem_spread = sem ** args.spread
    stress3_spread = float(np.sqrt(np.sum((mds3 - sem_spread) ** 2) / np.sum(sem_spread ** 2)))
    print(f"保真度: 2D ρ={rho2:.3f} stress={stress2:.3f} | 3D ρ={rho3:.3f} stress={stress3:.3f} "
          f"(拉伸目标 stress3={stress3_spread:.3f})")

    # ---- z：分数高度（P1 下限，避免低分离群压扁高分带）----
    finite_scores = np.array([_finite(nodes[i]["score"]) for i in range(n)])
    fs = finite_scores[finite_scores > 0]
    floor = float(np.percentile(fs, 1)) if P1_FLOOR and len(fs) else 0.0
    ceiling = float(finite_scores.max()) if len(finite_scores) else 1.0
    z_range = max(ceiling - floor, 1e-9)
    z_of = np.clip((finite_scores - floor) / z_range, 0.0, 1.0) * 200.0

    # ---- 父数组（NBN 边）----
    parents = np.full(n, -1, dtype=np.int32)
    for c, p in edges:
        parents[c] = p
    champ_i = int(np.argmax(finite_scores))
    if parents[champ_i] < 0:
        parents[champ_i] = champ_i

    # ---- 组装 nodes ----
    out_nodes = []
    for i, nd in enumerate(nodes):
        ui = uniq_hash_to_idx[hashes[i]]
        out_nodes.append({
            "id": nd["id"],
            "x": _finite(Y_all[ui][0]),
            "y": _finite(Y_all[ui][1]),
            "z": _finite(Y_all[ui][2]) if k >= 3 else 0.0,
            "zScore": _finite(z_of[i]),
            "score": _finite(nd["score"]),
            "rev": nd.get("rev", ""),
            "origin": nd.get("origin", ""),
            "op": nd.get("op", ""),
            "valid": 1 if nd.get("valid") else 0,
            "unique": 1 if nd.get("unique") else 0,
            "parent": int(parents[i]),
        })

    # ---- 轨迹（bestPath/path 映射到 MDS 坐标由前端做；这里只搬运节点下标）----
    trajs_in = data.get("trajectories", {}).get("list", [])
    trajs_out = []
    for t in trajs_in:
        trajs_out.append({
            "index": t["index"],
            "session": t.get("session", ""),
            "entry": t.get("entry", ""),
            "entryScore": _finite(t.get("entryScore")),
            "best": _finite(t.get("best")) if t.get("best") is not None else None,
            "verdict": t.get("verdict", ""),
            "completed": bool(t.get("completed")),
            "path": [int(x) for x in t.get("path", [])],
            "bestPath": [int(x) for x in t.get("bestPath", [])],
            **(
                {"chainPath": [int(x) for x in t["chainPath"]]}
                if t.get("chainPath") is not None
                else {}
            ),
            **(
                {"chainParents": [int(x) if x is not None else None for x in t["chainParents"]]}
                if t.get("chainParents") is not None
                else {}
            ),
        })
    trajOf = data.get("trajectories", {}).get("trajOf", [-1] * n)
    orderInTraj = data.get("trajectories", {}).get("orderInTraj", [-1] * n)

    # ---- 21 个入口的 NBN 父链 ----
    entry_chains = []
    for t in trajs_out:
        idx = next((i for i, nd in enumerate(out_nodes) if nd["id"] == t["entry"]), -1)
        if idx < 0:
            continue
        chain = []
        cur = idx
        seen = set()
        while cur >= 0 and cur not in seen and len(chain) < 60:
            seen.add(cur)
            chain.append(int(cur))
            p = int(parents[cur])
            if p < 0 or p == cur:
                break
            cur = p
        entry_chains.append({"entry": t["entry"], "chain": chain})

    out = {
        "generatedFrom": str(src_path),
        "generatedAt": time.strftime("%Y-%m-%d %H:%M:%S"),
        "method": "landmark-mds",
        "nodeCount": n,
        "uniqueCount": nu,
        "landmarks": len(lm),
        "dims": k,
        "fidelity": {
            "rho2": rho2, "stress2": stress2, "rho3": rho3, "stress3": stress3,
            "stress3_spread": stress3_spread,
        },
        "spread": args.spread,
        "nodes": out_nodes,
        "trajectories": {"list": trajs_out, "trajOf": trajOf, "orderInTraj": orderInTraj},
        "entryChains": entry_chains,
        "champion": out_nodes[champ_i]["id"],
    }

    out_path.parent.mkdir(parents=True, exist_ok=True)
    out_path.write_text(
        json.dumps(out, ensure_ascii=False, allow_nan=False, separators=(",", ":")),
        encoding="utf-8",
    )
    meta = {
        "generatedAt": out["generatedAt"],
        "command": "venv/bin/python visual_platform/tools/build_mds_data.py",
        "inputs": {
            "src": str(src_path), "db": str(db_path), "cache": str(cache_path),
        },
        "params": {"landmarks": len(lm), "dims": k, "p1Floor": P1_FLOOR, "spread": args.spread},
        "outputStats": {
            "nodeCount": n, "uniqueCount": nu, "landmarks": len(lm),
            "fidelity": out["fidelity"],
            "trajectories": len(trajs_out), "entryChains": len(entry_chains),
        },
    }
    meta_path = out_path.with_suffix(".meta.json")
    meta_path.write_text(json.dumps(meta, ensure_ascii=False, indent=2), encoding="utf-8")
    size_mb = out_path.stat().st_size / 1e6
    print(f"完成 {time.time()-t0:.0f}s → {out_path} ({size_mb:.1f} MB)，meta → {meta_path}")


if __name__ == "__main__":
    main()
