# Coder 7B comparison: serving failure, not an algorithm-quality result

All fourteen registered requests reached a terminal outcome. Each recorded `TimeoutError: timed out`, after 900.015–900.102 seconds. History contains fourteen llm_request events, fourteen pipeline_failure events, fourteen trial_completed events, and a comparison_completed marker. No llm_response or evaluation_started event was recorded. There are no captured generated programs or candidate scores from this condition.

Interpretation: the registered deadline-to-response outcome is 0/14, but there are zero evaluated algorithms. Do not report these as fourteen geometrically invalid algorithms or as proof that Coder 7B is worse than the 3B model at code generation. The model-quality/selection comparison is unresolved because usable generation never reached evaluation. No experimental request was resent or given a longer timeout.

## Serving evidence

The service is isolated on port 11436, Ollama version 0.13.5, CUDA visibility -1, CPU-only. Logs show model tensors and a 32768-token CPU context loaded; runner startup was reported at about 5.6 seconds. HTTP generate entries end with status 500 around fifteen minutes. Some log entries explicitly report client disconnection. This is consistent with the recorded client deadlines, not evidence of an independently diagnosed model failure. The allocation was CPU, not GPU. Plenty of system RAM was available in the snapshot; this alone cannot exclude CPU/runtime contention or software issues.

The exact root cause remains undetermined. Do not claim deadlock, incompatibility, insufficient model capability or that a larger context caused the failure without further diagnostic evidence. With non-streaming experimental responses, no intermediate tokens were captured; absence of a final reply does not establish zero internal generation.

## One separate diagnostic call

After the experiment, one separately recorded probe used prompt `Reply with OK.`, num_predict=1, num_ctx=2048, num_thread=4, num_gpu=0, stream=true, temperature=0 and a 45-second socket timeout. It timed out at 45.053 seconds with zero received chunks. Its request and outcome are in output/coder_service_probe_20261029. This is one service diagnostic, not a research candidate or an additional trial in the fourteen-request comparison. It changes context/output length and uses a shorter deadline, so it is not an isolated ablation.

The probe's log also reports CPU model loading in about 5.6 seconds, followed by a 45-second HTTP 500. Its lingering runner was identified by parent PID 2471767 and the private model-blob path before receiving SIGTERM. No shared Ollama service or other researcher's process was stopped. The private API service itself remains available.

## Next action

Do not schedule another full batch on the same unvalidated serving path. First establish successful short streamed inference on an isolated, verified runtime—potentially a reserved GPU or separately configured CPU runtime—and measure response behavior. Any runtime upgrade, attention setting or device change requires a recorded diagnostic configuration and must not alter the completed registration. Benchmark a representative prompt before registering a new research condition. Preserve diagnostic calls separately and record any additional compute cost.

The original matched prompts, parents, model digest and failures remain available. A future successful condition must get a new revision and explicit serving settings; these fourteen failed attempts cannot be replaced. No change to official-verifier compatibility, target achievement or NBN structural-diversity conclusions is supported.
