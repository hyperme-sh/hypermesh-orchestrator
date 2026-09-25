"""Ticket wait comes from the flag, then the env, then one heartbeat window."""

from __future__ import annotations

import pytest

from hypermesh_orchestrator.config import (
    DEFAULT_TICKET_WAIT_S,
    TEST_API,
    TEST_CHAT,
    Config,
    OrchestratorError,
    resolve_ticket_wait_s,
)

TENANT = "aaaaaaaa-bbbb-cccc-dddd-eeeeeeeeeeee"


def _config(**overrides: object) -> Config:
    fields: dict[str, object] = {
        "mode": "renter",
        "api_base": TEST_API,
        "chat_base": TEST_CHAT,
        "tenant": TENANT,
        "api_key": "pk_test.renter-key",
    }
    fields.update(overrides)
    return Config(**fields)  # type: ignore[arg-type]


def test_default_ticket_wait_covers_one_heartbeat_window():
    assert DEFAULT_TICKET_WAIT_S == 180.0
    assert _config().ticket_wait_s == 180.0


def test_flag_overrides_env_and_env_overrides_the_default():
    assert resolve_ticket_wait_s(flag=None, env=None) == 180.0
    assert resolve_ticket_wait_s(flag=None, env="") == 180.0
    assert resolve_ticket_wait_s(flag=None, env=" 45 ") == 45.0
    assert resolve_ticket_wait_s(flag=90.0, env="45") == 90.0


def test_bad_ticket_wait_is_rejected():
    with pytest.raises(OrchestratorError, match="number of seconds"):
        resolve_ticket_wait_s(flag=None, env="soon")
    with pytest.raises(OrchestratorError, match="zero or more"):
        resolve_ticket_wait_s(flag=-1.0, env=None)
    with pytest.raises(OrchestratorError, match="zero or more"):
        _config(ticket_wait_s=-5)
