from __future__ import annotations

import json
import sys
import tempfile
import types
import unittest
from pathlib import Path
from types import SimpleNamespace
from unittest import mock

import numpy as np

from visual_platform.runtime import region_runner


HIT_MARKER = "HIT_MARKER"
NEAR_MARKER = "NEAR_MARKER"
FAR_MARKER = "FAR_MARKER"


class _StubFunction:
    def __init__(self, marker: str, score: float | None, operator: str):
        self.marker = marker
        self.score = score
        self.operator = operator
        self.algorithm = "{stub}"
        self.parents = ["p"]
        self.evaluate_time = 0.2
        self.sample_time = 0.1

    def __str__(self) -> str:
        return f"def pack_circles(n):\n    pass  # {self.marker}"


#: 每次构造的 EoH 桩实例，用来断言运行器传给 EoH 的采样预算。
_EOH_INSTANCES: list = []


def _install_eoh_stubs(sample_specs: list[list[tuple[str, float | None]]]) -> None:
    """Install lightweight stand-ins for llm4ad.method.eoh so the segment loop
    can be exercised without the ~100s eager torch/matplotlib import or any
    real LLM call."""

    class EoHProfilerStub:
        def __init__(self, log_dir=None, *, initial_num_samples=0, **kwargs):
            del kwargs
            self._log_dir = log_dir
            self._num_samples = int(initial_num_samples or 0)
            self._cur_gen = 0

        def register_function(self, function, program="", *, resume_mode=False):
            del resume_mode
            self._num_samples += 1
            self._write_json(function, program)

        def _write_json(self, function, program="", **kwargs):
            del kwargs

        def register_population(self, pop):
            del pop

        def finish(self):
            return None

        def record_parameters(self, *args, **kwargs):
            del args, kwargs

    class EoHStub:
        _instance_counter = 0

        def __init__(self, **kwargs):
            self.profiler = kwargs.get("profiler")
            self.max_sample_nums = kwargs.get("max_sample_nums")
            self._population = SimpleNamespace(_population=[], _next_gen_pop=[], survival=lambda: None)
            EoHStub._instance_counter += 1
            self._spec_index = min(EoHStub._instance_counter - 1, len(sample_specs) - 1)
            _EOH_INSTANCES.append(self)

        def register_prescored_seed_function(self, function, *, score, algorithm="", operator="seed", sample_time=0.0, evaluate_time=0.0):
            del function, score, algorithm, sample_time, evaluate_time
            self.profiler.register_function(
                _StubFunction(FAR_MARKER, 2.4, operator)
            )
            return True

        def register_seed_function(self, function, *, algorithm="", operator="seed", sample_time=0.0):
            del function, algorithm, sample_time
            self.profiler.register_function(
                _StubFunction(FAR_MARKER, 2.4, operator)
            )
            return True

        def run(self):
            for marker, score in sample_specs[self._spec_index]:
                operator = "e1" if marker == HIT_MARKER else "m1"
                self.profiler.register_function(_StubFunction(marker, score, operator))

    eoh_module = types.ModuleType("llm4ad.method.eoh")
    eoh_module.EoH = EoHStub
    eoh_module.EoHProfiler = EoHProfilerStub
    profiler_module = types.ModuleType("llm4ad.method.eoh.profiler")
    profiler_module.EoHProfiler = EoHProfilerStub
    sys.modules["llm4ad.method.eoh"] = eoh_module
    sys.modules["llm4ad.method.eoh.profiler"] = profiler_module


def _unit_vectors(dim: int = 32, count: int = 8) -> np.ndarray:
    rng = np.random.default_rng(7)
    vectors = rng.normal(size=(count, dim)).astype(np.float32)
    vectors /= np.linalg.norm(vectors, axis=1, keepdims=True)
    return vectors


