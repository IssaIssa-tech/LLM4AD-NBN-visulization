#!/usr/bin/env python
"""从爬山日志里解析每条"轨迹"（一次 [挖山] 从入口到判死的完整过程）。

日志格式（三次爬山会话）：
  [ts] [挖山] <entry_id> rep=<score> 续挖起点=<score> 预算剩余 N      # 开始
  [ts]   -> 已注册 N 个新解到 revision <rev>（共 C）                    # 每批注册，C=该 revision 累计数
  [ts] [挖山] <entry_id> 完成 best=<b> delta_vs_rep=<d> evaluated=<e> verdict=...  # 结束

输出：每条轨迹 = entry 节点 + 注册进会话 revision 的 [start_cum+1 .. end_cum] 节点。
"""

from __future__ import annotations

from pathlib import Path
REPO_ROOT = Path(__file__).resolve().parents[2]
import argparse
import json
import re
from dataclasses import dataclass, asdict
from pathlib import Path


START_RE = re.compile(r"^\[(?P<ts>[^\]]+)\] \[挖山\] (?P<entry>\S+) rep=(?P<rep>[0-9.eE+-]+)")
DONE_RE = re.compile(r"^\[(?P<ts>[^\]]+)\] \[挖山\] \S+ 完成 best=(?P<best>[0-9.eE+-]+).*evaluated=(?P<evaluated>\d+).*verdict=(?P<verdict>.*)$")
REG_RE = re.compile(r"^\[(?P<ts>[^\]]+)\]\s+-> 已注册 (?P<count>\d+) 个新解到 revision (?P<rev>\S+)（共 (?P<cum>\d+)）")


@dataclass
class Trajectory:
    index: int
    session: str
    entry_id: str
    entry_score: float
    revision: str
    start_ts: str
    end_ts: str | None
    best_score: float | None
    evaluated: int | None
    verdict: str | None
    cum_start: int
    cum_end: int | None
    node_count: int | None
    completed: bool


def parse_log(path: Path, session: str, start_index: int) -> list[Trajectory]:
    lines = path.read_text(encoding="utf-8", errors="replace").splitlines()
    trajectories: list[Trajectory] = []
    current: Trajectory | None = None
    last_cum: int | None = None

    for line in lines:
        m = START_RE.match(line)
        if m:
            current = Trajectory(
                index=start_index + len(trajectories),
                session=session,
                entry_id=m.group("entry"),
                entry_score=float(m.group("rep")),
                revision="",
                start_ts=m.group("ts"),
                end_ts=None,
                best_score=None,
                evaluated=None,
                verdict=None,
                cum_start=last_cum or 0,
                cum_end=None,
                node_count=None,
                completed=False,
            )
            continue
        if current is None:
            continue
        m = REG_RE.match(line)
        if m:
            current.revision = m.group("rev")
            last_cum = int(m.group("cum"))
            current.cum_end = last_cum
            continue
        m = DONE_RE.match(line)
        if m:
            current.end_ts = m.group("ts")
            current.best_score = float(m.group("best"))
            current.evaluated = int(m.group("evaluated"))
            current.verdict = m.group("verdict").strip()
            current.completed = True
            current.node_count = (current.cum_end or 0) - current.cum_start
            trajectories.append(current)
            current = None

    # 未完成的轨迹（会话被中断）
    if current is not None:
        current.node_count = (current.cum_end or 0) - current.cum_start
        trajectories.append(current)

    return trajectories


def main() -> None:
    parser = argparse.ArgumentParser(description="从爬山日志解析轨迹")
    parser.add_argument("--logs", nargs="+", default=[
        str(REPO_ROOT / 'logs/climb_run.log'),
        str(REPO_ROOT / 'logs/climb_nbn.log'),
        str(REPO_ROOT / 'logs/climb_nbn04.log'),
    ])
    parser.add_argument("--sessions", nargs="+", default=["ball-0.05-15000", "nbn-0.05-4000", "nbn-0.04-6000"])
    parser.add_argument("--out", type=str, default=str(REPO_ROOT / 'data/graphs/trajectories.json'))
    args = parser.parse_args()

    all_tr: list[Trajectory] = []
    for log, session in zip(args.logs, args.sessions):
        path = Path(log)
        if not path.exists():
            print(f"skip missing {path}")
            continue
        trs = parse_log(path, session, len(all_tr))
        print(f"{path.name}: {len(trs)} 条轨迹")
        all_tr.extend(trs)

    out = {
        "generated_at": str(Path(args.out).stat().st_mtime) if Path(args.out).exists() else None,
        "trajectories": [asdict(t) for t in all_tr],
    }
    Path(args.out).write_text(json.dumps(out, ensure_ascii=False, indent=1), encoding="utf-8")
    for t in all_tr:
        print(
            f"  #{t.index:02d} [{t.session}] {t.entry_id} rep={t.entry_score} "
            f"-> best={t.best_score} ev={t.evaluated} nodes=[{t.cum_start+1}..{t.cum_end}] "
            f"n={t.node_count} {'OK' if t.completed else 'UNFINISHED'}"
        )


if __name__ == "__main__":
    main()
