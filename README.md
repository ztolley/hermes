# Hermes + Qwen3 Coder Next Compose Stack

Self-contained Docker Compose stack for running:
- `hermes` as the gateway / agent container with its built-in API server enabled
- `open-webui` as a browser UI for Hermes
- `qwen` as a local vLLM OpenAI-compatible Qwen3 Coder Next NVFP4 model server
- `qwen-autocomplete` as a small vLLM OpenAI-compatible model server for VS
  Code autocomplete

The repo is laid out so someone can check it out, read this file, set a few
environment values, and run the stack without depending on files outside the
repo checkout.

Safe for public GitHub:
- commit the tracked files in this repo
- do not commit `.env`
- do not commit `./secrets/ssh/*` other than `./secrets/ssh/README.md`
- do not commit anything under `./data`

## Simple Version

Yes: this stack runs Qwen3 Coder Next 80B as an NVFP4-compressed model in a
Docker container on the DGX Spark.

The active model server is:
- image: `avarok/dgx-vllm-nvfp4-kernel:v23`
- model: `saricles/Qwen3-Coder-Next-NVFP4-GB10`
- API: OpenAI-compatible vLLM on `http://localhost:3001/v1`
- Hermes talks to it internally at `http://qwen:3001/v1`

There is also a separate autocomplete model server:
- image: `vllm-node:latest`
- model: `Qwen/Qwen2.5-Coder-3B`
- API: OpenAI-compatible vLLM on `http://localhost:3002/v1`
- intended client: VS Code autocomplete / inline completion tooling

This was not just the Docker run command from the Hugging Face discussion copied
into Compose. That example was the useful starting point because it identified a
DGX Spark-capable vLLM image. The Compose setup here also had to:
- wire the image into this stack's `qwen` service
- mount the existing repo-local Hugging Face and vLLM caches
- expose it on the existing `QWEN_PORT`
- keep Hermes and Open WebUI pointed at the Qwen-backed API path
- disable the broken FlashInfer FP4 MoE path for this image on GB10
- force the Marlin NVFP4 fallback so the server actually starts

The important caveat is that the model is still NVFP4, but the working backend
is Marlin, not the faster FlashInfer CUTLASS backend mentioned in some examples.
FlashInfer CUTLASS got further than the old custom build, but then failed during
JIT compilation with unsupported GB10 PTX instructions. Marlin starts cleanly
and produced around 58 output tokens/second on warmed short code-completion
tests on this Spark.

## What This Stack Does

- Builds Hermes from the upstream `NousResearch/hermes-agent` repository.
- Enables Hermes's built-in OpenAI-compatible API server inside the gateway
  container.
- Runs Open WebUI against that Hermes API so you get a browser chat interface.
- Runs a DGX Spark NVFP4-capable vLLM image for Qwen3 Coder Next.
- Runs a separate small Qwen coder model for VS Code autocomplete.
- Persists all runtime state under `./data`.
- Keeps user-editable config under `./settings`.
- Keeps host-SSH material under `./secrets/ssh`.

## Repository Layout

- `docker-compose.yml`
  Main stack definition.
- `Dockerfile`
  Hermes image build.
- `settings/hermes/config.yaml`
  Hermes config template rendered at container startup.
- `scripts/benchmark_endpoints.py`
  Local benchmark for the large Qwen, autocomplete, and Hermes endpoints.
- `docs/health-performance.md`
  Known-good health, memory, and performance baseline.
- `compose.override.yml.example`
  Starting point for local tuning experiments.
- `secrets/ssh/`
  SSH files used by Hermes to run commands on the host.
- `data/hermes/`
  Persistent Hermes runtime state.
- `data/open-webui/`
  Persistent Open WebUI state, including its first-launch connection settings.
- `data/qwen/`
  Persistent Hugging Face cache for Qwen models and runtime caches for the
  large Qwen service.
- `data/qwen-autocomplete/`
  Persistent vLLM, FlashInfer, Triton, and temp caches for the small
  autocomplete service.

## Prerequisites

