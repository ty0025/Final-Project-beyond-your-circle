"""Environment loading, locked model constants and runtime settings.

The model and the gateway URL are constants on purpose: the course key may only
call ``gpt-6-luna`` through Portkey, so neither can be overridden from the env.
"""

from __future__ import annotations

import functools
import math
import os
import re
from dataclasses import dataclass
from pathlib import Path
from typing import Callable, Mapping

from dotenv import dotenv_values

REPO_DIR: Path = Path(__file__).resolve().parents[1]
MODEL = "gpt-6-luna"  # locked
PORTKEY_BASE_URL = "https://api.portkey.ai/v1"  # locked
APP_SLUG = "mgt409-final"  # used in prompt_cache_key
API_KEY_ENV = "PORTKEY_API_KEY"


class ConfigError(RuntimeError):
    """Required configuration is missing; the message tells the user how to fix it."""


# Labels of the .env files found by the most recent load_env() call.
_ENV_LABELS: list[str] = []

# Template values such as "your_portkey_api_key_here" or "<your key>" are not keys.
_PLACEHOLDER_RE = re.compile(r"^(?:<.*>|your[_\- ].*|.*_here|changeme|x{3,}|\.\.\.)$", re.IGNORECASE)


def is_placeholder(value: str | None) -> bool:
    """True for an unfilled template value of PORTKEY_API_KEY (copied from .env.example or the README)."""
    return bool(value) and bool(_PLACEHOLDER_RE.match(value.strip()))


def load_env(repo_dir: Path = REPO_DIR) -> list[Path]:
    """Load ``repo_dir/.env`` then ``repo_dir.parent/.env`` without overriding anything.

    Real environment variables win over both files, and the repo file wins over the
    parent file. An empty value, or a placeholder key such as ``your_portkey_api_key_here``
    (a copied ``.env.example``), never shadows a real value from a later file. Returns the
    files that existed, in load order.
    """
    repo_dir = Path(repo_dir)
    candidates = (
        (repo_dir / ".env", ".env (repo)"),
        (repo_dir.parent / ".env", ".env (parent)"),
    )
    found: list[Path] = []
    labels: list[str] = []
    for path, label in candidates:
        if not path.is_file():
            continue
        try:
            values = dotenv_values(path, encoding="utf-8-sig")  # tolerate a Windows BOM
        except (OSError, ValueError):
            continue
        for key, value in values.items():
            # Whitespace-only values count as empty, so they never hide a real value from a later file.
            if not (value or "").strip() or (key == API_KEY_ENV and is_placeholder(value)):
                continue
            current = (os.environ.get(key) or "").strip()
            if not current or (key == API_KEY_ENV and is_placeholder(current)):
                os.environ[key] = value
        found.append(path)
        labels.append(label)
    _ENV_LABELS[:] = labels
    return found


def env_files_loaded() -> list[str]:
    """Which .env files were found, as safe labels (never paths or values)."""
    return list(_ENV_LABELS)


def get_api_key() -> str:
    key = (os.environ.get(API_KEY_ENV) or "").strip()
    if is_placeholder(key):
        raise ConfigError(
            f"{API_KEY_ENV} still has the placeholder value from the template. Replace it with your real "
            f"key in the .env file (project folder {REPO_DIR.name} or the folder above it), then restart the app."
        )
    if not key:
        raise ConfigError(
            f"{API_KEY_ENV} is not set. Create a file named .env in the project folder "
            f"({REPO_DIR.name}) or in the folder above it, add the line "
            f"{API_KEY_ENV}=<your key>, then restart the app. "
            "(On a server, set it as an environment variable instead.)"
        )
    return key


def key_configured() -> bool:
    key = (os.environ.get(API_KEY_ENV) or "").strip()
    return bool(key) and not is_placeholder(key)


