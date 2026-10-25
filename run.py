#!/usr/bin/env python3
"""Start the app (API + web UI) on http://127.0.0.1:8000.

Usage: python run.py [--host HOST] [--port PORT] [--no-browser] [--forwarded-allow-ips IPS]
The PORT environment variable (set by hosts such as Render, or in .env) overrides the default port.
"""

from __future__ import annotations

import argparse
import os
import socket
import sys
import threading
import time
import webbrowser
from pathlib import Path
from typing import Callable

MIN_PYTHON = (3, 10)
REPO_DIR = Path(__file__).resolve().parent
BROWSER_WAIT_S = 30.0


def _utf8_console() -> None:
    """Windows consoles default to a legacy code page; never crash on non-ASCII output."""
    for stream in (sys.stdout, sys.stderr):
        reconfigure = getattr(stream, "reconfigure", None)
        if reconfigure is not None:
            try:
                reconfigure(encoding="utf-8", errors="replace")
            except (OSError, ValueError):
                pass


def _default_port() -> int:
    raw = os.environ.get("PORT", "").strip()
    if raw.isdigit() and 0 < int(raw) < 65536:
        return int(raw)
    return 8000


def _port(value: str) -> int:
    port = int(value)
    if not 0 < port < 65536:
        raise argparse.ArgumentTypeError("port must be between 1 and 65535")
    return port


def _local_host(host: str) -> str:
    """The address a browser on this machine uses to reach a server bound to ``host``."""
    return "127.0.0.1" if host in ("0.0.0.0", "::", "") else host


def _browser_url(host: str, port: int) -> str:
    host = _local_host(host)
    if ":" in host:
        host = f"[{host}]"
    return f"http://{host}:{port}"


def _open_browser_when_ready(
    url: str,
    host: str,
    port: int,
    *,
    timeout_s: float = BROWSER_WAIT_S,
    opener: Callable[[str], object] = webbrowser.open,
) -> None:
    """Open ``url`` once ``host:port`` accepts connections (or after ``timeout_s`` anyway).

    uvicorn only listens after importing the app, which can take several seconds on a slow
    or freshly installed machine; a fixed delay would open a "can't reach this page" tab.
    """
    deadline = time.monotonic() + timeout_s
    while time.monotonic() < deadline:
        try:
            with socket.create_connection((host, port), timeout=0.5):
                break
        except OSError:
            time.sleep(0.25)
    opener(url)


def _forwarded_allow_ips(cli_value: str | None) -> str | None:
    """Proxy addresses allowed to set X-Forwarded-For, i.e. the client IP the rate limiter sees.

    ``--forwarded-allow-ips`` wins, then the FORWARDED_ALLOW_IPS env var (uvicorn reads it
    itself). On Render (which sets RENDER) every request arrives through Render's proxy, so
    all addresses are trusted; otherwise uvicorn's default (loopback only) applies. Trust a
    proxy only when the app is really behind one: anyone else could fake their address.
    """
    if cli_value:
        return cli_value
    if os.environ.get("FORWARDED_ALLOW_IPS"):
        return None
    if os.environ.get("RENDER"):
        return "*"
    return None


def main(argv: list[str] | None = None) -> int:
    _utf8_console()
    if sys.version_info < MIN_PYTHON:
        print(
            f"Python {MIN_PYTHON[0]}.{MIN_PYTHON[1]} or newer is required (this is {sys.version.split()[0]}).",
            file=sys.stderr,
        )
        return 1

    parser = argparse.ArgumentParser(description="Run the MGT 409 final project app.")
    parser.add_argument("--host", default="127.0.0.1", help="interface to bind (default: 127.0.0.1)")
    parser.add_argument("--port", type=_port, default=None, help="port (default: $PORT, also from .env, or 8000)")
    parser.add_argument("--no-browser", action="store_true", help="do not open a browser window")
    parser.add_argument(
        "--forwarded-allow-ips",
        default=None,
        help="proxy IPs trusted for X-Forwarded-For, e.g. '*' behind a hosting proxy (default: automatic)",
    )
    args = parser.parse_args(argv)

    if str(REPO_DIR) not in sys.path:
        sys.path.insert(0, str(REPO_DIR))
    try:
        import uvicorn

        from app import config  # importing config loads the .env files
    except ImportError as exc:
        print(f"Missing dependency ({exc.name}). Run: python -m pip install -r requirements.txt", file=sys.stderr)
        return 1

    # Resolved only now: PORT may come from a .env file, which the import above loaded.
    port = args.port if args.port is not None else _default_port()

    env_files = config.env_files_loaded()
    configured = config.key_configured()
    print(f"Model: {config.MODEL} via Portkey")
    print(f".env files found: {', '.join(env_files) if env_files else 'none'}")
    print(f"PORTKEY_API_KEY configured: {'yes' if configured else 'no'}")
    if not configured:
        print(
            "  -> Add a line PORTKEY_API_KEY=<your key> to a .env file in this folder or the folder above it,"
            " then restart. The UI still opens and shows this hint."
        )

    url = _browser_url(args.host, port)
    print(f"Serving on {url}  (press Ctrl+C to stop)")
    if not args.no_browser:
        threading.Thread(
            target=_open_browser_when_ready, args=(url, _local_host(args.host), port), daemon=True
        ).start()

    uvicorn.run(
        "app.server:app",
        host=args.host,
        port=port,
        log_level="info",
        proxy_headers=True,
        forwarded_allow_ips=_forwarded_allow_ips(args.forwarded_allow_ips),
    )
    return 0


if __name__ == "__main__":
    sys.exit(main())
