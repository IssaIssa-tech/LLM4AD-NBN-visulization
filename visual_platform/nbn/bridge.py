from __future__ import annotations

import hashlib
import importlib
import importlib.util
import logging
import math
import os
import re
import sqlite3
import sys
from dataclasses import dataclass
from datetime import datetime
from functools import lru_cache
from pathlib import Path
from typing import Any, Callable

import numpy as np

from visual_platform.services.graph_sample_service import clean_sample_data

BASE_DIR = Path(__file__).resolve().parent.parent  # visual_platform/（本级是 nbn/）
# 仓库根 = 包含 visual_platform/ 与 llm4ad/ 的那一层
WORKSPACE_DIR = BASE_DIR.parent
DEFAULT_DISTANCE_METRIC = "codet5p_embedding_cosine"
CODET5_MODEL_REPO = "Salesforce/codet5p-110m-embedding"
LOCAL_CODET5_MODEL_DIR = BASE_DIR / "models" / "codet5p-110m-embedding"
logger = logging.getLogger(__name__)
ProgressCallback = Callable[[dict[str, Any]], None]

# Layout spread controls (tunable via environment variables)
GRAPH_SPREAD_XY = max(50.0, float(os.getenv("VISUAL_PLATFORM_GRAPH_SPREAD_XY", "300") or "300"))
GRAPH_SPREAD_Z = max(50.0, float(os.getenv("VISUAL_PLATFORM_GRAPH_SPREAD_Z", "200") or "200"))

# Minimum normalized radius in the cone-tree layout so zero-distance twins
# stay visible next to their parent instead of overlapping it exactly.
CONE_MIN_RADIUS = 0.02

# Z-axis curve: blends linear with power so high-score solutions get more
# vertical separation (improvements are harder near the top, so scores cluster
# there and a purely linear map makes them look cramped).
#   z_norm = (1-α)·t + α·t^p,  t = (score-floor)/range ∈ [0,1]
# α=0 → linear,  α=1 → pure power.  p>1 stretches the top.
Z_CURVE_ALPHA = max(0.0, min(1.0, float(os.getenv("VISUAL_PLATFORM_Z_CURVE_ALPHA", "0.6") or "0.6")))
Z_CURVE_POWER = max(1.0, float(os.getenv("VISUAL_PLATFORM_Z_CURVE_POWER", "3.0") or "3.0"))


def _sample_source(sample: dict[str, Any]) -> str:
    function_text = str(sample.get("function", "") or "").strip()
    if function_text:
        return function_text
    program_text = str(sample.get("program", "") or "").strip()
    if program_text:
        return program_text
    return str(sample.get("algorithm", "") or "").strip()


def _function_preview(sample: dict[str, Any]) -> str:
    return _sample_source(sample).strip()


def _program_preview(sample: dict[str, Any]) -> str:
    """Full executable program (preface + all helper functions + entry).

    Falls back to the entry-function source when a distinct program was not
    stored, so the frontend 'full program' toggle always has content.
    """
    program_text = str(sample.get("program", "") or "").strip()
    if program_text:
        return program_text
    return _function_preview(sample)


def _normalize_distance_metric(distance_metric: str | None) -> str:
    metric = str(distance_metric or "").strip().lower()
    if not metric:
        return DEFAULT_DISTANCE_METRIC
    aliases = {
        "auto": DEFAULT_DISTANCE_METRIC,
        "codet5": "codet5p_embedding_cosine",
        "codet5p": "codet5p_embedding_cosine",
        "embedding": "codet5p_embedding_cosine",
        "embedding_cosine": "codet5p_embedding_cosine",
        "code_embedding": "codet5p_embedding_cosine",
    }
    normalized = aliases.get(metric, metric)
    return normalized if normalized == DEFAULT_DISTANCE_METRIC else DEFAULT_DISTANCE_METRIC


def get_distance_metric_name(distance_metric: str | None = None) -> str:
    return _normalize_distance_metric(distance_metric)


def _codet5_checkpoint_candidates() -> list[str]:
    local_candidates: list[str] = []
    remote_candidates: list[str] = []
    env_path = str(os.getenv("VISUAL_PLATFORM_CODET5_DIR", "") or "").strip()
    if env_path:
        local_candidates.append(env_path)
    if LOCAL_CODET5_MODEL_DIR.exists():
        local_candidates.append(str(LOCAL_CODET5_MODEL_DIR))
    if not local_candidates:
        remote_candidates.append(CODET5_MODEL_REPO)

    unique: list[str] = []
    seen: set[str] = set()
    for candidate in [*local_candidates, *remote_candidates]:
        key = str(candidate).strip()
        if key and key not in seen:
            unique.append(key)
            seen.add(key)
    return unique


def _load_transformers_auto_classes() -> tuple[Any, Any]:
    os.environ.setdefault("USE_TORCH", "1")
    os.environ.setdefault("USE_TF", "0")
    try:
        from transformers import AutoModel, AutoTokenizer

        return AutoModel, AutoTokenizer
    except Exception as root_error:
        try:
            from transformers.models.auto import AutoTokenizer
            from transformers.models.auto.modeling_auto import AutoModel

            return AutoModel, AutoTokenizer
        except Exception as nested_error:
            raise RuntimeError(
                "Unable to import transformers AutoModel/AutoTokenizer. "
                f"root import failed with {type(root_error).__name__}: {root_error}; "
                f"module import failed with {type(nested_error).__name__}: {nested_error}"
            ) from nested_error


