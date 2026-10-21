from __future__ import annotations

import json
import shutil
from pathlib import Path
from typing import Any


BASE_DIR = Path(__file__).resolve().parent

HISTORY_SAMPLE_SOURCES: dict[str, dict[str, Any]] = {
    "circle_packing_history": {
        "label": "Circle Packing 历史样本",
        "samples_dir": BASE_DIR.parent / "example" / "tasks" / "circle_packing" / "EoH_settings&logs" / "EoH_sample_history" / "samples",
    }
}


def list_history_sources() -> list[dict[str, str]]:
    items: list[dict[str, str]] = []
    for key, meta in HISTORY_SAMPLE_SOURCES.items():
        samples_dir = Path(meta["samples_dir"])
        items.append(
            {
                "key": key,
                "label": str(meta.get("label", key)),
                "path": str(samples_dir),
            }
        )
    return items


def import_history_samples(source_key: str, target_log_dir: Path) -> dict[str, Any]:
    source = HISTORY_SAMPLE_SOURCES.get(source_key)
    if source is None:
        available = ", ".join(sorted(HISTORY_SAMPLE_SOURCES))
        raise ValueError(f"Unknown history source '{source_key}'. Available sources: {available}")

    source_samples_dir = Path(source["samples_dir"])
    if not source_samples_dir.exists():
        raise FileNotFoundError(f"History samples directory not found: {source_samples_dir}")

    sample_files = sorted(
        [path for path in source_samples_dir.glob("samples_*.json") if path.name != "samples_best.json"],
        key=lambda path: path.name,
    )
    if not sample_files:
        raise FileNotFoundError(f"No history sample files found in: {source_samples_dir}")

    target_samples_dir = target_log_dir / "samples"
    target_samples_dir.mkdir(parents=True, exist_ok=True)

    sample_count = 0
    imported_files = 0
    best_score: float | None = None
    best_sample_order: int | None = None
    for sample_file in sample_files:
        target_file = target_samples_dir / sample_file.name
        shutil.copy2(sample_file, target_file)
        imported_files += 1
        try:
            content = json.loads(target_file.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError):
            continue
        if not isinstance(content, list):
            continue
        for item in content:
            if not isinstance(item, dict):
                continue
            sample_count += 1
            raw_score = item.get("score")
            if isinstance(raw_score, (int, float)):
                score = float(raw_score)
                if best_score is None or score > best_score:
                    best_score = score
                    sample_order = item.get("sample_order")
                    best_sample_order = int(sample_order) if isinstance(sample_order, int) else best_sample_order

    try:
        best_file = source_samples_dir / "samples_best.json"
        if best_file.exists():
            shutil.copy2(best_file, target_samples_dir / best_file.name)
    except OSError:
        pass

    population_dir = target_log_dir / "population"
    population_dir.mkdir(parents=True, exist_ok=True)
    (population_dir / "end.json").write_text("[]\n", encoding="utf-8")

    return {
        "sourceKey": source_key,
        "sourceLabel": source.get("label", source_key),
        "sourcePath": str(source_samples_dir),
        "importedFiles": imported_files,
        "sampleCount": sample_count,
        "bestScore": best_score,
        "bestSampleOrder": best_sample_order,
    }
