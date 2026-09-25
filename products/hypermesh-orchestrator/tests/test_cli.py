"""The renter key comes from the environment, not a command-line flag."""

from __future__ import annotations

import pytest

from hypermesh_orchestrator.cli import build_parser, main


def test_missing_env_key_exits(capsys, monkeypatch):
    monkeypatch.delenv("HYPERMESH_API_KEY", raising=False)
    assert main(["--tenant", "aaaaaaaa-bbbb-cccc-dddd-eeeeeeeeeeee"]) == 1
    assert "HYPERMESH_API_KEY is required" in capsys.readouterr().err


def test_api_key_is_not_a_flag():
    help_text = build_parser().format_help()
    assert "--api-key" not in help_text
    with pytest.raises(SystemExit):
        build_parser().parse_args(
            ["--api-key", "pk_test.secret", "--tenant", "aaaaaaaa-bbbb-cccc-dddd-eeeeeeeeeeee"]
        )
