#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""爬山器：按山地图逐座爬山，连续种群 EoH，自适应判死，判死换山。

读 --mountains 山地图（rep_id/rep_score/size/unique/density_0_05/dist_champion）
和 DB 入口代码，从入口爬；默认跳过挖透巨山（unique ≥ --crowded-unique）。
无"普查"步骤：一座山要么挖到判死、要么预算耗尽，检查点写 results JSON。
"""

from __future__ import annotations

import argparse
import hashlib
import json
import math
import os
import sys
import tempfile
import time
from pathlib import Path
from typing import Any

import numpy as np

REPO_ROOT = Path(__file__).resolve().parents[2]
for candidate in (str(REPO_ROOT), str(REPO_ROOT / "visual_platform")):
    if candidate not in sys.path:
        sys.path.insert(0, candidate)

from visual_platform.nbn.bridge import get_codet5_embedding_matrix
from visual_platform.nbn.region_analysis import is_valid_score
from visual_platform.runtime.database import get_connection
from visual_platform.runtime.runner_task_loader import load_circle_packing_evaluation

from visual_platform.tools.climb_experiment import (
    _create_collecting_profiler_class,
    _is_failed_operator,
    _load_individual,
    _run_eoh_segment,
    EmbeddingStore,
    ArmState,
    _build_llm,
)

WORKSPACE_ROOT = Path(os.environ.get("CLIMB_WORKSPACE_ROOT", str(REPO_ROOT)))
DEFAULT_MOUNTAINS = WORKSPACE_ROOT / "data" / "graphs" / "mountains_0.05.json"
DEFAULT_RESULTS = WORKSPACE_ROOT / "data" / "runs" / "basin_results.json"
DEFAULT_REPORT = WORKSPACE_ROOT / "reports" / "盆地挖掘报告.md"

MOUNTAIN_DIST = 0.05
IMPROVE_EPS = 1e-7
# v4 链爬行（峰值导向）：
# - PEAK_RADIUS：进行时 R > 0.03 的节点 = 峰值（一个思路的当前最高分）
# - V4_IMPROVE_EPS：判"分数更高"用 1e-13（冠军平台分差 5e-13，1e-9/1e-7 会把更高误判成平分）
# - STALL_BLOCKS：锚点连续 N 块无新父事件 → 停滞换山（链爬行v4方案.md §7，v1.2 定为 N=3）
PEAK_RADIUS = 0.03
V4_IMPROVE_EPS = 1e-13
STALL_BLOCKS = 3
# CLIMB_DEATH_ON_STALL=1：停滞满 STALL_BLOCKS 块无新父 → 直接判死终止（不换山），
# 用于验证"纯单山爬（无峰池换山）终点是否 R>0.03"（用户 2026-09-04 指示的实验变体）。
DEATH_ON_STALL = os.environ.get("CLIMB_DEATH_ON_STALL") == "1"
DRIFT_EPS = 1e-12
DEFAULT_DEATH_WINDOW = 180
DEFAULT_MAX_WINDOW = 480
CROWDED_UNIQUE = 500  # mountains with >= this many unique codes are "heavily mined"
# 爬山产生的样本会挂在这个 workspace 下（可在平台上查看/建图）。
# 原值是作者库里的固定 UUID；这里允许用环境变量覆盖，且 _ensure_dig_revision
# 会在新库上自动补建该 workspace（否则外键约束会让 climber 直接失败）。
DIG_WORKSPACE_ID = os.environ.get("CLIMB_DIG_WORKSPACE_ID", "a895f3aa-bc61-49f4-bc4a-53bfdd008250")
KNOWN_NPZ = Path(os.environ.get("CLIMB_KNOWN_NPZ", str(WORKSPACE_ROOT / "data" / "vectors" / "known_vectors.npz")))

# Neutral climb prompt: no tool names (scipy), no method bias (constructive),
# no time limit. The evaluator timeout is a configurable safety net only, and
# the single complete def requirement is the only hard format constraint.
DIGGER_BASE_TASK = (
    "Pack n circles in the unit square [0,1]^2 to maximize the sum of their "
    "radii. Implement the function below; it will be called with n=26 and its "
    "output validated."
)

# 偏好区提示词：默认空。需要引导大模型生成偏好时，在此填入指导语
# （或运行时用 --preference "..." 注入），会以 [PREFERENCE] 块拼进提示词。
DIGGER_PREFERENCE = ""

DIGGER_EVALUABILITY = (
    "Mandatory evaluability requirements:\n"
    "1. Write exactly one complete top-level function `def pack_circles(n: int) -> np.ndarray`; "
    "put all imports and all logic inside it, and add nothing else at the top level.\n"
    "2. Return an (n, 3) array, rows (x, y, radius); every circle inside [0,1]^2 "
    "(x-r >= -1e-12, x+r <= 1+1e-12, likewise y); radius >= 0; for any two circles, "
    "center distance >= r_i + r_j - 1e-12.\n"
    "3. The function must return normally (do not raise exceptions)."
)
_CANONICAL_CACHE = REPO_ROOT / "visual_platform" / ".codet5_embeddings_cache.sqlite3"
_CANONICAL_DB = REPO_ROOT / "visual_platform" / "llm4ad_platform.sqlite3"
# 工作区已在原生 ext4（~/wip）上，默认直接读写权威副本，不再需要 /tmp 工作副本。
# 若以后把工作区放到慢盘（如 9p 挂载），可用 CLIMB_WORKING_DB / CLIMB_WORKING_CACHE
# 指到快盘路径恢复"工作副本"模式（prepare 时复制、结束/定期同步回权威位置）。
_WORKING_CACHE = Path(os.environ.get("CLIMB_WORKING_CACHE", str(_CANONICAL_CACHE)))
_WORKING_DB = Path(os.environ.get("CLIMB_WORKING_DB", str(_CANONICAL_DB)))


def _prepare_working_copies() -> None:
    """默认（工作区在原生 ext4）什么都不做：直接读写权威副本即可。
    只有显式设置了 CLIMB_WORKING_DB / CLIMB_WORKING_CACHE（工作副本模式）时，
    才把权威库复制到快盘路径；运行时应让 VISUAL_PLATFORM_DB /
    VISUAL_PLATFORM_CODET5_CACHE 指向工作副本（模块常量在 import 时绑定）。"""
    import shutil

    if _WORKING_DB == _CANONICAL_DB and _WORKING_CACHE == _CANONICAL_CACHE:
        return
    _WORKING_CACHE.parent.mkdir(parents=True, exist_ok=True)
    if _CANONICAL_CACHE.is_file() and (
        not _WORKING_CACHE.is_file()
        or _CANONICAL_CACHE.stat().st_mtime > _WORKING_CACHE.stat().st_mtime
    ):
        try:
            shutil.copy2(_CANONICAL_CACHE, _WORKING_CACHE)
        except OSError:
            pass
    if _CANONICAL_DB.is_file() and (
        not _WORKING_DB.is_file()
        or _CANONICAL_DB.stat().st_mtime > _WORKING_DB.stat().st_mtime
    ):
        try:
            _log(f"复制主库工作副本 D→/tmp（{_CANONICAL_DB.stat().st_size // 1024 // 1024}MB）")
            shutil.copy2(_CANONICAL_DB, _WORKING_DB)
            _log("主库工作副本就绪")
        except OSError as error:
            _log(f"主库工作副本复制失败：{error}")


def _sync_working_copies() -> None:
    import shutil

    if _WORKING_DB == _CANONICAL_DB and _WORKING_CACHE == _CANONICAL_CACHE:
        return
    if _WORKING_CACHE.is_file():
        try:
            _CANONICAL_CACHE.parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(_WORKING_CACHE, _CANONICAL_CACHE)
            _log(f"向量库已同步回权威位置（{_CANONICAL_CACHE.name}）")
        except OSError as error:
            _log(f"向量库同步回权威位置失败：{error}")
    if _WORKING_DB.is_file():
        try:
            _CANONICAL_DB.parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(_WORKING_DB, _CANONICAL_DB)
            _log(f"主库已同步回权威位置（{_CANONICAL_DB.name}）")
        except OSError as error:
            _log(f"主库同步回权威位置失败：{error}")


def _sync_vectors_only() -> None:
    """工作副本模式下定期把向量库同步回权威位置，避免 /tmp 清理丢失嵌入。"""
    import shutil

    if _WORKING_DB == _CANONICAL_DB and _WORKING_CACHE == _CANONICAL_CACHE:
        return
    if _WORKING_CACHE.is_file():
        try:
            if not _CANONICAL_CACHE.is_file() or (
                _WORKING_CACHE.stat().st_mtime > _CANONICAL_CACHE.stat().st_mtime
            ):
                _CANONICAL_CACHE.parent.mkdir(parents=True, exist_ok=True)
                shutil.copy2(_WORKING_CACHE, _CANONICAL_CACHE)
                _log("向量库已定期同步回权威位置")
        except OSError as error:
            _log(f"向量库定期同步失败：{error}")
# One continuous EoH per mountain: "chunks" are ONLY checkpoint boundaries
# (the population carries over), not evolution restarts.
CHUNK_MAX_SAMPLES = 40
CHUNK_GENERATIONS = 8
EMPTY_CHUNK_RETRIES = 3


def _log(message: str) -> None:
    print(f"[{time.strftime('%Y-%m-%d %H:%M:%S')}] {message}", flush=True)


_MISSING_IMPORTS_LOG = Path(
    os.environ.get("MISSING_IMPORTS_LOG", str(WORKSPACE_ROOT / "logs" / "missing_imports.log"))
)
_missing_import_seen: set[tuple[str, str]] = set()


def _record_missing_imports(records: list[dict[str, Any]], basin_id: str) -> None:
    """静态检查生成样本里 import 的包是否可用，缺失的追加记录到日志文件
    （每个 basin+模块每轮只记一条），用于事后看哪些包需要补充安装。"""
    try:
        import ast
        import importlib.util

        missing: list[tuple[str, float | None]] = []
        for record in records:
            code = str(record.get("code") or "")
            if not code:
                continue
            try:
                tree = ast.parse(code)
            except Exception:
                continue
            for node in ast.walk(tree):
                if isinstance(node, ast.Import):
                    mod = str(node.names[0].name or "") if node.names else ""
                elif isinstance(node, ast.ImportFrom) and node.level == 0:
                    mod = str(node.module or "")
                else:
                    continue
                if not mod:
                    continue
                top = mod.split(".")[0]
                if (basin_id, top) in _missing_import_seen:
                    continue
                try:
                    spec = importlib.util.find_spec(top)
                except (ImportError, ValueError, AttributeError, ModuleNotFoundError):
                    spec = None
                if spec is None:
                    _missing_import_seen.add((basin_id, top))
                    score = record.get("score")
                    missing.append((top, float(score) if is_valid_score(score) else None))
        if not missing:
            return
        log_path = Path(_MISSING_IMPORTS_LOG)
        log_path.parent.mkdir(parents=True, exist_ok=True)
        with open(log_path, "a", encoding="utf-8") as f:
            for top, score in missing:
                score_text = "invalid" if score is None else f"{score:.4f}"
                f.write(
                    f"[{time.strftime('%Y-%m-%d %H:%M:%S')}] basin={basin_id} "
                    f"missing_module={top} score={score_text}\n"
                )
    except Exception as error:
        _log(f"[missing-imports] 记录失败：{error}")


def _load_known_vectors() -> tuple[list[dict[str, Any]], np.ndarray]:
    # Fast path: load the pre-built known vectors from native storage. The
    # heavy DB+cache read at startup is slow/flaky on the 9p mount. The npz may
    # lag the DB by the samples inserted during this run - acceptable for
    # discovery (new samples are added incrementally); rebuild explicitly with
    # CLIMB_REBUILD_KNOWN=1 when a fresh map is required.
    current_count: int | None = None
    try:
        with get_connection() as conn:
            current_count = int(
                conn.execute(
                    "SELECT COUNT(*) AS c FROM individuals "
                    "WHERE score IS NOT NULL AND code IS NOT NULL AND length(code) > 50"
                ).fetchone()["c"]
            )
    except Exception:
        current_count = None
    if KNOWN_NPZ.is_file() and not os.environ.get("CLIMB_REBUILD_KNOWN"):
        try:
            data = np.load(KNOWN_NPZ, allow_pickle=True)
            return list(data["records"]), np.asarray(data["vectors"], dtype=np.float32)
        except Exception:
            pass
    with get_connection() as conn:
        rows = conn.execute(
            "SELECT id, score, code, algorithm_summary FROM individuals "
            "WHERE score IS NOT NULL AND code IS NOT NULL AND length(code) > 50"
        ).fetchall()
    records: list[dict[str, Any]] = []
    for r in rows:
        s = float(r["score"])
        if math.isfinite(s) and s > 0:
            records.append(
                {
                    "id": str(r["id"]),
                    "score": s,
                    "code": str(r["code"]).strip(),
                    "summary": str(r["algorithm_summary"] or ""),
                }
            )
    # NOTE: pass NO progress_callback (stable cache key). A fresh lambda
    # per call defeats @lru_cache on the model loader and reloads the
    # CodeT5 model (1-2 min) on every cache-miss embedding. MUST stay outside
    # the record loop (one call for the whole set, not O(n^2)).
    vectors, _ = get_codet5_embedding_matrix([{"function": r["code"]} for r in records])
    V = np.asarray(vectors, dtype=np.float32)
    V = V / np.linalg.norm(V, axis=1, keepdims=True)
    try:
        KNOWN_NPZ.parent.mkdir(parents=True, exist_ok=True)
        np.savez(
            KNOWN_NPZ,
            records=np.asarray(records, dtype=object),
            vectors=V,
            n_records=len(records),
        )
    except Exception:
        pass
    return records, V


def _load_mountains(path: Path) -> list[dict[str, Any]]:
    data = json.loads(path.read_text(encoding="utf-8"))
    mountains = data.get("mountains", [])
    mountains = [m for m in mountains if m.get("rep_id")]
    for index, m in enumerate(mountains):
        m.setdefault("basin_id", m["rep_id"])
    return mountains


def _basin_node(rep_id: str, code: str, score: float, summary: str) -> dict[str, Any]:
    return {"id": rep_id, "code": code, "score": score, "algorithm": summary}


def _load_results(path: Path) -> dict[str, Any] | None:
    if not path.is_file():
        return None
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return None


def _save_results(results: dict[str, Any], path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_suffix(".json.tmp")
    tmp.write_text(json.dumps(results, ensure_ascii=False, indent=2), encoding="utf-8")
    tmp.replace(path)


class Discovery:
    """A generated sample whose min distance to every known solution is
    >= MOUNTAIN_DIST starts a new mountain (dynamic queue growth)."""

    def __init__(self, records: list[dict[str, Any]], vectors: np.ndarray) -> None:
        self._codes: list[str] = [r["code"] for r in records]
        self._vectors = vectors.copy()
        self._new_vectors: list[np.ndarray] = []
        self._new_records: list[dict[str, Any]] = []

    def check(self, code: str, score: float, summary: str = "") -> dict[str, Any] | None:
        code = str(code or "").strip()
        if not code or code in self._codes:
            return None
        vectors, _ = get_codet5_embedding_matrix([{"function": code}])
        v = np.asarray(vectors[0], dtype=np.float32)
        v = v / float(np.linalg.norm(v))
        d_known = (
            float((1.0 - np.clip(self._vectors @ v, -1.0, 1.0)).min())
            if self._vectors.shape[0]
            else math.inf
        )
        d_new = math.inf
        if self._new_vectors:
            stack = np.asarray(self._new_vectors, dtype=np.float32)
            d_new = float((1.0 - np.clip(stack @ v, -1.0, 1.0)).min())
        if min(d_known, d_new) >= MOUNTAIN_DIST:
            self._codes.append(code)
            self._new_vectors.append(v)
            record = {"id": "", "score": float(score), "code": code, "summary": summary}
            self._new_records.append(record)
            return record
        return None


class RegionGate:
    """链爬行区域约束 v4（峰值导向 + 换山，--region-radius > 0 时启用）。

    定义驱动（链爬行v4方案.md §0/§7 定稿）：
    - 进行时 R：节点到"所有已知更高分解中语义最近者"的距离，池 = 历史（known）
      + 本轮此前已处理节点（session），先算 R 再把 X 加进 session；
    - 峰值（peak）：进行时 R > PEAK_RADIUS(0.03) 的节点 = 一个思路的当前最高分；
      峰值池 = 本轮所有峰值（含入口），按分数降序，是换山候选 + 交付物；
    - 动态球：半径 R_锚 = 锚点到最近更高分解的距离（known + session），换锚后重算；
    - 新父事件 = d(X,锚) < R_锚 且 score(X) > score(锚) → 换锚到 X（链推进）；
      若新锚本身是峰值，旧"当前峰值"被吸收（同一思路续到更高峰）；
    - 换山：停滞（R_锚 > 0.03 且连续 STALL_BLOCKS 块无新父事件）→ 记"停滞换山"；
      收敛（R_锚 <= 0.03 且连续 STALL_BLOCKS 块无新父事件）→ 记"收敛换山"；
      然后换峰值池下一个未爬峰值；池空 → 终止。
    - 球外 R>0.03 的峰值只进池不进种群；球内峰值常驻种群。
    """

    def __init__(
        self,
        anchor_node: dict[str, Any],
        radius: float,
        entry_code: str | None = None,
        known_records: list[dict[str, Any]] | None = None,
        topk: int = 8,
        add_anchor_peak: bool = True,
    ) -> None:
        self._topk = max(2, int(topk))
        self._fallback_radius = float(radius)
        self.radius = float(radius)
        self.anchor: dict[str, Any] = dict(anchor_node)
        self.entry_code = entry_code or str(anchor_node.get("code", ""))
        self.anchor_vec: np.ndarray | None = None
        self.entry_vec: np.ndarray | None = None
        self.reference: dict[str, Any] | None = None
        self.ball_members: list[dict[str, Any]] = []
        self.chain: list[dict[str, Any]] = [
            {
                "id": str(anchor_node.get("id", "")),
                "score": float(anchor_node.get("score", 0.0)),
                "d_from_entry": 0.0,
            }
        ]
        self._cache: dict[str, np.ndarray] = {}
        self._cache_lock = __import__("threading").Lock()
        # known 池：图内已知解（code, score）；session 池：本会话生成的有效解
        self._known: list[tuple[str, float]] = []
        for rec in known_records or []:
            code = str(rec.get("code", "") or "").strip()
            score = rec.get("score")
            if code and is_valid_score(score):
                self._known.append((code, float(score)))
        self._session: list[tuple[str, float]] = []
        # v4 峰值池：{code, score, r_during, node_id, verdict}，按分数降序
        self.peak_pool: list[dict[str, Any]] = []
        self._peak_by_code: dict[str, dict[str, Any]] = {}
        self.current_peak_code: str | None = None
        # 锚点真实 R（最近更高分解距离；无更高分解 = inf）；radius 是球半径（含兜底）
        self.anchor_r: float = math.inf
        self.stall_blocks: int = 0
        self.mountain_index: int = 0
        self.mountain_switches: list[dict[str, Any]] = []
        # 预置锚点/入口向量
        self.anchor_vec = self._embed(self.anchor["code"])
        self.entry_vec = self._embed(self.entry_code)
        self._refresh()
        if add_anchor_peak:
            # 入口也是峰值（R=0.0354>0.03），进池作为第一个；入口 R<=0.03 时兜底仍入池
            self.add_peak(
                self.anchor["code"],
                float(self.anchor["score"]),
                self.anchor_r,
                str(self.anchor.get("id", "")),
            )
            self.current_peak_code = self.anchor["code"]

    def _embed(self, code: str) -> np.ndarray:
        code = str(code or "").strip()
        h = hashlib.sha256(code.encode("utf-8")).hexdigest()
        with self._cache_lock:
            v = self._cache.get(h)
            if v is None:
                vectors, _ = get_codet5_embedding_matrix([{"function": code}])
                v = np.asarray(vectors[0], dtype=np.float32)
                v = v / float(np.linalg.norm(v))
                self._cache[h] = v
        return v

    @staticmethod
    def _d(v1: np.ndarray, v2: np.ndarray) -> float:
        return float(1.0 - np.clip(np.dot(v1, v2), -1.0, 1.0))

    def _refresh(self) -> None:
        """重算 R_锚（最近更高分解距离）、reference（链下一站）、ball_members（球内 top-K）。"""
        av = self.anchor_vec
        anchor_score = float(self.anchor["score"])
        best: tuple[float, str, float] | None = None
        for code, score in self._pool():
            if score <= anchor_score + V4_IMPROVE_EPS:
                continue
            d = self._d(av, self._embed(code))
            if best is None or d < best[0]:
                best = (d, code, score)
        if best is not None:
            self.anchor_r = best[0]
            self.radius = max(best[0], 1e-4)
            self.reference = {"code": best[1], "score": best[2], "dist": best[0]}
        else:
            self.anchor_r = math.inf
            self.radius = self._fallback_radius
            self.reference = None
        mems: list[tuple[float, str]] = []
        for code, score in self._pool():
            if self._d(av, self._embed(code)) < self.radius:
                mems.append((score, code))
        mems.sort(key=lambda x: -x[0])
        self.ball_members = [
            {"code": c, "score": s} for s, c in mems[: self._topk]
        ]

    def _pool(self) -> list[tuple[str, float]]:
        return self._known + self._session

    def _during_r(self, code: str, score: float, v: np.ndarray) -> float:
        """进行时 R：到"池 = 历史 + 本轮此前节点"中分数更高者的最近距离。"""
        best_d = math.inf
        for pcode, pscore in self._pool():
            if pscore > score + V4_IMPROVE_EPS:
                d = self._d(v, self._embed(pcode))
                if d < best_d:
                    best_d = d
        return best_d

    def add_peak(self, code: str, score: float, r_during: float, node_id: str = "") -> None:
        """加入峰值池（按 code 去重，分数更高时更新），池按分数降序。"""
        code = str(code or "").strip()
        if not code:
            return
        score = float(score)
        entry = self._peak_by_code.get(code)
        if entry is not None:
            if score > float(entry["score"]) + V4_IMPROVE_EPS:
                entry["score"] = score
                entry["r_during"] = float(r_during) if math.isfinite(float(r_during)) else None
                entry["node_id"] = node_id
                self.peak_pool.sort(key=lambda p: -float(p["score"]))
            return
        entry = {
            "code": code,
            "score": score,
            "r_during": float(r_during) if math.isfinite(float(r_during)) else None,
            "node_id": node_id,
            "verdict": "unclimbed",
            "max_reached": score,
        }
        self._peak_by_code[code] = entry
        self.peak_pool.append(entry)
        self.peak_pool.sort(key=lambda p: -float(p["score"]))

    def check(
        self, code: str, score: float, node_id: str = ""
    ) -> tuple[bool, float, float, bool, float, bool]:
        """评估一个生成节点。返回
        (in_region, d_to_anchor, d_to_entry, became_new_anchor, r_during, is_peak)。
        进行时 R 先算、再加入 session（顺序别反）。"""
        v = self._embed(code)
        d_anchor = self._d(v, self.anchor_vec)
        d_entry = self._d(v, self.entry_vec)
        r_during = math.nan
        is_peak = False
        if is_valid_score(score):
            score = float(score)
            r_during = self._during_r(code, score, v)
            # 峰值判定（v1.1 修正）：R>0.03 且 score 严格高于锚点分 —— 同分/低分
            # 近重复不算新思路（否则峰值池会被 0.52 噪声填满）
            is_peak = (
                r_during > PEAK_RADIUS
                and score > float(self.anchor["score"]) + V4_IMPROVE_EPS
            )
            if is_peak:
                self.add_peak(code, score, r_during, node_id)
            self._session.append((code, score))
        in_region = d_anchor < self.radius
        became = False
        if (
            in_region
            and is_valid_score(score)
            and float(score) > float(self.anchor["score"]) + V4_IMPROVE_EPS
        ):
            self.anchor = {"id": node_id, "code": code, "score": float(score)}
            self.anchor_vec = v
            became = True
            self.chain.append(
                {"id": node_id, "score": float(score), "d_from_entry": d_entry}
            )
            self._refresh()
            # 当前峰值跟踪：新锚若本身是峰值（突破），旧当前峰值被吸收（同一思路续到更高峰）
            if is_peak and self.current_peak_code and self.current_peak_code != code:
                old = self._peak_by_code.get(self.current_peak_code)
                if old is not None:
                    old["verdict"] = "吸收"
                self.current_peak_code = code
            # 当前峰值"爬到的最高分"（链推进时更新，交付物里能看到思路的实际最高分）
            if self.current_peak_code:
                cp = self._peak_by_code.get(self.current_peak_code)
                if cp is not None:
                    cp["max_reached"] = max(
                        float(cp.get("max_reached", 0.0)), float(score)
                    )
        return in_region, d_anchor, d_entry, became, r_during, is_peak

    def in_region(self, code: str) -> bool:
        v = self._embed(code)
        return self._d(v, self.anchor_vec) < self.radius

    def switch_anchor(self, node: dict[str, Any]) -> None:
        """换山：把锚点换成峰值池里的下一个未爬峰值，重算球 R，链记录。"""
        self.anchor = dict(node)
        self.anchor_vec = self._embed(str(node.get("code", "")))
        self.mountain_index += 1
        self._refresh()
        self.chain.append(
            {
                "id": str(node.get("node_id", "") or node.get("id", "")),
                "score": float(node.get("score", 0.0)),
                "d_from_entry": self._d(self.anchor_vec, self.entry_vec),
            }
        )
        self.current_peak_code = str(node.get("code", ""))

    def switch_mountain(self, reason: str) -> dict[str, Any] | None:
        """停滞/收敛换山：给当前峰值记 verdict，返回峰值池下一个未爬峰值（无则 None）。"""
        if self.current_peak_code:
            entry = self._peak_by_code.get(self.current_peak_code)
            if entry is not None:
                entry["verdict"] = reason
        anchor_code = str(self.anchor.get("code", ""))
        for peak in self.peak_pool:
            if peak.get("verdict") == "unclimbed" and peak.get("code") != anchor_code:
                return dict(peak)
        return None

    def seed_population(self) -> list[dict[str, Any]]:
        """初始/补种种群（v4）：锚点（常驻）+ 球内峰值（常驻）+ 球内高分成员，去重。
        球外峰值（含 reference）不进种群。"""
        seen: set[str] = set()
        out: list[dict[str, Any]] = []
        anchor_code = str(self.anchor.get("code", "") or "").strip()
        if anchor_code:
            seen.add(anchor_code)
            out.append(
                {"code": anchor_code, "score": float(self.anchor["score"]), "algorithm": ""}
            )
        av = self.anchor_vec
        for peak in self.peak_pool:
            code = str(peak.get("code", "") or "").strip()
            if not code or code in seen:
                continue
            if self._d(av, self._embed(code)) < self.radius:
                seen.add(code)
                out.append({"code": code, "score": float(peak["score"]), "algorithm": ""})
        for node in self.ball_members:
            code = str(node.get("code", "") or "").strip()
            if not code or code in seen:
                continue
            seen.add(code)
            out.append({"code": code, "score": float(node["score"]), "algorithm": ""})
        return out[: self._topk + 1]

    def resume_dict(self) -> dict[str, Any]:
        return {
            "anchor": dict(self.anchor),
            "chain": list(self.chain),
            "entry_code": self.entry_code,
            "peak_pool": list(self.peak_pool),
            "current_peak_code": self.current_peak_code,
            "stall_blocks": int(self.stall_blocks),
            "mountain_index": int(self.mountain_index),
            "mountain_switches": list(self.mountain_switches),
        }


def _run_basin_segment(
    *,
    basin_id: str,
    seed_node: dict[str, Any],
    segment_index: int,
    samples: int,
    task: Any,
    llm: Any,
    base_description: str,
    evaluability_constraints: str,
    log_dir: Path,
    discovery: Discovery | None,
    num_samplers: int,
    num_evaluators: int,
) -> tuple[dict[str, Any], list[dict[str, Any]]]:
    state = ArmState(basin_id, "vanilla", seed_node, EmbeddingStore())
    state.current_best = dict(seed_node)
    segment_record, segment_records = _run_eoh_segment(
        state=state,
        segment_index=segment_index,
        samples=samples,
        weights={},
        directive="",
        task=task,
        llm=llm,
        base_description=base_description,
        log_dir=log_dir,
        seed_nodes=[seed_node],
        filter_enabled=False,
        num_samplers=num_samplers,
        num_evaluators=num_evaluators,
        evaluability_constraints=evaluability_constraints,
    )
    discovered: list[dict[str, Any]] = []
    if discovery is not None:
        for record in segment_records:
            if record.get("filtered") or _is_failed_operator(record.get("operator", "")):
                continue
            if not is_valid_score(record.get("score")):
                continue
            new_basin = discovery.check(
                record["code"],
                float(record["score"]),
                str(record.get("algorithm", "") or ""),
            )
            if new_basin is not None:
                new_basin["discovered_by"] = basin_id
                discovered.append(new_basin)
    segment_record["discovered"] = discovered
    segment_record["basin_best"] = state.current_best.get("score")
    return segment_record, segment_records


def _ensure_dig_revision(revision_id: str) -> None:
    """One dedicated revision per dig run: dug samples become first-class
    nodes (reusable / graphable / visualizable in the platform)."""
    with get_connection() as conn:
        # revisions.workspace_id 有外键约束；全新数据库里不一定存在该 workspace
        # （作者库里是 "t0"）。先补建，否则插入直接 FOREIGN KEY constraint failed。
        conn.execute(
            "INSERT OR IGNORE INTO workspaces (workspace_id, name) VALUES (?, ?)",
            (DIG_WORKSPACE_ID, "basin_dig"),
        )
        conn.execute(
            "INSERT OR IGNORE INTO revisions "
            "(revision_id, workspace_id, mode, lifecycle_status, graph_status, config, started_at) "
            "VALUES (?, ?, 'basin_dig', 'running', 'none', ?, datetime('now'))",
            (
                revision_id,
                DIG_WORKSPACE_ID,
                json.dumps({"mode": "basin_dig", "source": "multi-basin digger"}),
            ),
        )


def _complete_dig_revision(revision_id: str) -> None:
    with get_connection() as conn:
        conn.execute(
            "UPDATE revisions SET lifecycle_status='completed', finished_at=datetime('now') "
            "WHERE revision_id=?",
            (revision_id,),
        )


def _dig_revision_max_sample_order(revision_id: str) -> int:
    with get_connection() as conn:
        row = conn.execute(
            "SELECT COALESCE(MAX(sample_order), 0) AS max_order FROM individuals WHERE revision_id=?",
            (revision_id,),
        ).fetchone()
        return int(row["max_order"]) if row else 0


def _insert_dig_samples(
    segment_records: list[dict[str, Any]],
    *,
    revision_id: str,
    basin_id: str,
    segment_index: int,
    counter_ref: dict[str, int],
    code_to_id: dict[str, str] | None = None,
) -> int:
    """Register a segment's valid solutions as individuals (source=basin_dig).

    v4：raw_payload 带 op（算子名）+ parents（父节点 id 列表，按代码匹配入口/已注册
    节点 id，匹配不到记 code_hash）+ peak（是否峰值）+ r_during（进行时 R）。
    """
    from visual_platform.repositories.individual_repository import insert_individual

    code_to_id = code_to_id if code_to_id is not None else {}
    inserted = 0
    for record in segment_records:
        if record.get("operator") == "region_seed" or record.get("filtered"):
            continue
        score = record.get("score")
        if not is_valid_score(score):
            continue
        counter = counter_ref["value"]
        counter_ref["value"] += 1
        record_code = str(record["code"]).strip()
        # 父节点 id 解析：parents 是父代码 → 按代码匹配入口/本轮已注册节点 id
        parent_ids: list[Any] = []
        for pcode in record.get("parents") or []:
            pcode = str(pcode or "").strip()
            pid = code_to_id.get(pcode)
            if pid:
                parent_ids.append(pid)
            else:
                parent_ids.append(
                    {"code_hash": hashlib.sha256(pcode.encode("utf-8")).hexdigest()}
                )
        new_id = f"dig-{revision_id}-s{counter}"
        insert_individual(
            {
                "id": new_id,
                "revision_id": revision_id,
                "workspace_id": DIG_WORKSPACE_ID,
                "sample_order": counter,
                "generation": 0,
                "score": float(score),
                "function": record["code"],
                "algorithm": str(record.get("algorithm", "") or ""),
                "source_kind": "basin_dig",
                "origin_kind": "basin_dig",
                "basin_id": basin_id,
                "segment_index": segment_index,
                "operator": str(record.get("operator", "") or ""),
                "op": str(record.get("operator", "") or ""),
                "parents": parent_ids,
                "region": str(record.get("region", "") or ""),
                "d_to_entry": record.get("d_to_entry"),
                "d_to_anchor": record.get("d_to_anchor"),
                "r_during": record.get("r_during"),
                "peak": bool(record.get("is_peak", False)),
            }
        )
        code_to_id[record_code] = new_id
        inserted += 1
    return inserted


def _slim_segment(segment_record: dict[str, Any]) -> dict[str, Any]:
    """Persistable summary of a segment record. Full samples (with code) live
    in the DB (basin_dig revision) - keeping them out of the results JSON keeps
    the per-segment checkpoint small and avoids heavy 9p writes."""
    return {
        "segment": segment_record.get("segment"),
        "best": segment_record.get("basin_best"),
        "generated": segment_record.get("generated"),
        "evaluated": segment_record.get("evaluated"),
        "filtered": segment_record.get("filtered"),
        "valid": segment_record.get("valid"),
        "discovered": segment_record.get("discovered", []),
    }


def _population_snapshot(method: Any) -> list[dict[str, Any]]:
    """Persistable population: code + score + summary of the alive members."""
    snapshot: list[dict[str, Any]] = []
    for function in getattr(method._population, "_population", []) or []:
        code = str(function).strip()
        score = getattr(function, "score", None)
        if code and is_valid_score(score):
            snapshot.append(
                {
                    "code": code,
                    "score": float(score),
                    "algorithm": str(getattr(function, "algorithm", "") or ""),
                }
            )
    return snapshot


def _dig_mountain(
    *,
    basin: dict[str, Any],
    entry_node: dict[str, Any],
    original_rep_score: float,
    task: Any,
    llm: Any,
    base_description: str,
    log_dir: Path,
    samples_per_segment: int,
    death_window: int,
    max_window: int,
    discovery: Discovery | None,
    budget: dict[str, int],
    num_samplers: int,
    num_evaluators: int,
    evaluability_constraints: str,
    sample_sink: Any | None = None,
    resume_state: dict[str, Any] | None = None,
    checkpoint: Any | None = None,
    region_radius: float = 0.0,
    known_records: list[dict[str, Any]] | None = None,
) -> dict[str, Any]:
    """One continuous EoH per mountain. 'Chunks' are checkpoint boundaries
    only: the population carries over between chunks (no best-restart).

    region_radius > 0 时启用链爬行区域约束（RegionGate v2，见类注释）：
    动态半径=锚点最近更高分解距离；新父事件换锚；m3 局部改进算子 + 目标参考；
    代间过滤（区域外不进种群）+ 全量注册保留。
    """
    from llm4ad.method.eoh import EoH

    if resume_state:
        best = float(resume_state["best"])
        dry = int(resume_state["dry"])
        window = int(resume_state["window"])
        evaluated_total = int(resume_state["evaluated"])
        tot_sample_nums = int(resume_state.get("tot_sample_nums", evaluated_total))
        chunk_index = int(
            resume_state.get("chunk_index", resume_state.get("segment_index", 1))
        )
        segments = list(
            resume_state.get("segments", resume_state.get("chunks", []))
        )
        discovered_all = list(resume_state.get("discovered", []))
        population = list(resume_state.get("population", []))
        if not population and resume_state.get("seed_node"):
            # Back-compat with the old best-restart checkpoint format:
            # continue the continuous EoH from the persisted best.
            population = [dict(resume_state["seed_node"])]
    else:
        best = float(entry_node["score"])
        dry = 0
        window = death_window
        evaluated_total = 0
        tot_sample_nums = 0
        chunk_index = 1
        segments = []
        discovered_all = []
        population = [dict(entry_node)]

    # 区域约束（链爬行实验 v4：峰值导向 + 换山 + 无限预算）
    gate: RegionGate | None = None
    if region_radius > 0:
        resume_region = (resume_state or {}).get("region") if resume_state else None
        if resume_region and resume_region.get("anchor", {}).get("code"):
            gate = RegionGate(
                resume_region["anchor"],
                region_radius,
                entry_code=resume_region.get("entry_code")
                or str(entry_node.get("code", "")),
                known_records=known_records,
                add_anchor_peak=False,
            )
            gate.chain = list(resume_region.get("chain", []))
            # v4 峰值池 / 当前峰值 / 停滞块 / 换山记录 断点恢复（峰值池必须持久化）
            gate.peak_pool = list(resume_region.get("peak_pool", []))
            gate._peak_by_code = {str(p.get("code", "")): p for p in gate.peak_pool}
            gate.current_peak_code = resume_region.get("current_peak_code")
            gate.stall_blocks = int(resume_region.get("stall_blocks", 0))
            gate.mountain_index = int(resume_region.get("mountain_index", 0))
            gate.mountain_switches = list(resume_region.get("mountain_switches", []))
        else:
            gate = RegionGate(
                entry_node,
                region_radius,
                entry_code=str(entry_node.get("code", "")),
                known_records=known_records,
            )
        # 种群 = 已有（resume 时含球内生成子代）∪ 锚点 + 球内峰值 + 球内 top-K
        seen_codes = {str(m.get("code", "")) for m in population if m.get("code")}
        for node in gate.seed_population():
            code = str(node.get("code", ""))
            if code and code not in seen_codes:
                population.append(node)
                seen_codes.add(code)
        _log(
            f"  [区域v4] R={gate.radius:.4f} 峰值池{len(gate.peak_pool)} "
            f"当前峰值={str(gate.current_peak_code)[:32]} 球内top{len(gate.ball_members)} "
            f"初始种群{len(population)}"
        )

    death_reason = ""
    terminated_by_pool = False
    empty_chunks = 0
    while budget["remaining"] > 0:
        # A fresh EoH per chunk, seeded with the persisted top-8 population:
        # population continuity is preserved (selection pressure carries over)
        # while each chunk's sample budget stays reliable. A single long-lived
        # EoH instance was observed to stop sampling after 1-2 chunks (its
        # internal generation/sample counters drift out of sync with the chunk
        # caps), killing mountains with "empty chunk" verdicts.
        collected_chunk: list[dict[str, Any]] = []
        profiler_class = _create_collecting_profiler_class()
        profiler = profiler_class(log_dir, collected_chunk, initial_num_samples=0)
        preference = DIGGER_PREFERENCE.strip()
        prompt_parts = [base_description]
        if preference:
            prompt_parts.append(f"[PREFERENCE]\n{preference}")
        prompt_parts.append(evaluability_constraints)
        task.task_description = "\n\n".join(prompt_parts)
        region_active = gate is not None
        method = EoH(
            llm=llm,
            profiler=profiler,
            evaluation=task,
            max_sample_nums=CHUNK_MAX_SAMPLES + len(population),
            max_generations=max(CHUNK_GENERATIONS, CHUNK_GENERATIONS * 2),
            pop_size=8,
            selection_num=2,
            num_samplers=num_samplers,
            num_evaluators=num_evaluators,
            operator_weights=(
                {"e1": 0.05, "e2": 0.15, "m1": 0.10, "m2": 0.20, "m3": 0.50}
                if region_active
                else {}
            ),
            use_m3_operator=region_active,
            resume_mode=True,
            debug_mode=False,
        )
        # v5：m3 恢复参考——把锚点的最近更高分解（父节点）喂给提示；
        # 无更高分解（全局最高）时 reference=None → m3 退化纯局部改进。
        if region_active:
            method._vp_m3_ref = gate.reference
        accepted_seeds = 0
        for member in population:
            ok = method.register_prescored_seed_function(
                member["code"],
                score=float(member["score"]),
                algorithm=str(member.get("algorithm", "") or ""),
                operator="region_seed",
            )
            accepted_seeds += int(bool(ok))
        if accepted_seeds <= 0:
            death_reason = "种群种子注册失败"
            break
        method._tot_sample_nums = 0
        if len(method._population._population) == 0 and len(method._population._next_gen_pop) > 0:
            method._population.survival()

        # 代间约束（链爬行实验，region_radius>0）：每个生成子代进种群前判区域。
        # 区域外的分数置 -inf → survival() 按分数排序时自然淘汰，永远当不了父代，
        # 种群只能由区域内成员构成 → 模型看到的父代码始终在区域内。
        # （profiler 先于 population 记录真分数，这里改分不影响入库分数。）
        if gate is not None:
            pop = method._population
            _orig_register = pop.register_function

            def _region_aware_register(func):
                try:
                    code = str(func).strip()
                    if code and not gate.in_region(code):
                        func.score = float("-inf")
                except Exception:
                    pass
                return _orig_register(func)

            pop.register_function = _region_aware_register

        method._multi_threaded_sampling(method._iteratively_use_eoh_operator)
        chunk_records = [
            record
            for record in collected_chunk
            if record.get("operator") != "region_seed"
        ]
        if not chunk_records:
            # Transient LLM/API failures can produce an empty chunk; do not
            # kill the mountain on one bad chunk.
            empty_chunks += 1
            if empty_chunks >= EMPTY_CHUNK_RETRIES:
                death_reason = f"生成连续失败（连续 {EMPTY_CHUNK_RETRIES} 块无新样本）"
                break
            _log(f"  [重试] {basin['basin_id'][:36]} 本块无新样本（第 {empty_chunks}/{EMPTY_CHUNK_RETRIES} 次），稍候重试")
            time.sleep(10)
            continue
        empty_chunks = 0
        _record_missing_imports(chunk_records, basin["basin_id"])
        evaluated = sum(
            1
            for record in chunk_records
            if not record.get("filtered")
            and not _is_failed_operator(record.get("operator", ""))
        )
        evaluated_total += evaluated
        budget["remaining"] -= evaluated
        tot_sample_nums = evaluated_total

        # 区域标注（链爬行 v4）：记录 in/out、距锚点/距入口距离、进行时 R、峰值、
        # 换锚事件；每块结束判停滞 → 换山 / 终止（峰值池空）
        region_stats: dict[str, Any] | None = None
        terminated_by_pool = False
        if gate is not None:
            region_stats = {"in": 0, "out": 0, "advances": 0, "peaks_found": 0,
                            "d_entry_median": None,
                            "anchor_score": float(gate.anchor["score"]),
                            "anchor_id": str(gate.anchor.get("id", "")),
                            "mountain": gate.mountain_index,
                            "stall_blocks": gate.stall_blocks}
            ds: list[float] = []
            for record in chunk_records:
                if record.get("filtered") or _is_failed_operator(record.get("operator", "")):
                    continue
                node_id = f"chunk{chunk_index}-s{record.get('sample_order', '')}"
                in_reg, d_anchor, d_entry, became, r_during, is_peak = gate.check(
                    record["code"],
                    float(record.get("score") or math.nan),
                    node_id,
                )
                record["region"] = "in" if in_reg else "out"
                record["d_to_anchor"] = d_anchor
                record["d_to_entry"] = d_entry
                record["r_during"] = r_during if math.isfinite(r_during) else None
                record["is_peak"] = bool(is_peak)
                if in_reg:
                    region_stats["in"] += 1
                    ds.append(d_entry)
                else:
                    region_stats["out"] += 1
                if became:
                    region_stats["advances"] += 1
                if is_peak:
                    region_stats["peaks_found"] += 1
            if ds:
                region_stats["d_entry_median"] = float(np.median(ds))
            region_stats["anchor_score"] = float(gate.anchor["score"])
            region_stats["anchor_id"] = str(gate.anchor.get("id", ""))
            # 停滞/换山检测（v5，链爬行v5修正提案.md §1）：
            #  - 新父事件重置停滞计数（分数仍在涨 = 爬升活着，哪怕没出峰）；
            #  - 连续 STALL_BLOCKS 块无新父事件 → 思路榨干 → 换山；
            #  - 锚点 R 不当判据（R<0.03 是爬升常态，见 v5 提案 §0）；
            #  - 锚点无更高分解（R=∞，到达全局最高）→ 标记"链顶/冠军"并终止（目标达成）；
            #  - 峰值池无未爬峰值 → 终止（池空）。
            if region_stats["advances"] > 0:
                gate.stall_blocks = 0
            else:
                gate.stall_blocks += 1
            region_stats["stall_blocks"] = gate.stall_blocks
            switch_now = False
            if gate.stall_blocks >= STALL_BLOCKS:
                if not math.isfinite(gate.anchor_r):
                    # 全局最高：无更高分解 → 链顶交付，终止（不再换山浪费）
                    reason = "链顶/冠军（全局最高，无更高分解）"
                    switch_now = False
                    terminated_by_pool = True
                    death_reason = (
                        f"终止：{reason}；连续 {gate.stall_blocks} 块无新父事件；"
                        f"共 {len(gate.peak_pool)} 峰已爬"
                    )
                else:
                    if DEATH_ON_STALL:
                        # 变体：停滞满 N 块无新父 → 直接判死（不换山），
                        # 观察纯单山爬终点是否 R>0.03（用户指示）。
                        reason = "停滞判死（N块无新父，不换山）"
                        switch_now = False
                        terminated_by_pool = True
                        death_reason = (
                            f"终止：{reason}；连续 {gate.stall_blocks} 块无新父事件；"
                            f"共 {len(gate.peak_pool)} 峰（未换山）"
                        )
                    else:
                        reason = "停滞换山"
                        switch_now = True
            if switch_now:
                next_peak = gate.switch_mountain(reason)
                if next_peak is None:
                    terminated_by_pool = True
                    death_reason = (
                        f"终止：峰值池空（{reason} 后峰值池无未爬峰值；"
                        f"共 {len(gate.peak_pool)} 峰已爬）"
                    )
                else:
                    gate.switch_anchor(next_peak)
                    gate.stall_blocks = 0  # 新山重新计停滞
                    gate.mountain_switches.append(
                        {
                            "from_peak": {
                                "code": str(gate.chain[-2].get("id", "")),
                                "score": gate.chain[-2].get("score"),
                            },
                            "to_peak": {
                                "code": str(next_peak.get("node_id", "")),
                                "score": float(next_peak.get("score", 0.0)),
                            },
                            "reason": reason,
                            "chunk": chunk_index,
                            "stalled_blocks": int(gate.stall_blocks),
                        }
                    )
                    dry = 0
                    window = death_window
                    best = max(best, float(next_peak["score"]))
                    remaining = sum(
                        1 for p in gate.peak_pool if p.get("verdict") == "unclimbed"
                    )
                    _log(
                        f"  [换山] {reason} 新锚点 score={float(next_peak['score']):.4f} "
                        f"R={gate.radius:.4f} 峰值池剩余未爬 {remaining}"
                    )

        for record in chunk_records:
            if record.get("filtered") or _is_failed_operator(record.get("operator", "")):
                continue
            dry += 1
            score = record.get("score")
            in_region = gate is None or record.get("region") == "in"
            best_eps = V4_IMPROVE_EPS if gate is not None else IMPROVE_EPS
            if (
                in_region
                and is_valid_score(score)
                and float(score) > best + best_eps
            ):
                window = min(max_window, max(window, 2 * dry))
                dry = 0
                best = float(score)
        new_discovered: list[dict[str, Any]] = []
        if discovery is not None:
            for record in chunk_records:
                if record.get("filtered") or _is_failed_operator(record.get("operator", "")):
                    continue
                if not is_valid_score(record.get("score")):
                    continue
                new_basin = discovery.check(
                    record["code"],
                    float(record["score"]),
                    str(record.get("algorithm", "") or ""),
                )
                if new_basin is not None:
                    new_basin["discovered_by"] = basin["basin_id"]
                    new_discovered.append(new_basin)
        discovered_all.extend(new_discovered)
        population = _population_snapshot(method)
        if gate is not None:
            # 种群只保留区域内成员（代间过滤之外的兜底）；
            # 锚点 + 目标参考 + 球内 top-K 常驻（区域沿链爬的关键）
            kept = [m for m in population if gate.in_region(m["code"])]
            seen_codes = {str(m.get("code", "")) for m in kept}
            for node in gate.seed_population():
                code = str(node.get("code", ""))
                if code and code not in seen_codes:
                    kept.append({"code": code, "score": float(node["score"]), "algorithm": ""})
                    seen_codes.add(code)
            population = kept[:8]
        segments.append(
            {
                "chunk": chunk_index,
                "best": best,
                "generated": len(chunk_records),
                "evaluated": evaluated,
                "discovered": new_discovered,
                "region": region_stats,
            }
        )
        if sample_sink is not None:
            sample_sink(chunk_records, chunk_index, basin["basin_id"])
        if checkpoint is not None:
            checkpoint(
                {
                    "in_progress": True,
                    "best": best,
                    "dry": dry,
                    "window": window,
                    "evaluated": evaluated_total,
                    "tot_sample_nums": tot_sample_nums,
                    "chunk_index": chunk_index + 1,
                    "segments": segments,
                    "population": population,
                    "discovered": discovered_all,
                    "delta_vs_rep": best - float(original_rep_score),
                    **(
                        {"region": gate.resume_dict()}
                        if gate is not None
                        else {}
                    ),
                }
            )
        if dry >= window and gate is None:
            # 判死窗口只作非区域模式的兜底；v4 区域模式用"停滞/收敛换山 + 峰值池空终止"
            death_reason = f"判死（连续 {dry} 个评测样本无改进 ≥ 窗口 {window}）"
            break
        if terminated_by_pool:
            break
        chunk_index += 1

    if not death_reason:
        death_reason = "全局预算耗尽（未判死）"
    try:
        method._profiler.finish()
    except Exception:
        pass
    method._sampler.llm.close()
    return {
        "basin_id": basin["basin_id"],
        "entry_score": float(entry_node["score"]),
        "original_rep_score": float(original_rep_score),
        "best": best,
        "delta_vs_entry": best - float(entry_node["score"]),
        "delta_vs_rep": best - float(original_rep_score),
        "evaluated": evaluated_total,
        "segments": segments,
        "discovered": discovered_all,
        "verdict": death_reason,
        "window": window,
        "in_progress": False,
        **(
            {
                "mountain_switches": list(gate.mountain_switches),
                "region": {
                    "radius": region_radius,
                    **gate.resume_dict(),
                },
            }
            if gate is not None
            else {}
        ),
    }


def _best_dig_samples(basin_ids: set[str]) -> dict[str, dict[str, Any]]:
    """批量取每个山的已挖最高分解（一次全表读，避免逐山 LIKE 慢查询）。"""
    best: dict[str, dict[str, Any]] = {}
    try:
        with get_connection() as conn:
            rows = conn.execute(
                "SELECT score, code, algorithm_summary, raw_payload "
                "FROM individuals WHERE source_kind='basin_dig'"
            ).fetchall()
        for row in rows:
            if row["score"] is None:
                continue
            try:
                payload = json.loads(str(row["raw_payload"] or "") or "{}")
                basin_id = payload.get("basin_id") or payload.get("basin")
            except Exception:
                continue
            if basin_id not in basin_ids:
                continue
            score = float(row["score"])
            if basin_id not in best or score > best[basin_id]["score"]:
                best[basin_id] = {
                    "id": f"{basin_id}-best",
                    "code": str(row["code"]).strip(),
                    "score": score,
                    "algorithm": str(row["algorithm_summary"] or ""),
                }
    except Exception:
        pass
    return best


def build_climb_list(
    mountains: list[dict[str, Any]],
    *,
    entry_rule: str,
    basin_filter: set[str] | None = None,
    ordered_ids: list[str] | None = None,
) -> list[dict[str, Any]]:
    """把山地图整理成待爬清单：只选山、定顺序、解析入口，不做挖透判断。
    顺序来源：--list 文件 > --basins 点名 > 山地图原顺序。
    --basins / --list 里点名但山地图没有的 id（如 v4 入口 s134 不在 mountains 文件里），
    直接从 DB 加载个体补成单山清单（rep_score = 个体分，entry = 个体）。"""
    keep: set[str] | None = set(ordered_ids) if ordered_ids is not None else None
    best_samples: dict[str, dict[str, Any]] = {}
    if entry_rule == "current_best":
        candidate_ids = {m.get("basin_id") or m.get("rep_id") for m in mountains}
        best_samples = _best_dig_samples(candidate_ids)
    pool: list[dict[str, Any]] = []
    covered: set[str] = set()
    for mountain in mountains:
        basin_id = mountain.get("basin_id") or mountain.get("rep_id")
        if keep is not None and basin_id not in keep:
            continue
        if basin_filter and basin_id not in basin_filter:
            continue
        covered.add(basin_id)
        rep_score = float(mountain.get("rep_score") or 0.0)
        entry: dict[str, Any] | None = None
        if entry_rule == "current_best":
            entry = best_samples.get(basin_id)
        if entry is None:
            try:
                individual = _load_individual(basin_id)
            except RuntimeError:
                continue
            entry = _basin_node(
                basin_id,
                individual["code"],
                float(individual["score"]),
                individual.get("algorithm", ""),
            )
        pool.append(
            {
                "basin_id": basin_id,
                "rep_id": mountain.get("rep_id", basin_id),
                "rep_score": rep_score,
                "summary": mountain.get("summary", ""),
                "entry": entry,
            }
        )
    # 点名但不在山地图的 id：直接从 DB 加载（rep_score = 个体分）
    for extra_id in (basin_filter or set()) | (keep or set()):
        if extra_id in covered or not extra_id:
            continue
        try:
            individual = _load_individual(extra_id)
        except RuntimeError:
            continue
        pool.append(
            {
                "basin_id": extra_id,
                "rep_id": extra_id,
                "rep_score": float(individual["score"]),
                "summary": str(individual.get("algorithm", "") or "")[:200],
                "entry": _basin_node(
                    extra_id,
                    individual["code"],
                    float(individual["score"]),
                    individual.get("algorithm", ""),
                ),
            }
        )
        covered.add(extra_id)
    if ordered_ids is not None:
        order_map = {bid: i for i, bid in enumerate(ordered_ids)}
        pool.sort(key=lambda b: order_map.get(b["basin_id"], len(ordered_ids)))
    return pool


def run_dig(
    *,
    results: dict[str, Any],
    task: Any,
    llm: Any,
    base_description: str,
    evaluability_constraints: str,
    log_dir: Path,
    discovery: Discovery,
    args: argparse.Namespace,
    known_records: list[dict[str, Any]] | None = None,
) -> None:
    mountains = _load_mountains(Path(args.mountains))
    basin_filter = None
    if getattr(args, "basins", ""):
        basin_filter = {item.strip() for item in args.basins.split(",") if item.strip()}
    ordered_ids = None
    if getattr(args, "list", ""):
        data = json.loads(Path(args.list).read_text(encoding="utf-8"))
        ordered_ids = [str(x) for x in data.get("rep_ids", [])]
    entry_rule = getattr(args, "entry_rule", "current_best")
    dig_list = build_climb_list(
        mountains,
        entry_rule=entry_rule,
        basin_filter=basin_filter,
        ordered_ids=ordered_ids,
    )
    # 报告里要区分「山地图总共几座」与「本批清单排了几座」——原先只报前者，
    # 传了 --list 或 --basins 时会与实际开挖数不一致。
    results["meta"]["climb_list_size"] = len(dig_list)
    budget_used = int(results["meta"].get("budget_used", 0))
    # v4：预算无限。--global-budget <= 0（默认 0）语义 = 无限（链爬行v4方案.md §7.3）
    unlimited_budget = int(args.global_budget) <= 0
    budget = {
        "remaining": math.inf if unlimited_budget else max(0, int(args.global_budget) - budget_used)
    }
    results["meta"]["region_radius"] = getattr(args, "region_radius", 0.0)
    # One dedicated revision per dig run: dug samples become DB nodes.
    revision_id = results["meta"].get("dig_revision_id")
    if not revision_id:
        revision_id = f"basin_dig_{time.strftime('%Y%m%d_%H%M%S')}"
        results["meta"]["dig_revision_id"] = revision_id
    _ensure_dig_revision(revision_id)
    counter_ref = {"value": _dig_revision_max_sample_order(revision_id) + 1}

    # 父节点 id 解析映射：code → id。EoH 里父代码是 Function 的规范化 str（可能
    # 与 DB 原始 code 差结尾换行/引号格式），所以：① 全库已知节点按原始 code 收录
    # （无格式差异的简单代码可直接命中）；② 入口额外按规范化 code 收录（保证入口
    # id 一定命中）；③ 本轮新增节点边插边补（profiler 的 code 已是规范化形式）。
    # 其余匹配不到的父节点按文档记 code_hash。全库逐条规范化太慢（22k 条 >1min），
    # 且文档只要求匹配入口 id / 本轮已注册节点 id。
    code_to_id: dict[str, str] = {}
    for rec in known_records or []:
        c = str(rec.get("code", "") or "").strip()
        if c and rec.get("id"):
            code_to_id.setdefault(c, str(rec["id"]))
    try:
        from llm4ad.base import TextFunctionProgramConverter

        _entry_func = TextFunctionProgramConverter.text_to_function(
            str(entry["code"]).strip()
        )
        if _entry_func is not None:
            code_to_id[str(_entry_func).strip()] = str(entry["id"])
    except Exception:
        pass
    # 断点续挖时，重启前已入库的本轮节点也要能按代码匹配（profiler 的 code 是规范化
    # 字符串，DB code 列同样存规范化形式，strip 后与父代码一致）
    try:
        with get_connection() as conn:
            _rows = conn.execute(
                "SELECT id, code FROM individuals WHERE revision_id=? AND code IS NOT NULL",
                (revision_id,),
            ).fetchall()
        for _row in _rows:
            _c = str(_row["code"] or "").strip()
            if _c:
                code_to_id.setdefault(_c, str(_row["id"]))
    except Exception:
        pass

    def _sample_sink(
        segment_records: list[dict[str, Any]],
        segment_index: int,
        basin_id: str,
    ) -> None:
        inserted = _insert_dig_samples(
            segment_records,
            revision_id=revision_id,
            basin_id=basin_id,
            segment_index=segment_index,
            counter_ref=counter_ref,
            code_to_id=code_to_id,
        )
        results["meta"]["dig_sample_counter"] = counter_ref["value"]
        if inserted:
            _log(f"  -> 已注册 {inserted} 个新解到 revision {revision_id}（共 {counter_ref['value']}）")

    for basin in dig_list:
        basin_id = basin["basin_id"]
        state = results["basins"].setdefault(basin_id, {})
        existing_dig = state.get("dig")
        if existing_dig and not existing_dig.get("in_progress", False) and not args.redo:
            _log(f"[跳过] {basin_id[:42]} 已有结论：{str(existing_dig.get('verdict',''))[:50]}")
            continue
        if budget["remaining"] <= 0:
            _log("全局预算耗尽，停止。")
            break
        rep_score = float(basin["rep_score"])
        resume_state = (
            existing_dig.get("resume")
            if existing_dig and existing_dig.get("in_progress", False)
            else None
        )
        entry = basin["entry"]
        _log(
            f"[挖山] {basin_id[:42]} rep={rep_score:.4f} 续挖起点={entry['score']:.4f} "
            f"预算剩余 {budget['remaining']}"
            f"{' [断点续挖]' if resume_state else ''}"
        )

        def _checkpoint(partial: dict[str, Any]) -> None:
            state["dig"] = {
                "basin_id": basin_id,
                "entry_score": float(entry["score"]),
                "original_rep_score": rep_score,
                "in_progress": True,
                "verdict": "进行中",
                "resume": partial,
                "best": partial["best"],
                "delta_vs_rep": partial["delta_vs_rep"],
                "evaluated": partial["evaluated"],
                "dig_revision_id": revision_id,
            }
            results["meta"]["budget_used"] = (
                partial["evaluated"]
                if unlimited_budget
                else int(args.global_budget) - budget["remaining"]
            )
            _save_results(results, Path(args.results_path))

        dig = _dig_mountain(
            basin=basin,
            entry_node=entry,
            original_rep_score=rep_score,
            task=task,
            llm=llm,
            base_description=base_description,
            log_dir=log_dir,
            samples_per_segment=args.samples_per_segment,
            death_window=args.death_window,
            max_window=args.max_window,
            discovery=discovery,
            budget=budget,
            num_samplers=args.num_samplers,
            num_evaluators=args.num_evaluators,
            evaluability_constraints=evaluability_constraints,
            sample_sink=_sample_sink,
            resume_state=resume_state,
            checkpoint=_checkpoint,
            region_radius=getattr(args, "region_radius", 0.0),
            known_records=known_records,
        )
        state["dig"] = dig
        state["final_best"] = dig["best"]
        state["final_delta_vs_rep"] = dig["delta_vs_rep"]
        enqueued_codes = {nb.get("code") for nb in results["discovered_basins"]}
        for new_basin in dig.get("discovered", []):
            if new_basin.get("code") in enqueued_codes:
                continue
            new_id = f"new-{len(results['discovered_basins']) + 1}"
            new_entry = {
                "basin_id": new_id,
                "rep_id": new_basin.get("id") or "",
                "rep_score": float(new_basin["score"]),
                "code": new_basin.get("code", ""),
                "size": 1,
                "unique": 1,
                "summary": new_basin.get("summary", ""),
                "origin": "discovered",
                "discovered_by": new_basin.get("discovered_by"),
            }
            results["discovered_basins"].append(new_entry)
            results["queue"].append(new_entry)
            enqueued_codes.add(new_basin.get("code", ""))
            _log(f"  -> 发现新山 {new_id} score={new_basin['score']:.4f}")
        results["meta"]["budget_used"] = (
            dig["evaluated"] if unlimited_budget else int(args.global_budget) - budget["remaining"]
        )
        _save_results(results, Path(args.results_path))
        if not args.no_discovery:
            _sync_vectors_only()
        _log(
            f"[挖山] {basin_id[:42]} 完成 best={dig['best']:.4f} "
            f"delta_vs_rep={dig['delta_vs_rep']:.4f} evaluated={dig['evaluated']} "
            f"verdict={dig['verdict'][:60]}"
        )
    unfinished = [
        basin["basin_id"]
        for basin in dig_list
        if not (results["basins"].get(basin["basin_id"]) or {}).get("dig")
    ]
    if unfinished:
        _log(f"还有 {len(unfinished)} 座山未挖完（预算耗尽），revision 保持 running。")
    else:
        _complete_dig_revision(revision_id)
        _log(f"清单全部挖完，revision {revision_id} 已标记 completed。")


def write_report(results: dict[str, Any], args: argparse.Namespace) -> None:
    mountains = _load_mountains(Path(args.mountains))
    entry_rule = getattr(args, "entry_rule", "current_best")
    basin_filter = None
    if getattr(args, "basins", ""):
        basin_filter = {item.strip() for item in args.basins.split(",") if item.strip()}
    ordered_ids = None
    if getattr(args, "list", ""):
        data = json.loads(Path(args.list).read_text(encoding="utf-8"))
        ordered_ids = [str(x) for x in data.get("rep_ids", [])]
    dig_list = build_climb_list(
        mountains,
        entry_rule=entry_rule,
        basin_filter=basin_filter,
        ordered_ids=ordered_ids,
    )
    lines: list[str] = []
    lines.append("# 盆地挖掘报告（v2：判死换山）")
    lines.append("")
    lines.append(f"生成时间：{time.strftime('%Y-%m-%d %H:%M:%S')}")
    lines.append("")
    _queued = results["meta"].get("climb_list_size")
    lines.append(
        f"- 山地图共 {results['meta']['initial_mountains']} 座（语义距离 {MOUNTAIN_DIST}）"
        f"；本批爬山清单 {_queued if _queued is not None else '—'} 座"
    )
    lines.append(
        f"- 判死窗口：初始 {DEFAULT_DEATH_WINDOW} / 上限 {DEFAULT_MAX_WINDOW}（评测样本计）"
    )
    lines.append("")
    lines.append("## 一、判死挖山结果（一座座挖到判死再换）")
    lines.append("")
    lines.append("| 山 | rep | 续挖起点 | 最终 best | vs rep | 评测数 | verdict |")
    lines.append("|---|---|---|---|---|---|---|")
    for basin_id, state in results["basins"].items():
        dig = state.get("dig")
        if not dig:
            continue
        lines.append(
            "| %s | %.4f | %.4f | %.4f | %.4f | %d | %s |"
            % (
                basin_id[:36],
                dig.get("original_rep_score", 0),
                dig.get("entry_score", 0),
                dig["best"],
                dig.get("delta_vs_rep", 0),
                dig.get("evaluated", 0),
                dig.get("verdict", "")[:70],
            )
        )
    lines.append("")
    lines.append("## 二、预算使用与未挖完清单")
    lines.append("")
    total_evaluated = sum(
        int((s.get("dig") or {}).get("evaluated") or 0)
        for s in results["basins"].values()
    )
    budget_given = int(args.global_budget) if args.global_budget else "不限"
    lines.append(f"- 全局预算：{budget_given} 评测样本；已使用：{total_evaluated}。")
    unfinished: list[str] = []
    unfinished_reasons: list[str] = []
    for basin in dig_list:
        basin_id = basin["basin_id"]
        state = results["basins"].get(basin_id) or {}
        dig = state.get("dig")
        if dig is None:
            unfinished.append(basin_id)
            unfinished_reasons.append("未开始（预算耗尽前未轮到）")
        elif "预算耗尽" in str(dig.get("verdict") or ""):
            unfinished.append(basin_id)
            unfinished_reasons.append(f"挖到一半预算耗尽（已用 {dig.get('evaluated', 0)}）")
    if unfinished:
        lines.append("")
        lines.append("| 未挖完的山 | 原因 |")
        lines.append("|---|---|")
        for basin_id, reason in zip(unfinished, unfinished_reasons, strict=False):
            lines.append("| %s | %s |" % (basin_id[:40], reason))
    else:
        lines.append("清单内全部山已判死或给出结论。")
    lines.append("")
    lines.append("## 三、动态发现的新山")
    lines.append("")
    if results["discovered_basins"]:
        lines.append("| 新山 | score | 来源 |")
        lines.append("|---|---|---|")
        for nb in results["discovered_basins"]:
            lines.append("| %s | %.4f | %s |" % (nb["basin_id"], nb["rep_score"], nb.get("discovered_by", "")))
    else:
        lines.append("（暂无）")
    lines.append("")
    lines.append("## 四、链爬行 v4（峰值导向）摘要")
    lines.append("")
    any_region = False
    for basin_id, state in results["basins"].items():
        dig = state.get("dig") or {}
        region = dig.get("region") or {}
        peak_pool = region.get("peak_pool") or []
        switches = dig.get("mountain_switches") or region.get("mountain_switches") or []
        if not peak_pool:
            continue
        any_region = True
        lines.append(f"### {basin_id[:36]}（入口 {dig.get('entry_score', 0):.4f} → best {dig.get('best', 0):.4f}，评测 {dig.get('evaluated', 0)}）")
        lines.append("")
        lines.append(f"- 终止 verdict：{dig.get('verdict', '')}")
        lines.append(f"- 换山 {len(switches)} 次")
        lines.append("")
        lines.append("| 峰值 | 分 | 进行时R | 爬到的最高分 | verdict |")
        lines.append("|---|---|---|---|---|")
        for p in sorted(peak_pool, key=lambda x: -float(x.get("score", 0))):
            r = p.get("r_during")
            r_txt = "∞" if r is None else f"{r:.4f}"
            mr = p.get("max_reached")
            mr_txt = f"{float(mr):.6f}" if mr is not None else "—"
            lines.append(
                "| %s | %.6f | %s | %s | %s |"
                % (str(p.get("code", ""))[:40], float(p.get("score", 0)),
                   r_txt, mr_txt, p.get("verdict", ""))
            )
        if switches:
            lines.append("")
            lines.append("| # | 原因 | 块 | 从 | 到 |")
            lines.append("|---|---|---|---|---|")
            for i, sw in enumerate(switches, 1):
                fr = sw.get("from_peak") or {}
                to = sw.get("to_peak") or {}
                lines.append(
                    "| %d | %s | %d | %.6f(%s) | %.6f(%s) |"
                    % (i, sw.get("reason", ""), int(sw.get("chunk", 0)),
                       float(fr.get("score", 0) or 0), str(fr.get("code", ""))[:20],
                       float(to.get("score", 0) or 0), str(to.get("code", ""))[:20])
                )
        lines.append("")
    if not any_region:
        lines.append("（本批次无区域链爬行数据）")
    lines.append("")
    lines.append("原始数据：`basin_results.json`。")
    report_path = Path(args.report_path)
    report_path.parent.mkdir(parents=True, exist_ok=True)
    report_path.write_text("\n".join(lines), encoding="utf-8")
    _log(f"报告已写入 {report_path}")


def main() -> None:
    parser = argparse.ArgumentParser(description="爬山器：按清单逐座爬山、判死换山")
    parser.add_argument("--phase", choices=("dig", "finalize"), default="dig")
    parser.add_argument("--smoke", action="store_true")
    parser.add_argument(
        "--no-discovery",
        action="store_true",
        help="跳过新山发现（不需要嵌入模型，启动快）；本批次只重爬已知山",
    )
    parser.add_argument("--mountains", type=str, default=str(DEFAULT_MOUNTAINS))
    parser.add_argument("--results-path", type=str, default=str(DEFAULT_RESULTS))
    parser.add_argument("--report-path", type=str, default=str(DEFAULT_REPORT))
    parser.add_argument("--samples-per-segment", type=int, default=30)
    parser.add_argument("--num-samplers", type=int, default=8)
    parser.add_argument("--num-evaluators", type=int, default=8)
    parser.add_argument(
        "--entry-rule",
        choices=("current_best", "original_rep"),
        default="current_best",
        help="current_best=从已挖最高分解续爬；original_rep=从山的原始入口爬",
    )
    parser.add_argument("--list", type=str, default="",
                        help="有序爬山清单 JSON（含 rep_ids 数组）；不填则爬 --mountains 里全部山")
    parser.add_argument("--basins", type=str, default="", help="只爬指定山（rep_id 逗号分隔）")
    parser.add_argument("--redo", action="store_true", default=False,
                        help="忽略已有结论，从入口重新爬（否则已判死的山跳过）")
    parser.add_argument("--death-window", type=int, default=DEFAULT_DEATH_WINDOW)
    parser.add_argument("--max-window", type=int, default=DEFAULT_MAX_WINDOW)
    parser.add_argument(
        "--eval-timeout",
        type=int,
        default=60,
        help="评测超时秒数（防失控安全网；时间预算型算法可调大，如 60/120；不写进提示词）",
    )
    parser.add_argument(
        "--preference",
        type=str,
        default="",
        help="偏好区提示词（默认空；注入后以 [PREFERENCE] 块拼进提示词，指导生成偏好）",
    )
    parser.add_argument(
        "--global-budget",
        type=int,
        default=0,
        help="全局评测样本预算上限（0=直到清单挖完）",
    )
    parser.add_argument(
        "--region-radius",
        type=float,
        default=0.0,
        help="区域约束半径（链爬行实验）：>0 时只有距当前锚点 < radius 的节点算有效改进/进种群，"
             "区域内最高分成为新锚点（区域沿 NBN 链爬）；0=关闭（原始行为）",
    )
    args = parser.parse_args()

    global DIGGER_PREFERENCE
    if args.preference:
        DIGGER_PREFERENCE = args.preference

    # --smoke：小步模式，用于快速验证「LLM 生成 → 评价 → 入库」整条链路是否通。
    # 不指定预算时默认只花 12 次评价，避免误用时消耗大量额度。
    if args.smoke:
        global CHUNK_MAX_SAMPLES, CHUNK_GENERATIONS
        CHUNK_MAX_SAMPLES = min(CHUNK_MAX_SAMPLES, 6)
        CHUNK_GENERATIONS = min(CHUNK_GENERATIONS, 2)
        if int(args.global_budget) <= 0:
            args.global_budget = 12
        print(
            f"[smoke] 小步模式：每块 {CHUNK_MAX_SAMPLES} 样本 / {CHUNK_GENERATIONS} 代，"
            f"评价预算 {args.global_budget}"
        )

    mountains = _load_mountains(Path(args.mountains))
    if not mountains:
        raise SystemExit(f"山清单为空：{args.mountains}")

    if args.no_discovery:
        records: list[dict[str, Any]] = []
        vectors = np.zeros((0, 256), dtype=np.float32)
        discovery = None
    else:
        _prepare_working_copies()
        records, vectors = _load_known_vectors()
        discovery = Discovery(records, vectors)
    # 冒烟是「一次性验证」，不续跑：否则上一次的 budget_used 会留在检查点里，
    # 第二次运行会因 "预算耗尽" 立刻退出，看起来像没生效。
    if args.smoke:
        if Path(args.results_path).exists():
            print(f"[smoke] 冒烟不续跑：忽略已有检查点 {args.results_path}，本次从零开始")
        results = None
    else:
        results = _load_results(Path(args.results_path))
    if results is None:
        results = {"meta": {}, "basins": {}, "discovered_basins": [], "queue": []}
    results.setdefault("discovered_basins", [])
    results.setdefault("queue", [])
    results["meta"].setdefault("initial_mountains", len(mountains))
    results["meta"].setdefault("known_count", len(records))

    if args.phase == "finalize":
        write_report(results, args)
        return

    task = load_circle_packing_evaluation()(timeout_seconds=args.eval_timeout)
    llm = _build_llm()
    base_description = DIGGER_BASE_TASK
    log_dir = Path(tempfile.mkdtemp(prefix="climber_"))
    run_dig(
        results=results,
        task=task,
        llm=llm,
        base_description=base_description,
        evaluability_constraints=DIGGER_EVALUABILITY,
        log_dir=log_dir,
        discovery=discovery,
        args=args,
        known_records=records if not args.no_discovery else None,
    )
    if not args.no_discovery:
        _sync_working_copies()
    results["generated_at"] = time.strftime("%Y-%m-%d %H:%M:%S")
    _save_results(results, Path(args.results_path))
    write_report(results, args)
    _log("判死挖山阶段完成。")


if __name__ == "__main__":
    main()