@lru_cache(maxsize=1)
def _load_codet5_embedding_model(progress_callback: ProgressCallback | None = None) -> tuple[Any, Any, Any]:
    import torch

    AutoModel, AutoTokenizer = _load_transformers_auto_classes()

    device = "cuda" if torch.cuda.is_available() else "cpu"
    if progress_callback is not None:
        progress_callback(
            {
                "stage": "loading_model",
                "stageLabel": "加载 CodeT5 模型",
                "message": f"Loading CodeT5 embedding model on {device}.",
            }
        )
    errors: list[str] = []
    for checkpoint in _codet5_checkpoint_candidates():
        load_kwargs = {"trust_remote_code": True}
        if Path(checkpoint).exists():
            load_kwargs["local_files_only"] = True
        try:
            # 上游 Salesforce/codet5p-110m-embedding 的 config.json 现在已不再包含
            # is_decoder，而它自带的建模代码会读这个属性，导致
            #   AttributeError: 'CodeT5pEmbeddingConfig' object has no attribute 'is_decoder'
            # 这里显式补上（不修改上游文件），使模型可直接加载。
            config = None
            try:
                from transformers import AutoConfig

                config = AutoConfig.from_pretrained(checkpoint, **load_kwargs)
                if not hasattr(config, "is_decoder"):
                    config.is_decoder = False
            except Exception:
                config = None
            tokenizer = AutoTokenizer.from_pretrained(checkpoint, **load_kwargs)
            model_kwargs = dict(load_kwargs)
            if config is not None:
                model_kwargs["config"] = config
            model = AutoModel.from_pretrained(checkpoint, **model_kwargs).to(device)
            model.eval()
            if progress_callback is not None:
                progress_callback(
                    {
                        "stage": "loading_model",
                        "stageLabel": "加载 CodeT5 模型",
                        "message": f"Loaded CodeT5 embedding model from {checkpoint} on {device}.",
                    }
                )
            return tokenizer, model, torch.device(device)
        except Exception as error:
            errors.append(f"{checkpoint}: {type(error).__name__}: {error}")
    raise RuntimeError("Unable to load CodeT5 embedding model. " + " | ".join(errors))


@lru_cache(maxsize=1)
def _load_codet5_slow_tokenizer() -> Any:
    _, AutoTokenizer = _load_transformers_auto_classes()

    errors: list[str] = []
    for checkpoint in _codet5_checkpoint_candidates():
        load_kwargs = {"trust_remote_code": True, "use_fast": False}
        if Path(checkpoint).exists():
            load_kwargs["local_files_only"] = True
        try:
            return AutoTokenizer.from_pretrained(checkpoint, **load_kwargs)
        except Exception as error:
            errors.append(f"{checkpoint}: {type(error).__name__}: {error}")
    raise RuntimeError("Unable to load slow CodeT5 tokenizer. " + " | ".join(errors))


# Env override: point the embedding cache at a fast local path (e.g. native
# ext4) to avoid flaky 9p/drvfs I/O on /mnt/d under heavy load.
CODET5_EMBEDDING_DB_FILE = Path(
    os.environ.get(
        "VISUAL_PLATFORM_CODET5_CACHE",
        str(BASE_DIR / ".codet5_embeddings_cache.sqlite3"),
    )
)
CODET5_BATCH_SIZE = max(4, int(os.getenv("VISUAL_PLATFORM_CODET5_BATCH_SIZE", "24") or "24"))
CODET5_MAX_LENGTH = max(128, int(os.getenv("VISUAL_PLATFORM_CODET5_MAX_LENGTH", "1024") or "1024"))
NBN_QUERY_BLOCK_SIZE = max(64, int(os.getenv("VISUAL_PLATFORM_NBN_QUERY_BLOCK_SIZE", "256") or "256"))
NBN_NUM_THREADS = max(1, int(os.getenv("VISUAL_PLATFORM_NBN_NUM_THREADS", "4") or "4"))


def _embedding_db_connect() -> sqlite3.Connection:
    connection = sqlite3.connect(str(CODET5_EMBEDDING_DB_FILE))
    connection.execute(
        """
        CREATE TABLE IF NOT EXISTS embeddings (
            code_hash TEXT PRIMARY KEY,
            dim INTEGER NOT NULL,
            vector BLOB NOT NULL,
            updated_at TEXT NOT NULL
        )
        """
    )
    return connection


def _load_cached_embeddings(code_hashes: list[str]) -> dict[str, np.ndarray]:
    if not code_hashes:
        return {}
    connection = _embedding_db_connect()
    try:
        rows: list[tuple[str, int, bytes]] = []
        chunk_size = 900
        for start in range(0, len(code_hashes), chunk_size):
            batch = code_hashes[start : start + chunk_size]
            placeholders = ",".join("?" for _ in batch)
            rows.extend(
                connection.execute(
                    f"SELECT code_hash, dim, vector FROM embeddings WHERE code_hash IN ({placeholders})",
                    batch,
                ).fetchall()
            )
    finally:
        connection.close()

    cached: dict[str, np.ndarray] = {}
    for code_hash, dim, blob in rows:
        vector = np.frombuffer(blob, dtype=np.float32, count=int(dim)).copy()
        cached[str(code_hash)] = vector
    return cached


