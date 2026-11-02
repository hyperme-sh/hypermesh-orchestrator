# Hypermesh orchestrator development

This repository owns the orchestrator CLI, configuration and fan-out behavior.
Start with README.md and src/hypermesh_orchestrator. Preserve the renter/native
shared execution path, environment-only API key, per-run idempotency and lease
cleanup boundaries. Tests use mocked HTTP; do not replace them with live calls.

Run `bash scripts/check-package.sh` for source, wheel and source-archive checks.
Keep runtime behavior changes separate from packaging changes.
