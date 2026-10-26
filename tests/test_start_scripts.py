"""start.sh recovery paths, run with fake interpreters (offline, no real venv or pip), and its git mode."""

from __future__ import annotations

import os
import shutil
import subprocess
from pathlib import Path

import pytest

REPO_DIR = Path(__file__).resolve().parents[1]


def _bash() -> str | None:
    bash = shutil.which("bash")
    if bash and os.name == "nt" and "system32" in bash.lower():
        return None  # the WSL launcher sees a different filesystem; Git Bash is fine
    return bash


BASH = _bash()

# A system interpreter. FAKE_OK=1 makes it report Python 3.11+; "-m venv DIR" installs
# FAKE_VENV_TEMPLATE as DIR/bin/python and exits with FAKE_VENV_EXIT.
FAKE_SYSTEM_PYTHON = """#!/usr/bin/env bash
case "$1" in
  -c)
    case "$2" in
      *version_info*) [ "${FAKE_OK:-1}" = 1 ]; exit $? ;;
      *) echo "3.12.1"; exit 0 ;;
    esac ;;
  -m)
    if [ "$2" = venv ]; then
      mkdir -p "$3/bin" && cp "$FAKE_VENV_TEMPLATE" "$3/bin/python" && chmod +x "$3/bin/python"
      exit "${FAKE_VENV_EXIT:-0}"
    fi ;;
esac
exit 3
"""

GOOD_VENV_PYTHON = """#!/usr/bin/env bash
case "$1" in
  -c) exit 0 ;;
  -m) [ "$2" = pip ] && exit 0 ;;
  run.py) shift; echo "RUN OK $*"; exit 0 ;;
esac
exit 3
"""

# A venv made by macOS's stock Python 3.9: pip exists, but no openai 3.x wheel installs.
OLD_VENV_PYTHON = """#!/usr/bin/env bash
case "$1" in
  -c) exit 1 ;;
  -m) [ "$2" = pip ] && [ "$3" = --version ] && exit 0
      echo "ERROR: No matching distribution found for openai<4,>=3.26" >&2; exit 1 ;;
  run.py) echo "RUN OK"; exit 0 ;;
esac
exit 3
"""

# A half-built venv (Debian/Ubuntu without python3-venv): no pip.
NO_PIP_VENV_PYTHON = """#!/usr/bin/env bash
case "$1" in
  -c) exit 0 ;;
  -m) echo "No module named pip" >&2; exit 1 ;;
  run.py) echo "RUN OK"; exit 0 ;;
esac
exit 3
"""

CANDIDATES = ("python3", "python3.14", "python3.13", "python3.12", "python3.11", "python3.10", "python")


def _write_exec(path: Path, text: str) -> Path:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(text.encode("utf-8"))  # LF line endings on every OS
    path.chmod(0o755)
    return path


@pytest.fixture
def sandbox(tmp_path: Path):
    if BASH is None:
        pytest.skip("bash is not available")
    project = tmp_path / "project"
    project.mkdir()
    shutil.copy(REPO_DIR / "start.sh", project / "start.sh")
    (project / "requirements.txt").write_bytes(b"")
    fakebin = tmp_path / "fakebin"
    for name in CANDIDATES:  # shadow every real interpreter the script could pick
        _write_exec(fakebin / name, FAKE_SYSTEM_PYTHON)
    templates = {
        "good": _write_exec(tmp_path / "templates" / "good", GOOD_VENV_PYTHON),
        "old": _write_exec(tmp_path / "templates" / "old", OLD_VENV_PYTHON),
        "nopip": _write_exec(tmp_path / "templates" / "nopip", NO_PIP_VENV_PYTHON),
    }

    def start(*, system_ok: bool = True, venv: str = "good", venv_exit: int = 0) -> subprocess.CompletedProcess:
        env = dict(os.environ)
        env.update(
            PATH=str(fakebin) + os.pathsep + env.get("PATH", ""),
            FAKE_OK="1" if system_ok else "0",
            FAKE_VENV_TEMPLATE=templates[venv].as_posix(),
            FAKE_VENV_EXIT=str(venv_exit),
        )
        return subprocess.run(
            [BASH, "start.sh", "--no-browser"], cwd=project, env=env, capture_output=True, text=True, timeout=60
        )

    def install_venv(kind: str) -> None:
        _write_exec(project / ".venv" / "bin" / "python", templates[kind].read_text(encoding="utf-8"))

    return project, start, install_venv


def test_venv_from_an_old_python_is_recreated(sandbox):
    project, start, install_venv = sandbox
    install_venv("old")  # left behind by a first attempt with Python 3.9

    proc = start()

    assert proc.returncode == 0, proc.stderr
    assert "recreating" in proc.stdout
    assert "RUN OK --no-browser" in proc.stdout
    assert (project / ".venv" / "bin" / "python").read_text(encoding="utf-8") == GOOD_VENV_PYTHON


def test_half_built_venv_prints_the_hint_and_a_rerun_recovers(sandbox):
    project, start, _ = sandbox

    first = start(venv="nopip", venv_exit=1)

    assert first.returncode == 1
    assert "python3-venv" in first.stderr
    assert not (project / ".venv").exists(), "a half-built .venv must not be reused by the next run"

    second = start()
    assert second.returncode == 0, second.stderr
    assert "RUN OK" in second.stdout


def test_venv_without_pip_is_recreated(sandbox):
    project, start, install_venv = sandbox
    install_venv("nopip")
    proc = start()
    assert proc.returncode == 0, proc.stderr
    assert "recreating" in proc.stdout and "RUN OK" in proc.stdout


def test_no_python_311_gives_a_clear_message(sandbox):
    project, start, _ = sandbox
    proc = start(system_ok=False)
    assert proc.returncode == 1
    assert "Python 3.11 or newer is required" in proc.stderr
    assert "python.org/downloads" in proc.stderr
    assert not (project / ".venv").exists()


def test_good_venv_is_reused(sandbox):
    project, start, install_venv = sandbox
    install_venv("good")
    proc = start()
    assert proc.returncode == 0, proc.stderr
    assert "recreating" not in proc.stdout and "Creating" not in proc.stdout
    assert "RUN OK" in proc.stdout


def test_start_sh_is_committed_as_executable():
    """Mac/Linux graders run ./start.sh; on Windows (core.filemode=false) git would record 100644."""
    git = shutil.which("git")
    if git is None:
        pytest.skip("git is not available")
    proc = subprocess.run(
        [git, "-c", f"safe.directory={REPO_DIR.as_posix()}", "ls-files", "--stage", "start.sh"],
        cwd=REPO_DIR,
        capture_output=True,
        text=True,
    )
    if proc.returncode != 0 or not proc.stdout.strip():
        pytest.skip("start.sh is not tracked by git in this checkout")
    assert proc.stdout.split()[0] == "100755"


def test_start_sh_has_unix_line_endings():
    assert b"\r\n" not in (REPO_DIR / "start.sh").read_bytes()
