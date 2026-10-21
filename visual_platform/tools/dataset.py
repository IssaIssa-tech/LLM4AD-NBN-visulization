#!/usr/bin/env python
"""有效解集：所有聚类工具（山 / 家族 / 重聚类）共用的"哪些解算数"口径。

规则（写死在这里，避免每个脚本各自筛、口径不一致）：
  1. 分数有效：有限（非 -inf/inf）且 > 0；
  2. 代码非空且长度 > 50；
  3. sha256 去重（代码去首尾空白后取哈希），同码只留最高分；
  4. 排序：(score desc, id asc)，保证可复现。

用法：
  # 导出当前有效解集快照（所有聚类工具可共用，避免每次重查重筛）
  venv/bin/python tools/dataset.py --save <repo>/data/solutions/valid_solutions.json
  # 只导出高分子集（可选）
  venv/bin/python tools/dataset.py --save <repo>/data/solutions/valid_solutions.json --score-min 2.6
"""

from __future__ import annotations

import argparse
import hashlib
import json
import math
import sqlite3
import sys
import time
from pathlib import Path
from typing import Any

REPO_ROOT = Path(__file__).resolve().parents[2]
for candidate in (str(REPO_ROOT), str(REPO_ROOT / "visual_platform")):
    if candidate not in sys.path:
        sys.path.insert(0, candidate)

from visual_platform.runtime.database import get_connection


def load_valid_unique_codes(
    score_min: float | None = None,
) -> list[dict[str, Any]]:
    """返回规范的有效唯一码列表（含 code），排序 (score desc, id asc)。"""
    with get_connection() as conn:
        conn.row_factory = sqlite3.Row
        rows = conn.execute(
            """
            SELECT id, revision_id, score, code, algorithm_summary
            FROM individuals
            WHERE score IS NOT NULL AND code IS NOT NULL AND length(code) > 50
            ORDER BY score DESC, id ASC
            """
        ).fetchall()
    best: dict[str, dict[str, Any]] = {}
    for row in rows:
        score = float(row["score"])
        if not math.isfinite(score) or score <= 0:
            continue
        if score_min is not None and score < score_min:
            continue
        code = str(row["code"] or "").strip()
        digest = hashlib.sha256(code.encode("utf-8")).hexdigest()
        if digest not in best or score > best[digest]["score"]:
            best[digest] = {
                "id": str(row["id"]),
                "revision_id": str(row["revision_id"]),
                "score": score,
                "code": code,
                "algorithm_summary": str(row["algorithm_summary"] or ""),
            }
    return list(best.values())


def load_from_snapshot(path: Path, score_min: float | None = None) -> list[dict[str, Any]]:
    """从快照 JSON 读取有效解集（可按 score_min 再过滤）。"""
    data = json.loads(Path(path).read_text(encoding="utf-8"))
    codes = [dict(r) for r in data.get("codes", [])]
    if score_min is not None:
        codes = [r for r in codes if r["score"] >= score_min]
    return codes


def save_snapshot(path: Path, score_min: float | None = None) -> dict[str, Any]:
    codes = load_valid_unique_codes(score_min=score_min)
    payload = {
        "generated_at": time.strftime("%Y-%m-%d %H:%M:%S"),
        "score_min": score_min,
        "count": len(codes),
        "codes": codes,
    }
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, ensure_ascii=False), encoding="utf-8")
    return payload


def main() -> None:
    parser = argparse.ArgumentParser(description="导出有效解集快照（山/家族/重聚类共用）")
    parser.add_argument("--save", type=str, required=True, help="输出 JSON 路径")
    parser.add_argument("--score-min", type=float, default=None, help="可选分数下限")
    args = parser.parse_args()
    payload = save_snapshot(Path(args.save), score_min=args.score_min)
    print(
        f"已导出 {payload['count']} 个有效唯一码到 {args.save} "
        f"（score_min={args.score_min}）"
    )


if __name__ == "__main__":
    main()
