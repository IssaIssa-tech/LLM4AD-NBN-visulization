#!/usr/bin/env python
"""盆地账本（多方案）：method + threshold 组成一个方案，账本里各存一份盆地表。

method 支持：
  - ball：0.05 球 leader 聚类（d-net），anchor = leader
  - nbn ：最近更好邻居树（Nearest-Better Network），剪断 distance_to_parent > threshold 的边，
          连通块 = 盆地，anchor = 该块顶端（局部最优/根）

命令：
  init --method ball|nbn --threshold X  建某方案的盆地表
  select --scheme <id>                  选"未爬"盆地出队列
  export --scheme <id>                  导出爬山器能读的 mountains + list
  update --scheme <id> --results ...    把爬山结果回写进该方案的盆地状态卡
"""

from __future__ import annotations

import argparse
import json
import sys
import time
from pathlib import Path
from typing import Any

import numpy as np

REPO_ROOT = Path(__file__).resolve().parents[2]
for candidate in (str(REPO_ROOT), str(REPO_ROOT / "visual_platform")):
    if candidate not in sys.path:
        sys.path.insert(0, candidate)

from visual_platform.nbn.bridge import (
    _compute_exact_nbn,
    get_codet5_embedding_matrix,
)
from visual_platform.tools.dataset import load_from_snapshot, load_valid_unique_codes


DEFAULT_D = 0.05


def scheme_id(method: str, threshold: float) -> str:
    return f"{method}-{threshold:g}"


def _embed(codes: list[dict[str, Any]]) -> np.ndarray:
    emb = get_codet5_embedding_matrix([{"function": r["code"]} for r in codes])[0]
    emb = np.asarray(emb, dtype=np.float32)
    emb = emb / np.linalg.norm(emb, axis=1, keepdims=True)
    return emb


def _load_archive(path: Path) -> dict[str, Any]:
    if path.is_file():
        return json.loads(path.read_text(encoding="utf-8"))
    return {"schemes": {}}


def _save_archive(path: Path, archive: dict[str, Any]) -> None:
    archive["updated_at"] = time.strftime("%Y-%m-%d %H:%M:%S")
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(archive, ensure_ascii=False, indent=1), encoding="utf-8")


def _get_scheme(archive: dict[str, Any], sid: str) -> dict[str, Any]:
    schemes = archive.setdefault("schemes", {})
    return schemes.setdefault(sid, {"method": sid.split("-")[0], "threshold": float(sid.split("-")[1]), "basins": []})


def _basin_record(
    bid: str, anchor_id: str, anchor_code: str, best: float, members: int,
    dist_champion: float, method: str, threshold: float,
) -> dict[str, Any]:
    return {
        "basin_id": bid,
        "method": method,
        "threshold": threshold,
        "anchor_id": anchor_id,
        "anchor_code": anchor_code,
        "state": "unclimbed",
        "best": float(best),
        "best_id": anchor_id,
        "best_code": anchor_code,
        "verdict": "",
        "entry_score": float(best),
        "member_count": int(members),
        "unique_count": int(members),
        "density_0_05": int(members),
        "dist_champion": float(dist_champion),
        "created_at": time.strftime("%Y-%m-%d %H:%M:%S"),
    }


def _ball_basins(codes: list[dict[str, Any]], emb: np.ndarray, d: float) -> list[dict[str, Any]]:
    n = len(codes)
    assigned = np.zeros(n, dtype=bool)
    champion = emb[0]
    basins: list[dict[str, Any]] = []
    for i in range(n):
        if assigned[i]:
            continue
        dist = 1.0 - np.clip(emb[i] @ emb.T, -1.0, 1.0)
        members = np.where((~assigned) & (dist < d))[0]
        assigned[members] = True
        anchor = codes[i]
        d_champ = float(1.0 - np.clip(emb[i] @ champion, -1.0, 1.0))
        basins.append(_basin_record(f"m{len(basins)+1:03d}", anchor["id"], anchor["code"], anchor["score"], len(members), d_champ, "ball", d))
    return basins


