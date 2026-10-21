#!/usr/bin/env python
"""多样性视图实验（不改原图，只读图、输出新文件）。

把全量 NBN 树按"到父节点距离 > 阈值"剪长边 → 变成森林（每棵 = 一个盆地/思路），
节点按盆地着色，输出：
  - 带 basin 字段的新图 JSON（保留原字段，另存，不覆盖原图）
  - 静态 PNG（x/y 平面按盆地着色，根用星标）

用法：
  venv/bin/python tools/graph_diversity.py --threshold 0.04 \
      --graph .local/runs/all_20260814_020211/graph_full.json \
      --out-json <repo>/data/graphs/graph_diversity_t04.json \
      --out-png <repo>/figs/nbn_diversity_t04.png
"""

from __future__ import annotations

from pathlib import Path
REPO_ROOT = Path(__file__).resolve().parents[2]
import argparse
import json
from collections import Counter
from pathlib import Path
from typing import Any

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np


def main() -> None:
    parser = argparse.ArgumentParser(description="NBN 图多样性视图（剪长边成森林 + 按盆地着色）")
    parser.add_argument("--graph", type=str, default=str(REPO_ROOT / "visual_platform" / '.local/runs/all_20260814_020211/graph_full.json'))
    parser.add_argument("--threshold", type=float, default=0.04, help="剪边阈值（distanceToParent > 此值即剪）")
    parser.add_argument("--out-json", type=str, default=str(REPO_ROOT / 'data/graphs/graph_diversity.json'))
    parser.add_argument("--out-png", type=str, default=str(REPO_ROOT / 'figs/nbn_diversity.png'))
    args = parser.parse_args()

    graph = json.loads(Path(args.graph).read_text(encoding="utf-8"))
    nodes = graph["nodes"]
    n = len(nodes)
    parents = np.array([int(x.get("ofecParentIndex", -1)) for x in nodes], dtype=np.int32)
    dists = np.array([float(x.get("distanceToParent", 0.0)) for x in nodes], dtype=np.float64)

    # 剪边：父边距离 > 阈值 → 该节点是自己所在盆地的根
    root = np.full(n, -1, dtype=np.int32)

    def find(i: int) -> int:
        seen = []
        j = i
        while True:
            if root[j] != -1:
                r = root[j]
                break
            p = int(parents[j])
            if p < 0 or p == j or float(dists[j]) > args.threshold:
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

    root_ids = sorted(np.unique(root))
    root_index = {r: k for k, r in enumerate(root_ids)}
    sizes = Counter(int(r) for r in root)
    print(f"节点 {n}，剪边阈值 {args.threshold} → 盆地数 {len(root_ids)}")

    # 每个节点加 basin 字段
    for i, node in enumerate(nodes):
        r = int(root[i])
        node["basin"] = root_index[r]
        node["basinRoot"] = str(nodes[r].get("id", r))
        node["cutEdge"] = bool(int(parents[i]) < 0 or parents[i] == i or dists[i] > args.threshold)

    # 盆地摘要（根分数、成员数、根摘要）
    basin_info = []
    for k, r in enumerate(root_ids):
        root_node = nodes[r]
        basin_info.append(
            {
                "basin": k,
                "size": sizes[int(r)],
                "rootScore": root_node.get("score"),
                "rootSummary": (root_node.get("algorithmSummary") or "")[:80],
                "rootId": root_node.get("id"),
            }
        )
    basin_info.sort(key=lambda b: -b["size"])
    print("\nTop 15 盆地（按成员数）:")
    for b in basin_info[:15]:
        print(f"  b{b['basin']:>3} 成员={b['size']:>6} 根分={b['rootScore']} | {b['rootSummary'][:50]}")

    out_json = Path(args.out_json)
    out_json.parent.mkdir(parents=True, exist_ok=True)
    out_json.write_text(json.dumps(graph, ensure_ascii=False), encoding="utf-8")

    # 静态图：x/y 按盆地着色
    xs = np.array([float(x.get("x", 0)) for x in nodes])
    ys = np.array([float(x.get("y", 0)) for x in nodes])
    basin_arr = np.array([x["basin"] for x in nodes])
    colors = plt.get_cmap("turbo")(basin_arr / max(1, len(root_ids) - 1))
    fig, ax = plt.subplots(figsize=(11, 10), dpi=150)
    ax.scatter(xs, ys, c=colors, s=3, alpha=0.55, linewidths=0)
    rx = np.array([float(nodes[r].get("x", 0)) for r in root_ids])
    ry = np.array([float(nodes[r].get("y", 0)) for r in root_ids])
    ax.scatter(rx, ry, marker="*", c="black", s=80, label="盆地根(局部最优)")
    ax.set_title(f"NBN diversity view: cut {args.threshold} -> {len(root_ids)} basins (colored by basin)")
    ax.legend(loc="upper right")
    ax.set_xlabel("x"); ax.set_ylabel("y")
    ax.axis("off")
    out_png = Path(args.out_png)
    out_png.parent.mkdir(parents=True, exist_ok=True)
    fig.savefig(out_png, bbox_inches="tight")
    print(f"\n已写出: {out_json} / {out_png}")

    # 盆地规模分布图（top 40）
    top = basin_info[:40]
    fig2, ax2 = plt.subplots(figsize=(13, 6), dpi=150)
    labels = [f"b{b['basin']}" for b in top]
    values = [b["size"] for b in top]
    ax2.bar(range(len(values)), values, color="steelblue")
    ax2.set_yscale("log")
    ax2.set_xticks(range(len(values)))
    ax2.set_xticklabels(labels, rotation=90, fontsize=7)
    ax2.set_ylabel("members (log)")
    ax2.set_title(f"Basin size distribution (cut {args.threshold}, top {len(values)} of {len(root_ids)})")
    fig2.tight_layout()
    size_png = out_png.with_name(out_png.stem + "_sizes.png")
    fig2.savefig(size_png, bbox_inches="tight")
    print(f"规模分布图: {size_png}")


if __name__ == "__main__":
    main()
