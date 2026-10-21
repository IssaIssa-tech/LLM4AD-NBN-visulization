from __future__ import annotations

import hashlib
import importlib
import importlib.util
import math
import os
import re
import sqlite3
import sys
from dataclasses import dataclass
from functools import lru_cache
from pathlib import Path
from typing import Any, Callable

import numpy as np


BASE_DIR = Path(__file__).resolve().parent
WORKSPACE_DIR = BASE_DIR.parents[2]
OFEC_ROOT = Path(os.getenv("OFEC_ROOT", str(BASE_DIR.parents[1] / "ofec")))
DEFAULT_DISTANCE_METRIC = "codet5p_embedding_cosine"
FALLBACK_DISTANCE_METRIC = "token_jaccard_fallback"
CODET5_MODEL_REPO = "Salesforce/codet5p-110m-embedding"
LOCAL_CODET5_MODEL_DIR = BASE_DIR.parent / "modal" / "codet5p-110m-embedding"


class OFECNBNError(RuntimeError):
    pass


@dataclass(frozen=True)
class NBNNodeRecord:
    index: int
    x: float
    y: float
    z: float
    parent_index: int


@dataclass(frozen=True)
class NBNMetricRecord:
    index: int
    parent_index: int
    distance_to_parent: float
    fitness: float


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


def _tokenize_code(text: str) -> set[str]:
    return set(re.findall(r"[A-Za-z_][A-Za-z0-9_]*|\d+|==|!=|<=|>=|[-+*/%(){}\[\],.:]", text))


def _fallback_distance(pred: str, ref: str) -> float:
    pred_tokens = _tokenize_code(pred)
    ref_tokens = _tokenize_code(ref)
    if not pred_tokens and not ref_tokens:
        return 0.0
    union = pred_tokens | ref_tokens
    if not union:
        return 0.0
    similarity = len(pred_tokens & ref_tokens) / len(union)
    return 1.0 - similarity


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
        "token": FALLBACK_DISTANCE_METRIC,
        "token_jaccard": FALLBACK_DISTANCE_METRIC,
        "jaccard": FALLBACK_DISTANCE_METRIC,
    }
    return aliases.get(metric, metric)


def get_distance_metric_name(distance_metric: str | None = None) -> str:
    return _normalize_distance_metric(distance_metric)


def _codet5_checkpoint_candidates() -> list[str]:
    candidates: list[str] = []
    env_path = str(os.getenv("VISUAL_PLATFORM_CODET5_DIR", "") or "").strip()
    if env_path:
        candidates.append(env_path)
    if LOCAL_CODET5_MODEL_DIR.exists():
        candidates.append(str(LOCAL_CODET5_MODEL_DIR))
    candidates.append(CODET5_MODEL_REPO)

    unique: list[str] = []
    seen: set[str] = set()
    for candidate in candidates:
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
def _load_codet5_embedding_model() -> tuple[Any, Any, Any]:
    import torch

    AutoModel, AutoTokenizer = _load_transformers_auto_classes()

    device = "cuda" if torch.cuda.is_available() else "cpu"
    errors: list[str] = []
    for checkpoint in _codet5_checkpoint_candidates():
        load_kwargs = {"trust_remote_code": True}
        if Path(checkpoint).exists():
            load_kwargs["local_files_only"] = True
        try:
            tokenizer = AutoTokenizer.from_pretrained(checkpoint, **load_kwargs)
            from transformers import AutoConfig, T5Config

            config = AutoConfig.from_pretrained(checkpoint, **load_kwargs)
            # The original Salesforce config predates Transformers 5, which
            # moved several T5 defaults out of PretrainedConfig.
            if getattr(config, "model_type", "") == "codet5p_embedding":
                for name, value in T5Config().to_dict().items():
                    if not hasattr(config, name):
                        setattr(config, name, value)
            model = AutoModel.from_pretrained(checkpoint, config=config, **load_kwargs).to(device)
            model.eval()
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


