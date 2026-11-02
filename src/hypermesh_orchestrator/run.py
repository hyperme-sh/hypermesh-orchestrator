"""Ask AIuditor for the allowed set, reuse or open one lease per host, stitch.

Tickets are checked before a new lease is opened. A lease opened here
is polled until its ticket appears or the wait expires, then closed.
A starting or active lease for the same host is reused. The idempotency
key is scoped to this run, so a later run can book again after a close.

Does not call AIuditor allocate. Native mode is the same function with the
flags pointed at the plane.
"""

from __future__ import annotations

import time
import uuid
from collections.abc import Callable
from dataclasses import dataclass

import httpx

from hypermesh_orchestrator.config import (
    Config,
    OrchestratorError,
    api_url,
    chat_completions_url,
    tenant_headers,
)

LIVE_LEASE = frozenset({"starting", "active"})
DEFAULT_TICKET_POLL_S = 0.25


class TicketMissing(OrchestratorError):
    pass


@dataclass(frozen=True)
class Host:
    connection_id: str
    device_id: str


@dataclass(frozen=True)
class OpenedLease:
    device_id: str
    lease_id: str
    opened_here: bool


def fetch_allowed(config: Config, client: httpx.Client) -> list[Host]:
    response = client.get(
        api_url(config.api_base, "/api/v1/aiuditor/allowed"),
        headers=tenant_headers(config),
    )
    if response.status_code != 200:
        raise OrchestratorError(f"allowed set request failed: {response.status_code}")
    payload = response.json()
    rows = payload.get("hosts") if isinstance(payload, dict) else None
    hosts: list[Host] = []
    for row in rows or []:
        if not isinstance(row, dict):
            continue
        device_id = str(row.get("device_id") or "").strip()
        connection_id = str(row.get("connection_id") or "").strip()
        if not device_id or not connection_id:
            continue
        hosts.append(Host(connection_id=connection_id, device_id=device_id))
    hosts.sort(key=lambda host: host.device_id)
    return hosts


def fetch_host_tickets(config: Config, client: httpx.Client) -> dict[str, str]:
    """device id → lease id for tickets the plane has already issued."""

    response = client.get(
        api_url(config.api_base, "/api/v1/hypermesh/renter/host-tickets"),
        headers=tenant_headers(config),
    )
    if response.status_code != 200:
        raise TicketMissing("host ticket missing")
    payload = response.json()
    rows = payload.get("hosts") if isinstance(payload, dict) else None
    found: dict[str, str] = {}
    for row in rows or []:
        if not isinstance(row, dict) or row.get("ticket_present") is not True:
            continue
        lease_id = str(row.get("lease_id") or "").strip()
        device_id = str(row.get("device_id") or "").strip()
        if lease_id and device_id:
            found[device_id] = lease_id
    return found


def list_leases(config: Config, client: httpx.Client) -> list[dict[str, str]]:
    response = client.get(
        api_url(config.api_base, "/api/v1/hypermesh/leases"),
        headers=tenant_headers(config),
    )
    if response.status_code != 200:
        raise OrchestratorError(f"list leases failed: {response.status_code}")
    payload = response.json()
    rows = payload if isinstance(payload, list) else []
    live: list[dict[str, str]] = []
    for row in rows:
        if not isinstance(row, dict):
            continue
        status = str(row.get("status") or "")
        device_id = str(row.get("device_id") or "").strip()
        lease_id = str(row.get("id") or "").strip()
        if status in LIVE_LEASE and device_id and lease_id:
            live.append({"id": lease_id, "device_id": device_id, "status": status})
    return live


def idempotency_key(config: Config, host: Host, attempt_id: str) -> str:
    """One booking attempt. Retries in this run reuse attempt_id. A later run does not."""

    return f"{config.tenant}:{attempt_id}:{config.catalog_id}:{host.device_id}"


def open_lease(
    config: Config, client: httpx.Client, host: Host, attempt_id: str
) -> OpenedLease:
    headers = tenant_headers(config)
    headers["Idempotency-Key"] = idempotency_key(config, host, attempt_id)
    response = client.post(
        api_url(config.api_base, "/api/v1/hypermesh/leases"),
        headers=headers,
        json={
            "kind": "p2_loaded_model",
            "catalog_id": config.catalog_id,
            "device_id": host.device_id,
            "purpose": "renter",
            "reserved_hours": 1,
        },
    )
    if response.status_code not in {200, 201}:
        raise OrchestratorError(f"lease open failed: {response.status_code}")
    body = response.json()
    lease_id = str(body.get("id") or "").strip() if isinstance(body, dict) else ""
    if not lease_id:
        raise OrchestratorError("lease id missing")
    return OpenedLease(device_id=host.device_id, lease_id=lease_id, opened_here=True)


def close_lease(config: Config, client: httpx.Client, lease: OpenedLease) -> None:
    response = client.post(
        api_url(config.api_base, f"/api/v1/hypermesh/leases/{lease.lease_id}/close"),
        headers=tenant_headers(config),
    )
    if response.status_code not in {200, 204, 409}:
        raise OrchestratorError(f"lease close failed: {response.status_code}")


