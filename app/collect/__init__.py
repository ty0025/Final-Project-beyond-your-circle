"""Bounded collection from verified public sources (no model calls; deterministic extraction).

- ``fetch``: allowlisted, robots-aware, size/time/page-capped HTTPS fetcher (no API key).
- ``records``: the unified event/program/community record with evidence and explicit unknowns.
- ``sources``: connected sources, their parsers, and checked-but-not-connected candidates.
- ``store``: refresh, last-success persistence, and cached/snapshot fallback.
"""