def count_cached_embedding_hashes(code_hashes: list[str]) -> int:
    if not code_hashes:
        return 0
    unique_hashes = list(dict.fromkeys(code_hashes))
    connection = _embedding_db_connect()
    try:
        matched_hashes: set[str] = set()
        chunk_size = 900
        for start in range(0, len(unique_hashes), chunk_size):
            batch = unique_hashes[start : start + chunk_size]
            placeholders = ",".join("?" for _ in batch)
            rows = connection.execute(
                f"SELECT code_hash FROM embeddings WHERE code_hash IN ({placeholders})",
                batch,
            ).fetchall()
            matched_hashes.update(str(row[0]) for row in rows)
    finally:
        connection.close()
    return sum(1 for code_hash in code_hashes if code_hash in matched_hashes)


def embedding_cache_entry_count() -> int:
    connection = _embedding_db_connect()
    try:
        row = connection.execute("SELECT COUNT(*) FROM embeddings").fetchone()
        return int(row[0]) if row else 0
    finally:
        connection.close()


def _store_cached_embeddings(vectors_by_hash: dict[str, np.ndarray]) -> None:
    if not vectors_by_hash:
        return
    connection = _embedding_db_connect()
    try:
        timestamp = datetime.now().isoformat(timespec="seconds")
        rows = [
            (
                code_hash,
                int(vector.shape[0]),
                sqlite3.Binary(np.asarray(vector, dtype=np.float32).tobytes()),
                timestamp,
            )
            for code_hash, vector in vectors_by_hash.items()
        ]
        connection.executemany(
            "INSERT OR REPLACE INTO embeddings (code_hash, dim, vector, updated_at) VALUES (?, ?, ?, ?)",
            rows,
        )
        connection.commit()
    finally:
        connection.close()


def _batch_embed_missing_codes(
    missing_items: list[tuple[str, str]],
    *,
    progress_callback: ProgressCallback | None = None,
) -> dict[str, np.ndarray]:
    if not missing_items:
        return {}

    tokenizer, model, device = _load_codet5_embedding_model(progress_callback=progress_callback)
    import torch

    vectors_by_hash: dict[str, np.ndarray] = {}
    total_items = len(missing_items)
    processed_items = 0
    for start in range(0, len(missing_items), CODET5_BATCH_SIZE):
        batch = missing_items[start : start + CODET5_BATCH_SIZE]
        batch_hashes = [item[0] for item in batch]
        batch_vectors_by_hash: dict[str, np.ndarray] = {}
        batch_texts = [item[1] for item in batch]
        if progress_callback is not None:
            progress_callback(
                {
                    "stage": "embedding",
                    "stageLabel": "计算 CodeT5 Embedding",
                    "current": processed_items,
                    "total": total_items,
                    "message": (
                        f"Embedding batch {start // CODET5_BATCH_SIZE + 1}/"
                        f"{math.ceil(total_items / CODET5_BATCH_SIZE)} on {device}."
                    ),
                }
            )
        inputs = tokenizer(
            batch_texts,
            return_tensors="pt",
            padding=True,
            truncation=True,
            max_length=CODET5_MAX_LENGTH,
        ).to(device)
        with torch.no_grad():
            outputs = model(**inputs)
            hidden = outputs.last_hidden_state if hasattr(outputs, "last_hidden_state") else outputs[0]
            if hidden.ndim == 3:
                mask = inputs["attention_mask"].unsqueeze(-1)
                pooled = (hidden * mask).sum(dim=1) / mask.sum(dim=1).clamp(min=1)
            else:
                pooled = hidden
            if pooled.ndim == 1:
                pooled = pooled.unsqueeze(0)
            pooled = torch.nn.functional.normalize(pooled, p=2, dim=1)
            batch_vectors = pooled.detach().cpu().numpy().astype(np.float32)

        if batch_vectors.shape[0] != len(batch_hashes):
            slow_tokenizer = _load_codet5_slow_tokenizer()
            for code_hash, code_text in batch:
                single_inputs = slow_tokenizer(
                    code_text,
                    return_tensors="pt",
                    truncation=True,
                    max_length=CODET5_MAX_LENGTH,
                )
                single_inputs = {key: value.to(device) for key, value in single_inputs.items()}
                with torch.no_grad():
                    single_outputs = model(**single_inputs)
                    single_hidden = single_outputs.last_hidden_state if hasattr(single_outputs, "last_hidden_state") else single_outputs[0]
                    if single_hidden.ndim == 3:
                        single_mask = single_inputs["attention_mask"].unsqueeze(-1)
                        single_pooled = (single_hidden * single_mask).sum(dim=1) / single_mask.sum(dim=1).clamp(min=1)
                    else:
                        single_pooled = single_hidden
                    if single_pooled.ndim == 1:
                        single_pooled = single_pooled.unsqueeze(0)
                    single_pooled = torch.nn.functional.normalize(single_pooled, p=2, dim=1)
                    batch_vectors_by_hash[code_hash] = single_pooled.detach().cpu().numpy().astype(np.float32).reshape(-1)
            _store_cached_embeddings(batch_vectors_by_hash)
            vectors_by_hash.update(batch_vectors_by_hash)
            processed_items += len(batch)
            if progress_callback is not None:
                progress_callback(
                    {
                        "stage": "embedding",
                        "stageLabel": "计算 CodeT5 Embedding",
                        "current": processed_items,
                        "total": total_items,
                        "message": f"Embedded {processed_items}/{total_items} new samples.",
                    }
                )
            continue

        for code_hash, vector in zip(batch_hashes, batch_vectors, strict=False):
            batch_vectors_by_hash[code_hash] = np.asarray(vector, dtype=np.float32).reshape(-1)
        _store_cached_embeddings(batch_vectors_by_hash)
        vectors_by_hash.update(batch_vectors_by_hash)
        processed_items += len(batch)
        if progress_callback is not None:
            progress_callback(
                {
                    "stage": "embedding",
                    "stageLabel": "计算 CodeT5 Embedding",
                    "current": processed_items,
                    "total": total_items,
                    "message": f"Embedded {processed_items}/{total_items} new samples.",
                }
            )
    return vectors_by_hash


