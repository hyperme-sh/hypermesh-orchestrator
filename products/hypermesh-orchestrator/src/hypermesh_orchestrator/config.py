"""Flags for renter-run and network-native. Same fields. No second scheduler."""

from __future__ import annotations

from dataclasses import dataclass

TEST_API = "https://api.test.hyperme.sh"
TEST_CHAT = "https://chat.test.hyperme.sh"
DEFAULT_CATALOG = "llama-3.1-8b-q4"
DEFAULT_MESSAGE = "Reply with the single word ready."
# Matches hypermesh fleet health: a host heartbeat older than this is stale,
# and the host picks up lease_start on its next heartbeat.
DEFAULT_TICKET_WAIT_S = 180.0
CONTROL_PLANE_STUB = "/api/v1/hypermesh/renter/chat/completions"
MODES = frozenset({"renter", "native"})


class OrchestratorError(RuntimeError):
    pass


@dataclass(frozen=True)
class Config:
    mode: str
    api_base: str
    chat_base: str
    tenant: str
    api_key: str
    catalog_id: str = DEFAULT_CATALOG
    message: str = DEFAULT_MESSAGE
    ticket_wait_s: float = DEFAULT_TICKET_WAIT_S

    def __post_init__(self) -> None:
        if self.mode not in MODES:
            raise OrchestratorError("mode must be renter or native")
        if not self.api_base.strip() or not self.chat_base.strip():
            raise OrchestratorError("api base and chat base are required")
        if not self.tenant.strip() or not self.api_key.strip():
            raise OrchestratorError("tenant and API key are required")
        if not _wait_ok(self.ticket_wait_s):
            raise OrchestratorError("ticket wait must be zero or more seconds")
        chat_completions_url(self.chat_base)


def chat_completions_url(chat_base: str) -> str:
    """Renter door. Never the control-plane 409 stub."""

    root = chat_base.strip().rstrip("/")
    if CONTROL_PLANE_STUB in root:
        raise OrchestratorError("refusing the control-plane chat stub")
    if root.endswith("/v1"):
        url = f"{root}/chat/completions"
    else:
        url = f"{root}/v1/chat/completions"
    if CONTROL_PLANE_STUB in url:
        raise OrchestratorError("refusing the control-plane chat stub")
    return url


def api_url(api_base: str, path: str) -> str:
    return api_base.strip().rstrip("/") + path


def _wait_ok(value: float) -> bool:
    return value >= 0 and value == value and value != float("inf")


def resolve_ticket_wait_s(*, flag: float | None, env: str | None) -> float:
    """Flag wins. Otherwise HYPERMESH_TICKET_WAIT_S. Otherwise one heartbeat window."""

    if flag is not None:
        if not _wait_ok(flag):
            raise OrchestratorError("ticket wait must be zero or more seconds")
        return flag
    if env is None or not env.strip():
        return DEFAULT_TICKET_WAIT_S
    try:
        parsed = float(env.strip())
    except ValueError as exc:
        raise OrchestratorError("HYPERMESH_TICKET_WAIT_S must be a number of seconds") from exc
    if not _wait_ok(parsed):
        raise OrchestratorError("ticket wait must be zero or more seconds")
    return parsed


def tenant_headers(config: Config) -> dict[str, str]:
    """The chat door reads Authorization Bearer and ignores a second key header."""

    return {
        "Authorization": f"Bearer {config.api_key}",
        "X-Tenant-ID": config.tenant,
        "Content-Type": "application/json",
    }
