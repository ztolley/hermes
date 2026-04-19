# Health And Performance Baseline

This document records the known-good DGX Spark profile for the Compose stack.
Update it when changing model images, context, memory utilization, ports, or
autocomplete models.

## Stable Profile

- Open WebUI: `http://spark-1.local:3000`
- Qwen3 Coder Next 80B NVFP4: `http://spark-1.local:3001/v1`
- Qwen autocomplete: `http://spark-1.local:3002/v1`
- Hermes gateway: `http://spark-1.local:8000/v1`

Large model:
- image: `avarok/dgx-vllm-nvfp4-kernel:v23`
- model: `saricles/Qwen3-Coder-Next-NVFP4-GB10`
- `QWEN_GPU_MEMORY_UTILIZATION=0.62`
- `QWEN_MAX_MODEL_LEN=131072`
- `QWEN_MAX_NUM_SEQS=2`
- NVFP4 backend: Marlin fallback

Autocomplete model:
- image: `vllm-node:latest`
- model: `Qwen/Qwen2.5-Coder-3B`
- `AUTOCOMPLETE_GPU_MEMORY_UTILIZATION=0.08`
- `AUTOCOMPLETE_MAX_MODEL_LEN=4096`

## Last Observed Runtime

Observed on April 19, 2026 with both model containers running:

- Large Qwen GPU process memory: about `65.3 GiB`
- Autocomplete GPU process memory: about `9.7 GiB`
- Large Qwen model load memory: `42.7 GiB`
- Large Qwen available KV cache memory: `18.81 GiB`
- Large Qwen GPU KV cache size: `205,088 tokens`
- Large Qwen reported max concurrency at 131k context: `6.11x`
- Autocomplete model load memory: `5.79 GiB`
- Autocomplete available KV cache memory: `1.49 GiB`
- Autocomplete GPU KV cache size: `43,248 tokens`

The large model is capped by `QWEN_MAX_NUM_SEQS=2`, so the reported `6.11x`
capacity is headroom, not the active request concurrency limit.

## Health Checks

```bash
docker compose ps
curl http://127.0.0.1:3001/v1/models
curl http://127.0.0.1:3002/v1/models
curl http://127.0.0.1:8000/health
```

For Hermes model routing:

```bash
set -a
. ./.env
set +a

curl http://127.0.0.1:8000/v1/models \
  -H "Authorization: Bearer ${HERMES_API_KEY}"
```

## Benchmarking

Run the benchmark script from the repo root:

```bash
python3 scripts/benchmark_endpoints.py --runs 2
```

Record the output before and after any tuning change. Focus on:
- time to first token
- total latency
- output tokens per second
- whether all endpoints still respond

Baseline run on April 19, 2026:

```text
qwen-large: median_ttft_s=3.548, median_output_tok_s=51.41
qwen-autocomplete: median_ttft_s=0.068, median_output_tok_s=31.07
hermes-gateway: median_ttft_s=2.867
```

The script measures streaming time-to-first-token and non-streaming throughput
as separate requests, so treat the numbers as comparison baselines rather than
as a single end-to-end trace.

## Tuning Candidates

Safe first experiments:
- `QWEN_MAX_MODEL_LEN=196608` with `QWEN_MAX_NUM_SEQS=2`
- a slightly higher `QWEN_GPU_MEMORY_UTILIZATION`, only if the autocomplete
  service still starts reliably
- alternate autocomplete models, measured against `Qwen/Qwen2.5-Coder-3B`

Riskier experiments:
- `QWEN_MAX_MODEL_LEN=262144`
- `QWEN_MAX_NUM_SEQS=4`
- speculative decoding for the large model
- larger autocomplete models such as 7B-class coder models

Use `compose.override.yml.example` as the starting point for experiments.

## Autocomplete Model Notes

The current small autocomplete model is `Qwen/Qwen2.5-Coder-3B`. Public model
guidance generally treats Qwen2.5-Coder as a strong local code model family,
with 3B being the practical low-latency choice and 7B offering a possible
quality improvement at higher latency and memory cost.

Do not assume a larger autocomplete model is automatically better for VS Code.
Autocomplete quality depends heavily on prompt shape, fill-in-the-middle support,
context truncation, and editor integration behavior. Benchmark any candidate
against real files before making it the default.
