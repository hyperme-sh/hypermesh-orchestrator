# Hypermesh orchestrator

Package version `0.1.0`. See [release policy](docs/release-policy.md) and
[contributor guidance](AGENTS.md). Apache-2.0 LICENSE and NOTICE ship with the source
and container. Historical tags and distributions remain intact.

Orchestrator owns host-market pricing and timing. AIuditor owns audit, safety and
RBAC; conductor owns model routing and cost. The lease client here acquires
capacity within AIuditor's allowed host set; it does not move money.

One binary. A tenant starts it (renter-run), or the same binary is started with the flags pointed at the plane (network-native). There is no second scheduler and no separate native fork.

AIuditor stays grant and audit. This process asks `GET /api/v1/aiuditor/allowed` for the allowed host set, then opens **one** Hypermesh lease per host (`POST /api/v1/hypermesh/leases`). It does not call `POST /catalog/{id}/allocate` (that call still binds one host). It does not place constellations or mixture-of-experts routes.

Each host still gets its own gateway ticket from the plane. The process reads `GET /api/v1/hypermesh/renter/host-tickets` before it opens a lease. A host that already has a ticket, or a `starting` or `active` lease, is reused. `offered`, `funded`, and `suspended` leases are not reused. Legacy `paid` states are also not usable capacity. A new lease is opened only for a host that has neither, with an `Idempotency-Key` of tenant, a per-run attempt id, catalog, and device. Retries inside that run send the same attempt id. A later run sends a new one, so a closed lease is not replayed.

A lease opened here is created `offered`. It can start once the plane's accounting
backend marks it funded. With the internal backend, funding is backed by the
organization's token/hour quota; external settlement belongs to that backend.
The orchestrator never pays, grants quota, or infers usable capacity from funding.
It waits for the plane's host ticket; adjust `--ticket-wait-s` for that wait.

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
payment, gateway or deployment acceptance. PR CI uses read-only repository permissions and no service credentials.
Workers use GitHub-hosted Ubuntu.

## Container distribution

Merged main publishes `ghcr.io/hyperme-sh/hypermesh-orchestrator/runtime:test`.
Use the moving TEST channel; no deployed version or digest pin is required.
PR checks use read-only permissions and mocked HTTP. Jobs use GitHub-hosted Ubuntu. No Actions archives,
package bundles or release tags are published. Temporary package files are used
only for validation. Runtime configuration and keys are supplied at invocation.

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