def get_codet5_embedding_matrix(
    samples: list[dict[str, Any]],
    *,
    progress_callback: ProgressCallback | None = None,
) -> tuple[np.ndarray, dict[str, int]]:
    sources = [_sample_source(sample) for sample in samples]
    code_hashes = [hashlib.sha256(source.encode("utf-8")).hexdigest() for source in sources]
    if progress_callback is not None:
        progress_callback(
            {
                "stage": "cache_lookup",
                "stageLabel": "检查 Embedding 缓存",
                "current": 0,
                "total": len(samples),
                "message": f"Checking embedding cache for {len(samples)} samples.",
            }
        )
    cached_vectors = _load_cached_embeddings(code_hashes)
    missing_items = [
        (code_hash, source)
        for code_hash, source in zip(code_hashes, sources, strict=False)
        if code_hash not in cached_vectors
    ]
    if progress_callback is not None:
        progress_callback(
            {
                "stage": "cache_lookup",
                "stageLabel": "检查 Embedding 缓存",
                "current": len(samples) - len(missing_items),
                "total": len(samples),
                "message": (
                    f"Cache hit {len(samples) - len(missing_items)}/{len(samples)} samples; "
                    f"need to embed {len(missing_items)} samples."
                ),
            }
        )
    if missing_items:
        cached_vectors.update(
            _batch_embed_missing_codes(
                missing_items,
                progress_callback=progress_callback,
            )
        )

    embeddings = np.vstack([
        np.asarray(cached_vectors[code_hash], dtype=np.float32)
        for code_hash in code_hashes
    ])
    return embeddings, {
        "sampleCount": len(samples),
        "cachedEmbeddingCount": len(samples) - len(missing_items),
        "newEmbeddingCount": len(missing_items),
    }


def sample_code_hashes(samples: list[dict[str, Any]]) -> list[str]:
    return [hashlib.sha256(_sample_source(sample).encode("utf-8")).hexdigest() for sample in samples]


def _codet5_distance_matrix(samples: list[dict[str, Any]]) -> list[list[float]]:
    embeddings, _ = get_codet5_embedding_matrix(samples)
    similarity = np.clip(np.dot(embeddings, embeddings.T), -1.0, 1.0)
    distance = 1.0 - similarity
    np.fill_diagonal(distance, 0.0)
    return distance.tolist()


def _codet5_distance_matrix_numpy(embeddings: np.ndarray) -> np.ndarray:
    similarity = np.clip(np.dot(embeddings, embeddings.T), -1.0, 1.0)
    distance = np.asarray(1.0 - similarity, dtype=np.float32)
    np.fill_diagonal(distance, 0.0)
    return distance


def build_distance_matrix(samples: list[dict[str, Any]]) -> tuple[list[list[float]], str, str | None]:
    requested_metric = get_distance_metric_name()
    return build_distance_matrix_with_metric(samples, requested_metric)


def build_distance_matrix_with_metric(samples: list[dict[str, Any]], distance_metric: str | None) -> tuple[list[list[float]], str, str | None]:
    requested_metric = get_distance_metric_name(distance_metric)
    return _codet5_distance_matrix(samples), requested_metric, None


def _compute_robust_score_bounds(samples: list[dict[str, Any]]) -> tuple[float, float]:
    """Compute score bounds for sanitization: robust floor, exact ceiling.

    Garbage scores (None, NaN, inf, |score|>1e6) are excluded so they cannot
    distort the normalization range used by OFEC's cone-tree layout.

    Floor uses the 1st percentile so legit-but-extreme low scores cannot crush
    the Z scale. Ceiling is the TRUE maximum of the surviving scores: clamping
    the top (old 99th-percentile behaviour) collapsed the best ~1% into one
    tied fitness value, so the NBN root was picked at random inside that club
    instead of being the actual champion, and their Z heights were flattened.
    """
    finite_scores: list[float] = []
    for sample in samples:
        raw = sample.get("score")
        if raw is None:
            continue
        try:
            value = float(raw)
        except (TypeError, ValueError):
            continue
        if math.isfinite(value) and abs(value) <= 1e6:
            finite_scores.append(value)
    if not finite_scores:
        return -1.0, 1.0
    if len(finite_scores) <= 4:
        return min(finite_scores), max(finite_scores)
    arr = np.asarray(finite_scores, dtype=np.float64)
    floor = float(np.percentile(arr, 1.0))
    ceiling = max(finite_scores)
    if ceiling <= floor:
        return min(finite_scores), max(finite_scores)
    return floor, ceiling