CODET5_EMBEDDING_DB_FILE = Path(__file__).parent / ".codet5_embeddings_cache.sqlite3"
CODET5_BATCH_SIZE = max(4, int(os.getenv("VISUAL_PLATFORM_CODET5_BATCH_SIZE", "24") or "24"))
CODET5_MAX_LENGTH = max(128, int(os.getenv("VISUAL_PLATFORM_CODET5_MAX_LENGTH", "1024") or "1024"))
NBN_QUERY_BLOCK_SIZE = max(64, int(os.getenv("VISUAL_PLATFORM_NBN_QUERY_BLOCK_SIZE", "256") or "256"))


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
        rows = [
            (
                code_hash,
                int(vector.shape[0]),
                sqlite3.Binary(np.asarray(vector, dtype=np.float32).tobytes()),
                Path(__file__).stat().st_mtime_ns,
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


def _batch_embed_missing_codes(missing_items: list[tuple[str, str]]) -> dict[str, np.ndarray]:
    if not missing_items:
        return {}

    tokenizer, model, device = _load_codet5_embedding_model()
    import torch

    vectors_by_hash: dict[str, np.ndarray] = {}
    for start in range(0, len(missing_items), CODET5_BATCH_SIZE):
        batch = missing_items[start : start + CODET5_BATCH_SIZE]
        batch_hashes = [item[0] for item in batch]
        batch_vectors_by_hash: dict[str, np.ndarray] = {}
        batch_texts = [item[1] for item in batch]
        inputs = tokenizer(
            batch_texts,
            return_tensors="pt",
            padding=True,
            truncation=True,
            max_length=CODET5_MAX_LENGTH,
        ).to(device)
        with torch.no_grad():
            outputs = model(**inputs)
            hidden = outputs if isinstance(outputs, torch.Tensor) else (outputs.last_hidden_state if hasattr(outputs, "last_hidden_state") else outputs[0])
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
                    single_hidden = single_outputs if isinstance(single_outputs, torch.Tensor) else (single_outputs.last_hidden_state if hasattr(single_outputs, "last_hidden_state") else single_outputs[0])
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
            continue

        for code_hash, vector in zip(batch_hashes, batch_vectors, strict=False):
            batch_vectors_by_hash[code_hash] = np.asarray(vector, dtype=np.float32).reshape(-1)
        _store_cached_embeddings(batch_vectors_by_hash)
        vectors_by_hash.update(batch_vectors_by_hash)
    return vectors_by_hash


def get_codet5_embedding_matrix(samples: list[dict[str, Any]]) -> tuple[np.ndarray, dict[str, int]]:
    sources = [_sample_source(sample) for sample in samples]
    code_hashes = [hashlib.sha256(source.encode("utf-8")).hexdigest() for source in sources]
    cached_vectors = _load_cached_embeddings(code_hashes)
    missing_items = [
        (code_hash, source)
        for code_hash, source in zip(code_hashes, sources, strict=False)
        if code_hash not in cached_vectors
    ]
    if missing_items:
        cached_vectors.update(_batch_embed_missing_codes(missing_items))

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


def build_distance_function(samples: list[dict[str, Any]]) -> Callable[[int, int], float]:
    sources = [_sample_source(sample) for sample in samples]

    def _distance(lhs: int, rhs: int) -> float:
        pred = sources[lhs]
        ref = sources[rhs]
        return _fallback_distance(pred, ref)

    return _distance


def build_distance_matrix(samples: list[dict[str, Any]]) -> tuple[list[list[float]], str, str | None]:
    requested_metric = get_distance_metric_name()
    return build_distance_matrix_with_metric(samples, requested_metric)


def build_distance_matrix_with_metric(samples: list[dict[str, Any]], distance_metric: str | None) -> tuple[list[list[float]], str, str | None]:
    requested_metric = get_distance_metric_name(distance_metric)
    if requested_metric == "codet5p_embedding_cosine":
        try:
            return _codet5_distance_matrix(samples), "codet5p_embedding_cosine", None
        except Exception as error:
            fallback_reason = (
                "CodeT5 embedding distance unavailable, fallback to token_jaccard_fallback: "
                f"{type(error).__name__}: {error}"
            )
            token_matrix, actual_metric, _ = build_distance_matrix_with_metric(samples, FALLBACK_DISTANCE_METRIC)
            return token_matrix, actual_metric, fallback_reason

    distance_function = build_distance_function(samples)
    size = len(samples)
    
    # Fast vectorized Jaccard distance calculation
    sources = [_sample_source(sample) for sample in samples]
    token_sets = [_tokenize_code(src) for src in sources]
    
    vocab = {}
    for tset in token_sets:
        for t in tset:
            if t not in vocab:
                vocab[t] = len(vocab)
                
    if not vocab:
        return [[0.0] * size for _ in range(size)], FALLBACK_DISTANCE_METRIC, None

    M = np.zeros((size, len(vocab)), dtype=bool)
    for i, tset in enumerate(token_sets):
        for t in tset:
            M[i, vocab[t]] = True
            
    # M.astype(np.float32) avoids integer overflow on large matrices and allows fast BLAS operations
    M_float = M.astype(np.float32)
    intersection = np.dot(M_float, M_float.T)
    sizes = M_float.sum(axis=1)
    union = sizes[:, None] + sizes[None, :] - intersection
    
    union[union == 0] = 1.0
    similarity = intersection / union
    D = 1.0 - similarity
    np.fill_diagonal(D, 0.0)
    
    return D.tolist(), FALLBACK_DISTANCE_METRIC, None


def _candidate_module_files() -> list[Path]:
    env_path = os.getenv("OFEC_NBN_MODULE_PATH", "").strip()
    candidates: list[Path] = []
    if env_path:
        path = Path(env_path)
        if path.is_file():
            candidates.append(path)
        elif path.is_dir():
            candidates.extend(sorted(path.glob("ofec_nbn*.pyd")))
            candidates.extend(sorted(path.glob("ofec_nbn*.so")))

    if OFEC_ROOT.exists():
        for pattern in ("ofec_nbn*.pyd", "ofec_nbn*.so"):
            candidates.extend(sorted(OFEC_ROOT.rglob(pattern)))

    unique_candidates: list[Path] = []
    seen: set[str] = set()
    for path in candidates:
        key = str(path.resolve())
        if key not in seen:
            unique_candidates.append(path)
            seen.add(key)
    return unique_candidates


@lru_cache(maxsize=1)
def load_ofec_module() -> Any:
    explicit_name = os.getenv("OFEC_NBN_MODULE_NAME", "").strip()
    if explicit_name:
        try:
            return importlib.import_module(explicit_name)
        except ModuleNotFoundError as exc:
            raise OFECNBNError(
                f"Unable to import OFEC module '{explicit_name}'. "
                "Check OFEC_NBN_MODULE_NAME or OFEC_NBN_MODULE_PATH."
            ) from exc

    try:
        return importlib.import_module("ofec_nbn")
    except ModuleNotFoundError:
        pass

    for module_path in _candidate_module_files():
        spec = importlib.util.spec_from_file_location("ofec_nbn", module_path)
        if spec is None or spec.loader is None:
            continue
        module = importlib.util.module_from_spec(spec)
        sys.modules["ofec_nbn"] = module
        spec.loader.exec_module(module)
        return module

    raise OFECNBNError(
        "OFEC NBN Python module is not available. "
        "Build `ofec_nbn` from `d:/WIP/OPEC/OFEC_DYY/run/pybind_module.cpp`, "
        "or point `OFEC_NBN_MODULE_PATH` to the compiled module."
    )


def _parse_visualization_file(file_path: Path) -> dict[int, NBNNodeRecord]:
    if not file_path.exists():
        raise OFECNBNError(f"Missing OFEC visualization output: {file_path}")

    records: dict[int, NBNNodeRecord] = {}
    with file_path.open("r", encoding="utf-8") as handle:
        next(handle, None)
        for line in handle:
            parts = line.strip().split()
            if len(parts) < 5:
                continue
            index = int(parts[0])
            records[index] = NBNNodeRecord(
                index=index,
                x=float(parts[1]),
                y=float(parts[2]),
                z=float(parts[3]),
                parent_index=int(parts[4]),
            )
    return records


def _parse_metric_file(file_path: Path) -> dict[int, NBNMetricRecord]:
    if not file_path.exists():
        raise OFECNBNError(f"Missing OFEC metric output: {file_path}")

    records: dict[int, NBNMetricRecord] = {}
    with file_path.open("r", encoding="utf-8") as handle:
        next(handle, None)
        for line in handle:
            parts = line.strip().split()
            if len(parts) < 4:
                continue
            index = int(parts[0])
            records[index] = NBNMetricRecord(
                index=index,
                parent_index=int(parts[1]),
                distance_to_parent=float(parts[2]),
                fitness=float(parts[3]),
            )
    return records


def _normalize_positions(records: dict[int, NBNNodeRecord]) -> dict[int, tuple[float, float, float]]:
    if not records:
        return {}

    xs = [record.x for record in records.values()]
    ys = [record.y for record in records.values()]
    zs = [record.z for record in records.values()]

    def _scale(values: list[float]) -> tuple[float, float]:
        max_abs = max((abs(value) for value in values), default=0.0)
        if max_abs == 0:
            max_abs = 1.0
        return max_abs, 130.0 / max_abs

    x_abs, x_scale = _scale(xs)
    y_abs, y_scale = _scale(ys)
    z_abs, z_scale = _scale(zs)
    _ = (x_abs, y_abs, z_abs)

    return {
        index: (record.x * x_scale, record.y * y_scale, record.z * z_scale)
        for index, record in records.items()
    }


def _score_array(samples: list[dict[str, Any]]) -> np.ndarray:
    return np.asarray(
        [float(sample["score"]) if sample.get("score") is not None else -1e9 for sample in samples],
        dtype=np.float64,
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
        coords[:, axis] = axis_values * (140.0 / scale)
    return coords, {"layoutMode": "pca3"}


def _compute_exact_nbn(embeddings: np.ndarray, scores: np.ndarray) -> tuple[np.ndarray, np.ndarray]:
    total = embeddings.shape[0]
    if total == 0:
        return np.zeros(0, dtype=np.int32), np.zeros(0, dtype=np.float32)

    order = np.argsort(-scores, kind="stable")
    parents = np.full(total, -1, dtype=np.int32)
    distances = np.zeros(total, dtype=np.float32)
    processed = np.empty(total, dtype=np.int32)
    processed_count = 0
    cursor = 0

    while cursor < total:
        group_end = cursor + 1
        current_score = scores[order[cursor]]
        while group_end < total and scores[order[group_end]] == current_score:
            group_end += 1

        group_indices = order[cursor:group_end]
        if processed_count == 0:
            parents[group_indices] = group_indices
            distances[group_indices] = 0.0
        else:
            better_indices = processed[:processed_count]
            better_embeddings = embeddings[better_indices]
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

        processed[processed_count : processed_count + len(group_indices)] = group_indices
        processed_count += len(group_indices)
        cursor = group_end

    return parents, distances


def _build_exact_nbn_graph(
    samples: list[dict[str, Any]],
    embeddings: np.ndarray,
    *,
    requested_metric: str,
    actual_metric: str,
    fallback_reason: str | None,
    embedding_stats: dict[str, Any] | None = None,
    nbn_result: tuple[np.ndarray, np.ndarray] | None = None,
    backend_stats: dict[str, Any] | None = None,
) -> dict[str, Any]:
    scores = _score_array(samples)
    parents, distances = nbn_result if nbn_result is not None else _compute_exact_nbn(embeddings, scores)
    coordinates, layout_meta = _project_embeddings_to_3d(embeddings)

    nodes: list[dict[str, Any]] = []
    edges: list[dict[str, Any]] = []
    for index, sample in enumerate(samples):
        raw_score = sample.get("score")
        nodes.append(
            {
                "id": sample["id"],
                "sampleOrder": sample.get("origin_sample_order", sample["sample_order"]),
                "mergedSampleOrder": sample["sample_order"],
                "generation": sample.get("generation"),
                "isLatestRun": bool(sample.get("is_latest_run")),
                "isLatestRound": bool(sample.get("is_latest_round")),
                "score": raw_score,
                "rawScore": raw_score,
                "ofecFitness": raw_score,
                "operator": sample.get("operator", ""),
                "algorithm": sample.get("algorithm", ""),
                "algorithmSummary": (sample.get("algorithm", "") or "No algorithm summary")[:160],
                "functionPreview": _function_preview(sample),
                "sourceKind": sample.get("source_kind", ""),
                "sourceRunId": sample.get("source_run_id", ""),
                "sourceLabel": sample.get("source_label", ""),
                "originKind": sample.get("origin_kind", sample.get("source_kind", "")),
                "hasExternalExpert": sample.get("origin_kind") == "external_expert",
                "x": float(coordinates[index, 0]),
                "y": float(coordinates[index, 1]),
                "z": float(coordinates[index, 2]),
                "ofecIndex": index,
                "ofecParentIndex": int(parents[index]),
                "distanceToParent": float(distances[index]),
            }
        )
        parent_index = int(parents[index])
        if parent_index < 0 or parent_index == index or parent_index >= len(samples):
            continue
        edges.append(
            {
                "source": sample["id"],
                "target": samples[parent_index]["id"],
                "distance": float(distances[index]),
            }
        )

    return {
        "nodes": nodes,
        "edges": edges,
        "truncated": False,
        "graphSource": "ofec_nbn_portable" if nbn_result is not None else "exact_nbn_cached",
        "distanceMetric": actual_metric,
        "distanceMetricRequested": requested_metric,
        "distanceMetricFallbackReason": fallback_reason,
        "graphBuildStats": {
            **(embedding_stats or {}),
            **layout_meta,
            "nbnMode": "exact_nearest_better_neighbor",
            **(backend_stats or {}),
        },
    }


def run_ofec_nbn(samples: list[dict[str, Any]], output_dir: Path, *, distance_metric: str | None = None) -> dict[str, Any]:
    requested_metric = get_distance_metric_name(distance_metric)
    if not samples:
        return {
            "nodes": [],
            "edges": [],
            "truncated": False,
            "graphSource": "ofec_nbn",
            "distanceMetric": requested_metric,
            "distanceMetricRequested": requested_metric,
        }

    # Cosine embeddings are passed directly to C++; no NxN distance matrix.
    try:
        from .portable_nbn import compute
    except ImportError:
        from portable_nbn import compute
    if requested_metric != DEFAULT_DISTANCE_METRIC:
        raise OFECNBNError("Portable NBN requires codet5p_embedding_cosine; token Jaccard is not a cosine metric.")
    try:
        embeddings, embedding_stats = get_codet5_embedding_matrix(samples)
        scores = np.asarray([float(s["score"]) if s.get("score") is not None else -1e9 for s in samples], dtype=np.float64)
        parents, distances, backend_stats = compute(output_dir, embeddings, scores)
    except Exception as exc:
        raise OFECNBNError(f"Portable NBN failed: {exc}") from exc
    output_dir.mkdir(parents=True, exist_ok=True)
    node_ids = backend_stats.pop("_sampleNodeIds")
    representative_indices = backend_stats.pop("_representativeIndices")
    effective_fitness = backend_stats.pop("_effectiveFitness")
    graph = _build_exact_nbn_graph(
        samples, embeddings, requested_metric=requested_metric,
        actual_metric=DEFAULT_DISTANCE_METRIC, fallback_reason=None,
        embedding_stats=embedding_stats, nbn_result=(parents, distances),
        backend_stats=backend_stats,
    )
    for index, node in enumerate(graph["nodes"]):
        node["nbnNodeId"] = node_ids[index]
        node["nbnRepresentativeIndex"] = representative_indices[index]
        node["isDuplicateEncoding"] = representative_indices[index] != index
        node["ofecFitness"] = effective_fitness[index]
    return graph

