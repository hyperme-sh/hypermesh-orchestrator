FROM ghcr.io/astral-sh/uv:python3.13-bookworm-slim@sha256:531f855bda2c73cd6ef67d56b733b357cea384185b3022bd09f05e002cd144ca AS build
WORKDIR /app
COPY pyproject.toml uv.lock LICENSE NOTICE ./
COPY src src
RUN uv sync --frozen --no-dev --no-editable
FROM python:3.13-slim-bookworm@sha256:281d39ff02e3b389401586134ff9e6572954687822a58055ec07a60ded4e0b7f
WORKDIR /app
COPY --from=build /app/.venv /app/.venv
COPY LICENSE NOTICE /usr/share/licenses/hypermesh-orchestrator/
ARG SOURCE_SHA
ARG BUILT_AT
LABEL org.opencontainers.image.source="https://github.com/hyperme-sh/hypermesh-orchestrator" \
      org.opencontainers.image.revision="${SOURCE_SHA}" \
      org.opencontainers.image.licenses="Apache-2.0"
USER 65532:65532
ENTRYPOINT ["/app/.venv/bin/hypermesh-orchestrator"]
