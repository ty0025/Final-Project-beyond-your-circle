"""run.py: port resolution, browser opening and proxy trust (uvicorn is stubbed; nothing is served)."""

from __future__ import annotations

import os
import shutil
import socket
import subprocess
import sys
import threading
import time
from pathlib import Path

import pytest

import run

REPO_DIR = Path(__file__).resolve().parents[1]


# --------------------------------------------------------------------------- PORT from .env


def test_port_set_in_dotenv_is_used(tmp_path: Path):
    # A scratch copy, so its .env lookup (repo folder, then the folder above) stays inside tmp_path.
    repo = tmp_path / "course" / "repo"
    (repo / "app").mkdir(parents=True)
    shutil.copy(REPO_DIR / "run.py", repo / "run.py")
    shutil.copy(REPO_DIR / "app" / "__init__.py", repo / "app" / "__init__.py")
    shutil.copy(REPO_DIR / "app" / "config.py", repo / "app" / "config.py")
    (repo / ".env").write_text("PORT=8767\n", encoding="utf-8")
    script = (
        "import sys, types\n"
        "fake = types.ModuleType('uvicorn')\n"
        "fake.run = lambda app, **kw: print('UVICORN_PORT', kw['port'])\n"
        "sys.modules['uvicorn'] = fake\n"
        "import run\n"
        "sys.exit(run.main(['--no-browser']))\n"
    )
    env = {k: v for k, v in os.environ.items() if k not in ("PORT", "PYTHONPATH")}

    proc = subprocess.run(
        [sys.executable, "-c", script], cwd=repo, env=env, capture_output=True, text=True, timeout=60
    )

    assert proc.returncode == 0, proc.stderr
    assert "UVICORN_PORT 8767" in proc.stdout
    assert "http://127.0.0.1:8767" in proc.stdout


@pytest.fixture
def uvicorn_calls(monkeypatch) -> list[dict]:
    import uvicorn

    calls: list[dict] = []
    monkeypatch.setattr(uvicorn, "run", lambda app, **kw: calls.append({"app": app, **kw}))
    monkeypatch.delenv("PORT", raising=False)
    monkeypatch.delenv("RENDER", raising=False)
    monkeypatch.delenv("FORWARDED_ALLOW_IPS", raising=False)
    return calls


def test_port_flag_wins_over_env(uvicorn_calls, monkeypatch):
    monkeypatch.setenv("PORT", "8767")
    assert run.main(["--no-browser", "--port", "8123"]) == 0
    assert uvicorn_calls[0]["port"] == 8123


# --------------------------------------------------------------------------- proxy trust (rate limiting behind Render)


def test_local_run_trusts_no_forwarded_header(uvicorn_calls):
    run.main(["--no-browser"])
    call = uvicorn_calls[0]
    assert call["proxy_headers"] is True
    assert call["forwarded_allow_ips"] is None  # uvicorn default: loopback only


def test_render_trusts_its_proxy(uvicorn_calls, monkeypatch):
    monkeypatch.setenv("RENDER", "true")
    run.main(["--host", "0.0.0.0", "--no-browser"])
    assert uvicorn_calls[0]["forwarded_allow_ips"] == "*"


def test_forwarded_allow_ips_flag_and_env(uvicorn_calls, monkeypatch):
    run.main(["--no-browser", "--forwarded-allow-ips", "10.0.0.0/8"])
    assert uvicorn_calls[-1]["forwarded_allow_ips"] == "10.0.0.0/8"

    monkeypatch.setenv("RENDER", "true")
    monkeypatch.setenv("FORWARDED_ALLOW_IPS", "10.1.2.3")
    run.main(["--no-browser"])
    assert uvicorn_calls[-1]["forwarded_allow_ips"] is None, "uvicorn reads FORWARDED_ALLOW_IPS itself"


# --------------------------------------------------------------------------- browser opens when the server is ready


def _free_port() -> int:
    with socket.socket() as s:
        s.bind(("127.0.0.1", 0))
        return s.getsockname()[1]


def test_browser_opens_only_once_the_server_listens():
    port = _free_port()
    opened: list[float] = []
    waiter = threading.Thread(
        target=run._open_browser_when_ready,
        args=(f"http://127.0.0.1:{port}", "127.0.0.1", port),
        kwargs={"timeout_s": 20, "opener": lambda url: opened.append(time.monotonic())},
        daemon=True,
    )
    waiter.start()
    time.sleep(1.0)
    assert opened == [], "nothing listens yet, so the browser must wait"

    listening_since = time.monotonic()
    with socket.create_server(("127.0.0.1", port)):
        waiter.join(10)
    assert len(opened) == 1
    assert opened[0] >= listening_since


def test_browser_still_opens_after_the_timeout():
    opened: list[str] = []
    port = _free_port()
    run._open_browser_when_ready(f"http://127.0.0.1:{port}", "127.0.0.1", port, timeout_s=0.3, opener=opened.append)
    assert opened == [f"http://127.0.0.1:{port}"]


def test_main_starts_the_browser_waiter_instead_of_a_fixed_timer(uvicorn_calls, monkeypatch):
    started = threading.Event()
    seen: list[tuple] = []

    def fake_waiter(*args, **kwargs):
        seen.append(args)
        started.set()

    monkeypatch.setattr(run, "_open_browser_when_ready", fake_waiter)
    run.main(["--host", "0.0.0.0", "--port", "8125"])
    assert started.wait(5)
    assert seen == [("http://127.0.0.1:8125", "127.0.0.1", 8125)]
