# Hermes + Nemotron Compose Stack

Self-contained Docker Compose stack for running:
- `hermes` as the gateway / agent container with its built-in API server enabled
- `open-webui` as a browser UI for Hermes
- `nemotron` as a local TensorRT-LLM OpenAI-compatible model server

The repo is laid out so someone can check it out, read this file, set a few
environment values, and run the stack without depending on files outside the
repo checkout.

Safe for public GitHub:
- commit the tracked files in this repo
- do not commit `.env`
- do not commit `./secrets/ssh/*` other than `./secrets/ssh/README.md`
- do not commit anything under `./data`

## What This Stack Does

- Builds Hermes from the upstream `NousResearch/hermes-agent` repository.
- Enables Hermes's built-in OpenAI-compatible API server inside the gateway
  container.
- Runs Open WebUI against that Hermes API so you get a browser chat interface.
- Runs Nemotron 3 Super through NVIDIA's TensorRT-LLM runtime using the DGX
  Spark settings NVIDIA publishes for this model.
- Persists all runtime state under `./data`.
- Keeps user-editable config under `./settings`.
- Keeps host-SSH material under `./secrets/ssh`.

## Repository Layout

- `docker-compose.yml`
  Main stack definition.
- `Dockerfile`
  Hermes image build.
- `vendor/nemotron-build/`
  Legacy self-contained vLLM / Nemotron build context kept as a fallback.
- `settings/hermes/config.yaml`
  Hermes config template rendered at container startup.
- `settings/nemotron/`
  TensorRT-LLM config template and Nemotron-specific runtime assets.
- `secrets/ssh/`
  SSH files used by Hermes to run commands on the host.
- `data/hermes/`
  Persistent Hermes runtime state.
- `data/open-webui/`
  Persistent Open WebUI state, including its first-launch connection settings.
- `data/nemotron/`
  Persistent Hugging Face, vLLM, FlashInfer, Triton, and temp caches.

## Prerequisites

- Docker with Compose plugin
- NVIDIA Container Toolkit / GPU-enabled Docker
- A DGX Spark or another compatible GPU host for the Nemotron runtime
- `sshd` running on the host if you want Hermes to execute commands on that host
- Network access during build
  Hermes is cloned from GitHub and the Nemotron container downloads model
  weights on first start.

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

3. Prepare SSH material for Hermes if you want it to run commands on the host:

See [`./secrets/ssh/README.md`](./secrets/ssh/README.md).

At minimum this folder should contain:
- `id_rsa`
- `id_rsa.pub`
- `known_hosts`

4. Review ports and tuning in `.env` if needed:
- `HERMES_GATEWAY_PORT=8000`
- `OPEN_WEBUI_PORT=3000`
- `NEMOTRON_PORT=9000`
- `HERMES_API_KEY=...`
- `NEMOTRON_GPU_MEMORY_UTILIZATION=0.9`
- `NEMOTRON_MAX_MODEL_LEN=1048576`
- `NEMOTRON_MAX_NUM_SEQS=8`
- `NEMOTRON_MAX_NUM_TOKENS=8192`

5. Start the stack:

```bash
docker compose up -d --build
```

6. Verify it is healthy:

```bash
docker compose ps
curl http://localhost:8000/health
curl http://localhost:9000/v1/models
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
  SSH working directory, or the Nemotron port
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

### Nemotron

- Nemotron runs TensorRT-LLM and exposes an OpenAI-compatible API on
  `http://localhost:9000/v1` by default.
- Runtime caches are persisted under `./data/nemotron/`.
- Change the port by editing `NEMOTRON_PORT` in `.env`.
- This stack follows NVIDIA's DGX Spark guidance for Nemotron 3 Super:
  `NEMOTRON_GPU_MEMORY_UTILIZATION=0.9`,
  `NEMOTRON_MAX_MODEL_LEN=1048576`,
  `NEMOTRON_MAX_NUM_SEQS=8`, and
  `NEMOTRON_MAX_NUM_TOKENS=8192`.
- Compared with the earlier vLLM defaults in this repo, the TensorRT-LLM
  profile is more aggressive on memory use, increases the default context from
  131072 to 1048576 tokens, and uses FP16 Mamba cache with stochastic rounding
  to make that fit on a single DGX Spark.

## Build And Run

Build everything:

```bash
docker compose build
```

Pull the NVIDIA Nemotron runtime image:

```bash
docker compose pull nemotron
```

Start everything:

```bash
docker compose up -d
```

For a fresh checkout, the most common first commands are:

```bash
docker compose pull nemotron
docker compose up -d --build
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

View Hermes logs:

```bash
docker compose logs -f hermes
```

View Nemotron logs:

```bash
docker compose logs -f nemotron
```

Check the Nemotron API from the host:

```bash
curl http://localhost:9000/v1/models
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
- Nemotron: `9000`

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

## Notes On Nemotron Runtime

- `nemotron` now uses NVIDIA's prebuilt TensorRT-LLM container instead of a
  local source build.
- The first start can still take a while because the model weights must be
  downloaded and the runtime may build/cache kernels for the local Spark.
- The legacy vLLM source-build path is still in
  [`./vendor/nemotron-build/README.md`](./vendor/nemotron-build/README.md) if
  you ever need to revert.

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

### Nemotron fails during startup with a GPU memory error

If logs mention insufficient free memory, either:
- stop other GPU workloads
- lower `NEMOTRON_GPU_MEMORY_UTILIZATION` in `.env`
- lower `NEMOTRON_MAX_MODEL_LEN` in `.env`

On busy machines, the failure can happen even when the GPU is large enough in
total because the TensorRT-LLM profile is configured for a large 1M-token
context window and a high free-memory fraction by default. The repo now follows
NVIDIA's more aggressive Spark profile, so reducing either knob is the first
thing to try if you want more headroom for host-side work.

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
