from __future__ import annotations

import os
import shutil
from dataclasses import fields
from pathlib import Path

import pytest
from dotenv import dotenv_values

from app import config
from app.config import REPO_DIR, ConfigError, Settings, get_api_key, get_settings, key_configured, load_env
from tests.conftest import DUMMY_KEY


def write_env(path: Path, **values: str) -> Path:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("".join(f"{k}={v}\n" for k, v in values.items()), encoding="utf-8")
    return path


@pytest.fixture
def repo(tmp_path: Path) -> Path:
    """A fake repo folder inside a fake course folder (the 'folder above')."""
    repo_dir = tmp_path / "course" / "final project"
    repo_dir.mkdir(parents=True)
    os.environ.pop("PORTKEY_API_KEY", None)
    return repo_dir


# --------------------------------------------------------------------------- .env lookup


def test_repo_env_wins_over_parent_env(repo: Path):
    repo_env = write_env(repo / ".env", PORTKEY_API_KEY="repo-key-1234567890")
    parent_env = write_env(repo.parent / ".env", PORTKEY_API_KEY="parent-key-1234567890", MGT409_TEST_PARENT_ONLY="yes")

    loaded = load_env(repo)

    assert [p.resolve() for p in loaded] == [repo_env.resolve(), parent_env.resolve()]
    assert get_api_key() == "repo-key-1234567890"
    # The parent file is still loaded for keys the repo file does not define.
    assert os.environ.get("MGT409_TEST_PARENT_ONLY") == "yes"


def test_parent_env_used_when_repo_has_none(repo: Path):
    parent_env = write_env(repo.parent / ".env", PORTKEY_API_KEY="parent-key-1234567890")

    loaded = load_env(repo)

    assert [p.resolve() for p in loaded] == [parent_env.resolve()]
    assert get_api_key() == "parent-key-1234567890"


def test_real_env_var_wins_over_both_files(repo: Path):
    write_env(repo / ".env", PORTKEY_API_KEY="repo-key-1234567890")
    write_env(repo.parent / ".env", PORTKEY_API_KEY="parent-key-1234567890")
    os.environ["PORTKEY_API_KEY"] = "real-env-key-1234567890"

    load_env(repo)

    assert get_api_key() == "real-env-key-1234567890"


def test_no_env_files_is_fine(repo: Path):
    assert load_env(repo) == []
    assert key_configured() is False


def test_load_env_is_idempotent(repo: Path):
    write_env(repo / ".env", PORTKEY_API_KEY="repo-key-1234567890")
    first = load_env(repo)
    second = load_env(repo)
    assert first == second
    assert get_api_key() == "repo-key-1234567890"


def test_env_files_loaded_are_labels_not_paths_or_values():
    labels = config.env_files_loaded()
    assert isinstance(labels, list)
    for label in labels:
        assert isinstance(label, str)
        assert not os.path.isabs(label)
        assert DUMMY_KEY not in label


# --------------------------------------------------------------------------- API key


def test_missing_key_raises_config_error_with_fix_it_message():
    os.environ.pop("PORTKEY_API_KEY", None)
    with pytest.raises(ConfigError) as exc_info:
        get_api_key()
    message = str(exc_info.value)
    assert "PORTKEY_API_KEY" in message
    assert ".env" in message
    assert key_configured() is False


def test_blank_key_counts_as_missing():
    os.environ["PORTKEY_API_KEY"] = "   "
    with pytest.raises(ConfigError):
        get_api_key()
    assert key_configured() is False


def test_key_is_stripped():
    os.environ["PORTKEY_API_KEY"] = "  stripped-key-1234567890 \n"
    assert get_api_key() == "stripped-key-1234567890"
    assert key_configured() is True


def test_config_error_is_a_runtime_error():
    assert issubclass(ConfigError, RuntimeError)


# --------------------------------------------------------------------------- placeholder keys (copied .env.example)


def test_copied_env_example_does_not_hide_the_parent_key(repo: Path):
    shutil.copy(REPO_DIR / ".env.example", repo / ".env")
    write_env(repo.parent / ".env", PORTKEY_API_KEY="parent-key-1234567890")

    load_env(repo)

    assert get_api_key() == "parent-key-1234567890"
    assert key_configured() is True


@pytest.mark.parametrize("placeholder", ["your_portkey_api_key_here", "<your key>", "YOUR-KEY", "paste_key_here"])
def test_placeholder_in_repo_env_does_not_hide_the_parent_key(repo: Path, placeholder: str):
    write_env(repo / ".env", PORTKEY_API_KEY=placeholder)
    write_env(repo.parent / ".env", PORTKEY_API_KEY="parent-key-1234567890")

    load_env(repo)

    assert get_api_key() == "parent-key-1234567890"


def test_placeholder_only_counts_as_not_configured(repo: Path):
    write_env(repo / ".env", PORTKEY_API_KEY="your_portkey_api_key_here")
    load_env(repo)
    os.environ["PORTKEY_API_KEY"] = "your_portkey_api_key_here"  # e.g. exported in the shell

    assert key_configured() is False
    with pytest.raises(ConfigError) as exc_info:
        get_api_key()
    assert "placeholder" in str(exc_info.value)
    assert "PORTKEY_API_KEY" in str(exc_info.value)


def test_placeholder_env_var_is_replaced_by_a_real_key_from_a_file(repo: Path):
    os.environ["PORTKEY_API_KEY"] = "your_portkey_api_key_here"
    write_env(repo.parent / ".env", PORTKEY_API_KEY="parent-key-1234567890")
    load_env(repo)
    assert get_api_key() == "parent-key-1234567890"