- Docker with Compose plugin
- NVIDIA Container Toolkit / GPU-enabled Docker
- A DGX Spark or another compatible GPU host for the Qwen NVFP4 runtime
- `sshd` running on the host if you want Hermes to execute commands on that host
- Network access during build
  Hermes is cloned from GitHub during the build.
  The Qwen runtime image is pulled from Docker Hub.

## First-Time Setup

1. Copy the environment file:

```bash
cp .env.example .env
```

2. Edit `.env` and set at minimum:
- `TELEGRAM_BOT_TOKEN`
- `TELEGRAM_ALLOWED_USERS`
- `TELEGRAM_HOME_CHANNEL`
- `HERMES_HOST_SSH_USER`
- `HERMES_HOST_SSH_CWD`
- `HF_TOKEN` if the selected Hugging Face model requires authentication

3. Prepare SSH material for Hermes if you want it to run commands on the host:

See [`./secrets/ssh/README.md`](./secrets/ssh/README.md).

At minimum this folder should contain:
- `id_rsa`
- `id_rsa.pub`
- `known_hosts`

4. Review ports and tuning in `.env` if needed:
- `HERMES_GATEWAY_PORT=8000`
- `OPEN_WEBUI_PORT=3000`
- `QWEN_PORT=3001`
- `AUTOCOMPLETE_PORT=3002`
- `HERMES_API_KEY=...`
- `QWEN_MODEL=saricles/Qwen3-Coder-Next-NVFP4-GB10`
- `QWEN_GPU_MEMORY_UTILIZATION=0.62`
- `QWEN_MAX_MODEL_LEN=131072`
- `QWEN_MAX_NUM_SEQS=2`
- `AUTOCOMPLETE_MODEL=Qwen/Qwen2.5-Coder-3B`
- `AUTOCOMPLETE_GPU_MEMORY_UTILIZATION=0.08`

5. Start the stack:

```bash
docker compose up -d --build
```

6. Verify it is healthy:

```bash
docker compose ps
curl http://localhost:8000/health
curl http://localhost:3001/v1/models
curl http://localhost:3002/v1/models
```

7. Capture a benchmark baseline:

```bash
python3 scripts/benchmark_endpoints.py --runs 2
```

## How Configuration Works

### Hermes

- Hermes stores runtime state inside the container at `/app/.hermes`.
- On the host, that is persisted at `./data/hermes/home`.
- `settings/hermes/config.yaml` is treated as a template, not the final runtime
  file.
- When the container starts, it runs `envsubst` against that template and writes
  the generated file to `/app/.hermes/config.yaml`.
- The same container also runs Hermes's built-in API server because Compose sets
  `API_SERVER_ENABLED`, `API_SERVER_HOST`, `API_SERVER_PORT`, and
  `API_SERVER_KEY` as environment variables.

That means:
- edit `./settings/hermes/config.yaml` to change the template
- edit `.env` to change template-backed values such as the SSH user, SSH port,
  SSH working directory, or the Qwen port
- edit `.env` to change Hermes API settings such as `HERMES_GATEWAY_PORT` and
  `HERMES_API_KEY`
- inspect `/app/.hermes/config.yaml` inside the container if you want to see the
  rendered runtime file

### Open WebUI

- Open WebUI runs in its own container and stores its database under
  `./data/open-webui`.
- It talks to Hermes over the internal Compose network at
  `http://hermes:${HERMES_GATEWAY_PORT}/v1`.
- On first launch, Open WebUI reads `OPENAI_API_BASE_URL` and `OPENAI_API_KEY`
  from Compose and saves them into its internal database.

Important:
- those environment variables only control Open WebUI's first launch
- after that, connection settings are stored in `./data/open-webui`
- if you later change `HERMES_API_KEY` or the Hermes API port, update the
  connection in the Open WebUI admin UI or remove `./data/open-webui` and start
  fresh

### Qwen

- Qwen runs vLLM and exposes an OpenAI-compatible API on
  `http://localhost:3001/v1` by default.
- It uses the prebuilt DGX Spark image
  `avarok/dgx-vllm-nvfp4-kernel:v23`; the active stack no longer builds a
  local Qwen runtime image.
- The default model is `saricles/Qwen3-Coder-Next-NVFP4-GB10`, an NVFP4
  compressed Qwen3 Coder Next model intended for GB10 / DGX Spark.
