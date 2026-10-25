"""Structured output of the matcher agent (validated with a strict JSON schema).

The model states only what the user asked for and why a listing may serve that purpose, backed by
exact quotes. Participation conditions, dates, places, costs and links are computed or restored by
the server from the stored record (app/domain/conditions.py, verify.py), never taken from the model.
"""

from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, StrictBool


class _Strict(BaseModel):
    model_config = ConfigDict(extra="forbid")


SOM_IDENTITY = "Yale SOM graduate student"
_PARTICIPATION_NOTE = {"in_person": "wants to take part in person", "online": "wants to take part online",
                       "either": "is fine with in person or online"}
_TIME_NOTE = {"this_week": "wants something this week (the next 7 days)",
              "next_few_weeks": "wants something in the next few weeks"}


class RunOptions(_Strict):
    """Conditions the user set with the form next to the request box.

    Enums only, so no client free text can reach the model through them; the server turns them into
    fixed sentences (``note``) and applies them in code (``conditions.effective_understood``).
    A missing or false value means "not set": it never says anything about the user.
    """

    som_student: StrictBool | None = None
    participation: Literal["in_person", "online", "either"] | None = None
    time_window: Literal["this_week", "next_few_weeks"] | None = None

    def is_set(self) -> bool:
        return bool(self.som_student) or self.participation is not None or self.time_window is not None

    def public(self) -> dict:
        """Only the fields the user set (for traces and the UI)."""
        out: dict = {}
        if self.som_student:
            out["som_student"] = True
        if self.participation:
            out["participation"] = self.participation
        if self.time_window:
            out["time_window"] = self.time_window
        return out

    def note(self) -> str:
        """Server-written sentence appended to the model input (never contains client text)."""
        parts = []
        if self.som_student:
            parts.append(f"the user is a {SOM_IDENTITY}")
        if self.participation:
            parts.append(f"the user {_PARTICIPATION_NOTE[self.participation]}")
        if self.time_window:
            parts.append(f"the user {_TIME_NOTE[self.time_window]}")
        return ("Conditions the user set with the form (treat them exactly like the user's own words): "
                + "; ".join(parts) + ".")


class UnderstoodRequest(_Strict):
    interests: list[str] = Field(description="Interests in the user's own words, e.g. ['film photography'].")
    purpose: str | None = Field(description="What the user wants to get out of it, in their words; null if not said.")
    purpose_type: Literal["meet_people_or_join_community", "learn_or_discuss_topic", "do_the_activity", "watch_or_spectate", "not_stated"]
    participation: Literal["in_person", "online", "either", "not_stated"]
    play_or_watch: Literal["play", "watch", "either", "not_applicable", "not_stated"]
    experience_level: str | None = Field(description="Only if the user said it, e.g. 'beginner', 'never taken a class'; else null.")
    identity: str | None = Field(description="Only if the user said it, e.g. 'Yale SOM MBA student'; else null.")
    time_window: Literal["this_week", "next_few_weeks", "not_stated"] = Field(
        description="'this_week' or 'next_few_weeks' only if the user asked for that time; recurring/regular is NOT a time window.")
    time_preference: str | None = Field(description="Other timing words the user used (e.g. 'weekends', 'regularly'); else null.")
    location_preference: str | None = Field(description="Only if the user said it; else null.")
    not_stated: list[str] = Field(description="Which of: purpose, participation, experience_level, identity, time_window, location_preference the user did not say.")


class Pick(_Strict):
    record_id: str = Field(description="Exactly as returned by search_listings/get_listing.")
    fit: Literal["close", "exploratory"]
    why: str = Field(description="One or two sentences on how this listing serves the user's PURPOSE. No dates, times, prices, places or links.")
    interaction: str = Field(description="What kind of contact with other people the page describes (e.g. group meetings, competitions, a workshop). If the page does not describe it, say 'not described on the page'.")
    interaction_quote: str | None = Field(description="Exact words from the listing that show the interaction; null if the page does not describe it.")
    exploration_link: str | None = Field(description="Exploratory picks only: the concrete connection to the user's interest; null for close picks.")
    link_quote: str | None = Field(description="Exploratory picks only: exact words from the listing that show that connection; else null.")
    evidence_quotes: list[str] = Field(description="1-3 exact phrases (5-25 words) copied from the get_listing text that show topic relevance.")


class Recommendations(_Strict):
    understood: UnderstoodRequest
    picks: list[Pick] = Field(description="At most 6: close matches first, then at most 2 exploratory ones. Empty if nothing fits.")
    summary: str = Field(description="Two or three sentences for the user, honest about gaps.")
    follow_up_question: str | None = Field(description="One question if missing information would change the picks; else null.")
