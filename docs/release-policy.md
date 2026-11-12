# Release policy

The current source package version is declared in pyproject.toml (0.1.0).
Apache-2.0 LICENSE and NOTICE ship with the source and runtime container.
Historical tags, releases and qualification records remain intact; they do not
require every subsequent development checkout to reproduce an old archive.

## Validation and distribution

Package CI validates source, installed wheel and rebuilt source archive with
mocked HTTP. Development needs no previous stable release. A selected candidate
must match its declared build; never fabricate baseline identities or hashes.

Merged main builds/checks the CLI container and publishes the moving GHCR
`runtime:test` channel. PR checks are read-only. Private jobs use debrunner;
public jobs use hosted Ubuntu. The publisher verifies the built image and skips
superseded main revisions. Keys are runtime environment configuration, never
baked into the image. No package bundles, Actions uploads or test-release tags
are published. Temporary package builds are discarded after validation.

TEST consumers follow the moving channel without version/digest pins or matching
peer-build requirements. Source/image identity checks are diagnostics, not
service pins. Integration/e2e stays in scheduled CI; failed nightly runs become
new issues rather than preventing completion of implemented PRs.

## Production and permissions

No automatic stable publication is configured. Production promotion, manual
tags/releases and package-version changes require explicit authorization for
their specific targets. TEST publication is not production acceptance. Preserve
historical release records and never substitute test output for a stable baseline.
Do not add human approval gates, required reviewers or branch protections unless
explicitly requested; use automated checks and advisory review.

Public-source checks scan a disposable exact-tree single-commit copy. They do not
rewrite remote history, publish a snapshot or change repository visibility.
Private hosted-network and business details belong in the private operator docs.
