from __future__ import annotations

from typing import Any

from flask import Blueprint, jsonify, request
from visual_platform.runtime.runner_llm import probe_real_llm
from visual_platform.services.translation_service import translate_algorithm_text
from visual_platform.services.expert_adapt_service import adapt_expert_solution_code
from visual_platform.importer.history import list_history_sources
from visual_platform.services.region_service import recommend_regions

def create_misc_blueprint() -> Blueprint:
    bp = Blueprint("misc_routes", __name__)

    @bp.post("/api/test-llm")
    def api_test_llm() -> Any:
        payload = request.get_json(silent=True) or {}
        llm_config = payload.get("llm", {})
        if not isinstance(llm_config, dict):
            llm_config = {}

        try:
            result = probe_real_llm(llm_config)
            return jsonify(result)
        except Exception as error:
            return jsonify({"ok": False, "error": str(error)})

    @bp.post("/api/translate-algorithm")
    def api_translate_algorithm() -> Any:
        payload = request.get_json(silent=True) or {}
        text = str(payload.get("text", "") or "")
        llm_config = payload.get("llm", {})
        if not isinstance(llm_config, dict):
            llm_config = {}

        try:
            translated_text = translate_algorithm_text(text, llm_config)
            return jsonify({"ok": True, "translatedText": translated_text})
        except Exception as error:
            return jsonify({"ok": False, "error": str(error), "translatedText": text.strip()})

    @bp.post("/api/expert/adapt")
    def api_expert_adapt() -> Any:
        payload = request.get_json(silent=True) or {}
        raw_code = str(payload.get("functionText", payload.get("code", "")) or "")
        llm_config = payload.get("llm", {})
        if not isinstance(llm_config, dict):
            llm_config = {}
        time_budget_seconds = int(payload.get("timeBudgetSeconds", 300) or 300)

        try:
            result = adapt_expert_solution_code(
                raw_code,
                llm_config,
                time_budget_seconds=time_budget_seconds,
            )
            return jsonify(result)
        except Exception as error:
            return jsonify({"ok": False, "error": str(error)})

    @bp.post("/api/regions/recommend")
    def api_region_recommend() -> Any:
        payload = request.get_json(silent=True) or {}
        revision_id = str(payload.get("revisionId", "") or "").strip()
        if not revision_id:
            return jsonify({"ok": False, "error": "缺少 revisionId。"}), 400
        try:
            result, error = recommend_regions(revision_id)
            if error is not None:
                return jsonify({"ok": False, "error": error}), 409
            return jsonify({"ok": True, "data": result})
        except Exception as error:
            return jsonify({"ok": False, "error": str(error)}), 500

    @bp.get("/api/defaults")
    def api_defaults() -> Any:
        return jsonify(
            {
                "mode": "direct_ai",
                "historyImport": {
                    "defaultSource": "circle_packing_history",
                    "sources": list_history_sources(),
                },
                "llm": {
                    "host": _default_llm_host(),
                    "key": "",
                    "model": _default_llm_model(),
                    "thinking": _default_llm_thinking(),
                    "timeout": 60,
                },
                "method": {
                    "max_sample_nums": 64,
                    "max_generations": 8,
                    "pop_size": 8,
                    "num_samplers": 4,
                    "num_evaluators": 4,
                    "timeout_seconds": 120,
                    "distance_metric": "codet5p_embedding_cosine",
                    "region_segments": 5,
                    "samples_per_segment": 30,
                    "fusion_mode": "none",
                },
            }
        )

    return bp


def _default_llm_host() -> str:
    import os

    return str(os.getenv("VISUAL_PLATFORM_LLM_HOST", "") or "").strip()


def _default_llm_model() -> str:
    import os

    return str(os.getenv("VISUAL_PLATFORM_LLM_MODEL", "") or "").strip()


def _default_llm_thinking() -> str:
    """Default to reasoning disabled: EOH's code parser treats a chain of
    thought as code, so the configured DeepSeek model must not emit one."""
    import os

    return str(os.getenv("VISUAL_PLATFORM_LLM_THINKING", "disabled") or "disabled").strip()
