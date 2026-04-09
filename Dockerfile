# syntax=docker/dockerfile:1.6

# --------------------------------------------------------------
# Hermes Agent Dockerfile – builds from upstream source
# --------------------------------------------------------------
FROM python:3.11-slim

# Install git, SSH client, and minimal build tools
RUN apt-get update && apt-get install -y --no-install-recommends \
        git \
        openssh-client \
        rsync \
        gettext-base \
        build-essential \
    && rm -rf /var/lib/apt/lists/*

# Working directory inside the container
WORKDIR /app

# Ensure the Hermes config directory exists
ENV HERMES_DIR=/app/.hermes
RUN mkdir -p $HERMES_DIR

# -----------------------------------------------------------------
# Build‑time arguments – allow overriding the repo/branch if needed
# -----------------------------------------------------------------
ARG HERMES_REPO=https://github.com/NousResearch/hermes-agent.git
ARG HERMES_BRANCH=main

# Clone the Hermes agent source (shallow clone for speed)
RUN git clone --depth 1 --branch $HERMES_BRANCH $HERMES_REPO hermes-agent && \
    cd hermes-agent && \
    pip install --no-cache-dir '.[messaging,cron]'

# Default entrypoint – you can override with `docker compose run hermes chat`, etc.
ENTRYPOINT ["hermes"]
CMD ["gateway"]
