# Model Hosting Experiments

This document records the next safe experiments for the DGX Spark stack. Keep
the default Compose profile stable; use `.env` changes and measured restarts for
one experiment at a time.

## Current Baseline

Observed on April 20, 2026 after proving Continue works well against the large
model and removing the standalone autocomplete service:

- Large Qwen GPU process memory: about `77.8 GiB`
- Open WebUI container memory: about `0.7 GiB`
- Hermes container memory: about `0.2 GiB`
- Total vLLM GPU process memory: about `77.8 GiB`
- Memory reclaimed: about `10.8 GiB`

Benchmark from `python3 scripts/benchmark_endpoints.py --runs 2`:

```text
qwen-large: median_ttft_s=0.080, median_output_tok_s=50.98
hermes-gateway: median_ttft_s=2.819
```

The large model also handled a completion-style autocomplete probe on
`/v1/completions` at about `59 output tokens/s` for a short prompt. That makes
it worth testing Continue against the large endpoint before changing model
hosting. Continue has since been switched to that endpoint and works well.

## Editor Autocomplete

Continue/Roo should point at:

```text
http://spark-1.local:3001/v1
```

Use model:

```text
saricles/Qwen3-Coder-Next-NVFP4-GB10
```

The previous small autocomplete service and its cache have been removed.

## Experiment 1: Speculative Decoding

Do not assume a generic small Qwen model will improve Qwen3 Coder Next. Qwen
2.5 Coder 3B has the same vocabulary size, but it is a different model family
(`qwen2` vs `qwen3_next`), so acceptance rate may be poor. It may also consume
roughly the same memory that was just reclaimed.

The running Qwen image uses vLLM `0.16.0rc2.dev236+g3b30e6150.d20260221`, whose
server accepts speculative decoding through `--speculative-config`.

As of this baseline, there is no default recommended speculative model for the
current NVFP4 target. Treat speculation as a measured experiment only after
identifying a draft/speculator that explicitly targets Qwen3 Coder Next and the
serving backend in use.

When testing a candidate, recreate only the large model service:

```bash
docker compose up -d --force-recreate qwen
python3 scripts/benchmark_endpoints.py --runs 3
nvidia-smi
```

Accept the change only if all of these are true:

- output tokens/s improves by at least `15%`
- time-to-first-token does not regress materially
- GPU process memory remains within the reclaimed headroom
- quality on real coding prompts is unchanged

If it fails or memory is worse, clear `QWEN_SPECULATIVE_ARGS` and recreate
`qwen`.

## Experiment 3: Open WebUI Image Generation

Prefer remote OpenAI image generation before local Flux/ComfyUI. It adds no
DGX memory pressure and Open WebUI already has an OpenAI image-generation
integration.

Set these in `.env`:

```env
OPENWEBUI_ENABLE_IMAGE_GENERATION=true
OPENWEBUI_IMAGE_GENERATION_ENGINE=openai
OPENWEBUI_IMAGE_GENERATION_MODEL=gpt-image-1.5
OPENWEBUI_IMAGE_SIZE=auto
OPENWEBUI_IMAGES_OPENAI_API_BASE_URL=https://api.openai.com/v1
OPENWEBUI_IMAGES_OPENAI_API_KEY=your_openai_api_key_here
OPENWEBUI_IMAGES_OPENAI_API_PARAMS={"quality":"medium"}
```

Then update the Open WebUI admin image settings or reset/recreate Open WebUI if
you want environment variables to repopulate its persistent config.

ChatGPT Plus is not the same thing as OpenAI API access. Use an OpenAI API key
with billing enabled for this path.

## Experiment 4: Speech To Text

Open WebUI already includes local faster-whisper STT. Start with `base` or
`small` on CPU; do not allocate GPU memory to STT until the model-hosting
profile is settled.

Recommended initial settings:

```env
OPENWEBUI_WHISPER_MODEL=base
OPENWEBUI_WHISPER_VAD_FILTER=true
OPENWEBUI_WHISPER_LANGUAGE=en
OPENWEBUI_WHISPER_COMPUTE_TYPE=int8
```

If recognition quality is not good enough, try `small`, then `medium`. Treat
`large`/`large-v3`/Turbo-class variants as follow-up tests only after measuring
latency and memory pressure.

## Routing

Hermes is currently configured with one model provider:

```yaml
model:
  default: saricles/Qwen3-Coder-Next-NVFP4-GB10
  provider: custom
  base_url: http://qwen:${QWEN_PORT}/v1
```

Use Open WebUI for media routing first: text chat goes to Hermes, image
generation goes to the configured image backend, and STT stays inside Open
WebUI. Add a router such as LiteLLM only if there is a concrete need to expose
multiple text/vision model endpoints behind one OpenAI-compatible API.
