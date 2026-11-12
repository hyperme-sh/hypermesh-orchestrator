# Hypermesh orchestrator contributor guidance

Read README.md and docs/release-policy.md. Retain both this file and release
policy in public distributions. Keep private business and operator material in
the private documentation repository.

## Ownership and runtime boundaries

Orchestrator owns host-market pricing and timing. AIuditor owns audit, safety and
RBAC; conductor owns model routing and cost. Preserve the shared renter/native
execution path, environment-only API key, per-run idempotency and lease cleanup.
Use owner HTTP contracts; do not perform payments or grant accounting balances.
Funding is not a usable host ticket. Keep legacy wire inputs compatible.

## Validation and CI

Run `bash scripts/check-package.sh` for unit/contract checks against source,
installed wheel and rebuilt source archive. Tests use mocked HTTP. Integration,
e2e and shared-resource runs belong in CI and the nightly batch; never start or
repeat those suites manually. Green PR CI and clean review complete issues;
nightly failures become new issues, not completion gates.

Jobs use `[self-hosted, linux, x64, debrunner]` while private and automatically
switch to GitHub-hosted `ubuntu-24.04` when public. Public PRs must not reach
private runners or receive publication credentials. PR validation is read-only.
Only validated merged-main container builds may update the GHCR TEST channel.
No artifact uploads, package bundles or test-release tags. Keep credentials out
of builds and expose the registry token only to the publication step.

## Version and publication authority

Keep the declared package version unchanged without explicit authorization.
Manual tags/releases and production promotion need authorization for the specific
target and action. Preserve historical tags and releases. TEST services follow
moving channels, with patch-compatible peer contracts and no deployment pins.
Image identity and source revision may be recorded for diagnostics.

Never add required reviewers, branch protections, approval rulesets, environment
approvals, CODEOWNERS approval requirements or human release/deployment gates
unless explicitly requested. Automated checks and advisory reviews are welcome.