def _fake_embed(samples: list[dict], *, label: str) -> np.ndarray:
    vectors = _unit_vectors()
    a = vectors[0]
    orth = vectors[1] - float(vectors[1].dot(a)) * a
    orth = (orth / np.linalg.norm(orth)).astype(np.float32)
    b = (a + 0.3 * orth)
    b = (b / np.linalg.norm(b)).astype(np.float32)  # d(a,b) ~ 0.043
    history = vectors[2:5]
    if label == "history":
        return history.copy()
    if label == "anchor":
        return a.reshape(1, -1).copy()
    if label == "direction":
        return b.reshape(1, -1).copy()
    # segment samples: code markers decide the vector.
    out: list[np.ndarray] = []
    for sample in samples:
        code = str(sample.get("function", "") or "")
        if HIT_MARKER in code:
            mid = a + b
            mid = (mid / np.linalg.norm(mid)).astype(np.float32)
            out.append(mid)
        elif NEAR_MARKER in code:
            # Exactly endpoint B: d(near,B)=0 so the lens criterion fails.
            out.append(b)
        else:
            out.append(history[0])
    return np.vstack(out).astype(np.float32)


class RegionRunnerFlowTest(unittest.TestCase):
    def setUp(self):
        self.tmp = Path(tempfile.mkdtemp(prefix="vp_region_test_"))
        _EOH_INSTANCES.clear()

    def tearDown(self):
        import shutil

        shutil.rmtree(self.tmp, ignore_errors=True)

    def _run(
        self,
        *,
        region: dict,
        sample_specs: list[list[tuple[str, float | None]]],
        segments: int = 1,
        samples_per_segment: int = 4,
    ) -> dict:
        _install_eoh_stubs(sample_specs)
        log_dir = self.tmp / "runs" / "region-test" / "log"
        log_dir.mkdir(parents=True, exist_ok=True)
        task = SimpleNamespace(
            template_program="import numpy as np\ndef pack_circles(n):\n    return np.zeros((n, 3))",
            task_description="Implement a circle packing heuristic.",
        )
        history = [
            {"id": "h1", "score": 2.0, "function": "def pack_circles(n):\n    return None"},
            {"id": "h2", "score": 2.4, "function": "def pack_circles(n):\n    return None"},
            {"id": "h3", "score": 2.6, "function": "def pack_circles(n):\n    return None"},
        ]
        endpoint_nodes = [
            {
                "id": "endpoint-a",
                "sampleOrder": 1,
                "score": 2.7,
                "rawScore": 2.7,
                "algorithm": "anchor algo",
                "functionPreview": "def pack_circles(n):\n    return None",
                "operator": "e1",
            },
            {
                "id": "endpoint-b",
                "sampleOrder": 2,
                "score": 2.5,
                "rawScore": 2.5,
                "algorithm": "direction algo",
                "functionPreview": "def pack_circles(n):\n    return None",
                "operator": "e1",
            },
        ]
        method_config = {
            "region_segments": segments,
            "samples_per_segment": samples_per_segment,
            "pop_size": 8,
            "num_samplers": 1,
            "num_evaluators": 1,
        }
        llm_config = {"timeout": 120}
        llm = object()

        patchers = [
            mock.patch.object(region_runner, "_embed_samples", side_effect=_fake_embed),
            mock.patch.object(region_runner, "_load_history_samples", return_value=history),
            mock.patch.object(region_runner, "_champion_avoidance_block", return_value=""),
            mock.patch.object(region_runner, "persist_sample_record"),
            mock.patch.object(region_runner, "update_run_progress"),
            mock.patch.object(region_runner, "merge_real_run_meta"),
            mock.patch.object(region_runner, "record_run_timing"),
            mock.patch.object(region_runner, "has_generated_samples", return_value=True),
            mock.patch.object(region_runner, "hydrate_nodes_from_db", return_value=endpoint_nodes),
            mock.patch("visual_platform.services.revision_generation_service.complete_run"),
        ]
        for patcher in patchers[:-1]:
            patcher.start()
        complete_run = patchers[-1].start()
        try:
            region_runner.run_region_search_mode(
                run_label="region-test",
                log_dir=log_dir,
                task=task,
                llm=llm,
                llm_config=llm_config,
                method_config=method_config,
                prompt="",
                region=region,
                source_revision_id="fake-source",
                model_name="stub",
            )
        finally:
            for patcher in patchers:
                patcher.stop()
        return {"complete_run": complete_run, "log_dir": log_dir}

    def test_edge_region_fills_and_ships(self):
        result = self._run(
            region={"type": "edge", "a": "endpoint-a", "b": "endpoint-b"},
            sample_specs=[[(HIT_MARKER, 2.6), (NEAR_MARKER, 2.55), (FAR_MARKER, None)]],
            segments=1,
        )
        complete_run = result["complete_run"]
        self.assertTrue(complete_run.called)
        call_kwargs = complete_run.call_args
        result_payload = call_kwargs.kwargs.get("result") or call_kwargs.args[1]
        self.assertEqual(result_payload["verdict"], "FILLED")
        self.assertEqual(result_payload["ships"], 2)
        self.assertEqual(result_payload["valid"], 2)
        self.assertIn("coverage", result_payload)
        self.assertIn("conclusion", result_payload)
        self.assertEqual(result_payload["fusionMode"], "none")
        ledger = (result["log_dir"].parent / "region_ledger.jsonl").read_text(encoding="utf-8")
        records = [json.loads(line) for line in ledger.splitlines() if line.strip()]
        self.assertEqual(len(records), 2)  # one segment + final
        self.assertEqual(records[0]["hit_count"], 1)
        report = (result["log_dir"].parent / "region_report.md").read_text(encoding="utf-8")
        self.assertIn("FILLED", report)

    def test_segment_budget_leaves_room_for_new_samples(self):
        """种子也会占用 EoH 的采样预算，所以每段预算必须是「每段样本数 + 种子数」。

        修复前 max_sample_nums 直接等于 samples_per_segment：edge 区域有两个种子
        （A、B 都是种子节点）时，每段样本数=2 会把预算占满，EoH 循环一次都不进，
        本段生成 0 个新解，报告却给 BUDGET_OUT + 「新颖率 0%」，看着像"区域没货"。
        """
        result = self._run(
            region={"type": "edge", "a": "endpoint-a", "b": "endpoint-b"},
            sample_specs=[[(FAR_MARKER, 2.0)]],
            segments=1,
            samples_per_segment=2,
        )
        ledger = (result["log_dir"].parent / "region_ledger.jsonl").read_text(encoding="utf-8")
        records = [json.loads(line) for line in ledger.splitlines() if line.strip()]
        seed_count = len(records[0]["seeds"])
        self.assertGreater(seed_count, 0)
        self.assertEqual(_EOH_INSTANCES[-1].max_sample_nums, 2 + seed_count)
        self.assertGreater(_EOH_INSTANCES[-1].max_sample_nums, 2)

    def test_expand_region_fractures_after_two_drift_segments(self):
        result = self._run(
            region={"type": "expand", "a": "endpoint-a"},
            sample_specs=[
                [(FAR_MARKER, 2.0)],
                [(FAR_MARKER, None)],
                [(FAR_MARKER, 2.0)],
            ],
            segments=3,
        )
        complete_run = result["complete_run"]
        result_payload = complete_run.call_args.kwargs.get("result") or complete_run.call_args.args[1]
        self.assertEqual(result_payload["verdict"], "FRACTURE")
        ledger = (result["log_dir"].parent / "region_ledger.jsonl").read_text(encoding="utf-8")
        records = [json.loads(line) for line in ledger.splitlines() if line.strip()]
        # Stopped after two drift segments (third spec never used).
        self.assertEqual(len(records), 3)  # two segments + final
        self.assertTrue(all(record["drift"] for record in records[:-1]))


if __name__ == "__main__":
    unittest.main(verbosity=2)
