# Health And Performance Baseline

This document records the known-good DGX Spark profile for the Compose stack.
Update it when changing model images, context, memory utilization, ports, or
serving profiles.

## Stable Profile

- Open WebUI: `http://spark-1.local:3000`
- Qwen3 Coder Next 80B NVFP4: `http://spark-1.local:3001/v1`
- Hermes gateway: `http://spark-1.local:8000/v1`

Large model:
- image: `avarok/dgx-vllm-nvfp4-kernel:v23`
- model: `saricles/Qwen3-Coder-Next-NVFP4-GB10`
- `QWEN_GPU_MEMORY_UTILIZATION=0.62`
- `QWEN_MAX_MODEL_LEN=131072`
- `QWEN_MAX_NUM_SEQS=2`
- NVFP4 backend: Marlin fallback

## Last Observed Runtime

Observed on April 20, 2026 after moving Continue autocomplete to the large
model and removing the standalone autocomplete service:

- Large Qwen GPU process memory: about `77.1-77.8 GiB`
- Open WebUI container memory: about `0.7 GiB`
- Hermes container memory: about `0.2 GiB`
- Memory reclaimed from removing the standalone autocomplete service: about
  `10.8 GiB`

The optional Qwen3-VL vision server is not part of the stable profile. It is
behind the `vision` Compose profile and should be measured separately before it
is left running.

The large model is capped by `QWEN_MAX_NUM_SEQS=2`, so the reported `6.11x`
capacity is headroom, not the active request concurrency limit.

## Health Checks

```bash
docker compose ps
curl http://127.0.0.1:3001/v1/models
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
hermes-gateway: median_ttft_s=2.867
```

Warm baseline run on April 20, 2026 after 12 hours uptime:

```text
qwen-large: median_ttft_s=0.080, median_output_tok_s=50.98
hermes-gateway: median_ttft_s=2.819
```

Post-restart run on April 20, 2026 after removing autocomplete:

```text
qwen-large: median_ttft_s=0.073, median_output_tok_s=51.19
hermes-gateway: median_ttft_s=2.867
```

The script measures streaming time-to-first-token and non-streaming throughput
as separate requests, so treat the numbers as comparison baselines rather than
as a single end-to-end trace.

## Tuning Candidates

Safe first experiments:
- optional `qwen-vl` profile for local image understanding
- `QWEN_MAX_MODEL_LEN=196608` with `QWEN_MAX_NUM_SEQS=2`
- a slightly higher `QWEN_GPU_MEMORY_UTILIZATION`, now that the large model is
  the only local text model server

Riskier experiments:
- `QWEN_MAX_MODEL_LEN=262144`
- `QWEN_MAX_NUM_SEQS=4`
- speculative decoding for the large model

Use `compose.override.yml.example` as the starting point for experiments.
