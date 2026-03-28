"""Compatibility shim for legacy `python main.py` usage.

The canonical backend entrypoint is `api.main:app`.
"""

from __future__ import annotations

import argparse
import os

import uvicorn

from api.main import app

__all__ = ["app"]


def _parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Launch the ruleIQ API.")
    parser.add_argument("--host", default=os.getenv("HOST", "0.0.0.0"))
    parser.add_argument("--port", type=int, default=int(os.getenv("PORT", "8000")))
    parser.add_argument(
        "--reload",
        action="store_true",
        default=os.getenv("RELOAD", "").lower() in {"1", "true", "yes"},
        help="Enable auto-reload for local development.",
    )
    return parser.parse_args()


def main() -> None:
    args = _parse_args()
    uvicorn.run(
        "api.main:app",
        host=args.host,
        port=args.port,
        reload=args.reload,
        log_level="info",
    )


if __name__ == "__main__":
    main()
