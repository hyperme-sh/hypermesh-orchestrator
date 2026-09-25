"""Tickets are checked before a lease is opened. A retry does not double-book."""

from __future__ import annotations

import json

import httpx
import pytest

from hypermesh_orchestrator.config import (
    DEFAULT_CATALOG,
    TEST_API,
    TEST_CHAT,
    Config,
    OrchestratorError,
    chat_completions_url,
)
from hypermesh_orchestrator.run import TicketMissing, run

HOST_A = "dddddddd-dddd-4ddd-8ddd-dddddddddd01"
HOST_B = "dddddddd-dddd-4ddd-8ddd-dddddddddd02"
LEASE_A = "11111111-1111-4111-8111-111111111111"
LEASE_B = "22222222-2222-4222-8222-222222222222"
TENANT = "aaaaaaaa-bbbb-cccc-dddd-eeeeeeeeeeee"
TEXT = {LEASE_A: "from-host-a", LEASE_B: "from-host-b"}
LEASE_FOR = {HOST_A: LEASE_A, HOST_B: LEASE_B}


def _config(**overrides: str) -> Config:
    fields = {
        "mode": "renter",
        "api_base": TEST_API,
        "chat_base": TEST_CHAT,
        "tenant": TENANT,
        "api_key": "pk_test.renter-key",
    }
    fields.update(overrides)
    return Config(**fields)


def _ticket(device_id: str) -> dict[str, object]:
    return {
        "lease_id": LEASE_FOR[device_id],
        "device_id": device_id,
        "ticket_present": True,
    }


class Plane:
    def __init__(
        self,
        *,
        tickets: list[str] | None = None,
        grant_ticket_on_open: bool = False,
        chat_status: int = 200,
    ) -> None:
        self.calls: list[str] = []
        self.opened: list[str] = []
        self.closed: list[str] = []
        self.idempotency: list[str] = []
        self.tickets = {device_id: _ticket(device_id) for device_id in tickets or []}
        self.leases: list[dict[str, str]] = []
        self.grant_ticket_on_open = grant_ticket_on_open
        self.chat_status = chat_status

    def handler(self, request: httpx.Request) -> httpx.Response:
        path = request.url.path
        self.calls.append(f"{request.method} {request.url.host} {path}")
        if path.endswith("/allocate"):
            return httpx.Response(500, json={"detail": "allocate must not be called"})
        if path == "/api/v1/aiuditor/allowed" and request.method == "GET":
            return httpx.Response(
                200,
                json={
                    "hosts": [
                        {"connection_id": "c1", "device_id": HOST_A, "status": "ready"},
                        {"connection_id": "c2", "device_id": HOST_B, "status": "ready"},
                    ]
                },
            )
        if path == "/api/v1/hypermesh/renter/host-tickets" and request.method == "GET":
            return httpx.Response(200, json={"hosts": list(self.tickets.values())})
        if path == "/api/v1/hypermesh/leases" and request.method == "GET":
            return httpx.Response(200, json=self.leases)
        if path == "/api/v1/hypermesh/leases" and request.method == "POST":
            body = json.loads(request.content)
            device_id = body["device_id"]
            assert body["kind"] == "p2_loaded_model"
            key = request.headers.get("Idempotency-Key")
            assert key == f"{TENANT}:{DEFAULT_CATALOG}:{device_id}"
            self.idempotency.append(key)
            lease_id = LEASE_FOR[device_id]
            self.opened.append(device_id)
            self.leases.append(
                {"id": lease_id, "device_id": device_id, "status": "active"}
            )
            if self.grant_ticket_on_open:
                self.tickets[device_id] = _ticket(device_id)
            return httpx.Response(
                201,
                json={"id": lease_id, "device_id": device_id, "status": "active"},
            )
        if path.endswith("/close") and request.method == "POST":
            lease_id = path.split("/")[-2]
            self.closed.append(lease_id)
            return httpx.Response(200, json={"id": lease_id, "status": "failed"})
        if path == "/v1/chat/completions" and request.method == "POST":
            body = json.loads(request.content)
            lease_id = body["lease_id"]
            assert request.headers["X-Hypermesh-Lease-Id"] == lease_id
            if self.chat_status != 200:
                return httpx.Response(self.chat_status, json={"detail": "down"})
            return httpx.Response(
                200,
                json={
                    "object": "chat.completion",
                    "choices": [
                        {"message": {"role": "assistant", "content": TEXT[lease_id]}}
                    ],
                },
            )
        return httpx.Response(404, json={"path": path})

    def client(self) -> httpx.Client:
        return httpx.Client(transport=httpx.MockTransport(self.handler))


def _lease_posts(calls: list[str]) -> list[str]:
    return [
        call
        for call in calls
        if call.endswith("/api/v1/hypermesh/leases") and call.startswith("POST ")
    ]


