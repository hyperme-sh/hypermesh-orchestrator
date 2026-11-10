"""Run one completion per ticketed lease and stitch the results."""
from __future__ import annotations

import time
from collections.abc import Callable

import httpx

from .config import Config, OrchestratorError, chat_completions_url, tenant_headers
# Keep the original module-level imports available to existing Python callers.
from .leases import (
    DEFAULT_TICKET_POLL_S, LIVE_LEASE, Host, OpenedLease, TicketMissing, acquire_leases,
    close_lease, fetch_allowed, fetch_host_tickets, idempotency_key, list_leases, open_lease,
)


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

    with acquire_leases(config, client=client, ticket_wait_s=ticket_wait_s, ticket_poll_s=ticket_poll_s,
                        sleep=sleep, monotonic=monotonic, attempt_id=attempt_id) as leases:
        return stitch([(lease, complete(config, client, lease)) for lease in leases], catalog_id=config.catalog_id)
