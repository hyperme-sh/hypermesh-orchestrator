# Hypermesh orchestrator

One binary. A tenant starts it (renter-run), or the same binary is started with the flags pointed at the plane (network-native). There is no second scheduler and no separate native fork.

AIuditor stays grant and audit. This process asks `GET /api/v1/aiuditor/allowed` for the allowed host set, then opens **one** Hypermesh lease per host (`POST /api/v1/hypermesh/leases`). It does not call `POST /catalog/{id}/allocate` (that call still binds one host). It does not place constellations or mixture-of-experts routes.

Each host still gets its own gateway ticket from the plane. The process reads `GET /api/v1/hypermesh/renter/host-tickets` before it opens a lease. A host that already has a ticket, or a `starting` or `active` lease, is reused. `offered`, `paid`, and `suspended` leases are not reused. A new lease is opened only for a host that has neither, with an `Idempotency-Key` of tenant, a per-run attempt id, catalog, and device. Retries inside that run send the same attempt id. A later run sends a new one, so a closed lease is not replayed.

After an open, host tickets are polled until they match the leases this run selected, or for 5 seconds. On timeout, or when a completion fails, leases opened in this run are closed with `POST /api/v1/hypermesh/leases/{id}/close`. No partial stitch is returned.

The renter key is `HYPERMESH_API_KEY` in the environment, not a command-line flag. It is sent once, as `Authorization: Bearer`.

## Defaults

| Flag | Default |
|------|---------|
| `--mode` | `renter` (`native` is the same code path) |
| `--api-base` | `https://api.test.hyperme.sh` |
| `--chat-base` | `https://chat.test.hyperme.sh` |
| `--catalog-id` | `llama-3.1-8b-q4` |

Do not point `--chat-base` at `POST /api/v1/hypermesh/renter/chat/completions`. That control-plane route is not the renter door.

```bash
cd products/hypermesh-orchestrator
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
cd products/hypermesh-orchestrator && uv run pytest -q
```
