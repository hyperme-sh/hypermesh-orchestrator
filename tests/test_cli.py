"""The renter key comes from the environment, not a command-line flag."""

from __future__ import annotations

import pytest

from hypermesh_orchestrator.cli import build_parser, main


def test_missing_env_key_exits(capsys, monkeypatch):
    monkeypatch.delenv("HYPERMESH_API_KEY", raising=False)
    assert main(["--tenant", "aaaaaaaa-bbbb-cccc-dddd-eeeeeeeeeeee"]) == 1
    assert "HYPERMESH_API_KEY is required" in capsys.readouterr().err


def test_ticket_wait_flag_overrides_the_env(monkeypatch):
    seen: dict[str, float] = {}

    def fake_run(config, *, client, ticket_wait_s):
        seen["wait"] = ticket_wait_s
        seen["config"] = config.ticket_wait_s
        return {"object": "chat.completion"}

    monkeypatch.setenv("HYPERMESH_API_KEY", "pk_test.renter-key")
    monkeypatch.setenv("HYPERMESH_TICKET_WAIT_S", "45")
    monkeypatch.setattr("hypermesh_orchestrator.cli.run", fake_run)
    assert main(["--tenant", "aaaaaaaa-bbbb-cccc-dddd-eeeeeeeeeeee", "--ticket-wait-s", "90"]) == 0
    assert seen == {"wait": 90.0, "config": 90.0}


def test_ticket_wait_reads_the_env_when_the_flag_is_omitted(monkeypatch):
    seen: dict[str, float] = {}

    def fake_run(config, *, client, ticket_wait_s):
        seen["wait"] = ticket_wait_s
        return {"object": "chat.completion"}

    monkeypatch.setenv("HYPERMESH_API_KEY", "pk_test.renter-key")
    monkeypatch.setenv("HYPERMESH_TICKET_WAIT_S", "200")
    monkeypatch.setattr("hypermesh_orchestrator.cli.run", fake_run)
    assert main(["--tenant", "aaaaaaaa-bbbb-cccc-dddd-eeeeeeeeeeee"]) == 0
    assert seen["wait"] == 200.0


def test_api_key_is_not_a_flag():
    help_text = build_parser().format_help()
    assert "--api-key" not in help_text
    with pytest.raises(SystemExit):
        build_parser().parse_args(
            ["--api-key", "pk_test.secret", "--tenant", "aaaaaaaa-bbbb-cccc-dddd-eeeeeeeeeeee"]
        )
