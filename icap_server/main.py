#!/usr/bin/env python3
"""Entry point for the ICAP demo server."""

from __future__ import annotations

import argparse
import asyncio
import logging
import sys

from .config import IcapServerConfig
from .server import IcapServer


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="RFC 3507 ICAP demo server")
    parser.add_argument("--host", default=None, help="Bind address (default: 127.0.0.1)")
    parser.add_argument("--port", type=int, default=None, help="Bind port (default: 1344)")
    parser.add_argument(
        "--log-level",
        default="INFO",
        choices=["DEBUG", "INFO", "WARNING", "ERROR"],
    )
    args = parser.parse_args(argv)

    logging.basicConfig(
        level=getattr(logging, args.log_level),
        format="%(asctime)s %(levelname)s [%(name)s] %(message)s",
    )

    config = IcapServerConfig.from_env()
    if args.host:
        config.host = args.host
    if args.port:
        config.port = args.port

    server = IcapServer(config)
    try:
        asyncio.run(server.serve_forever())
    except KeyboardInterrupt:
        print("\nICAP server stopped.")
        return 0
    return 0


if __name__ == "__main__":
    sys.exit(main())
