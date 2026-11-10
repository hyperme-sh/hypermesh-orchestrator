"""One binary. Renter-run is the default. Native points the same flags at the plane."""

from __future__ import annotations

from dataclasses import asdict
import argparse
import json
import os
import sys

import httpx

from hypermesh_orchestrator.config import (
    DEFAULT_CATALOG,
    DEFAULT_MESSAGE,
    TEST_API,
    TEST_CHAT,
    Config,
    OrchestratorError,
    resolve_ticket_wait_s,
)
from hypermesh_orchestrator.leases import acquire_leases
from hypermesh_orchestrator.run import run


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="hypermesh-orchestrator",
        description=(
            "Open one Hypermesh lease per AIuditor-allowed host and stitch "
            "one completion. Native mode uses the same path with flags pointed "
            "at the plane."
        ),
    )
    parser.add_argument("--mode", choices=("renter", "native"), default="renter")
    parser.add_argument("--api-base", default=TEST_API)
    parser.add_argument("--chat-base", default=TEST_CHAT)
    parser.add_argument("--tenant", required=True)
    parser.add_argument("--catalog-id", default=DEFAULT_CATALOG)
    parser.add_argument("--message", default=DEFAULT_MESSAGE)
    parser.add_argument(
        "--ticket-wait-s",
        type=float,
        default=None,
        help="Seconds to wait for a host ticket after a new lease (default 180)",
    )
    parser.add_argument("--prepare-leases", action="store_true", help="Return ticketed leases as JSON without inference")
    return parser


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    api_key = os.environ.get("HYPERMESH_API_KEY", "").strip()
    if not api_key:
        print("HYPERMESH_API_KEY is required", file=sys.stderr)
        return 1
    try:
        ticket_wait_s = resolve_ticket_wait_s(
            flag=args.ticket_wait_s,
            env=os.environ.get("HYPERMESH_TICKET_WAIT_S"),
        )
        config = Config(
            mode=args.mode,
            api_base=args.api_base,
            chat_base=args.chat_base,
            tenant=args.tenant,
            api_key=api_key,
            catalog_id=args.catalog_id,
            message=args.message,
            ticket_wait_s=ticket_wait_s,
        )
        with httpx.Client(timeout=httpx.Timeout(30.0)) as client:
            if args.prepare_leases:
                with acquire_leases(config, client=client) as leases:
                    print(json.dumps({"schema_version": 1, "leases": [asdict(lease) for lease in leases]}), flush=True)
                return 0
            stitched = run(config, client=client, ticket_wait_s=config.ticket_wait_s)
    except OrchestratorError as exc:
        print(str(exc), file=sys.stderr)
        return 1
    print(json.dumps(stitched))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
