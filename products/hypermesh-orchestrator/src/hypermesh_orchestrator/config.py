"""Flags for renter-run and network-native. Same fields. No second scheduler."""

from __future__ import annotations

from dataclasses import dataclass

TEST_API = "https://api.test.hyperme.sh"
TEST_CHAT = "https://chat.test.hyperme.sh"
TEST_PORTAL = "https://portal.test.hyperme.sh"
DEFAULT_CATALOG = "llama-3.1-8b-q4"
DEFAULT_MESSAGE = "Reply with the single word ready."
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
    success_url: str = f"{TEST_PORTAL}/hypermesh/ok"
    cancel_url: str = f"{TEST_PORTAL}/hypermesh/cancel"

    def __post_init__(self) -> None:
        if self.mode not in MODES:
            raise OrchestratorError("mode must be renter or native")
        if not self.api_base.strip() or not self.chat_base.strip():
            raise OrchestratorError("api base and chat base are required")
        if not self.tenant.strip() or not self.api_key.strip():
            raise OrchestratorError("tenant and API key are required")
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


def tenant_headers(config: Config) -> dict[str, str]:
    """The chat door reads Authorization Bearer and ignores a second key header."""

    return {
        "Authorization": f"Bearer {config.api_key}",
        "X-Tenant-ID": config.tenant,
        "Content-Type": "application/json",
    }
