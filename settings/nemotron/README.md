This directory is for Nemotron-side project settings and runtime templates.

Current layout:
- `extra-llm-api-config.yml.template`
  Rendered at container startup for TensorRT-LLM's `trtllm-serve` config.

The current stack runs Nemotron 3 Super through NVIDIA's TensorRT-LLM
container and keeps the serve-time settings in a repo-local template so the
runtime knobs are visible and versioned alongside the compose file.

The repo defaults are tuned for the validated DGX Spark coexistence profile:
- `NEMOTRON_GPU_MEMORY_UTILIZATION=0.75`
- `NEMOTRON_MAX_MODEL_LEN=131072`
- `NEMOTRON_MAX_NUM_SEQS=4`
- `NEMOTRON_MAX_NUM_TOKENS=8192`

Raise those values only if the Spark is more dedicated to Nemotron and you have
confirmed the extra memory headroom on the live machine.