def _close_opened(
    config: Config, client: httpx.Client, leases: list[OpenedLease]
) -> None:
    for lease in leases:
        if lease.opened_here:
            close_lease(config, client, lease)


def _completion_text(payload: object) -> str:
    if not isinstance(payload, dict):
        return ""
    choices = payload.get("choices")
    if not isinstance(choices, list) or not choices or not isinstance(choices[0], dict):
        return ""
    message = choices[0].get("message")
    if not isinstance(message, dict):
        return ""
    content = message.get("content")
    return content if isinstance(content, str) else ""


def complete(config: Config, client: httpx.Client, lease: OpenedLease) -> str:
    headers = tenant_headers(config)
    headers["X-Hypermesh-Lease-Id"] = lease.lease_id
    response = client.post(
        chat_completions_url(config.chat_base),
        headers=headers,
        json={
            "lease_id": lease.lease_id,
            "model": config.catalog_id,
            "messages": [{"role": "user", "content": config.message}],
            "max_tokens": 16,
        },
    )
    if response.status_code != 200 or not response.content.strip():
        raise OrchestratorError("completion failed")
    text = _completion_text(response.json())
    if not text.strip():
        raise OrchestratorError("completion failed")
    return text


def stitch(parts: list[tuple[OpenedLease, str]], *, catalog_id: str) -> dict[str, object]:
    return {
        "object": "chat.completion",
        "model": catalog_id,
        "choices": [
            {
                "index": 0,
                "message": {
                    "role": "assistant",
                    "content": "\n".join(text for _lease, text in parts),
                },
                "finish_reason": "stop",
            }
        ],
        "leases": [lease.lease_id for lease, _text in parts],
    }


def _tickets_match(selected: list[OpenedLease], tickets: dict[str, str]) -> bool:
    return all(tickets.get(lease.device_id) == lease.lease_id for lease in selected)


def _await_tickets(
    config: Config,
    client: httpx.Client,
    selected: list[OpenedLease],
    *,
    ticket_wait_s: float,
    ticket_poll_s: float,
    sleep: Callable[[float], None],
    monotonic: Callable[[], float],
) -> dict[str, str]:
    """Poll until every selected lease has its ticket, or the wait expires."""

    deadline = monotonic() + max(0.0, ticket_wait_s)
    confirmed = fetch_host_tickets(config, client)
    while not _tickets_match(selected, confirmed) and monotonic() < deadline:
        step = min(ticket_poll_s, deadline - monotonic())
        if step <= 0:
            break
        sleep(step)
        confirmed = fetch_host_tickets(config, client)
    return confirmed


def _select_leases(
    config: Config,
    client: httpx.Client,
    hosts: list[Host],
    tickets: dict[str, str],
    live: list[dict[str, str]],
    attempt_id: str,
) -> list[OpenedLease]:
    """Reuse a ticketed or starting/active lease. Open only a host that has neither."""

    by_device = {row["device_id"]: row["id"] for row in live}
    selected: list[OpenedLease] = []
    for host in hosts:
        ticket_lease = tickets.get(host.device_id)
        if ticket_lease:
            selected.append(
                OpenedLease(
                    device_id=host.device_id,
                    lease_id=ticket_lease,
                    opened_here=False,
                )
            )
            continue
        existing = by_device.get(host.device_id)
        if existing:
            selected.append(
                OpenedLease(device_id=host.device_id, lease_id=existing, opened_here=False)
            )
            continue
        selected.append(open_lease(config, client, host, attempt_id))
    return selected


def run(
    config: Config,
    *,
    client: httpx.Client,
    ticket_wait_s: float | None = None,
    ticket_poll_s: float = DEFAULT_TICKET_POLL_S,
    sleep: Callable[[float], None] = time.sleep,
    monotonic: Callable[[], float] = time.monotonic,
    attempt_id: str | None = None,
) -> dict[str, object]:
    """Renter and native both land here. Flags choose the URLs."""

    hosts = fetch_allowed(config, client)
    if not hosts:
        raise OrchestratorError("allowed set is empty")
    booking = attempt_id or uuid.uuid4().hex
    tickets = fetch_host_tickets(config, client)
    live = list_leases(config, client)
    selected = _select_leases(config, client, hosts, tickets, live, booking)
    wait_s = config.ticket_wait_s if ticket_wait_s is None else ticket_wait_s
    confirmed = _await_tickets(
        config,
        client,
        selected,
        ticket_wait_s=wait_s,
        ticket_poll_s=ticket_poll_s,
        sleep=sleep,
        monotonic=monotonic,
    )
    missing = [lease for lease in selected if confirmed.get(lease.device_id) != lease.lease_id]
    if missing:
        _close_opened(config, client, selected)
        raise TicketMissing("host ticket missing")
    parts: list[tuple[OpenedLease, str]] = []
    try:
        for lease in selected:
            parts.append((lease, complete(config, client, lease)))
    except OrchestratorError:
        _close_opened(config, client, selected)
        raise
    return stitch(parts, catalog_id=config.catalog_id)
