from __future__ import annotations

import argparse
from collections.abc import Sequence

import uvicorn

from radiusdeck.version import __version__


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="radiusdeck")
    parser.add_argument(
        "--version",
        action="version",
        version=f"radiusdeck {__version__}",
    )
    subparsers = parser.add_subparsers(dest="command", required=True)

    serve = subparsers.add_parser("serve", help="Run the RadiusDeck web server")
    serve.add_argument("--host", default="0.0.0.0")
    serve.add_argument("--port", default=8000, type=int)
    serve.add_argument(
        "--proxy-headers",
        action=argparse.BooleanOptionalAction,
        default=True,
        help="Honor X-Forwarded-* headers (enabled by default)",
    )
    serve.add_argument(
        "--forwarded-allow-ips",
        default="*",
        help="Comma-separated trusted proxy IPs (default: *)",
    )
    return parser


def main(argv: Sequence[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    if args.command == "serve":
        uvicorn.run(
            "radiusdeck.main:app",
            host=args.host,
            port=args.port,
            proxy_headers=args.proxy_headers,
            forwarded_allow_ips=args.forwarded_allow_ips,
        )
        return 0
    raise AssertionError(f"Unsupported command: {args.command}")


if __name__ == "__main__":
    raise SystemExit(main())
