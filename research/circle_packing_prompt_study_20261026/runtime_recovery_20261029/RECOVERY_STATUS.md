# Runtime recovery checkpoint — 2026-10-29

Research objective unchanged: compare historical-program selection and prompts using NBN information for Circle Packing N=26, assess quality and structural diversity against the 2.6360 target, and preserve complete histories. No new Circle Packing experiment was launched during this runtime work. Prior failed model requests remain unchanged.

## Recorded runtime checks

1. hits_1: explicitly disabling automatic attention in the old Ollama engine still timed out at 45 seconds with no received chunks.
2. hits_1: the alternate engine returned a completed one-token API response in 1.89 seconds, but no visible text. Its negative reported eval_duration is invalid telemetry and is not a speed measurement.
3. hits_1: a separate visible-output check returned `OK` in 15.55 seconds. This demonstrates short inference, not research-prompt readiness.
4. hits_1: the capped full-length prompt check on that engine timed out at 180 seconds with no captured chunks. Thus no full CPU batch was authorized by these readiness results.
5. hits_1: the free-memory/utilization guard found no eligible GPU at launch. That check made zero model calls. Availability changed between the initial snapshot and the guarded launch.
6. hits_9: direct access works and six RTX 3090 devices were idle with approximately 24 GiB free each at the snapshot. The model cache was copied to a new private directory. The full model-blob SHA-256 verified as `60e05f2100071479f596b964f89f510f057ce397ea22f2833a0cfe029bfc2463`, matching the installed Qwen Coder 7B weights. No new model weights were downloaded.
7. hits_9: copying the small Ollama binary did not provide a usable GPU runtime. Some CUDA files in hits_1's installation were unreadable or missing; those copy failures were not bypassed by changing permissions. The isolated check reported CPU-only allocation and timed out at 90 seconds. Its private process group was stopped; no shared processes were stopped.

These are service diagnostics, not generated optimization discoveries. Partial text is not evaluated as a candidate. The attention/engine changes do not establish the precise cause of all earlier timeouts.

## Private GPU-runtime preparation in progress

Private directory on hits_9: `/home/dyy/issa_nbn_runtime_20261029/`.

A complete official Ollama 0.13.5 archive was attempted privately, but downloaded only a few MiB in several minutes. Only that identified private download process was stopped. Its partial archive and stop note remain preserved. The replacement is a smaller pinned source build of [llama.cpp release b6780](https://github.com/ggml-org/llama.cpp/releases/tag/b6780), with private CMake 3.31.6 verified against the PyPI wheel digest, CUDA architecture 86 and four compilation jobs. This changes the serving package and must be registered explicitly before research use; it is not an unchanged-model-runtime ablation.

`build_hits9_gpu_runtime.py` records downloads, source hashes, build logs and failure states. On build success it permits one 32-token representative-prompt check only if a GPU is idle with at least 16 GiB free. It records the request, response, GPU and timing, then stops its own diagnostic server to release memory. It does not run or repair an algorithm or launch a research batch.

At this checkpoint, private build-tool retrieval completed and the source archive was still downloading. GPU inference is **not yet verified**. Check `llama_gpu_runtime_b6780/progress.json`, `failure.json`, and `readiness.json` on hits_9 before taking further action. Do not rerun the setup script over an existing folder.

## Cross-server clock warning for provenance

Nearly simultaneous read-only snapshots returned hits_1 UTC `2026-10-29T14:16:07Z` and hits_9 UTC `2026-10-29T22:23:49Z`, an approximately 8h 7m 42s disagreement. Shared server clocks were not changed. Cross-host ordering must use source host, request IDs and controller timing; do not infer chronology by sorting their raw UTC strings alone. Elapsed durations measured with monotonic clocks remain local measurements.

## Research boundary after readiness

Once full-prompt GPU inference is verified, prepare one finite comparison with fixed quality-only versus NBN-region parent pools and the existing prompt profiles, matched budgets and the unchanged evaluator on hits_1. Register the serving/host differences and every call before execution. Finish with a preliminary evidence report even if the target is not attained. Do not introduce additional repair loops or keep trying prompt variants until a winning result appears. This boundary supports the supervisor's investigation rather than replacing it.