- Runtime caches are persisted under `./data/qwen/`.
- Change the port by editing `QWEN_PORT` in `.env`.
- This stack is tuned for DGX Spark using
  `avarok/dgx-vllm-nvfp4-kernel:v23` and
  `saricles/Qwen3-Coder-Next-NVFP4-GB10`.
- The default profile uses `QWEN_GPU_MEMORY_UTILIZATION=0.62`,
  `QWEN_MAX_MODEL_LEN=131072`, and `QWEN_MAX_NUM_SEQS=2`.
- The large model's GPU memory target is deliberately below the standalone
  value so the small autocomplete service has room to start alongside it.
- The default profile uses Marlin for NVFP4 GEMM/MoE because the FlashInfer
  CUTLASS FP4 JIT path currently emits unsupported GB10 PTX instructions in
  this image.
- These backend settings are the key differences from the simple Docker run
  example:

```env
QWEN_USE_FLASHINFER_MOE_FP4=0
QWEN_TEST_FORCE_FP8_MARLIN=1
QWEN_NVFP4_GEMM_BACKEND=marlin
```

Without those settings, this image either failed in vLLM's compressed-tensors
MoE setup or failed later compiling FlashInfer FP4 kernels for GB10.

### Qwen Autocomplete

- `qwen-autocomplete` is a second vLLM server for editor autocomplete.
- It is independent from Hermes and Open WebUI; those services continue to use
  the large `qwen` service through Hermes.
- It listens on `http://localhost:3002/v1` by default.
- The default model is `Qwen/Qwen2.5-Coder-3B`.
- It uses `vllm-node:latest`, the same local image used by the older
  `~/Development/compose` autocomplete setup.
- It receives the same `HF_TOKEN` as the large model so gated or rate-limited
  Hugging Face downloads work consistently.
- It reserves a small GPU slice with
  `AUTOCOMPLETE_GPU_MEMORY_UTILIZATION=0.08` so it can run alongside the large
  Qwen3 Coder Next service.
- It uses `--generation-config vllm` so the server does not inherit unexpected
  generation defaults from the model repository.

Point VS Code / Roo / autocomplete tooling at:

```text
http://spark-1.local:3002/v1
```

Use the model name:

```text
Qwen/Qwen2.5-Coder-3B
```

## Build And Run

Build Hermes:

```bash
docker compose build hermes
```

Start everything:

```bash
docker compose up -d
```

For a fresh checkout, the most common first command is:

```bash
docker compose up -d --build hermes open-webui qwen qwen-autocomplete
```

The `qwen` image is pulled, not built locally. If only Qwen changed or you just
want to restart the model server:

```bash
docker compose up -d --force-recreate qwen
```

Restart only the VS Code autocomplete model:

```bash
docker compose up -d --force-recreate qwen-autocomplete
```

Start and stream logs:

```bash
docker compose up
```

## Useful Commands

Check service status:

```bash
docker compose ps
```

Run the endpoint benchmark:

```bash
python3 scripts/benchmark_endpoints.py --runs 2
```

See [`docs/health-performance.md`](docs/health-performance.md) for the current
known-good memory and performance baseline.

View Hermes logs:

```bash
docker compose logs -f hermes
```

View Qwen logs:

```bash
docker compose logs -f qwen
```

View autocomplete logs:

```bash
docker compose logs -f qwen-autocomplete
```

Check the Qwen API from the host:

```bash
curl http://localhost:3001/v1/models
```

Check the autocomplete API from the host:

```bash
curl http://localhost:3002/v1/models
```

Check the Hermes API from the host:

```bash
curl http://localhost:8000/health
```

List Hermes API models from the host:

```bash
curl http://localhost:8000/v1/models \
  -H "Authorization: Bearer ${HERMES_API_KEY}"
```

Open WebUI in a browser:

```text
http://localhost:3000
```

Open a shell in Hermes:

```bash
docker compose exec hermes sh
```

Check Hermes host-SSH from inside the container:

