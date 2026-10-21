import os
from pathlib import Path

BASE_DIR = Path(__file__).resolve().parent
STATIC_DIR = BASE_DIR / "static"


def _resolve_local_data_dir() -> Path:
    override = str(os.environ.get("VISUAL_PLATFORM_LOCAL_DATA_DIR", "") or "").strip()
    if override:
        return Path(override).expanduser().resolve()
    return BASE_DIR / ".local"


LOCAL_DATA_DIR = _resolve_local_data_dir()
RUNS_DIR = LOCAL_DATA_DIR / "runs"
DEBUG_DIR = LOCAL_DATA_DIR / "debug"
PROBE_DIR = LOCAL_DATA_DIR / "probe"
# 按 revision 生成的 3D 视图数据（NBN 锥树 / MDS 语义空间）缓存目录，见 services/basin3d_service.py
BASIN3D_DIR = LOCAL_DATA_DIR / "basin3d"
# runner CLI 在 2026-10 重构时移入 runtime/（原为 BASE_DIR / "runner.py"，已不存在）
RUNNER_PATH = BASE_DIR / "runtime" / "runner_cli.py"

DEFAULT_GRAPH_NODE_LIMIT = 50000
