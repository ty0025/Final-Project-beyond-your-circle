"""The committed cost evidence (evidence/q08_tokenomics.*) must follow from the committed ledger copies."""

from __future__ import annotations

import importlib.util
import json
from pathlib import Path

import pytest

REPO = Path(__file__).resolve().parents[1]


def _script():
    spec = importlib.util.spec_from_file_location("tokenomics_q8", REPO / "scripts" / "tokenomics_q8.py")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def test_cost_summary_categories_are_separate_and_complete():
    d = _script().build()
    cs = d["cost_summary"]
    typical, total = cs["i_typical_run_sample"], cs["ii_development_and_safety_testing_total"]
    assert d["cutoff_utc"] == "2026-10-25T21:23:30Z"
    assert (typical["runs"], typical["calls"]) == (9, 33)
    assert (total["runs"], total["calls"]) == (13, 46)
    assert typical["cost_usd"] == pytest.approx(0.007737975, abs=1e-12)
    assert total["cost_usd"] == pytest.approx(0.011382535, abs=1e-12)
    assert typical["per_run"]["mean_usd"] == pytest.approx(0.007737975 / 9, abs=1e-12)
    checks = d["checks_all_project_rows"]
    assert all(checks[k] for k in ("all_live", "all_status_ok", "no_missing_usage", "cost_recomputed_equals_ledger",
                                   "cached_plus_write_within_input", "reasoning_within_output", "unique_response_ids",
                                   "all_at_or_before_cutoff"))
    # Scenario arithmetic: mean cost per run x runs per user per month x users.
    for s in d["scaling_scenarios"]:
        assert s["10000_users_per_month_usd"] == pytest.approx(typical["per_run"]["mean_usd"] * s["runs_per_user_per_month"] * 10_000)


def test_committed_evidence_matches_the_script():
    committed = json.loads((REPO / "evidence" / "q08_tokenomics.json").read_text(encoding="utf-8"))
    fresh = _script().build()
    for key in ("i_typical_run_sample", "ii_development_and_safety_testing_total"):
        assert committed["cost_summary"][key] == fresh["cost_summary"][key]
    assert committed["scaling_scenarios"] == fresh["scaling_scenarios"]
    assert committed["cutoff_utc"] == fresh["cutoff_utc"]


def test_every_cost_figure_from_the_committed_copies_is_digit_for_digit_the_same():
    # Exact float equality on every Python >= 3.11 (math.fsum for totals, in-order += per run): sum() of floats
    # rounds differently before and after Python 3.12, which broke this on 3.11. Sections that read the
    # git-ignored local runs/ (local_ledger_check, iii) depend on the machine and are not compared.
    committed = json.loads((REPO / "evidence" / "q08_tokenomics.json").read_text(encoding="utf-8"))
    fresh = _script().build()
    for key in ("groups", "typical_runs", "comparisons_computed_from_the_same_rows", "checks_all_project_rows",
                "scaling_scenarios"):
        assert committed[key] == fresh[key], key


def test_load_skips_a_half_written_or_corrupt_line(tmp_path):
    good = {"run_id": "r_x", "mode": "live", "ts": "2026-10-26T00:00:00Z"}
    path = tmp_path / "usage.jsonl"
    path.write_text(json.dumps(good) + "\n\n[1, 2]\n" + '{"run_id": "r_y", "mo', encoding="utf-8")  # crash mid-write
    assert _script().load(path) == [good]


def test_local_ledger_checks_survive_a_half_written_last_line(tmp_path):
    m = _script()
    rows, _ = m.collect()  # committed copies, read before REPO is pointed at the temporary folder
    local = tmp_path / "runs" / "usage.jsonl"
    local.parent.mkdir()
    local.write_text("\n".join([json.dumps({"run_id": "r_new", "mode": "live", "ts": "2026-10-26T00:00:00Z"}),
                                json.dumps({"run_id": "r_old", "input_tokens": 10, "cached_tokens": 0, "cache_write_tokens": 0,
                                            "output_tokens": 5, "reasoning_tokens": 0, "cost_usd": 0.001}),  # legacy: no "mode"
                                '{"run_id": "r_y", "mo']), encoding="utf-8")
    m.REPO, m.LOCAL_LEDGERS, m.LEGACY_LEDGERS = tmp_path, {"normal": local}, (local,)
    assert m.local_ledger_check(rows)["normal"]["live_rows_not_counted"] == ["r_new"]  # reported, never folded in
    assert m.legacy_history()["calls"] == 1
