"""Beyond Your Circle domain: match a student's stated purpose to stored public listings.

- ``tools``: search_listings / get_listing over the collected records (no network, no model).
- ``models``: the matcher's structured output (what was understood + picks with quotes).
- ``verify``: deterministic verifier that keeps only retrieved, available records and checks quotes.
- ``prompts/matcher.md``: the matcher's system prompt.
"""

from __future__ import annotations

from pathlib import Path

from app.domain.conditions import effective_understood
from app.domain.models import Pick, Recommendations, RunOptions, UnderstoodRequest
from app.domain.tools import ListingSession, register_domain_tools
from app.domain.verify import verify_output

PROMPTS_DIR = Path(__file__).resolve().parent / "prompts"


def load_prompt(name: str) -> str:
    """System prompt text for agent ``name`` (``prompts/<name>.md``), with normalized line endings.

    The text must stay byte-identical between runs: it is the cached prompt prefix.
    """
    text = (PROMPTS_DIR / f"{name}.md").read_text(encoding="utf-8-sig")
    return text.replace("\r\n", "\n").strip()


__all__ = [
    "PROMPTS_DIR",
    "ListingSession",
    "Pick",
    "Recommendations",
    "RunOptions",
    "UnderstoodRequest",
    "effective_understood",
    "load_prompt",
    "register_domain_tools",
    "verify_output",
]