def _sanitize_score_value(
    raw_score: Any,
    score_floor: float,
    score_ceiling: float,
) -> float:
    """Sanitize a single score for NBN computation.

    None / NaN / -inf  ->  score_floor  (treated as worst)
    +inf               ->  score_ceiling (treated as best)
    Extreme outliers    ->  clamped to [floor, ceiling]
    """
    if raw_score is None:
        return score_floor
    try:
        value = float(raw_score)
    except (TypeError, ValueError):
        return score_floor
    if not math.isfinite(value):
        return score_floor if value < 0 else score_ceiling
    return max(score_floor, min(score_ceiling, value))


def _score_to_z(sanitized_score: float, score_floor: float, score_range: float) -> float:
    """Map a sanitized score to a Z coordinate with non-linear expansion.

    Blends linear with power:  z_norm = (1-α)·t + α·t^p
    where t = (score - floor) / range  ∈ [0, 1].

    With α > 0 and p > 1 the derivative grows toward t = 1, so
    high-score solutions — whose score gaps are naturally tiny —
    get visibly more vertical separation without crushing the bottom.
    """
    t = (sanitized_score - score_floor) / score_range if score_range > 1e-12 else 0.0
    t = max(0.0, min(1.0, t))
    z_norm = (1.0 - Z_CURVE_ALPHA) * t + Z_CURVE_ALPHA * (t ** Z_CURVE_POWER)
    return z_norm * GRAPH_SPREAD_Z


def _score_array(samples: list[dict[str, Any]]) -> np.ndarray:
    floor, ceiling = _compute_robust_score_bounds(samples)
    return np.asarray(
        [_sanitize_score_value(sample.get("score"), floor, ceiling) for sample in samples],
        dtype=np.float32,
    )


def _project_embeddings_to_3d(embeddings: np.ndarray) -> tuple[np.ndarray, dict[str, Any]]:
    if embeddings.size == 0:
        return np.zeros((0, 3), dtype=np.float32), {"layoutMode": "empty"}

    if embeddings.shape[0] == 1:
        return np.zeros((1, 3), dtype=np.float32), {"layoutMode": "single_point"}

    centered = embeddings - embeddings.mean(axis=0, keepdims=True)
    if centered.shape[1] <= 3:
        coords = np.zeros((centered.shape[0], 3), dtype=np.float32)
        coords[:, : centered.shape[1]] = centered
    else:
        covariance = np.dot(centered.T, centered) / max(centered.shape[0] - 1, 1)
        eigenvalues, eigenvectors = np.linalg.eigh(covariance)
        component_count = min(3, eigenvectors.shape[1])
        basis = eigenvectors[:, -component_count:]
        coords = np.zeros((centered.shape[0], 3), dtype=np.float32)
        coords[:, :component_count] = np.dot(centered, basis).astype(np.float32)

    for axis in range(3):
        axis_values = coords[:, axis]
        scale = np.percentile(np.abs(axis_values), 99.0) if axis_values.size else 1.0
        if not math.isfinite(scale) or scale <= 1e-6:
            scale = 1.0
        coords[:, axis] = axis_values * (GRAPH_SPREAD_XY / scale)
    return coords, {"layoutMode": "pca3"}


def _compute_exact_nbn(embeddings: np.ndarray, scores: np.ndarray) -> tuple[np.ndarray, np.ndarray]:
    total = embeddings.shape[0]
    if total == 0:
        return np.zeros(0, dtype=np.int32), np.zeros(0, dtype=np.float32)

    order = np.argsort(-scores, kind="stable")
    parents = np.full(total, -1, dtype=np.int32)
    distances = np.zeros(total, dtype=np.float32)
    # 已处理节点按分数序连续追加到这块预分配缓冲里，候选集用它做**零拷贝切片**。
    # 原实现每轮 `embeddings[better_indices]` 都会把已处理嵌入整块 gather 一次
    # （23k×256 实测累计搬运 255GB，占全部耗时的 57%）；缓冲区写法结果逐位相同，
    # 实测 23,148 节点从 ~60s 降到 ~8s。
    ordered_embeddings = np.empty_like(embeddings)
    processed_count = 0
    cursor = 0

    while cursor < total:
        group_end = cursor + 1
        current_score = scores[order[cursor]]
        while group_end < total and scores[order[group_end]] == current_score:
            group_end += 1

        group_indices = order[cursor:group_end]
        if processed_count == 0:
            # Top-score group: make the lowest-index member the unique root and
            # attach tied peers to their nearest earlier member, so the tree
            # always has exactly one deterministic root (the champion).
            root = group_indices[0]
            parents[root] = root
            distances[root] = 0.0
            for position in range(1, len(group_indices)):
                node = group_indices[position]
                earlier = group_indices[:position]
                similarity = np.clip(np.dot(embeddings[earlier], embeddings[node]), -1.0, 1.0)
                best_pos = int(np.argmax(similarity))
                parents[node] = earlier[best_pos]
                distances[node] = float(1.0 - similarity[best_pos])
        else:
            better_embeddings = ordered_embeddings[:processed_count]  # 视图，零拷贝
            better_indices = order[:processed_count]
            for block_start in range(0, len(group_indices), NBN_QUERY_BLOCK_SIZE):
                query_indices = group_indices[block_start : block_start + NBN_QUERY_BLOCK_SIZE]
                query_embeddings = embeddings[query_indices]
                similarity = np.dot(query_embeddings, better_embeddings.T)
                similarity = np.clip(similarity, -1.0, 1.0)
                best_positions = np.argmax(similarity, axis=1)
                best_similarity = similarity[np.arange(similarity.shape[0]), best_positions]
                parent_indices = better_indices[best_positions]
                parents[query_indices] = parent_indices
                distances[query_indices] = 1.0 - best_similarity.astype(np.float32)

        ordered_embeddings[processed_count : processed_count + len(group_indices)] = embeddings[group_indices]
        processed_count += len(group_indices)
        cursor = group_end

    return parents, distances


