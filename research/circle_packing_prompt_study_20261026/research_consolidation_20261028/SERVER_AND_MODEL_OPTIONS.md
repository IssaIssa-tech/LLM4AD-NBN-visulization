# Server snapshot and model-package options

Read-only check on 2026-10-28. Availability is transient; this is not a GPU reservation. No model was downloaded, loaded, removed or benchmarked, and no shared process was changed.

Eight NVIDIA RTX 4090 GPUs, each reporting 24,564 MiB total VRAM:

| GPU | Used MiB | Utilization percent |
|---|---:|---:|
| 0 | 20539 | 79 |
| 1 | 21288 | 36 |
| 2 | 16636 | 33 |
| 3 | 17949 | 74 |
| 4 | 16277 | 36 |
| 5 | 17757 | 26 |
| 6 | 18420 | 42 |
| 7 | 8358 | 38 |

All devices have active workloads. GPU 7 has the most unallocated VRAM in this snapshot, but is not idle or reserved for this project. Free memory alone is not authorization to occupy a shared device. `/mnt/data` reports approximately 940 GB available.

Our loopback Ollama service at port 11435 lists only qwen2.5:3b, Q4_K_M, digest `357c53fb659c5076de1d65ccb0b397446227b71a42be9d1603d46168015c9e4b`. Its `/api/ps` response lists no currently loaded model. This does not inventory every model file on the shared server, nor prove that every other service is idle.

## Proposed candidates, not verified installations

- [Qwen2.5-Coder 7B Ollama package](https://ollama.com/library/qwen2.5-coder:7b): official listing gives 4.7 GB model size and Q4_K_M. This is a lower-resource candidate for a first code-specialized pilot. Disk size is not total inference VRAM; context/KV cache and serving overhead also matter.
- [Qwen2.5-Coder 14B Ollama package](https://ollama.com/library/qwen2.5-coder:14b): official listing gives 9.0 GB model size and Q4_K_M. Consider when a suitable GPU allocation is available, not by assuming it fits safely into current shared workloads.
- [Upstream Qwen2.5-Coder-14B-Instruct model card](https://huggingface.co/Qwen/Qwen2.5-Coder-14B-Instruct): identifies the code-specialized open-weight model and Apache-2.0 license. Its behavior on this Circle Packing task has not been measured here.

Recommendation: prepare one model-package comparison using Coder 7B first, contingent on resource availability and an isolated installation. Keep one previously registered fourteen-request condition's prompts, parents, evaluator and generation cap fixed. Freeze actual downloaded digest, template and context configuration before any experiment. The larger/code-specialized model is a hypothesis for improving executable delivery, not a guaranteed improvement or proof of NBN guidance. Do not silently fall back to a different model if resources are unavailable.

Sources checked on 2026-10-28. These two package choices are practical comparisons within the existing Qwen/Ollama setup, not a claim that they are the latest or globally best coding models.
