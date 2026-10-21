"""按 revision 生成 / 缓存 3D 视图数据（NBN 锥树 + MDS 语义空间）。

背景：平台原先只有一份**静态快照**——
    static/data/nbn_basins_3d.json  (build_basin_3d_data.py 产物)
    static/data/mds3d_data.json     (build_mds_data.py 产物)
这两个文件是预实验时人工离线跑出来的，3D 页面又把路径写死，于是任何用户导入
自己的历史后，点开 3D 页面看到的都是别人的数据——「两张皮」。

这里把这条链接进服务，按 revision 现场生成并落盘缓存：

    .local/runs/<revision_id>/graph_full.json
      --build_basin_3d_data.py--> .local/basin3d/<revision_id>/nbn_3d.json
      --build_mds_data.py-------> .local/basin3d/<revision_id>/mds3d.json

注意 MDS 的输入是**上一步的 NBN 产物**（不是图文件本身），所以是链式的。
实测 14,000 节点：NBN 约 2.7s、MDS 约 6.2s，因此同步生成即可，不必再引入一个
Celery 任务类型（也少一个「worker 没跑就失败」的坑）。重复访问直接读缓存。
"""

from __future__ import annotations

import subprocess
import sys
import threading
from pathlib import Path

from visual_platform.config import BASE_DIR, BASIN3D_DIR, RUNS_DIR
# 复用统一的 DB_PATH：否则 VISUAL_PLATFORM_DB 覆盖只对平台生效、对 3D 构建不生效，
# 构建脚本会去读另一个库，产出的图与平台展示的数据对不上。
from visual_platform.runtime.database import DB_PATH

TOOLS_DIR = BASE_DIR / "tools"
NBN_TOOL = TOOLS_DIR / "build_basin_3d_data.py"
MDS_TOOL = TOOLS_DIR / "build_mds_data.py"
REPO_ROOT = BASE_DIR.parent
EMBEDDING_CACHE = BASE_DIR / ".codet5_embeddings_cache.sqlite3"

BUILD_TIMEOUT_SECONDS = 1800


class Basin3dError(RuntimeError):
    """带「下一步怎么办」提示的错误，直接回给前端展示。"""


def revision_graph_path(revision_id: str) -> Path:
    """该 revision 的 NBN 图（由工作台的「加载图谱」任务产出）。"""
    return RUNS_DIR / revision_id / "graph_full.json"


def _out_dir(revision_id: str) -> Path:
    """该 revision 的 3D 产物目录。

    注意：这里**不建目录**。status() 等只读路径也会调用本函数，
    若在此 mkdir，任何一次 GET /api/revisions/<id>/basin3d/status
    都会在磁盘上留下目录。目录改在真正要写入产物时创建。
    """
    return BASIN3D_DIR / revision_id


# 同一个 revision 的构建串行化：并发请求否则会重复起子进程，
# 并往同一个输出文件里同时写。
_BUILD_LOCKS: dict[str, threading.RLock] = {}
_BUILD_LOCKS_GUARD = threading.Lock()


def _build_lock(revision_id: str) -> threading.RLock:
    with _BUILD_LOCKS_GUARD:
        lock = _BUILD_LOCKS.get(revision_id)
        if lock is None:
            lock = threading.RLock()  # 可重入：ensure_mds 内部还会调用 ensure_nbn
            _BUILD_LOCKS[revision_id] = lock
        return lock


def nbn_path(revision_id: str) -> Path:
    return _out_dir(revision_id) / "nbn_3d.json"


def mds_path(revision_id: str) -> Path:
    return _out_dir(revision_id) / "mds3d.json"


VALID_SNAPSHOT = BASIN3D_DIR / "valid_solutions.json"
DATASET_TOOL = TOOLS_DIR / "dataset.py"