def _cone_tree_layout(parents: np.ndarray, distances: np.ndarray) -> np.ndarray:
    """Deterministic cone-tree XY layout (Python port of OFEC's NBN drawing).

    The root sits at the origin; every node owns an angular sector sized by
    the number of leaves in its subtree and is placed at
        parent_xy + radius * (cos(mid_angle), sin(mid_angle))
    where radius is the (normalized) distance to its parent.  Children are
    processed in ascending index order, so identical inputs always yield the
    identical layout — no HNSW randomness, no tie-break dice.
    """
    total = len(parents)
    coords = np.zeros((total, 2), dtype=np.float64)
    if total == 0:
        return coords

    children: list[list[int]] = [[] for _ in range(total)]
    roots: list[int] = []
    for index in range(total):
        parent = int(parents[index])
        if parent == index or parent < 0 or parent >= total:
            roots.append(index)
        else:
            children[parent].append(index)

    # BFS order guarantees parents are placed before their children.
    bfs: list[int] = list(roots)
    head = 0
    while head < len(bfs):
        bfs.extend(children[bfs[head]])
        head += 1
    if len(bfs) < total:  # cycle guard: leave unreachable nodes at the origin
        logger.warning("Cone-tree layout: %s nodes unreachable from root(s).", total - len(bfs))

    leaf_counts = np.ones(total, dtype=np.float64)
    for node in reversed(bfs):
        if children[node]:
            leaf_counts[node] = sum(leaf_counts[child] for child in children[node])

    finite = distances[np.isfinite(distances)]
    positive = finite[finite > 0]
    max_distance = float(positive.max()) if positive.size else 1.0

    two_pi = 2.0 * math.pi
    sectors = np.zeros((total, 2), dtype=np.float64)
    if len(roots) == 1:
        sectors[roots[0]] = (0.0, two_pi)
    elif roots:
        # Degenerate fallback: split the full circle among multiple roots.
        start = 0.0
        total_leaves = float(sum(leaf_counts[root] for root in roots))
        for root in roots:
            span = two_pi * leaf_counts[root] / total_leaves
            sectors[root] = (start, start + span)
            start += span

    for node in bfs:
        if not children[node]:
            continue
        begin, end = sectors[node]
        span = end - begin
        child_total = leaf_counts[node]
        cursor_angle = begin
        for child in children[node]:
            child_span = span * leaf_counts[child] / child_total
            sectors[child] = (cursor_angle, cursor_angle + child_span)
            mid = cursor_angle + child_span / 2.0
            cursor_angle += child_span
            raw = float(distances[child])
            radius = raw / max_distance if math.isfinite(raw) else 1.0
            radius = min(max(radius, CONE_MIN_RADIUS), 1.0)
            coords[child, 0] = coords[node, 0] + radius * math.cos(mid)
            coords[child, 1] = coords[node, 1] + radius * math.sin(mid)

    # Scale both axes jointly so the circular structure is preserved and the
    # root stays at the exact center of the picture.
    max_abs = float(np.max(np.abs(coords)))
    if max_abs > 1e-9:
        coords *= GRAPH_SPREAD_XY / max_abs
    return coords


def _tree_depth_z(parents: list[int], node_count: int) -> list[float]:
    """Mirror OFEC's cone-tree Z: depth 0 at the top, deeper nodes lower.

    Returns Z values in [-130, 0] matching the scale of `_normalize_positions`.
    """
    depths = [-1] * node_count
    for start in range(node_count):
        chain = []
        current = start
        while depths[current] < 0:
            parent = parents[current]
            if parent == current or parent < 0 or parent >= node_count:
                depths[current] = 0
                break
            chain.append(current)
            current = parent
            if len(chain) > node_count:  # cycle guard
                depths[current] = 0
                break
        for node in reversed(chain):
            depths[node] = depths[parents[node]] + 1
    max_depth = max(depths) if depths else 0
    scale = 130.0 / max_depth if max_depth > 0 else 0.0
    return [-depth * scale for depth in depths]


