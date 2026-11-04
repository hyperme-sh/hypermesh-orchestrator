# Hypermesh orchestrator development

This repository owns the orchestrator CLI, configuration and fan-out behavior.
Start with README.md and src/hypermesh_orchestrator. Preserve the renter/native
shared execution path, environment-only API key, per-run idempotency and lease
cleanup boundaries. Tests use mocked HTTP; do not replace them with live calls.

Run `bash scripts/check-package.sh` for source, wheel and source-archive checks.
Keep runtime behavior changes separate from packaging changes.

## Package publication permission boundary

Source/package validation keeps its existing runner policy and read-only contents.
The separate `.github/workflows/release.yml` publication job is the narrow exception:
it may use `contents: write` and `actions: read` on disposable `ubuntu-24.04` workers
solely through the exact-pinned shared package publisher. It must not check out or
execute this repository's code, install its packages, or receive private dependency
or deployment credentials. This hosted publication exception does not authorize
moving secret-bearing validation to another runner group. Stable publication must
retain any configured release-admission prerequisite for the exact tag/commit.
