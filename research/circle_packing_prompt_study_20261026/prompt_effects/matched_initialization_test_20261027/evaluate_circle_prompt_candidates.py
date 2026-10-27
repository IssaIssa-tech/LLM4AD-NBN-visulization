"""Safely evaluate generated Circle Packing candidates with recorded outcomes.

This utility is deliberately separate from generation.  It performs a conservative
static screen, executes each candidate in its own subprocess with a fixed timeout,
and preserves every outcome (including invalid programs and timeouts) in JSON.
"""

from __future__ import annotations

import argparse
import ast
import contextlib
import hashlib
import io
import json
import subprocess
import sys
import time
from pathlib import Path
from typing import Any

import numpy as np


ALLOWED_IMPORT_ROOTS = {"numpy", "math", "scipy"}
FORBIDDEN_NAMES = {
    "open", "exec", "eval", "compile", "__import__", "input", "breakpoint",
    "globals", "locals", "getattr", "setattr", "delattr",
}


def static_screen(path: Path) -> dict[str, Any]:
    """Reject obvious side effects before executing an LLM-produced program."""
    source = path.read_text(encoding="utf-8")
    try:
        tree = ast.parse(source, filename=str(path))
    except SyntaxError as exc:
        return {"ok": False, "reason": f"syntax_error: {exc.msg}"}

    functions = [node.name for node in tree.body if isinstance(node, ast.FunctionDef)]
    for node in tree.body:
        if isinstance(node, (ast.Import, ast.ImportFrom, ast.FunctionDef)):
            continue
        if isinstance(node, ast.Expr) and isinstance(getattr(node, "value", None), ast.Constant) and isinstance(node.value.value, str):
            continue
        return {"ok": False, "reason": "disallowed_top_level_statement"}
    if functions != ["pack_circles"]:
        return {"ok": False, "reason": f"expected_only_pack_circles_found_{functions}"}

    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            roots = {alias.name.split(".")[0] for alias in node.names}
            if not roots <= ALLOWED_IMPORT_ROOTS:
                return {"ok": False, "reason": f"disallowed_import_{sorted(roots - ALLOWED_IMPORT_ROOTS)}"}
        elif isinstance(node, ast.ImportFrom):
            root = (node.module or "").split(".")[0]
            if root not in ALLOWED_IMPORT_ROOTS:
                return {"ok": False, "reason": f"disallowed_import_{root}"}
        elif isinstance(node, ast.Name) and node.id in FORBIDDEN_NAMES:
            return {"ok": False, "reason": f"disallowed_name_{node.id}"}
    return {"ok": True}


def valid_circles(circles: np.ndarray, eps: float = 1e-12) -> bool:
    if circles.shape != (26, 3) or not np.isfinite(circles).all():
        return False
    for x, y, radius in circles:
        if radius < -eps or x - radius < -eps or y - radius < -eps:
            return False
        if x + radius > 1 + eps or y + radius > 1 + eps:
            return False
    for i in range(len(circles)):
        for j in range(i + 1, len(circles)):
            if np.hypot(circles[i, 0] - circles[j, 0], circles[i, 1] - circles[j, 1]) < circles[i, 2] + circles[j, 2] - eps:
                return False
    return True


def worker(path: Path) -> dict[str, Any]:
    started = time.perf_counter()
    result: dict[str, Any] = {"candidate_file": path.name, "code_sha256": hashlib.sha256(path.read_bytes()).hexdigest()}
    try:
        namespace: dict[str, Any] = {"__name__": "circle_candidate", "np": np}
        with contextlib.redirect_stdout(io.StringIO()), contextlib.redirect_stderr(io.StringIO()):
            exec(compile(path.read_text(encoding="utf-8"), str(path), "exec"), namespace)
            circles = np.asarray(namespace["pack_circles"](26), dtype=np.float64)
        result["shape"] = list(circles.shape)
        if circles.shape != (26, 3):
            result.update(status="invalid_shape", score=None)
        elif not np.isfinite(circles).all():
            result.update(status="nonfinite_output", score=None)
        elif not valid_circles(circles):
            result.update(status="invalid_geometry", score=None)
        else:
            result.update(status="valid", score=float(np.sum(circles[:, 2])))
    except Exception as exc:
        result.update(status="exception", score=None, error=f"{type(exc).__name__}: {exc}")
    result["runtime_seconds"] = time.perf_counter() - started
    return result


def evaluate(path: Path, timeout_seconds: int) -> dict[str, Any]:
    screening = static_screen(path)
    base: dict[str, Any] = {
        "candidate_path": str(path),
        "code_sha256": hashlib.sha256(path.read_bytes()).hexdigest(),
        "static_screen": screening,
    }
    if not screening["ok"]:
        return {**base, "status": "rejected_static", "score": None}
    started = time.perf_counter()
    try:
        completed = subprocess.run(
            [sys.executable, str(Path(__file__).resolve()), "--worker", str(path)],
            text=True, capture_output=True, timeout=timeout_seconds, check=False,
        )
    except subprocess.TimeoutExpired:
        return {**base, "status": "timeout", "score": None, "timeout_seconds": timeout_seconds,
                "wall_runtime_seconds": time.perf_counter() - started}
    if completed.returncode != 0:
        return {**base, "status": "runner_error", "score": None, "return_code": completed.returncode,
                "stderr": completed.stderr[-2000:], "wall_runtime_seconds": time.perf_counter() - started}
    try:
        payload = json.loads(completed.stdout)
    except json.JSONDecodeError:
        return {**base, "status": "runner_error", "score": None, "stdout": completed.stdout[-2000:],
                "wall_runtime_seconds": time.perf_counter() - started}
    return {**base, **payload, "wall_runtime_seconds": time.perf_counter() - started}


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--worker", type=Path)
    parser.add_argument("--run-dir", type=Path)
    parser.add_argument("--output", type=Path)
    parser.add_argument("--timeout-seconds", type=int, default=20)
    parser.add_argument("--quality-floor", type=float, default=None,
                        help="Optional score threshold recorded separately from geometric validity.")
    args = parser.parse_args()
    if args.worker:
        print(json.dumps(worker(args.worker), ensure_ascii=False))
        return
    if not args.run_dir or not args.output:
        raise SystemExit("--run-dir and --output are required outside --worker mode")
    if args.output.exists():
        raise SystemExit(f"Refusing to overwrite existing output: {args.output}")
    candidates = sorted(args.run_dir.glob("m*/candidate.py"))
    results = []
    for candidate in candidates:
        result = evaluate(candidate, args.timeout_seconds)
        result["arm"] = candidate.parent.name
        if args.quality_floor is not None and result.get("status") == "valid":
            result["quality_floor"] = args.quality_floor
            result["quality_gate"] = "pass" if result.get("score", float("-inf")) >= args.quality_floor else "below_floor"
        results.append(result)
    payload = {
        "purpose": "Controlled preflight evaluation of generated Circle Packing candidates.",
        "n_circles": 26,
        "geometry_epsilon": 1e-12,
        "timeout_seconds": args.timeout_seconds,
        "quality_floor": args.quality_floor,
        "python_executable": sys.executable,
        "results": results,
    }
    args.output.write_text(json.dumps(payload, indent=2, ensure_ascii=False), encoding="utf-8")
    print(json.dumps(payload, ensure_ascii=False))


if __name__ == "__main__":
    main()
