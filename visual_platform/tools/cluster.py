#!/usr/bin/env python
"""通用语义聚类工具（一个工具，两种视图，只靠参数区分）。

同一个操作：把"有效唯一码"按 CodeT5 嵌入余弦距离做 leader 聚类。
- 家族视图（交付粒度）：--score-min 2.6 --family-dist 0.02 --slsqp-threshold 50
- 山视图（地图/爬山粒度）：--score-min 0 --family-dist 0.05 --mined-unique 500

参数（默认空 = 全量有效解）：
  --score-min          分数下限（默认 None，即全量；家族视图给 2.6）
  --family-dist        聚类距离阈值（家族 0.02 / 山 0.05）
  --slsqp-threshold    "非 SLSQP 家族"判定：家族内 SLSQP 占比低于此值（百分比）
  --min-members        最少成员数
  --mined-unique       成员数 ≥ 此值标"挖透"（>0 时输出"可行动清单"）

有效解口径由 dataset.py 提供：分数有限且 >0、代码长度 >50、sha256 去重留最高分。
建议先导出快照：venv/bin/python tools/dataset.py --save <repo>/data/solutions/valid_solutions.json

示例：
  # 家族视图
  venv/bin/python tools/cluster.py --score-min 2.6 --family-dist 0.02 \
      --valid-set <repo>/data/solutions/valid_solutions.json \
      --out-json <repo>/data/solutions/家族清单.json --out-md <repo>/reports/家族清单.md
  # 山视图（重聚类）
  venv/bin/python tools/cluster.py --score-min 0 --family-dist 0.05 \
      --mined-unique 500 --valid-set <repo>/data/solutions/valid_solutions.json \
      --out-json <repo>/data/graphs/mountains_0.05.current.json --out-md <repo>/reports/山地图.md
"""

from __future__ import annotations

import argparse
import json
import re
import sys
import time
from collections import Counter
from pathlib import Path
from typing import Any

import numpy as np

REPO_ROOT = Path(__file__).resolve().parents[2]
for candidate in (str(REPO_ROOT), str(REPO_ROOT / "visual_platform")):
    if candidate not in sys.path:
        sys.path.insert(0, candidate)

from visual_platform.nbn.bridge import get_codet5_embedding_matrix
from visual_platform.tools.dataset import (
    load_from_snapshot,
    load_valid_unique_codes,
)


def _source_kind(revision_id: str) -> str:
    if revision_id == "20260711_152801_4674d01c":
        return "history"
    if revision_id.startswith("run-"):
        return "run"
    if revision_id.startswith("expert-"):
        return "expert"
    if revision_id == "basin_dig_20260811_170543":
        return "dig旧"
    if revision_id == "basin_dig_20260812_191959":
        return "dig新"
    return revision_id[:20]


def _detect_optimizers(code: str) -> dict[str, bool]:
    return {
        "SLSQP": bool(re.search("SLSQP", code)),
        "L-BFGS": bool(re.search("L-BFGS|LBFGS", code)),
        "difev": bool(re.search("differential_evolution", code)),
        "anneal": bool(re.search("anneal", code, re.I)),
        "scipy_opt": bool(re.search(r"scipy\.optimize", code)),
        "voronoi": bool(re.search("Voronoi", code)),
        "greedy": bool(re.search("grow|expand|inflate", code, re.I)),
    }


def _leader_cluster(emb: np.ndarray, threshold: float) -> list[list[int]]:
    """按分数降序（传入顺序）做 leader 聚类，返回每个族的成员索引。"""
    n = emb.shape[0]
    assigned = np.zeros(n, dtype=bool)
    clusters: list[list[int]] = []
    for i in range(n):
        if assigned[i]:
            continue
        d = 1.0 - np.clip(emb[i] @ emb.T, -1.0, 1.0)
        members = np.where((~assigned) & (d < threshold))[0]
        assigned[members] = True
        clusters.append(members.tolist())
    return clusters


