# Hypermesh orchestrator

## Current version authority

Current development version: `0.1.0`. The services remain before the unreleased
0.24.0 milestone. Earlier 0.24/1.0 preparation and publication notes below are
historical and do not authorize those versions. Existing tags and historical
artifacts remain untouched. Development uses exact source pins and rebuilt
artifacts; no prior release is required. Version changes, tags and publication
require the owner's explicit authorization to the agent.

One binary. A tenant starts it (renter-run), or the same binary is started with the flags pointed at the plane (network-native). There is no second scheduler and no separate native fork.

AIuditor stays grant and audit. This process asks `GET /api/v1/aiuditor/allowed` for the allowed host set, then opens **one** Hypermesh lease per host (`POST /api/v1/hypermesh/leases`). It does not call `POST /catalog/{id}/allocate` (that call still binds one host). It does not place constellations or mixture-of-experts routes.

Each host still gets its own gateway ticket from the plane. The process reads `GET /api/v1/hypermesh/renter/host-tickets` before it opens a lease. A host that already has a ticket, or a `starting` or `active` lease, is reused. `offered`, `paid`, and `suspended` leases are not reused. A new lease is opened only for a host that has neither, with an `Idempotency-Key` of tenant, a per-run attempt id, catalog, and device. Retries inside that run send the same attempt id. A later run sends a new one, so a closed lease is not replayed.

A lease opened here is created `offered` with a pending USDC payment, and it starts only after that payment settles. This process does not pay. Pay it in USDC (on the test plane, `POST /api/v1/payments/usdc/lease-payments/{id}/test-credit`), or raise `--ticket-wait-s` while it is paid elsewhere.

After an open, host tickets are polled until they match the leases this run selected. The wait defaults to 180 seconds, the same window the plane uses before a host heartbeat is stale. A host picks up `lease_start` on its next heartbeat, so the default covers one of those intervals. Override it with `--ticket-wait-s` or `HYPERMESH_TICKET_WAIT_S` (the flag wins). On timeout, or when a completion fails, leases opened in this run are closed with `POST /api/v1/hypermesh/leases/{id}/close`. No partial stitch is returned.

The renter key is `HYPERMESH_API_KEY` in the environment, not a command-line flag. It is sent once, as `Authorization: Bearer`.

## Defaults

| Flag | Default |
|------|---------|
| `--mode` | `renter` (`native` is the same code path) |
| `--api-base` | `https://api.test.hyperme.sh` |
| `--chat-base` | `https://chat.test.hyperme.sh` |
| `--catalog-id` | `llama-3.1-8b-q4` |
| `--ticket-wait-s` | `180` (or `HYPERMESH_TICKET_WAIT_S`) |

Do not point `--chat-base` at `POST /api/v1/hypermesh/renter/chat/completions`. That control-plane route is not the renter door.

```bash
HYPERMESH_API_KEY="$KEY" uv run hypermesh-orchestrator \
  --tenant "$TENANT" \
  --message "Reply with the single word ready."
```

Native, same binary, plane URLs:

```bash
HYPERMESH_API_KEY="$KEY" uv run hypermesh-orchestrator \
  --mode native \
  --api-base http://hypermesh-service:8000 \
  --chat-base http://hypermesh-gateway:8000 \
  --tenant "$TENANT"
```

## Tests

```bash
bash scripts/check-package.sh
```

The package check uses a frozen dependency lock, tests the source installation,
a fresh wheel outside the checkout, and a wheel rebuilt from the source archive.
It also verifies wheel payload bytes and the installed command entry point.
The test suite uses mocked HTTP and time; it does not establish live host,
payment, gateway or deployment acceptance. CI uses disposable GitHub-hosted
workers with read-only repository permissions and no service credentials.

## Release channels

Main validation retains its exact qualified files in Actions artifacts. It does
not create GitHub releases or tags. Historical `test-<commit>` prereleases remain
qualification evidence and do not establish an accepted stable release.

Stable publication requires an explicit `vMAJOR.MINOR.PATCH` tag, the exact
successful main validation artifact, compatible declared contracts and an actual
immutable stable baseline. The publisher independently verifies that evidence;
successful caller jobs alone cannot establish acceptance. Missing evidence and
first-stable bootstrap remain closed. Package qualification, coordinated consumer
acceptance and runtime deployment remain separate.

## Test qualification and stable acceptance

GitHub `test-<commit>` prereleases are development snapshots. Their embedded
package version does not reserve a stable version. Artifact and consumer evidence
lives under `releases/qualification`; the current wheel binding is still checked
by package CI, alongside any future explicit stable candidate. Earlier test
snapshot receipts are preserved there with an explicit non-stable classification.

`releases/accepted` and `SPANOPTICON_RELEASE_BASELINE_SHA` are reserved for an
actual immutable stable GitHub release. The pinned shared guard verifies the live
release channel, stable tag source and asset digests; a test snapshot cannot
become accepted through a provenance label. No stable baseline is recorded until
that release exists. Stable publication remains closed without a valid baseline;
first stable bootstrap and coordinated release qualification remain separate.
No stable version, approval prerequisite or deployment is introduced here.


### Published stable distribution

The accepted record binds the existing immutable `v0.24.0` release to its actual
GitHub release ID, source revision and published asset digests. Test snapshots
remain under `releases/qualification` and do not establish stable acceptance.
Runtime deployment and coordinated consumer acceptance remain separate.

### Actions qualification and stable publication

Main merges and workflow completion do not publish GitHub test releases. Exact
qualification files remain in Actions artifacts with finite retention. The pinned
publisher independently verifies a real immutable stable baseline and refuses
qualification snapshots, even if a caller job reports success. Existing valid
stable records are retained; no release, version change, deployment or human
approval prerequisite is introduced by this correction.

### Lease client

Python consumers can use `hypermesh_orchestrator.leases.acquire_leases(config,
client=client)` as a context manager. It yields ticket-confirmed leases with
device ID, lease ID and an ownership flag. Raising inside the context closes
leases opened by that attempt. Normal exit leaves them available to the renter.

Other runtimes can invoke the installed CLI with `--prepare-leases` and the
usual tenant, plane and catalog flags. Exit zero returns a single JSON object
with `schema_version: 1` and a `leases` array containing `device_id`, `lease_id`
and `opened_here`. This explicitly prepares capacity and can open offers.
The caller owns subsequent use and cleanup of newly opened leases. The default
CLI continues to perform inference and return a stitched completion.