def test_env_example_ships_without_a_key_value():
    values = dotenv_values(REPO_DIR / ".env.example")
    assert "PORTKEY_API_KEY" in values
    assert not values["PORTKEY_API_KEY"] or config.is_placeholder(values["PORTKEY_API_KEY"])


@pytest.mark.parametrize("key", ["pk-live-abcdef1234567890", "abcdEFGH1234/xyz+QRST", "test-key-1234567890"])
def test_real_looking_keys_are_not_placeholders(key: str):
    assert config.is_placeholder(key) is False


def test_model_and_gateway_are_locked():
    assert config.MODEL == "gpt-6-luna"
    assert config.PORTKEY_BASE_URL == "https://api.portkey.ai/v1"
    names = {f.name for f in fields(Settings)}
    assert not names & {"model", "base_url", "portkey_base_url"}, "model/gateway must not be configurable"


# --------------------------------------------------------------------------- Settings


def test_settings_defaults_match_contract():
    s = Settings()
    assert s.run_budget_usd == 0.05
    assert s.run_token_cap == 250_000
    assert s.daily_budget_usd == 2.00
    assert s.max_steps_per_agent == 8
    assert s.max_tool_calls_per_run == 30
    assert s.max_agent_depth == 2
    assert s.max_output_tokens == 4000
    assert s.max_input_chars == 8000
    assert s.rate_limit_runs == 15
    assert s.rate_limit_window_s == 600
    assert s.llm_guard is True
    assert s.runs_per_user_per_month == 30
    assert Path(s.data_dir).resolve() == (config.REPO_DIR / "data" / "sample").resolve()
    assert Path(s.runs_dir).resolve() == (config.REPO_DIR / "runs").resolve()
    assert s.request_timeout_s == 90.0


def test_get_settings_with_clean_env_uses_defaults(tmp_path: Path):
    s = get_settings()
    assert s.run_budget_usd == 0.05
    assert s.max_steps_per_agent == 8
    assert s.llm_guard is True
    assert Path(s.runs_dir).resolve() == (tmp_path / "runs").resolve()  # set by the isolated_env fixture


def test_get_settings_is_cached():
    assert get_settings() is get_settings()


def test_settings_env_parsing(tmp_path: Path):
    os.environ.update(
        {
            "RUN_BUDGET_USD": "0.10",
            "RUN_TOKEN_CAP": "5000",
            "DAILY_BUDGET_USD": "1.5",
            "MAX_STEPS_PER_AGENT": "3",
            "MAX_TOOL_CALLS_PER_RUN": "7",
            "MAX_AGENT_DEPTH": "1",
            "MAX_OUTPUT_TOKENS": "999",
            "MAX_INPUT_CHARS": "500",
            "RATE_LIMIT_RUNS": "4",
            "RATE_LIMIT_WINDOW_S": "60",
            "SAFETY_LLM_GUARD": "0",
            "RUNS_PER_USER_PER_MONTH": "12",
            "DATA_DIR": str(tmp_path / "data"),
            "RUNS_DIR": str(tmp_path / "other_runs"),
            "LLM_TIMEOUT_S": "12.5",
        }
    )
    get_settings.cache_clear()
    s = get_settings()
    assert s.run_budget_usd == pytest.approx(0.10)
    assert s.run_token_cap == 5000
    assert s.daily_budget_usd == pytest.approx(1.5)
    assert s.max_steps_per_agent == 3
    assert s.max_tool_calls_per_run == 7
    assert s.max_agent_depth == 1
    assert s.max_output_tokens == 999
    assert s.max_input_chars == 500
    assert s.rate_limit_runs == 4
    assert s.rate_limit_window_s == 60
    assert s.llm_guard is False
    assert s.runs_per_user_per_month == 12
    assert Path(s.data_dir).resolve() == (tmp_path / "data").resolve()
    assert Path(s.runs_dir).resolve() == (tmp_path / "other_runs").resolve()
    assert s.request_timeout_s == pytest.approx(12.5)


def test_relative_data_dir_resolves_against_repo():
    os.environ["DATA_DIR"] = "data/custom_set"
    get_settings.cache_clear()
    s = get_settings()
    assert Path(s.data_dir).is_absolute()
    assert Path(s.data_dir).resolve() == (config.REPO_DIR / "data" / "custom_set").resolve()


@pytest.mark.parametrize("value", ["0", "false", "False", "FALSE"])
def test_llm_guard_can_be_disabled(value: str):
    os.environ["SAFETY_LLM_GUARD"] = value
    get_settings.cache_clear()
    assert get_settings().llm_guard is False


@pytest.mark.parametrize("value", ["1", "true", "True"])
def test_llm_guard_enabled_values(value: str):
    os.environ["SAFETY_LLM_GUARD"] = value
    get_settings.cache_clear()
    assert get_settings().llm_guard is True


def test_bad_settings_values_fall_back_to_defaults():
    os.environ.update(
        {
            "RUN_BUDGET_USD": "cheap",
            "RUN_TOKEN_CAP": "lots",
            "DAILY_BUDGET_USD": "",
            "MAX_STEPS_PER_AGENT": "eight",
            "MAX_INPUT_CHARS": "1e9x",
            "LLM_TIMEOUT_S": "soon",
        }
    )
    get_settings.cache_clear()
    s = get_settings()
    assert s.run_budget_usd == 0.05
    assert s.run_token_cap == 250_000
    assert s.daily_budget_usd == 2.00
    assert s.max_steps_per_agent == 8
    assert s.max_input_chars == 8000
    assert s.request_timeout_s == 90.0