@dataclass(frozen=True)
class Settings:
    run_budget_usd: float = 0.05
    run_token_cap: int = 250_000
    daily_budget_usd: float = 2.00
    max_steps_per_agent: int = 8
    max_tool_calls_per_run: int = 30
    max_model_calls_per_run: int = 12  # every attempt counts, including guard calls and retries
    llm_max_retries: int = 1  # app-level retries of a failed model call (each attempt is ledgered)
    max_agent_depth: int = 2
    max_output_tokens: int = 4000
    max_input_chars: int = 8000
    rate_limit_runs: int = 15
    rate_limit_window_s: int = 600
    llm_guard: bool = True
    runs_per_user_per_month: int = 30
    data_dir: Path = REPO_DIR / "data" / "sample"
    runs_dir: Path = REPO_DIR / "runs"
    request_timeout_s: float = 90.0
    run_timeout_s: float = 180.0  # wall-clock limit for one whole run (guard + agent), all attempts included


# --- env parsing: every parser raises ValueError on a bad value -> default is kept ---

def _positive_float(raw: str) -> float:
    value = float(raw)
    if not math.isfinite(value) or value <= 0:
        raise ValueError(raw)
    return value


def _non_negative_float(raw: str) -> float:
    """0 is allowed (daily cap 0 = AI calls switched off; every run stops before its first model call)."""
    value = float(raw)
    if not math.isfinite(value) or value < 0:
        raise ValueError(raw)
    return value


def _int_at_least(minimum: int) -> Callable[[str], int]:
    def parse(raw: str) -> int:
        value = int(raw)
        if value < minimum:
            raise ValueError(raw)
        return value

    return parse


def _flag(raw: str) -> bool:
    text = raw.lower()
    if text in {"0", "false", "no", "off"}:
        return False
    if text in {"1", "true", "yes", "on"}:
        return True
    raise ValueError(raw)


def _path(raw: str) -> Path:
    path = Path(raw).expanduser()
    return path if path.is_absolute() else REPO_DIR / path


_ENV_SPEC: dict[str, tuple[str, Callable[[str], object]]] = {
    "run_budget_usd": ("RUN_BUDGET_USD", _positive_float),
    "run_token_cap": ("RUN_TOKEN_CAP", _int_at_least(1)),
    "daily_budget_usd": ("DAILY_BUDGET_USD", _non_negative_float),
    "max_steps_per_agent": ("MAX_STEPS_PER_AGENT", _int_at_least(1)),
    "max_tool_calls_per_run": ("MAX_TOOL_CALLS_PER_RUN", _int_at_least(1)),
    "max_model_calls_per_run": ("MAX_MODEL_CALLS_PER_RUN", _int_at_least(1)),
    "llm_max_retries": ("LLM_MAX_RETRIES", _int_at_least(0)),
    "max_agent_depth": ("MAX_AGENT_DEPTH", _int_at_least(0)),
    "max_output_tokens": ("MAX_OUTPUT_TOKENS", _int_at_least(1)),
    "max_input_chars": ("MAX_INPUT_CHARS", _int_at_least(1)),
    "rate_limit_runs": ("RATE_LIMIT_RUNS", _int_at_least(1)),
    "rate_limit_window_s": ("RATE_LIMIT_WINDOW_S", _int_at_least(1)),
    "llm_guard": ("SAFETY_LLM_GUARD", _flag),
    "runs_per_user_per_month": ("RUNS_PER_USER_PER_MONTH", _int_at_least(1)),
    "data_dir": ("DATA_DIR", _path),
    "runs_dir": ("RUNS_DIR", _path),
    "request_timeout_s": ("LLM_TIMEOUT_S", _positive_float),
    "run_timeout_s": ("RUN_TIMEOUT_S", _positive_float),
}


def settings_from_env(environ: Mapping[str, str] | None = None) -> Settings:
    """Build Settings from env vars; unset, empty or invalid values keep the default."""
    env = os.environ if environ is None else environ
    values: dict[str, object] = {}
    for field_name, (env_name, parse) in _ENV_SPEC.items():
        raw = (env.get(env_name) or "").strip()
        if not raw:
            continue
        try:
            values[field_name] = parse(raw)
        except (ValueError, TypeError, OverflowError):
            pass
    return Settings(**values)  # type: ignore[arg-type]


@functools.lru_cache(maxsize=1)
def get_settings() -> Settings:
    """Settings parsed from the environment once. Call ``get_settings.cache_clear()`` to re-read."""
    return settings_from_env()


load_env()