def _nbn_basins(codes: list[dict[str, Any]], emb: np.ndarray, scores: np.ndarray, d: float) -> list[dict[str, Any]]:
    parents, distances = _compute_exact_nbn(emb, scores)
    n = len(codes)
    root = np.full(n, -1, dtype=np.int32)
    def find(i: int) -> int:
        seen = []
        j = i
        while True:
            if root[j] != -1:
                r = root[j]
                break
            p = int(parents[j])
            if p == j or float(distances[j]) > d:
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
    size = np.bincount(root, minlength=n)
    champion = emb[0]
    basins: list[dict[str, Any]] = []
    for r in sorted(np.unique(root), key=lambda i: -size[i]):
        anchor = codes[int(r)]
        d_champ = float(1.0 - np.clip(emb[int(r)] @ champion, -1.0, 1.0))
        basins.append(_basin_record(f"m{len(basins)+1:03d}", anchor["id"], anchor["code"], anchor["score"], int(size[r]), d_champ, "nbn", d))
    return basins


def cmd_init(args: argparse.Namespace) -> None:
    if args.valid_set:
        codes = load_from_snapshot(Path(args.valid_set), score_min=args.score_min)
    else:
        codes = load_valid_unique_codes(score_min=args.score_min)
    print(f"有效唯一码: {len(codes)}", flush=True)
    emb = _embed(codes)
    scores = np.array([c["score"] for c in codes], dtype=np.float32)
    if args.method == "nbn":
        basins = _nbn_basins(codes, emb, scores, args.threshold)
    else:
        basins = _ball_basins(codes, emb, args.threshold)
    archive = _load_archive(Path(args.archive))
    schemes = archive.setdefault("schemes", {})
    sid = scheme_id(args.method, args.threshold)
    old_basins = schemes.get(sid, {}).get("basins", [])
    old_by_anchor = {b.get("anchor_id"): b for b in old_basins}
    matched: set[str] = set()
    next_id = max(
        (int(b["basin_id"][1:]) for b in old_basins if str(b.get("basin_id", "")).startswith("m")),
        default=0,
    ) + 1
    for b in basins:
        ob = old_by_anchor.get(b["anchor_id"])
        if ob is not None:
            # 保状态合并：id/state/best/verdict 沿旧记录走，只更新成员统计
            matched.add(b["anchor_id"])
            b["basin_id"] = ob["basin_id"]
            b["state"] = ob.get("state", "unclimbed")
            b["best"] = float(ob.get("best") or b["best"])
            b["best_id"] = ob.get("best_id") or b["best_id"]
            b["best_code"] = ob.get("best_code") or b["best_code"]
            b["verdict"] = ob.get("verdict", "")
            b["created_at"] = ob.get("created_at", b["created_at"])
        else:
            b["basin_id"] = f"m{next_id:03d}"
            next_id += 1
    # 旧盆地没匹配上（被合并/消失）→ 移入 legacy，状态不丢
    legacy = list(schemes.get(sid, {}).get("legacy_basins", []))
    for ob in old_basins:
        if ob.get("anchor_id") not in matched:
            legacy.append(ob)
    schemes[sid] = {
        "method": args.method,
        "threshold": args.threshold,
        "basins": basins,
        "legacy_basins": legacy,
        "generated_at": time.strftime("%Y-%m-%d %H:%M:%S"),
    }
    _save_archive(Path(args.archive), archive)
    print(
        f"方案 {sid} 建账完成：{len(basins)} 个盆地"
        f"（保留旧状态 {len(matched)}，新增 {len(basins) - len(matched)}）→ {args.archive}"
    )


def cmd_select(args: argparse.Namespace) -> None:
    archive = _load_archive(Path(args.archive))
    scheme = _get_scheme(archive, args.scheme)
    basins = [b for b in scheme.get("basins", []) if b.get("state") == "unclimbed"]
    if args.order == "dist_champion":
        basins.sort(key=lambda b: (-float(b.get("dist_champion", 0)), b["basin_id"]))
    elif args.order == "best_asc":
        basins.sort(key=lambda b: (float(b.get("best", 0)), b["basin_id"]))
    else:
        basins.sort(key=lambda b: (-float(b.get("best", 0)), b["basin_id"]))
    payload = {
        "generated_at": time.strftime("%Y-%m-%d %H:%M:%S"),
        "scheme": args.scheme,
        "order": args.order,
        "count": len(basins),
        "basin_ids": [b["basin_id"] for b in basins],
    }
    out = Path(args.out)
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(payload, ensure_ascii=False, indent=1), encoding="utf-8")
    print(f"方案 {args.scheme} 未爬盆地：{len(basins)} 个 → {out}")


