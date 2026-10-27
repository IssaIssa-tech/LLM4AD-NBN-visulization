"""Generate frozen M2-R trials via a local Ollama endpoint; no evaluation here."""
from __future__ import annotations

import hashlib
import json
import re
import urllib.request
from datetime import datetime, timezone
from pathlib import Path


ROOT = Path(__file__).resolve().parent
MANIFEST_PATH = ROOT / "run_manifest.json"


def extract_code(response: str) -> str:
    match = re.search(r"```(?:python)?\s*(.*?)```", response, flags=re.DOTALL | re.IGNORECASE)
    return match.group(1).strip() if match else response.strip()


def request(endpoint: str, model: str, prompt: str, temperature: float, num_predict: int, seed: int) -> dict:
    body = json.dumps({
        "model": model,
        "prompt": prompt,
        "stream": False,
        "keep_alive": "0",
        "options": {"temperature": temperature, "seed": seed, "num_predict": num_predict},
    }).encode("utf-8")
    req = urllib.request.Request(
        endpoint.rstrip("/") + "/api/generate", data=body,
        headers={"Content-Type": "application/json"}, method="POST",
    )
    with urllib.request.urlopen(req, timeout=600) as response:
        return json.loads(response.read().decode("utf-8"))


def main() -> None:
    manifest = json.loads(MANIFEST_PATH.read_text(encoding="utf-8"))
    endpoint = "http://127.0.0.1:11435"
    ledger = ROOT / "generation_ledger.jsonl"
    for trial in manifest["trials"]:
        trial_dir = ROOT / trial["trial_id"]
        prompt = (trial_dir / "prompt.txt").read_text(encoding="utf-8")
        record = {
            "trial_id": trial["trial_id"],
            "timestamp_utc": datetime.now(timezone.utc).isoformat(),
            "model": manifest["model"],
            "endpoint": endpoint,
            "temperature": manifest["temperature"],
            "num_predict": manifest["num_predict"],
            "sampling_seed": trial["sampling_seed"],
            "prompt_sha256": hashlib.sha256(prompt.encode("utf-8")).hexdigest(),
            "generation_status": "requested",
        }
        try:
            payload = request(endpoint, manifest["model"], prompt, manifest["temperature"], manifest["num_predict"], trial["sampling_seed"])
            raw = str(payload.get("response", ""))
            (trial_dir / "response.txt").write_text(raw, encoding="utf-8")
            code = extract_code(raw) + "\n"
            (trial_dir / "candidate.py").write_text(code, encoding="utf-8")
            record.update({
                "generation_status": "completed",
                "response_sha256": hashlib.sha256(raw.encode("utf-8")).hexdigest(),
                "code_sha256": hashlib.sha256(code.encode("utf-8")).hexdigest(),
                "eval_count": payload.get("eval_count"),
                "total_duration_ns": payload.get("total_duration"),
            })
        except Exception as exc:
            record.update({"generation_status": "failed", "error": f"{type(exc).__name__}: {exc}"})
        with ledger.open("a", encoding="utf-8") as stream:
            stream.write(json.dumps(record, ensure_ascii=False) + "\n")
        print(f"{trial['trial_id']}: {record['generation_status']}", flush=True)


if __name__ == "__main__":
    main()