def _build_exact_nbn_graph(
    samples: list[dict[str, Any]],
    embeddings: np.ndarray,
    *,
    requested_metric: str,
    actual_metric: str,
    fallback_reason: str | None,
    embedding_stats: dict[str, Any] | None = None,
) -> dict[str, Any]:
    scores = _score_array(samples)
    parents, distances = _compute_exact_nbn(embeddings, scores)
    coordinates, layout_meta = _project_embeddings_to_3d(embeddings)

    # Override Z with sanitized actual score (same as OFEC path).
    # PCA Z reflects embedding variance, not solution quality.
    score_floor, score_ceiling = _compute_robust_score_bounds(samples)
    score_range = score_ceiling - score_floor if score_ceiling > score_floor else 1.0

    nodes: list[dict[str, Any]] = []
    edges: list[dict[str, Any]] = []
    parent_list = [
        index
        if (samples[index].get("source_kind") == "external_expert" or samples[index].get("origin_kind") == "external_expert")
        else int(parents[index])
        for index in range(len(samples))
    ]
    tree_z = _tree_depth_z(parent_list, len(samples))
    for index, sample in enumerate(samples):
        raw_score = sample.get("score")
        is_expert = sample.get("source_kind") == "external_expert" or sample.get("origin_kind") == "external_expert"
        parent_index = index if is_expert else int(parents[index])
        distance_val = 0.0 if is_expert else float(distances[index])

        sanitized_score = _sanitize_score_value(raw_score, score_floor, score_ceiling)
        z = _score_to_z(sanitized_score, score_floor, score_range)

        node = {
            "id": sample["id"],
            "sampleOrder": sample.get("origin_sample_order", sample["sample_order"]),
            "mergedSampleOrder": sample["sample_order"],
            "generation": sample.get("generation"),
            "isLatestRevision": bool(sample.get("is_latest_revision")),
            "isLatestRun": bool(sample.get("is_latest_run")),
            "isLatestRound": bool(sample.get("is_latest_round")),
            "score": raw_score,
            "rawScore": raw_score,
            "ofecFitness": raw_score,
            "operator": sample.get("operator", ""),
            "algorithm": sample.get("algorithm", ""),
            "algorithmSummary": (sample.get("algorithm", "") or "No algorithm summary")[:160],
            "functionPreview": _function_preview(sample),
            "programPreview": _program_preview(sample),
            "sourceKind": sample.get("source_kind", ""),
            "sourceRevisionId": sample.get("source_revision_id", ""),
            "sourceLabel": sample.get("source_label", ""),
            "originKind": sample.get("origin_kind", sample.get("source_kind", "")),
            "hasExternalExpert": sample.get("origin_kind") == "external_expert",
            "x": float(coordinates[index, 0]),
            "y": float(coordinates[index, 1]),
            "z": float(z),
            "zScore": float(z),
            "zTree": float(tree_z[index]),
            "ofecIndex": index,
            "ofecParentIndex": parent_index,
            "distanceToParent": distance_val,
        }
        nodes.append(clean_sample_data(node))
        if parent_index < 0 or parent_index == index or parent_index >= len(samples):
            continue
        edges.append(
            {
                "source": sample["id"],
                "target": samples[parent_index]["id"],
                "distance": distance_val,
            }
        )

    return {
        "nodes": nodes,
        "edges": edges,
        "truncated": False,
        "graphSource": "exact_nbn_cached",
        "distanceMetric": actual_metric,
        "distanceMetricRequested": requested_metric,
        "distanceMetricFallbackReason": fallback_reason,
        "graphBuildStats": {
            **(embedding_stats or {}),
            **layout_meta,
            "nbnMode": "exact_nearest_better_neighbor",
        },
    }