def cmd_export(args: argparse.Namespace) -> None:
    archive = _load_archive(Path(args.archive))
    scheme = _get_scheme(archive, args.scheme)
    basins = scheme.get("basins", [])
    mountains = []
    for b in basins:
        mountains.append(
            {
                "basin_id": b["anchor_id"],
                "rep_id": b["anchor_id"],
                "rep_score": float(b["best"]),
                "size": int(b.get("member_count", 0)),
                "unique": int(b.get("unique_count", 0)),
                "summary": "",
                "density_0_05": int(b.get("density_0_05", 0)),
                "dist_champion": float(b.get("dist_champion", 0)),
            }
        )
    Path(args.mountains).write_text(json.dumps({"mountains": mountains}, ensure_ascii=False, indent=1), encoding="utf-8")
    Path(args.list).write_text(json.dumps({"rep_ids": [m["rep_id"] for m in mountains]}, ensure_ascii=False, indent=1), encoding="utf-8")
    print(f"导出 {len(mountains)} 个盆地 → {args.mountains} / {args.list}")


def cmd_update(args: argparse.Namespace) -> None:
    archive = _load_archive(Path(args.archive))
    scheme = _get_scheme(archive, args.scheme)
    results = json.loads(Path(args.results).read_text(encoding="utf-8"))
    states = results.get("basins", {})
    for b in scheme.get("basins", []):
        dig = (states.get(b["anchor_id"]) or {}).get("dig")
        if not dig:
            continue
        b["best"] = float(dig.get("best") or b["best"])
        b["verdict"] = str(dig.get("verdict", ""))
        if "判死" in b["verdict"]:
            b["state"] = "judged_dead"
        elif "预算" in b["verdict"]:
            b["state"] = "budget_out"
    _save_archive(Path(args.archive), archive)
    print(f"方案 {args.scheme} 状态卡已更新 → {args.archive}")


def main() -> None:
    parser = argparse.ArgumentParser(description="盆地账本（多方案：ball/nbn）")
    sub = parser.add_subparsers(dest="cmd", required=True)

    p_init = sub.add_parser("init", help="建账")
    p_init.add_argument("--method", choices=("ball", "nbn"), default="ball")
    p_init.add_argument("--threshold", type=float, default=DEFAULT_D)
    p_init.add_argument("--valid-set", type=str, default="")
    p_init.add_argument("--score-min", type=float, default=None)
    p_init.add_argument("--archive", type=str, default=str(REPO_ROOT / 'data/solutions/archive.json'))
    p_init.set_defaults(func=cmd_init)

    p_sel = sub.add_parser("select", help="选未爬盆地")
    p_sel.add_argument("--scheme", type=str, required=True)
    p_sel.add_argument("--archive", type=str, default=str(REPO_ROOT / 'data/solutions/archive.json'))
    p_sel.add_argument("--order", choices=("dist_champion", "best_asc", "best_desc"), default="dist_champion")
    p_sel.add_argument("--out", type=str, default=str(REPO_ROOT / 'data/graphs/climb_queue.json'))
    p_sel.set_defaults(func=cmd_select)

    p_exp = sub.add_parser("export", help="导出给爬山器")
    p_exp.add_argument("--scheme", type=str, required=True)
    p_exp.add_argument("--archive", type=str, default=str(REPO_ROOT / 'data/solutions/archive.json'))
    p_exp.add_argument("--mountains", type=str, default=str(REPO_ROOT / 'data/graphs/exported_mountains.json'))
    p_exp.add_argument("--list", type=str, default=str(REPO_ROOT / 'data/graphs/exported_list.json'))
    p_exp.set_defaults(func=cmd_export)

    p_upd = sub.add_parser("update", help="回写爬山结果")
    p_upd.add_argument("--scheme", type=str, required=True)
    p_upd.add_argument("--archive", type=str, default=str(REPO_ROOT / 'data/solutions/archive.json'))
    p_upd.add_argument("--results", type=str, required=True)
    p_upd.set_defaults(func=cmd_update)

    args = parser.parse_args()
    args.func(args)


if __name__ == "__main__":
    main()
