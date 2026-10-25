"""Refresh connected sources and keep the last successful records.

Data modes returned to callers:
- ``live``: records produced by the refresh that just ran.
- ``cached``: the last successful refresh on this machine (``runs/collect/``, gitignored).
- ``snapshot``: a committed, dated snapshot of a real collection (``data/snapshots/``), so a
  fresh clone works offline. Its ``collected_at`` is always shown; it is never presented as live.
- ``unavailable``: nothing collected yet. This means "no data", not "no events".

A failed or empty refresh never overwrites the last success. If some detail pages fail, the
previous records for those pages are carried forward with their original ``collected_at``.
"""

from __future__ import annotations

import json
import os
from dataclasses import dataclass, field
from datetime import date, datetime
from pathlib import Path
from typing import Any, Callable

import httpx

from app.collect.fetch import BoundedFetcher, FetchError, Page, utc_now_iso
from app.collect.records import Record
from app.collect.sources import NY, SOURCES, Source
from app.config import REPO_DIR, get_settings

SNAPSHOT_DIR = REPO_DIR / "data" / "snapshots"


def collect_dir(runs_dir: Path | None = None) -> Path:
    return (runs_dir or get_settings().runs_dir) / "collect"


def _write_json(path: Path, payload: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_suffix(path.suffix + ".tmp")
    tmp.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
    os.replace(tmp, path)


def _read_json(path: Path) -> Any | None:
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return None


def _save_raw(page, path: Path) -> None:
    """Keep the fetched HTML locally (gitignored) so field checks can be redone without refetching."""
    path.parent.mkdir(parents=True, exist_ok=True)
    header = f"<!-- url={page.url} fetched_at={page.fetched_at} bytes={page.n_bytes} -->\n"
    path.write_text(header + page.text, encoding="utf-8")


def read_status(runs_dir: Path | None = None) -> dict[str, dict]:
    return _read_json(collect_dir(runs_dir) / "status.json") or {}


def _write_status(source_id: str, status: dict, runs_dir: Path | None) -> None:
    all_status = read_status(runs_dir)
    all_status[source_id] = status
    _write_json(collect_dir(runs_dir) / "status.json", all_status)


@dataclass
class SourceResult:
    source_id: str
    data_mode: str  # live | cached | snapshot | unavailable
    collected_at: str | None
    records: list[Record] = field(default_factory=list)
    status: dict = field(default_factory=dict)

    def to_dict(self) -> dict:
        return {
            "source_id": self.source_id,
            "data_mode": self.data_mode,
            "collected_at": self.collected_at,
            "n_records": len(self.records),
            "status": self.status,
            "records": [r.model_dump() for r in self.records],
        }


def _load_payload(payload: dict | None, mode: str, source_id: str, status: dict) -> SourceResult | None:
    if not payload or not payload.get("records"):
        return None
    try:
        records = [Record.model_validate(r) for r in payload["records"]]
    except ValueError:
        return None
    return SourceResult(source_id, mode, payload.get("collected_at"), records, status)


def load_source(source_id: str, *, runs_dir: Path | None = None, snapshot_dir: Path | None = None) -> SourceResult:
    """Best stored data without touching the network: cached, else committed snapshot, else unavailable."""
    status = read_status(runs_dir).get(source_id, {})
    cached = _load_payload(_read_json(collect_dir(runs_dir) / f"{source_id}.json"), "cached", source_id, status)
    if cached:
        return cached
    snap = _load_payload(_read_json((snapshot_dir or SNAPSHOT_DIR) / f"{source_id}.json"), "snapshot", source_id, status)
    if snap:
        return snap
    return SourceResult(source_id, "unavailable", None, [], status)


def refresh_source(
    source: Source,
    *,
    runs_dir: Path | None = None,
    snapshot_dir: Path | None = None,
    transport: httpx.BaseTransport | None = None,
    sleep: Callable[[float], None] | None = None,
    today: date | None = None,
    simulated: bool = False,
) -> SourceResult:
    """One bounded refresh. Returns live records on success, otherwise the stored fallback.

    ``simulated=True`` marks the stored status as a simulated outage/test (shown as such in the UI).
    """
    today = today or datetime.now(NY).date()
    attempt_at = utc_now_iso()
    kwargs: dict[str, Any] = {"min_delay_s": source.min_delay_s, "transport": transport}
    if sleep is not None:
        kwargs["sleep"] = sleep
    records: list[Record] = []
    errors: list[dict] = []
    notes: list[str] = []
    failed_urls: list[str] = []
    listing_ok = False
    with BoundedFetcher(source.allowed_hosts, 1 + source.max_detail_pages, **kwargs) as fetcher:
        try:
            listing = fetcher.get(source.listing_url)
            urls, notes = source.parse_listing(listing, today)
            listing_ok = True
        except FetchError as exc:
            urls = []
            errors.append({"url": exc.url, "kind": exc.kind, "message": str(exc)})
        if len(urls) > source.max_detail_pages:
            notes.append(f"{len(urls) - source.max_detail_pages} detail page(s) skipped by the page cap")
            urls = urls[: source.max_detail_pages]
        for url in urls:
            try:
                page = fetcher.get(url)
                record = source.parse_detail(page, source)
                records.append(record)
                _save_raw(page, collect_dir(runs_dir) / "raw" / source.id / f"{record.record_id}.html")
            except FetchError as exc:
                failed_urls.append(url)
                errors.append({"url": exc.url, "kind": exc.kind, "message": str(exc)})
            except Exception as exc:  # parser bug on an unexpected page: keep going, record it
                failed_urls.append(url)
                errors.append({"url": url, "kind": "parse_error", "message": f"{type(exc).__name__}: {exc}"})
        robots = {h: fetcher.robots_note(h) for h in sorted(source.allowed_hosts)}
        requests_log = list(fetcher.log)

    previous = _read_json(collect_dir(runs_dir) / f"{source.id}.json")
    carried: list[dict] = []
    if records and previous and failed_urls:
        carried = [r for r in previous.get("records", []) if r.get("url") in failed_urls]

    if records:
        outcome = "partial" if errors else "ok"
    elif listing_ok and not errors:
        outcome = "empty"  # the listing had no items in the window; previous success is kept
    else:
        outcome = "failed"

    status = {
        "last_attempt_at": attempt_at,
        "last_outcome": outcome,
        "records_this_attempt": len(records),
        "carried_forward": len(carried),
        "pages_fetched": sum(1 for e in requests_log if not e["url"].endswith("/robots.txt")),
        "errors": errors,
        "notes": notes,
        "robots": robots,
        "requests": requests_log,
        "coverage": source.coverage,
        "last_success_at": (previous or {}).get("collected_at"),
        "simulated": simulated,
    }
    if records:
        status["last_success_at"] = attempt_at
        payload = {
            "source_id": source.id,
            "source_name": source.name,
            "collected_at": attempt_at,
            "coverage": source.coverage,
            "records": [r.model_dump() for r in records] + carried,
        }
        _write_json(collect_dir(runs_dir) / f"{source.id}.json", payload)
        _write_status(source.id, status, runs_dir)
        live = [Record.model_validate(r) for r in payload["records"]]
        return SourceResult(source.id, "live", attempt_at, live, status)

    _write_status(source.id, status, runs_dir)
    fallback = load_source(source.id, runs_dir=runs_dir, snapshot_dir=snapshot_dir)
    fallback.status = status
    return fallback


def reparse_cached(source_id: str, *, runs_dir: Path | None = None) -> SourceResult:
    """Re-run the current parser on the raw pages saved by the last refresh (no network).

    Keeps each record's original ``collected_at`` (the time its page was fetched).
    """
    path = collect_dir(runs_dir) / f"{source_id}.json"
    payload = _read_json(path)
    if not payload or not payload.get("records"):
        raise FileNotFoundError(f"No cached collection for {source_id}.")
    source = SOURCES[source_id]
    records: list[Record] = []
    for old in payload["records"]:
        raw_path = collect_dir(runs_dir) / "raw" / source_id / f"{old['record_id']}.html"
        header, _, body = raw_path.read_text(encoding="utf-8").partition("\n")
        meta = dict(part.split("=", 1) for part in header.strip("<!-> ").split() if "=" in part)
        page = Page(
            url=meta.get("url", old["url"]),
            requested_url=meta.get("url", old["url"]),
            status=200,
            content_type="text/html",
            text=body,
            n_bytes=int(meta.get("bytes", 0) or 0),
            fetched_at=meta.get("fetched_at", old["collected_at"]),
        )
        records.append(source.parse_detail(page, source))
    payload["records"] = [r.model_dump() for r in records]
    payload["reparsed_at"] = utc_now_iso()
    _write_json(path, payload)
    return SourceResult(source_id, "cached", payload.get("collected_at"), records, read_status(runs_dir).get(source_id, {}))


def refresh_all(source_ids: list[str] | None = None, **kwargs: Any) -> list[SourceResult]:
    ids = source_ids or list(SOURCES)
    return [refresh_source(SOURCES[i], **kwargs) for i in ids]


def save_snapshot(source_id: str, *, runs_dir: Path | None = None, snapshot_dir: Path | None = None) -> Path:
    """Copy the last successful real collection into the committed snapshot folder."""
    payload = _read_json(collect_dir(runs_dir) / f"{source_id}.json")
    if not payload or not payload.get("records"):
        raise FileNotFoundError(f"No successful collection for {source_id} to snapshot.")
    status = read_status(runs_dir).get(source_id, {})
    payload = {
        **payload,
        "snapshot_note": (
            "Fixed snapshot of a real automated collection. Shown as 'snapshot' with its collected_at "
            "date; not live data."
        ),
        "collection_outcome": status.get("last_outcome"),
        "requests": status.get("requests", []),
        "robots": status.get("robots", {}),
    }
    path = (snapshot_dir or SNAPSHOT_DIR) / f"{source_id}.json"
    _write_json(path, payload)
    return path
