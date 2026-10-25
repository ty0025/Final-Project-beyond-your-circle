"""Run events: streamed to the browser as NDJSON and persisted as a trace file."""

from __future__ import annotations

import asyncio
import json
import os
import re
import secrets
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from app.safety import redact_data

RUN_ID_RE = re.compile(r"^r_[0-9a-f]{12}$")
_SAFE_FILENAME_RE = re.compile(r"^[A-Za-z0-9_-]{1,64}$")


def new_run_id() -> str:
    return "r_" + secrets.token_hex(6)


def utc_now_ms() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="milliseconds").replace("+00:00", "Z")


def clip(text: Any, limit: int) -> str:
    """Shorten text to at most ``limit`` characters, marking the cut with an ellipsis."""
    text = "" if text is None else str(text)
    if len(text) <= limit:
        return text
    return text[: max(0, limit - 1)] + "…"


@dataclass
class Event:
    seq: int
    ts: str
    run_id: str
    type: str
    agent: str | None
    data: dict

    def to_dict(self) -> dict:
        return {
            "seq": self.seq,
            "ts": self.ts,
            "run_id": self.run_id,
            "type": self.type,
            "agent": self.agent,
            "data": self.data,
        }

    def to_json(self) -> str:
        return json.dumps(self.to_dict(), ensure_ascii=False, separators=(",", ":"), default=str)


class RunTrace:
    """Ordered event log for one run. ``queue`` (set by the server) receives every Event."""

    def __init__(self, run_id: str | None = None) -> None:
        self.run_id = run_id or new_run_id()
        self.started_at = utc_now_ms()
        self.events: list[Event] = []
        self.queue: asyncio.Queue | None = None
        self._seq = 0

    def emit(self, type: str, agent: str | None = None, **data: Any) -> Event:
        """Record an event. Secret-shaped strings in ``data`` are redacted here, once, so the live
        stream, the saved trace and its replay all show the same redacted values."""
        self._seq += 1
        event = Event(
            seq=self._seq, ts=utc_now_ms(), run_id=self.run_id, type=type, agent=agent, data=redact_data(data)
        )
        self.events.append(event)
        if self.queue is not None:
            self.queue.put_nowait(event)
        return event

    def to_dict(self) -> dict:
        return {
            "run_id": self.run_id,
            "started_at": self.started_at,
            "events": [event.to_dict() for event in self.events],
        }

    def save(self, runs_dir: Path) -> Path:
        """Write ``runs_dir/traces/<run_id>.json`` (atomically where the OS allows)."""
        if not _SAFE_FILENAME_RE.fullmatch(self.run_id):
            raise ValueError(f"unsafe run_id for a file name: {self.run_id!r}")
        path = Path(runs_dir) / "traces" / f"{self.run_id}.json"
        path.parent.mkdir(parents=True, exist_ok=True)
        payload = json.dumps(self.to_dict(), ensure_ascii=False, indent=2, default=str)
        tmp = path.with_name(path.name + ".tmp")
        tmp.write_text(payload, encoding="utf-8")
        try:
            os.replace(tmp, path)
        except OSError:  # e.g. the target is open by a reader on Windows
            path.write_text(payload, encoding="utf-8")
            tmp.unlink(missing_ok=True)
        return path

    @staticmethod
    def load(runs_dir: Path, run_id: str) -> dict | None:
        """Saved trace for ``run_id``, or None if the id is invalid, unknown or unreadable."""
        if not isinstance(run_id, str) or not RUN_ID_RE.fullmatch(run_id):
            return None
        path = Path(runs_dir) / "traces" / f"{run_id}.json"
        try:
            data = json.loads(path.read_text(encoding="utf-8"))
        except (OSError, ValueError):
            return None
        return data if isinstance(data, dict) else None
