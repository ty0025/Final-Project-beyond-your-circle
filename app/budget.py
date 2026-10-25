"""Per-run and daily spend guards."""

from __future__ import annotations

from app.config import Settings
from app.ledger import ModelCall, UsageLedger
from app.pricing import Usage


class BudgetExceeded(Exception):
    """A spend cap was reached. ``scope`` is "run_calls", "run_tokens", "run_usd" or "daily_usd"."""

    def __init__(self, scope: str, limit: float, spent: float) -> None:
        self.scope = scope
        self.limit = limit
        self.spent = spent
        super().__init__(self.describe())

    def describe(self) -> str:
        if self.scope == "run_calls":
            return f"Run model-call cap reached: {int(self.spent)} of {int(self.limit)} calls used."
        if self.scope == "run_tokens":
            return f"Run token cap reached: {int(self.spent):,} of {int(self.limit):,} tokens used."
        label = {"run_usd": "Run budget", "daily_usd": "Daily budget"}.get(self.scope, self.scope)
        return f"{label} reached: ${self.spent:.4f} spent of ${self.limit:.2f}."


class RunBudget:
    """Running totals for one run; checked before every model call."""

    def __init__(self, settings: Settings, ledger: UsageLedger, run_id: str) -> None:
        self.settings = settings
        self.ledger = ledger
        self.run_id = run_id
        self.usage = Usage()
        self.cost_usd = 0.0
        self.n_calls = 0  # every attempt, including failed ones and retries
        self.n_failed = 0
        self.usage_missing = False

    def check_before_call(self) -> None:
        settings = self.settings
        if self.n_calls >= settings.max_model_calls_per_run:
            raise BudgetExceeded("run_calls", settings.max_model_calls_per_run, self.n_calls)
        tokens = self.usage.total_tokens
        if tokens >= settings.run_token_cap:
            raise BudgetExceeded("run_tokens", settings.run_token_cap, tokens)
        if self.cost_usd >= settings.run_budget_usd:
            raise BudgetExceeded("run_usd", settings.run_budget_usd, self.cost_usd)
        today = self.ledger.today_cost_usd()
        if today >= settings.daily_budget_usd:
            raise BudgetExceeded("daily_usd", settings.daily_budget_usd, today)

    def record(self, call: ModelCall) -> None:
        self.usage = self.usage + call.usage
        self.cost_usd += call.cost_usd or 0.0  # None = not measured (failed call or missing usage)
        self.n_calls += 1
        if call.status != "ok":
            self.n_failed += 1
        if call.usage.missing:
            self.usage_missing = True
