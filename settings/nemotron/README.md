This directory is for Nemotron-side project settings and runtime templates.

Current layout:
- `extra-llm-api-config.yml.template`
  Rendered at container startup for TensorRT-LLM's `trtllm-serve` config.
- `mods/nemotron-super/`
  Legacy placeholder directory from the earlier vLLM-based stack.

The current stack uses NVIDIA's TensorRT-LLM Spark settings for Nemotron 3
Super and keeps them in a repo-local template so the defaults are visible and
versioned alongside the compose file.