def main() -> None:
    parser = argparse.ArgumentParser(description="通用语义聚类（家族/山 一个工具）")
    parser.add_argument("--score-min", type=float, default=None, help="分数下限（默认无）")
    parser.add_argument("--family-dist", type=float, default=0.02, help="聚类距离阈值")
    parser.add_argument("--slsqp-threshold", type=float, default=50.0,
                        help="非 SLSQP 家族判定（SLSQP 占比低于此百分比）")
    parser.add_argument("--min-members", type=int, default=1, help="最少成员数")
    parser.add_argument("--mined-unique", type=int, default=0,
                        help="成员数≥此值标挖透；>0 时输出可行动清单")
    parser.add_argument("--order", choices=("score", "density_asc", "dist_champion"),
                        default="dist_champion", help="爬山清单排序")
    parser.add_argument("--unique-max", type=float, default=None, help="清单：成员数上限")
    parser.add_argument("--density-max", type=float, default=None, help="清单：密度0.05 上限")
    parser.add_argument("--dist-champion-min", type=float, default=None, help="清单：离冠军距离下限")
    parser.add_argument("--valid-set", type=str, default="",
                        help="有效解集快照 JSON；不填则现场查库")
    parser.add_argument("--out-json", type=str, default=str(REPO_ROOT / 'data/graphs/聚类结果.json'))
    parser.add_argument("--out-md", type=str, default=str(REPO_ROOT / 'reports/聚类结果.md'))
    parser.add_argument("--out-list", type=str, default="",
                        help="输出有序爬山清单 JSON（rep_ids 数组，给 basin_digger --list 用）")
    args = parser.parse_args()

    if args.valid_set:
        codes = load_from_snapshot(Path(args.valid_set), score_min=args.score_min)
    else:
        codes = load_valid_unique_codes(score_min=args.score_min)
    print(f"有效唯一码: {len(codes)}（score_min={args.score_min}）", flush=True)
    if not codes:
        print("无数据，退出")
        return

    embeddings, info = get_codet5_embedding_matrix(
        [{"function": r["code"]} for r in codes]
    )
    emb = np.asarray(embeddings, dtype=np.float32)
    emb = emb / np.linalg.norm(emb, axis=1, keepdims=True)
    print(f"嵌入完成: {emb.shape} | cache={info}", flush=True)

    clusters = _leader_cluster(emb, args.family_dist)
    print(f"簇数（threshold={args.family_dist:g}）: {len(clusters)}", flush=True)

    champion_idx = 0  # codes 已按分数降序，首个即全局最高分
    families: list[dict[str, Any]] = []
    for cid, members in enumerate(clusters):
        if len(members) < args.min_members:
            continue
        ms = sorted(members, key=lambda j: -codes[j]["score"])
        rep = codes[ms[0]]
        dets = [_detect_optimizers(codes[j]["code"]) for j in ms]
        slsqp_pct = 100.0 * sum(1 for d in dets if d["SLSQP"]) / len(ms)
        rd = _detect_optimizers(rep["code"])
        kinds = dict(Counter(_source_kind(codes[j]["revision_id"]) for j in ms))
        d_rep = 1.0 - np.clip(emb @ emb[ms[0]], -1.0, 1.0)
        families.append(
            {
                "fam": cid + 1,
                "size": len(ms),
                "unique": len(ms),
                "best": float(rep["score"]),
                "rep_score": float(rep["score"]),
                "worst": float(codes[ms[-1]]["score"]),
                "rep_id": rep["id"],
                "rep_rev": rep["revision_id"],
                "summary": rep["algorithm_summary"][:200],
                "kinds": kinds,
                "slsqp_pct": round(slsqp_pct, 1),
                "rep_opt": {k: v for k, v in rd.items() if v},
                "density_0_05": int(np.sum(d_rep < 0.05)),
                "density_0_10": int(np.sum(d_rep < 0.10)),
                "dist_champion": float(d_rep[champion_idx]),
                "mined": bool(args.mined_unique > 0 and len(ms) >= args.mined_unique),
            }
        )
    families.sort(key=lambda f: (-f["best"], f["fam"]))

    payload = {
        "generated_at": time.strftime("%Y-%m-%d %H:%M:%S"),
        "params": {
            "score_min": args.score_min,
            "family_dist": args.family_dist,
            "slsqp_threshold": args.slsqp_threshold,
            "min_members": args.min_members,
            "mined_unique": args.mined_unique,
            "unique_codes": len(codes),
            "embedding_info": info,
        },
        "mountains": families,
    }
    out_json = Path(args.out_json)
    out_json.parent.mkdir(parents=True, exist_ok=True)
    out_json.write_text(json.dumps(payload, ensure_ascii=False, indent=1), encoding="utf-8")

    sizes = Counter(
        "1" if f["size"] == 1 else ("2-9" if f["size"] < 10 else ("10-99" if f["size"] < 100 else "100+"))
        for f in families
    )
    slsqp_all = sum(1 for f in families if f["slsqp_pct"] >= 99.0)
    nonslsqp = [f for f in families if f["slsqp_pct"] < args.slsqp_threshold]
    mined_n = sum(1 for f in families if f["mined"])

    lines = [
        f"# 聚类结果（threshold={args.family_dist:g}，{time.strftime('%Y-%m-%d %H:%M:%S')} 生成）\n",
        f"有效唯一码 {len(codes)} 个（score_min={args.score_min}）→ **{len(families)} 个簇**。",
        "可复现：`python tools/cluster.py --score-min "
        f"{args.score_min if args.score_min is not None else 0:g} --family-dist {args.family_dist:g} "
        f"--slsqp-threshold {args.slsqp_threshold:g} --mined-unique {args.mined_unique}`\n",
        "## 簇规模分布\n",
        "| 规模 | 簇数 |",
        "|---|---|",
    ]
    for k in ("1", "2-9", "10-99", "100+"):
        lines.append(f"| {k} | {sizes.get(k, 0)} |")
    lines += [
        "\n## 关键数字\n",
        f"- 簇总数：{len(families)}；SLSQP≥99% 的簇：{slsqp_all}（{100.0 * slsqp_all / len(families):.0f}%）；"
        f"SLSQP<{args.slsqp_threshold:g}% 的簇：{len(nonslsqp)}",
    ]
    if args.mined_unique > 0:
        lines.append(f"- 挖透（成员≥{args.mined_unique}）：{mined_n}；可行动：{len(families) - mined_n}")
    lines += [
        f"\n## 全部簇（按 best 降序）\n",
        "| # | best | 唯一码数 | SLSQP% | 代表优化器 | 密度0.05 | 离冠军 | 来源构成 | 代表思路摘要 |",
        "|---|---|---|---|---|---|---|---|---|",
    ]
    for f in families:
        opt = ",".join(f["rep_opt"].keys()) if f["rep_opt"] else "无scipy"
        kinds = " ".join(f"{k}:{v}" for k, v in f["kinds"].items())
        mined_mark = "（挖透）" if f["mined"] else ""
        lines.append(
            f"| {f['fam']} | {f['best']:.4f} | {f['size']} | {f['slsqp_pct']}% | {opt} | "
            f"{f['density_0_05']} | {f['dist_champion']:.3f} | {kinds} | "
            f"{f['summary'].replace('|', '｜')[:48]}{mined_mark} |"
        )
    lines += [
        f"\n## 非 SLSQP 簇（SLSQP<{args.slsqp_threshold:g}%，优化器分叉候选）\n",
        "| # | best | 唯一码数 | SLSQP% | 代表优化器 | 代表思路摘要 |",
        "|---|---|---|---|---|---|",
    ]
    for f in sorted(nonslsqp, key=lambda x: -x["best"]):
        opt = ",".join(f["rep_opt"].keys()) if f["rep_opt"] else "无scipy"
        lines.append(
            f"| {f['fam']} | {f['best']:.4f} | {f['size']} | {f['slsqp_pct']}% | {opt} | "
            f"{f['summary'].replace('|', '｜')[:60]} |"
        )
    if args.mined_unique > 0:
        lines += [
            "\n## 可行动清单（未挖透，按 best 降序）\n",
            "| # | best | 唯一码数 | 密度0.05 | 离冠军 | 代表思路摘要 |",
            "|---|---|---|---|---|---|",
        ]
        for f in [x for x in families if not x["mined"]]:
            lines.append(
                f"| {f['fam']} | {f['best']:.4f} | {f['size']} | {f['density_0_05']} | "
                f"{f['dist_champion']:.3f} | {f['summary'].replace('|', '｜')[:60]} |"
            )

    if args.out_list:
        actionable = [f for f in families if not (args.mined_unique > 0 and f["mined"])]
        if args.unique_max is not None:
            actionable = [f for f in actionable if f["unique"] <= args.unique_max]
        if args.density_max is not None:
            actionable = [f for f in actionable if f["density_0_05"] <= args.density_max]
        if args.dist_champion_min is not None:
            actionable = [f for f in actionable if f["dist_champion"] >= args.dist_champion_min]
        if args.order == "score":
            actionable.sort(key=lambda f: (-f["rep_score"], f["fam"]))
        elif args.order == "density_asc":
            actionable.sort(key=lambda f: (f["density_0_05"], -f["rep_score"]))
        else:
            actionable.sort(key=lambda f: (-f["dist_champion"], -f["rep_score"]))
        list_path = Path(args.out_list)
        list_path.parent.mkdir(parents=True, exist_ok=True)
        list_path.write_text(
            json.dumps(
                {
                    "generated_at": time.strftime("%Y-%m-%d %H:%M:%S"),
                    "order": args.order,
                    "mined_unique": args.mined_unique,
                    "count": len(actionable),
                    "rep_ids": [f["rep_id"] for f in actionable],
                },
                ensure_ascii=False,
                indent=1,
            ),
            encoding="utf-8",
        )
        print(f"爬山清单: {list_path}（{len(actionable)} 座）")

    out_md = Path(args.out_md)
    out_md.parent.mkdir(parents=True, exist_ok=True)
    out_md.write_text("\n".join(lines), encoding="utf-8")
    print(f"已写出: {out_md} / {out_json}")
    print(f"簇总数: {len(families)} | SLSQP>=99%: {slsqp_all} | 非SLSQP: {len(nonslsqp)}"
          + (f" | 挖透: {mined_n} | 可行动: {len(families) - mined_n}" if args.mined_unique > 0 else ""))


if __name__ == "__main__":
    main()
