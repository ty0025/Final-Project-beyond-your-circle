"""Collect public events/programs from the connected sources (no model calls, no API key).

    python scripts/collect.py refresh [--source caw-photo]   # live, bounded fetch (needs internet)
    python scripts/collect.py status                          # last attempt / last success per source
    python scripts/collect.py show [--source ycgs-events]     # stored records (cached or snapshot)
    python scripts/collect.py snapshot [--source caw-photo]   # copy last real success to data/snapshots/
    python scripts/collect.py reparse [--source caw-photo]    # re-run parsers on saved raw pages (offline)
    python scripts/collect.py sources                         # connected and not-connected sources

Runtime output goes to runs/collect/ (gitignored); snapshots in data/snapshots/ are committed.
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

REPO_DIR = Path(__file__).resolve().parents[1]
if str(REPO_DIR) not in sys.path:
    sys.path.insert(0, str(REPO_DIR))

from app.collect.sources import NOT_CONNECTED, SOURCES  # noqa: E402
from app.collect.store import load_source, read_status, refresh_all, reparse_cached, save_snapshot  # noqa: E402


def _summary(result) -> str:
    lines = [f"[{result.source_id}] mode={result.data_mode} collected_at={result.collected_at} records={len(result.records)}"]
    st = result.status or {}
    if st:
        lines.append(
            f"  last attempt {st.get('last_attempt_at')} -> {st.get('last_outcome')}; pages={st.get('pages_fetched')}; "
            f"errors={len(st.get('errors', []))}; carried_forward={st.get('carried_forward', 0)}"
        )
        for note in st.get("notes", []):
            lines.append(f"  note: {note}")
        for err in st.get("errors", []):
            lines.append(f"  error: {err['kind']} {err['url']}")
    for r in result.records:
        when = r.start or (next((s.start for s in r.sessions if s.start), None)) or r.date_text or "date unknown"
        lines.append(f"  - {r.kind:7} {when} | {r.title} | missing={','.join(r.missing) or '-'}")
    return "\n".join(lines)


def main(argv: list[str] | None = None) -> int:
    sys.stdout.reconfigure(encoding="utf-8")
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("command", choices=["refresh", "status", "show", "snapshot", "reparse", "sources"])
    parser.add_argument("--source", choices=sorted(SOURCES), help="limit to one source")
    args = parser.parse_args(argv)
    ids = [args.source] if args.source else list(SOURCES)

    if args.command == "sources":
        for s in SOURCES.values():
            print(f"CONNECTED  {s.id}: {s.name} ({s.publisher_type}) {s.listing_url}\n  coverage: {s.coverage}")
        for url, why in NOT_CONNECTED.items():
            print(f"NOT CONNECTED  {url}\n  {why}")
    elif args.command == "refresh":
        for result in refresh_all(ids):
            print(_summary(result))
    elif args.command == "status":
        print(json.dumps({k: {x: v for x, v in st.items() if x != "requests"} for k, st in read_status().items() if k in ids}, indent=2))
    elif args.command == "show":
        for i in ids:
            print(_summary(load_source(i)))
    elif args.command == "reparse":
        for i in ids:
            print(_summary(reparse_cached(i)))
    elif args.command == "snapshot":
        for i in ids:
            print(f"wrote {save_snapshot(i).relative_to(REPO_DIR)}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
