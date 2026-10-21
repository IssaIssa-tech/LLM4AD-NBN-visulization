#!/usr/bin/env python
"""用全库所有解构建前端 NBN 图。

流程：
  1. 新建一个 "all" revision，把 DB 里所有 individual 挂为成员；
  2. 创建 graph_build job；
  3. 进程内调用 execute_graph_build_job（纯 Python 精确最近更好树 + 锥树布局），
     完成后自动注册 graph artifact 到该 revision；
  4. 之后启动 web 栈（redis + celery + app），前端即可查看。

用法（爬行全部结束后运行）：
  venv/bin/python tools/build_all_graph.py --archive <repo>/data/solutions/archive.json
"""

from __future__ import annotations

import argparse
import json
import sys
import time
from pathlib import Path
from typing import Any

REPO_ROOT = Path(__file__).resolve().parents[2]
for candidate in (str(REPO_ROOT), str(REPO_ROOT / "visual_platform")):
    if candidate not in sys.path:
        sys.path.insert(0, candidate)

from visual_platform.config import RUNS_DIR
from visual_platform.runtime.database import get_connection


DIG_WORKSPACE_ID = "a895f3aa-bc61-49f4-bc4a-53bfdd008250"


def main() -> None:
    parser = argparse.ArgumentParser(description="全量 NBN 图构建")
    parser.add_argument("--max-nodes", type=int, default=50000)
    args = parser.parse_args()

    revision_id = f"all_{time.strftime('%Y%m%d_%H%M%S')}"
    log_dir = RUNS_DIR / revision_id / "log"
    log_dir.mkdir(parents=True, exist_ok=True)
    revision_dir = log_dir.parent
    config = {
        "mode": "unified_all",
        "log_dir": str(log_dir),
        "started_at": time.strftime("%Y-%m-%d %H:%M:%S"),
        "note": "全库所有解的统一 NBN 图",
    }
    (revision_dir / "config.json").write_text(json.dumps(config, ensure_ascii=False), encoding="utf-8")

    with get_connection() as conn:
        conn.execute(
            "INSERT OR IGNORE INTO revisions "
            "(revision_id, workspace_id, mode, lifecycle_status, graph_status, config, started_at) "
            "VALUES (?, ?, 'unified_all', 'running', 'none', ?, datetime('now'))",
            (revision_id, DIG_WORKSPACE_ID, json.dumps(config, ensure_ascii=False)),
        )
        ids = [r[0] for r in conn.execute("SELECT id FROM individuals").fetchall()]
        conn.executemany(
            "INSERT OR IGNORE INTO revision_nodes (revision_id, individual_id) VALUES (?, ?)",
            [(revision_id, i) for i in ids],
        )
    print(f"revision {revision_id} 已建，成员数 {len(ids)}", flush=True)

    from visual_platform.services import job_service
    from visual_platform.runtime.graph_executor import execute_graph_build_job

    job_id = f"graph_{revision_id}"
    job_service.update_job(
        job_id,
        revision_id,
        "graph_build",
        status="queued",
        stage="queued",
        stage_label="全量图构建",
        message="全量 NBN 图（所有解）",
        payload={"revisionId": revision_id, "maxNodes": args.max_nodes, "submittedAt": time.strftime("%Y-%m-%d %H:%M:%S")},
        started_at=time.strftime("%Y-%m-%d %H:%M:%S"),
    )
    result = execute_graph_build_job(
        revision_id,
        job_id=job_id,
        method_config={},
        max_nodes=args.max_nodes,
        source_revision_id=None,
        cluster_id=None,
        task_id=None,
    )
    print("图构建结果:", json.dumps(result, ensure_ascii=False)[:500])
    graph_file = revision_dir / "graph_full.json"
    print("图文件:", graph_file, "存在:", graph_file.exists())


if __name__ == "__main__":
    main()