```bash
docker compose exec hermes sh -lc 'ssh -o BatchMode=yes -o StrictHostKeyChecking=yes -o UpdateHostKeys=no -i /root/.ssh/id_rsa ${HERMES_HOST_SSH_USER}@host.docker.internal whoami'
```

Re-render Hermes after changing `.env`, `settings/hermes/config.yaml`, or
`secrets/ssh/*`:

```bash
docker compose up -d --build --force-recreate hermes
```

## Expected Ports

By default:
- Hermes API: `8000`
- Open WebUI: `3000`
- Qwen3 Coder Next vLLM: `3001`
- Qwen autocomplete vLLM: `3002`

Both the internal and published ports are driven from `.env`.

## How To Use It

You now have several ways to talk to Hermes:
- Telegram, using your configured bot token
- Open WebUI in a browser at `http://localhost:3000`
- The Hermes TUI with `docker compose exec -it hermes hermes chat`
- Direct HTTP calls to Hermes at `http://localhost:8000/v1`

For Open WebUI:
1. Start the stack with `docker compose up -d --build`
2. Open `http://localhost:3000`
3. Create the first user account; that user becomes the Open WebUI admin
4. Start a new chat and select `hermes-agent` from the model dropdown

For the TUI from another machine, you can still run:

```bash
ssh -t your-dgx-host 'cd /absolute/path/to/this/repo && docker compose exec -it hermes hermes chat'
```

That keeps the agent and model on the DGX while letting you use the TUI from
your local terminal.

## Persistence

This project uses repo-local bind mounts under `./data` instead of Docker named
volumes.

Why:
- easier to inspect manually
- easier to back up or move with the checkout
- clearer for a self-contained project

This is a good fit for this repo because the goal is "check out the repo and
have everything live alongside it".

## Notes On Qwen Builds

- The active `qwen` service does not build a local runtime image.
- It uses `avarok/dgx-vllm-nvfp4-kernel:v23`, which includes the DGX Spark
  NVFP4 kernel patches needed by this model.
- The `qwen-autocomplete` service also does not build locally. It uses the
  existing local `vllm-node:latest` image and sets `pull_policy: never` so
  Compose does not try to pull it from a registry.

## Public Repo Checklist

Before pushing this repo to GitHub:
- keep `.env` local only
- keep `./secrets/ssh/id_rsa`, `id_rsa.pub`, and `known_hosts` local only
- keep `./data` local only
- check `git status --ignored` if you want to confirm those files remain ignored

## Common Issues

### Hermes can’t SSH to the host

Check:
- `./secrets/ssh/id_rsa` exists
- `./secrets/ssh/known_hosts` exists
- host `sshd` is running
- the configured SSH user can SSH to itself on the host
- `.env` has the right `HERMES_HOST_SSH_USER`, `HERMES_HOST_SSH_PORT`, and
  `HERMES_HOST_SSH_CWD` values

### Qwen fails during startup with a GPU memory error

If logs mention insufficient free memory, either:
- stop other GPU workloads
- lower `QWEN_GPU_MEMORY_UTILIZATION` in `.env`
- lower `AUTOCOMPLETE_GPU_MEMORY_UTILIZATION` in `.env`

On busy machines, the failure can happen even when the GPU is large enough in
total because vLLM checks free memory at startup, not just installed memory.
This repo defaults that setting to `0.7` and a `131072` max context so
the box keeps more headroom for host-side work.

### Hermes is up but Telegram conflicts

That usually means another bot process is already polling the same token.
Make sure only one active Hermes/Telegram gateway is using that token.

### Open WebUI loads but Hermes does not appear in the model list

Check:
- Hermes is healthy: `curl http://localhost:8000/health`
- the Hermes model list works:
  `curl http://localhost:8000/v1/models -H "Authorization: Bearer ${HERMES_API_KEY}"`
- Open WebUI was started with the correct Hermes URL including `/v1`
- if Open WebUI was already launched once, remember that it stores connection
  settings in `./data/open-webui`; changing `.env` later does not rewrite that
  database automatically

## Files To Edit Most Often

- `.env`
  Secrets, ports, SSH target settings, and runtime tuning knobs.
- `settings/hermes/config.yaml`
  Hermes config template.
- `docker-compose.yml`
  Service definitions and mounts.