def build_nbn_graph(
    samples: list[dict[str, Any]],
    output_dir: Path,
    *,
    distance_metric: str | None = None,
    progress_callback: ProgressCallback | None = None,
) -> dict[str, Any]:
    requested_metric = get_distance_metric_name(distance_metric)
    if not samples:
        return {
            "nodes": [],
            "edges": [],
            "truncated": False,
            "graphSource": "empty",
            "distanceMetric": requested_metric,
            "distanceMetricRequested": requested_metric,
        }

    output_dir.mkdir(parents=True, exist_ok=True)

    graph_samples = samples
    if progress_callback is not None:
        progress_callback(
            {
                "stage": "prepare_samples",
                "stageLabel": "准备图构建样本",
                "current": 0,
                "total": len(graph_samples),
                "message": f"Preparing {len(graph_samples)} samples for CodeT5 NBN graph build.",
            }
        )
    embeddings, graph_build_stats = get_codet5_embedding_matrix(
        graph_samples,
        progress_callback=progress_callback,
    )
    fallback_reason: str | None = None
    actual_metric = requested_metric
    score_floor, score_ceiling = _compute_robust_score_bounds(graph_samples)
    sanitized_scores = np.asarray(
        [_sanitize_score_value(sample.get("score"), score_floor, score_ceiling) for sample in graph_samples],
        dtype=np.float64,
    )
    if progress_callback is not None:
        progress_callback(
            {
                "stage": "nbn_compute",
                "stageLabel": "执行 NBN 构图",
                "message": "Computing NBN with the configured backend (portable HNSW by default).",
            }
        )
    backend = os.getenv("VISUAL_PLATFORM_NBN_BACKEND", "portable").strip().lower()
    native_meta = None
    if backend == "portable":
        if requested_metric != DEFAULT_DISTANCE_METRIC:
            raise ValueError("Portable HNSW requires codet5p_embedding_cosine")
        from visual_platform.portable_nbn import compute
        # Preserve the native adapter's original first-encoding-owner semantics.
        # Display height still uses zgr's robust score normalization below.
        native_scores = np.asarray([
            float(sample["score"]) if sample.get("score") is not None
            and math.isfinite(float(sample["score"])) else -1e9
            for sample in graph_samples
        ], dtype=np.float64)
        parents, parent_distances, native_meta = compute(output_dir, embeddings, native_scores)
        backend_stats = {k: v for k, v in native_meta.items() if not k.startswith("_")}
        graph_source = "ofec_nbn_portable_cone_tree"
    elif backend == "exact":
        parents, parent_distances = _compute_exact_nbn(embeddings, sanitized_scores)
        backend_stats = {"nbnMode": "exact_nearest_better_neighbor"}
        graph_source = "exact_nbn_cone_tree"
    else:
        raise ValueError("VISUAL_PLATFORM_NBN_BACKEND must be portable or exact")

    if progress_callback is not None:
        progress_callback(
            {
                "stage": "parse_outputs",
                "stageLabel": "计算锥形树布局",
                "message": "Computing deterministic cone-tree layout.",
            }
        )
    layout_xy = _cone_tree_layout(parents, parent_distances)
    tree_z = _tree_depth_z([int(p) for p in parents], len(graph_samples))

    # Z axis uses the sanitized actual score so "higher = better" holds
    # visually; tree depth is kept as the alternative zTree coordinate.
    score_range = score_ceiling - score_floor if score_ceiling > score_floor else 1.0

    nodes: list[dict[str, Any]] = []
    edges: list[dict[str, Any]] = []

    for index, sample in enumerate(graph_samples):
        parent_index = int(parents[index])
        distance_val = float(parent_distances[index])
        raw_score = sample.get("score")

        sanitized_score = _sanitize_score_value(raw_score, score_floor, score_ceiling)
        z = _score_to_z(sanitized_score, score_floor, score_range)

        node = {
            "id": sample["id"],
            "sampleOrder": sample.get("origin_sample_order", sample["sample_order"]),
            "mergedSampleOrder": sample["sample_order"],
            "generation": sample.get("generation"),
            "isLatestRevision": bool(sample.get("is_latest_revision")),
            "isLatestRun": bool(sample.get("is_latest_run")),
            "isLatestRound": bool(sample.get("is_latest_round")),
            "score": raw_score,
            "rawScore": raw_score,
            "ofecFitness": raw_score,
            "operator": sample.get("operator", ""),
            "algorithm": sample.get("algorithm", ""),
            "algorithmSummary": (sample.get("algorithm", "") or "No algorithm summary")[:160],
            "functionPreview": _function_preview(sample),
            "programPreview": _program_preview(sample),
            "sourceKind": sample.get("source_kind", ""),
            "sourceRevisionId": sample.get("source_revision_id", ""),
            "sourceLabel": sample.get("source_label", ""),
            "originKind": sample.get("origin_kind", sample.get("source_kind", "")),
            "hasExternalExpert": sample.get("origin_kind") == "external_expert",
            "x": float(layout_xy[index, 0]),
            "y": float(layout_xy[index, 1]),
            "z": float(z),
            "zScore": float(z),
            "zTree": float(tree_z[index]),
            "ofecIndex": index,
            "ofecParentIndex": parent_index,
            "distanceToParent": distance_val,
        }
        if native_meta is not None:
            node["nbnNodeId"] = native_meta["_sampleNodeIds"][index]
            node["nbnRepresentativeIndex"] = native_meta["_representativeIndices"][index]
            node["isDuplicateEncoding"] = node["nbnRepresentativeIndex"] != index
            node["ofecFitness"] = native_meta["_effectiveFitness"][index]
        nodes.append(clean_sample_data(node))

    for index, sample in enumerate(graph_samples):
        parent_index = int(parents[index])
        if parent_index < 0 or parent_index == index or parent_index >= len(graph_samples):
            continue
        edges.append(
            {
                "source": sample["id"],
                "target": graph_samples[parent_index]["id"],
                "distance": float(parent_distances[index]),
            }
        )

    payload = {
        "nodes": nodes,
        "edges": edges,
        "truncated": False,
        "graphSource": graph_source,
        "distanceMetric": actual_metric,
        "distanceMetricRequested": requested_metric,
        "distanceMetricFallbackReason": fallback_reason,
    }
    if graph_build_stats:
        payload["graphBuildStats"] = {**graph_build_stats, **backend_stats, "layoutMode": "cone_tree_python"}
    else:
        payload["graphBuildStats"] = {**backend_stats, "layoutMode": "cone_tree_python"}
    if progress_callback is not None:
        progress_callback(
            {
                "stage": "completed",
                "stageLabel": "图构建完成",
                "current": len(graph_samples),
                "total": len(graph_samples),
                "message": "CodeT5 embedding graph build completed.",
            }
        )
    logger.info(
        "CodeT5 NBN graph build finished: samples=%s cached=%s new=%s",
        len(graph_samples),
        graph_build_stats.get("cachedEmbeddingCount") if graph_build_stats else None,
        graph_build_stats.get("newEmbeddingCount") if graph_build_stats else None,
    )
    return payload
