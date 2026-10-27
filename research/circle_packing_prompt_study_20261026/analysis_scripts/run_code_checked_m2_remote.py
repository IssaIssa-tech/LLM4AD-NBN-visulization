"""Run a pre-registered M2 generation with at most one error-informed repair."""
from __future__ import annotations

import hashlib
import json
import re
import sys
import urllib.request
from datetime import datetime, timezone
from pathlib import Path


ROOT = Path(__file__).resolve().parent
sys.path.insert(0, str(ROOT))
from evaluate_circle_prompt_candidates import evaluate  # noqa: E402


def extract_code(response: str) -> str:
    match = re.search(r"```(?:python)?\s*(.*?)```", response, flags=re.DOTALL | re.IGNORECASE)
    return match.group(1).strip() if match else response.strip()


def generate(endpoint: str, model: str, prompt: str, temperature: float, num_predict: int, seed: int) -> dict:
    body = json.dumps({"model": model, "prompt": prompt, "stream": False, "keep_alive": "0", "options": {"temperature": temperature, "seed": seed, "num_predict": num_predict}}).encode("utf-8")
    request = urllib.request.Request(endpoint.rstrip("/") + "/api/generate", data=body, headers={"Content-Type": "application/json"}, method="POST")
    with urllib.request.urlopen(request, timeout=600) as response:
        return json.loads(response.read().decode("utf-8"))


def repair_prompt(code: str, status: str, error: object) -> str:
    detail = str(error) if error else status
    return f"""Return exactly one Python code block and no explanation outside it.
The following Circle Packing candidate failed the recorded 8-second precheck:
`{detail}`.
Return a minimal corrected version of this exact candidate. Preserve its
intended structural mechanism and do not add a new algorithmic mechanism.
The code must define only `pack_circles(n: int) -> np.ndarray`, use only numpy,
math, or scipy submodules, have no helper functions or top-level execution,
and return finite `(n, 3)` circles inside the unit square with all-pairs
non-overlap. Use bounded loops only. Re-check syntax and all referenced names.

Candidate to repair:
```python
{code}
```
"""


def main() -> None:
    manifest = json.loads((ROOT / "run_manifest.json").read_text(encoding="utf-8"))
    endpoint = "http://127.0.0.1:11435"
    ledger = ROOT / "generation_ledger.jsonl"
    outcomes = []
    for trial in manifest["trials"]:
        directory = ROOT / trial["trial_id"]
        initial_prompt = (directory / "initial_prompt.txt").read_text(encoding="utf-8")
        row = {"trial_id": trial["trial_id"], "sampling_seed": trial["sampling_seed"], "initial": {}, "repair": None, "final": None}
        try:
            generated = generate(endpoint, manifest["model"], initial_prompt, manifest["temperature"], manifest["num_predict"], trial["sampling_seed"])
            response = str(generated.get("response", ""))
            initial_code = extract_code(response) + "\n"
            (directory / "initial_response.txt").write_text(response, encoding="utf-8")
            (directory / "initial_candidate.py").write_text(initial_code, encoding="utf-8")
            precheck = evaluate(directory / "initial_candidate.py", manifest["precheck_timeout_seconds"])
            row["initial"] = {"code_sha256": hashlib.sha256(initial_code.encode("utf-8")).hexdigest(), "precheck": precheck, "eval_count": generated.get("eval_count")}
            final_path = directory / "initial_candidate.py"
            if precheck["status"] != "valid":
                prompt = repair_prompt(initial_code, precheck["status"], precheck.get("error"))
                (directory / "repair_prompt.txt").write_text(prompt, encoding="utf-8")
                repaired = generate(endpoint, manifest["model"], prompt, manifest["temperature"], manifest["num_predict"], trial["sampling_seed"])
                repair_response = str(repaired.get("response", ""))
                repair_code = extract_code(repair_response) + "\n"
                (directory / "repair_response.txt").write_text(repair_response, encoding="utf-8")
                final_path = directory / "repaired_candidate.py"
                final_path.write_text(repair_code, encoding="utf-8")
                repair_precheck = evaluate(final_path, manifest["precheck_timeout_seconds"])
                row["repair"] = {"prompt_sha256": hashlib.sha256(prompt.encode("utf-8")).hexdigest(), "code_sha256": hashlib.sha256(repair_code.encode("utf-8")).hexdigest(), "precheck": repair_precheck, "eval_count": repaired.get("eval_count")}
            passed = row["repair"]["precheck"]["status"] == "valid" if row["repair"] else precheck["status"] == "valid"
            row["final"] = evaluate(final_path, manifest["full_timeout_seconds"]) if passed else {"status": "not_full_evaluated_precheck_failed", "score": None}
        except Exception as exc:
            row["final"] = {"status": "pipeline_error", "score": None, "error": f"{type(exc).__name__}: {exc}"}
        row["timestamp_utc"] = datetime.now(timezone.utc).isoformat()
        outcomes.append(row)
        with ledger.open("a", encoding="utf-8") as stream:
            stream.write(json.dumps(row, ensure_ascii=False) + "\n")
        print(f"{trial['trial_id']}: {row['final']['status']}", flush=True)
    (ROOT / "results.json").write_text(json.dumps({"manifest": manifest, "outcomes": outcomes}, indent=2, ensure_ascii=False), encoding="utf-8")


if __name__ == "__main__":
    main()