def _ensure_valid_snapshot() -> Path | None:
    """有效解快照（工具的 --valid）：只用于标记节点是否「有效 / 唯一」。

    平台不会自动产出它。缺了虽然也能出图，但**所有节点都标不上「唯一」**，
    MDS 视图会因此一个点都不显示（实测：唯一数 0 → 可见数 0）。
    这里按需生成：读整库、不嵌入，很快；库比快照新时重新生成。
    """
    if not DATASET_TOOL.exists():
        return None
    if VALID_SNAPSHOT.exists():
        fresh = True
        if DB_PATH.exists():
            fresh = VALID_SNAPSHOT.stat().st_mtime >= DB_PATH.stat().st_mtime
        if fresh:
            return VALID_SNAPSHOT
    VALID_SNAPSHOT.parent.mkdir(parents=True, exist_ok=True)
    _run_tool(DATASET_TOOL, ["--save", str(VALID_SNAPSHOT)])
    return VALID_SNAPSHOT if VALID_SNAPSHOT.exists() else None


def _run_tool(tool: Path, argv: list[str]) -> None:
    if not tool.exists():
        raise Basin3dError(f"缺少工具脚本：{tool}")
    try:
        proc = subprocess.run(
            [sys.executable, str(tool), *argv],
            cwd=str(REPO_ROOT),
            capture_output=True,
            text=True,
            timeout=BUILD_TIMEOUT_SECONDS,
        )
    except subprocess.TimeoutExpired as error:
        raise Basin3dError(
            f"{tool.name} 超时（>{BUILD_TIMEOUT_SECONDS}s），节点数可能过大。"
        ) from error
    if proc.returncode != 0:
        tail = ((proc.stderr or "") + (proc.stdout or "")).strip().splitlines()[-6:]
        raise Basin3dError(f"{tool.name} 执行失败：\n" + "\n".join(tail))


def ensure_nbn(revision_id: str, *, rebuild: bool = False) -> Path:
    """确保该 revision 的 NBN 锥树 3D 数据存在，返回文件路径。"""
    out = nbn_path(revision_id)
    if out.exists() and out.stat().st_size > 0 and not rebuild:
        return out
    with _build_lock(revision_id):
        # 双重检查：等锁期间可能已被另一个请求构建好。
        if out.exists() and out.stat().st_size > 0 and not rebuild:
            return out
        graph = revision_graph_path(revision_id)
        if not graph.exists():
            raise Basin3dError(
                f"该 revision 还没有图数据：{graph}\n"
                "请先在工作台点「加载图谱」生成图（该步骤需要 Celery worker 在运行）。"
            )
        out.parent.mkdir(parents=True, exist_ok=True)
        argv = ["--graph", str(graph), "--out", str(out)]
        if DB_PATH.exists():
            argv += ["--db", str(DB_PATH)]
        valid = _ensure_valid_snapshot()
        if valid is not None:
            # 缺 --valid 时工具仍能出图，但所有节点都标不上「唯一」——
            # MDS 视图会因此一个点都不显示，所以必须补上。
            argv += ["--valid", str(valid)]
        _run_tool(NBN_TOOL, argv)
        if not out.exists() or out.stat().st_size == 0:
            raise Basin3dError("build_basin_3d_data.py 执行完但未找到产物。")
        return out


def ensure_mds(revision_id: str, *, rebuild: bool = False) -> Path:
    """确保该 revision 的 MDS 语义空间数据存在（依赖 NBN 产物），返回文件路径。"""
    out = mds_path(revision_id)
    if out.exists() and out.stat().st_size > 0 and not rebuild:
        return out
    with _build_lock(revision_id):
        if out.exists() and out.stat().st_size > 0 and not rebuild:
            return out
        src = ensure_nbn(revision_id, rebuild=rebuild)
        out.parent.mkdir(parents=True, exist_ok=True)
        argv = ["--src", str(src), "--out", str(out)]
        if DB_PATH.exists():
            argv += ["--db", str(DB_PATH)]
        if EMBEDDING_CACHE.exists():
            argv += ["--cache", str(EMBEDDING_CACHE)]
        _run_tool(MDS_TOOL, argv)
        if not out.exists() or out.stat().st_size == 0:
            raise Basin3dError("build_mds_data.py 执行完但未找到产物。")
        return out


def status(revision_id: str) -> dict[str, object]:
    """给前端用：该 revision 的两份 3D 数据是否已生成。"""
    nbn = nbn_path(revision_id)
    mds = mds_path(revision_id)
    return {
        "revisionId": revision_id,
        "graphReady": revision_graph_path(revision_id).exists(),
        "nbnReady": nbn.exists() and nbn.stat().st_size > 0,
        "mdsReady": mds.exists() and mds.stat().st_size > 0,
    }