def test_fan_out_reuses_ticketed_hosts_and_does_not_open():
    plane = Plane(tickets=[HOST_A, HOST_B])
    stitched = run(_config(), client=plane.client())
    assert stitched["object"] == "chat.completion"
    assert stitched["choices"][0]["message"]["content"] == "from-host-a\nfrom-host-b"
    assert stitched["leases"] == [LEASE_A, LEASE_B]
    assert plane.opened == []
    assert plane.closed == []
    assert [call for call in plane.calls if call.endswith("/v1/chat/completions")] == [
        "POST chat.test.hyperme.sh /v1/chat/completions",
        "POST chat.test.hyperme.sh /v1/chat/completions",
    ]
    ticket_at = plane.calls.index(
        "GET api.test.hyperme.sh /api/v1/hypermesh/renter/host-tickets"
    )
    assert ticket_at < len(plane.calls)
    assert not any("allocate" in call for call in plane.calls)
    assert not any("/api/v1/health" in call for call in plane.calls)


def test_missing_ticket_closes_the_lease_this_run_opened():
    plane = Plane(grant_ticket_on_open=False)
    with pytest.raises(TicketMissing, match="host ticket missing"):
        run(_config(), client=plane.client())
    assert plane.opened == [HOST_A, HOST_B]
    assert plane.closed == [LEASE_A, LEASE_B]
    assert plane.idempotency == [
        f"{TENANT}:{DEFAULT_CATALOG}:{HOST_A}",
        f"{TENANT}:{DEFAULT_CATALOG}:{HOST_B}",
    ]
    first_ticket = next(i for i, call in enumerate(plane.calls) if "host-tickets" in call)
    first_open = next(i for i, call in enumerate(plane.calls) if call in _lease_posts(plane.calls))
    assert first_ticket < first_open
    assert not any(call.endswith("/v1/chat/completions") for call in plane.calls)


def test_completion_failure_closes_leases_opened_this_run():
    plane = Plane(grant_ticket_on_open=True, chat_status=502)
    with pytest.raises(OrchestratorError, match="completion failed"):
        run(_config(), client=plane.client())
    assert plane.opened == [HOST_A, HOST_B]
    assert plane.closed == [LEASE_A, LEASE_B]


def test_reused_lease_stays_open_when_completion_fails():
    plane = Plane(tickets=[HOST_A, HOST_B], chat_status=502)
    with pytest.raises(OrchestratorError, match="completion failed"):
        run(_config(), client=plane.client())
    assert plane.opened == []
    assert plane.closed == []


def test_retry_reuses_the_ticket_and_does_not_double_book():
    plane = Plane(grant_ticket_on_open=True)
    first = run(_config(), client=plane.client())
    opened = list(plane.opened)
    second = run(_config(), client=plane.client())
    assert opened == [HOST_A, HOST_B]
    assert plane.opened == opened
    assert second == first
    assert plane.closed == []


def test_native_mode_is_the_same_fan_out_with_plane_flags():
    renter = Plane(tickets=[HOST_A, HOST_B])
    native = Plane(tickets=[HOST_A, HOST_B])
    renter_body = run(_config(), client=renter.client())
    native_body = run(
        _config(
            mode="native",
            api_base="http://hypermesh-service:8000",
            chat_base="http://hypermesh-gateway:8000",
        ),
        client=native.client(),
    )
    assert native_body == renter_body

    def paths(calls: list[str]) -> list[str]:
        return [call.split(" ", 2)[2] for call in calls]

    assert paths(renter.calls) == paths(native.calls)
    assert paths(renter.calls) == [
        "/api/v1/aiuditor/allowed",
        "/api/v1/hypermesh/renter/host-tickets",
        "/api/v1/hypermesh/leases",
        "/api/v1/hypermesh/renter/host-tickets",
        "/v1/chat/completions",
        "/v1/chat/completions",
    ]
    assert all(
        "api.test.hyperme.sh" in call or "chat.test.hyperme.sh" in call
        for call in renter.calls
    )
    assert all(
        "hypermesh-service" in call or "hypermesh-gateway" in call for call in native.calls
    )
    assert any(
        call.startswith("GET hypermesh-service ")
        and call.endswith("/api/v1/hypermesh/renter/host-tickets")
        for call in native.calls
    )
    assert any(call.startswith("POST hypermesh-gateway ") for call in native.calls)
    assert _lease_posts(native.calls) == []


def test_chat_url_refuses_the_control_plane_stub():
    with pytest.raises(OrchestratorError, match="control-plane chat stub"):
        chat_completions_url(
            "https://api.test.hyperme.sh/api/v1/hypermesh/renter/chat/completions"
        )
    with pytest.raises(OrchestratorError, match="control-plane chat stub"):
        _config(chat_base="https://api.test.hyperme.sh/api/v1/hypermesh/renter/chat/completions")
