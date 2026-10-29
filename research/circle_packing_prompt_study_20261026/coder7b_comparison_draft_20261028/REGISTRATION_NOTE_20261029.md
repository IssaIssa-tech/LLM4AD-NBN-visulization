# Registered execution configuration — 2026-10-29

The folder/revision suffix 20261028 identifies the previously prepared draft. Actual registration timestamps in registration.json are authoritative; execution is being started on 2026-10-29 local time.

Installed package qwen2.5-coder:7b, Q4_K_M, digest `dae161e27b0e90dd1856c8bb3209201fd6736d8eb66298e75ed87571486f4364`. New model-aware runner: run_coder7b_comparison.py. The old model-pinned runner and its completed experiments remain unchanged.

All fourteen saved prompt texts and parent programs were compared to their original broad-comparison counterparts and match. Evaluator hashes, Python/numpy/scipy versions, graph identity, twenty-second evaluation timeout and 900-second model-response timeout match the baseline. Model sampling retains temperature 0.1, 1800 generated-token cap and the paired parent-specific seeds. Sixteen analytical slots still share fourteen unique calls.

All eight GPUs currently have active workloads. The isolated loopback service on port 11436 has CUDA visibility -1. Requests explicitly set num_gpu=0, num_thread=4 and num_ctx=32768. The model metadata advertises a 32768 context. Every saved prompt is under 8192 UTF-8 bytes (maximum about 4642 bytes); actual prompt_eval_count will be preserved in raw responses. This byte-size preflight is not an exact tokenizer count. Inspect actual counts and any truncation indicators before interpreting outcomes.

These CPU/context settings are explicit serving differences relative to incompletely recorded earlier defaults. Thus the experiment is a model-package comparison, not a pure model-size ablation or controlled timing benchmark. The new CPU service uses no shared GPU allocation. System load may still affect runtime. The existing 900-second response timeout is retained rather than silently increased for a larger model; preserve any model timeouts as failures and do not resend automatically.

No repairs, resampling, manual patches or replacement candidates are allowed. Record all responses, code, scores, coordinates when available and failures in the new platform history revision. Review static-contract compliance separately from geometry and quality. Target 2.6360 remains unachieved by prior runs; this registration claims no future improvement, structural diversity or official-verifier equivalence.
