# Comparison readiness check

Checked on 2026-10-28. This is a preflight record, not an experimental result.

- Direct SSH to hits_1 succeeded.
- Isolated platform history API returned HTTP 200 for `circle-history-verified-20261028`.
- Ollama on server loopback port 11435 lists `qwen2.5:3b`, Q4_K_M, digest `357c53fb659c5076de1d65ccb0b397446227b71a42be9d1603d46168015c9e4b`.
- All fourteen saved prompt hashes and parent-code hashes passed local verification. The manifest has sixteen analytical slots sharing fourteen unique requests.
- Remote reference-evaluation script SHA-256: `e056ae48460c9edb9f4b564aab49e58efdf6df808ad2bc7817c8c74581e1767b`.
- Remote screening/geometry utility SHA-256: `c2be5f5413ff066badd3b79c4b2a6eea685953f48b7b52ba0373e2ec204ae4d7`.

No new LLM call, evaluation, or running comparison job was started in this check. The comparison remains a draft. Next implementation work is an immutable registration and resumable runner that binds every unique request, response, evaluation and failure to platform history before generation. Freeze the actual dependency environment and execution order there. The existing twenty-second limit remains a named research condition; official verifier equivalence has not been established.

Git commit `87f51e7` contains the draft comparison. Local main was clean and aligned with the locally recorded origin/main at this check; no new remote comparison results were inferred from that status.
