This directory contains the previous self-contained Nemotron/vLLM build context.
It is kept in the repo as a fallback/reference, but `docker-compose.yml` no
longer uses it by default.

What lives here:
- `Dockerfile`: source-builds FlashInfer and vLLM for DGX Spark / GB10.
- `flashinfer_cache.patch`: keeps FlashInfer cubin downloads cache-friendly.
- `build-metadata.yaml`: lightweight metadata copied into the runtime image.

What does not live here anymore:
- Prebuilt wheel artifacts. The Dockerfile now builds FlashInfer and vLLM from
  source during `docker compose build nemotron`.

Why this folder still exists:
- Preserve the old source-build path in case TensorRT-LLM needs to be rolled
  back.
- Avoid losing the local patches/debug history that got the vLLM path working
  on DGX Spark.

Operational notes:
- The first build is heavy and can take a long time because it downloads and
  compiles NCCL, FlashInfer, and vLLM.
- Subsequent builds benefit from Docker/BuildKit layer and cache mounts.
- Runtime data for the built service is not stored here; it lives under
  the repo-root `./data/nemotron/`.
- Runtime tuning such as `NEMOTRON_GPU_MEMORY_UTILIZATION` lives in the repo
  root `.env`, not in this folder.
