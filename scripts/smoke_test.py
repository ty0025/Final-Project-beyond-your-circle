"""One tiny live call through LLMClient: proves the key, gateway and model work.

Usage (from the repo root):  python scripts/smoke_test.py

Prints the reply, latency, token usage and cost. Never prints the API key.
The call is not written to the usage ledger, so it does not skew tokenomics.
"""

from __future__ import annotations

import asyncio
import json
import sys
from pathlib import Path

REPO_DIR = Path(__file__).resolve().parents[1]
if str(REPO_DIR) not in sys.path:
    sys.path.insert(0, str(REPO_DIR))

from app.config import APP_SLUG, MODEL, PORTKEY_BASE_URL, ConfigError, env_files_loaded, key_configured  # noqa: E402
from app.llm import LLMClient, LLMError  # noqa: E402
from app.pricing import cost_usd  # noqa: E402

INSTRUCTIONS = "You are a terse assistant. Reply in at most eight words."
QUESTION = "Say hello to the MGT 409 class."


async def main() -> int:
    print(f"Model:      {MODEL} via {PORTKEY_BASE_URL}")
    print(f".env files: {', '.join(env_files_loaded()) or 'none found'}")
    print(f"Key set:    {'yes' if key_configured() else 'no'}")

    try:
        client = LLMClient()
    except ConfigError as exc:
        print(f"\nSetup problem: {exc}")
        return 2

    try:
        result = await client.create(
            instructions=INSTRUCTIONS,
            input_items=[{"role": "user", "content": [{"type": "input_text", "text": QUESTION}]}],
            cache_key=f"{APP_SLUG}-smoke",
            max_output_tokens=400,
        )
    except LLMError as exc:
        print(f"\nModel call failed: {exc}")
        return 1
    finally:
        await client.aclose()

    print(f"\nReply:      {result.output_text.strip() or '(empty)'}")
    print(f"Latency:    {result.latency_ms} ms")
    print(f"Response:   {result.response_id}")
    print("Usage:      " + json.dumps(result.usage.to_dict()))
    print(f"Cost:       ${cost_usd(result.usage):.8f}")
    return 0


if __name__ == "__main__":
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8")
    sys.exit(asyncio.run(main()))
