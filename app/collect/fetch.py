"""Bounded, polite fetcher for allowlisted public pages.

Separate from the model client on purpose: no API key, no auth headers, no cookies, no
environment proxies or .netrc (``trust_env=False``). Every request is HTTPS to an allowlisted
host, obeys robots.txt and a per-host delay, follows at most a few redirects (each hop
re-checked against the allowlist), and is capped in time, bytes and page count.
"""

from __future__ import annotations

import time
import urllib.robotparser
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Callable
from urllib.parse import urljoin, urlsplit

import httpx

USER_AGENT = "BeyondYourCircle/0.1 (MGT409 student project; manual refresh of public pages)"
ROBOTS_AGENT = "BeyondYourCircle"


@dataclass(frozen=True)
class FetchLimits:
    timeout_s: float = 15.0  # per request (connect 5 s); also a wall-clock cap while streaming
    max_bytes: int = 2_000_000
    max_redirects: int = 3
    max_delay_s: float = 15.0  # upper bound on any robots crawl-delay we honour


class FetchError(Exception):
    """kind: not_allowed | robots_disallow | page_cap | redirect_blocked | too_many_redirects |
    too_large | http_status | bad_content_type | timeout | network"""

    def __init__(self, kind: str, message: str, url: str) -> None:
        super().__init__(f"{kind}: {message}")
        self.kind = kind
        self.url = url


@dataclass
class Page:
    url: str  # final URL after redirects
    requested_url: str
    status: int
    content_type: str
    text: str
    n_bytes: int
    fetched_at: str  # UTC ISO
    redirects: list[str] = field(default_factory=list)


def utc_now_iso() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


class SimulatedOutageTransport(httpx.BaseTransport):
    """Every request fails like a dropped connection. Only for clearly labelled outage demos/tests."""

    def handle_request(self, request: httpx.Request) -> httpx.Response:
        raise httpx.ConnectError("simulated outage (COLLECT_SIMULATE_OUTAGE)", request=request)


def _real_transport() -> httpx.BaseTransport:
    # Tests replace this (tests/conftest.py) so the offline suite can never reach the network.
    return httpx.HTTPTransport(retries=0)


class BoundedFetcher:
    def __init__(
        self,
        allowed_hosts: frozenset[str] | set[str],
        max_pages: int,
        *,
        min_delay_s: float = 1.0,
        limits: FetchLimits = FetchLimits(),
        transport: httpx.BaseTransport | None = None,
        sleep: Callable[[float], None] = time.sleep,
        clock: Callable[[], float] = time.monotonic,
    ) -> None:
        self.allowed_hosts = frozenset(h.lower() for h in allowed_hosts)
        self.max_pages = max_pages
        self.min_delay_s = min_delay_s
        self.limits = limits
        self._sleep = sleep
        self._clock = clock
        self._client = httpx.Client(
            transport=transport or _real_transport(),
            headers={"User-Agent": USER_AGENT, "Accept": "text/html,application/xhtml+xml;q=0.9,*/*;q=0.5"},
            timeout=httpx.Timeout(limits.timeout_s, connect=5.0),
            follow_redirects=False,
            trust_env=False,
        )
        self.pages_used = 0
        self.log: list[dict] = []  # one entry per HTTP request (pages, redirects, robots.txt)
        self._robots: dict[str, urllib.robotparser.RobotFileParser | None] = {}
        self._robots_note: dict[str, str] = {}
        self._robots_unreachable: dict[str, str] = {}  # host -> error kind (e.g. network, timeout)
        self._last_request_at: dict[str, float] = {}

    def close(self) -> None:
        self._client.close()

    def __enter__(self) -> "BoundedFetcher":
        return self

    def __exit__(self, *exc: object) -> None:
        self.close()

    # ------------------------------------------------------------------ policy checks

    def is_allowed(self, url: str) -> bool:
        try:
            parts = urlsplit(url)
            port = parts.port
        except ValueError:  # malformed port or IPv6 literal: never fetched (was an uncaught crash)
            return False
        return (
            parts.scheme == "https"
            and (parts.hostname or "").lower() in self.allowed_hosts
            and parts.username is None
            and parts.password is None
            and port in (None, 443)
        )

    def robots_note(self, host: str) -> str | None:
        return self._robots_note.get(host)

    def _robots_for(self, host: str) -> urllib.robotparser.RobotFileParser | None:
        """Parsed robots.txt for host; None means 'everything allowed' (robots.txt absent)."""
        if host in self._robots:
            return self._robots[host]
        url = f"https://{host}/robots.txt"
        parser = urllib.robotparser.RobotFileParser()
        try:
            status, body, _ = self._request(url, max_bytes=200_000)
        except FetchError as exc:
            parser.parse(["User-agent: *", "Disallow: /"])  # unreachable robots.txt -> be conservative
            self._robots_note[host] = f"robots.txt unreachable ({exc.kind}); treated as disallow-all"
            self._robots_unreachable[host] = exc.kind
            self._robots[host] = parser
            return parser
        if status == 200:
            parser.parse(body.decode("utf-8", "replace").splitlines())
            self._robots_note[host] = "robots.txt read"
        elif 400 <= status < 500:
            parser = None
            self._robots_note[host] = f"robots.txt HTTP {status}; treated as allow-all"
        else:
            parser.parse(["User-agent: *", "Disallow: /"])
            self._robots_note[host] = f"robots.txt HTTP {status}; treated as disallow-all"
        self._robots[host] = parser
        return parser

    def _polite_wait(self, host: str) -> None:
        robots = self._robots.get(host)
        delay = self.min_delay_s
        if robots is not None:
            crawl_delay = robots.crawl_delay(ROBOTS_AGENT)
            if crawl_delay:
                delay = max(delay, float(crawl_delay))
        delay = min(delay, self.limits.max_delay_s)
        last = self._last_request_at.get(host)
        if last is not None:
            wait = delay - (self._clock() - last)
            if wait > 0:
                self._sleep(wait)

    # ------------------------------------------------------------------ requests

    def _request(self, url: str, *, max_bytes: int) -> tuple[int, bytes, httpx.Headers]:
        host = (urlsplit(url).hostname or "").lower()
        self._polite_wait(host)
        started = self._clock()
        entry: dict = {"url": url, "at": utc_now_iso()}
        try:
            with self._client.stream("GET", url) as response:
                chunks: list[bytes] = []
                size = 0
                for chunk in response.iter_bytes():
                    size += len(chunk)
                    if size > max_bytes:
                        raise FetchError("too_large", f"response exceeds {max_bytes} bytes", url)
                    if self._clock() - started > self.limits.timeout_s:
                        raise FetchError("timeout", f"download took over {self.limits.timeout_s:.0f} s", url)
                    chunks.append(chunk)
                entry.update(status=response.status_code, bytes=size)
                return response.status_code, b"".join(chunks), response.headers
        except FetchError as exc:
            entry.update(error=exc.kind)
            raise
        except httpx.TimeoutException as exc:
            entry.update(error="timeout")
            raise FetchError("timeout", type(exc).__name__, url) from None
        except httpx.HTTPError as exc:
            entry.update(error="network")
            raise FetchError("network", type(exc).__name__, url) from None
        finally:
            entry["ms"] = int((self._clock() - started) * 1000)
            self._last_request_at[host] = self._clock()
            self.log.append(entry)

    def get(self, url: str) -> Page:
        if self.pages_used >= self.max_pages:
            raise FetchError("page_cap", f"page budget of {self.max_pages} used up", url)
        if not self.is_allowed(url):
            raise FetchError("not_allowed", "URL is not HTTPS on an allowlisted host", url)
        self.pages_used += 1
        requested, current, hops = url, url, []
        while True:
            host = (urlsplit(current).hostname or "").lower()
            robots = self._robots_for(host)
            if host in self._robots_unreachable:  # report the real cause (e.g. network down), not "disallowed"
                kind = self._robots_unreachable[host]
                raise FetchError(kind, "robots.txt could not be fetched, so the page was not requested", current)
            if robots is not None and not robots.can_fetch(ROBOTS_AGENT, current):
                raise FetchError("robots_disallow", f"robots.txt disallows {urlsplit(current).path}", current)
            status, body, headers = self._request(current, max_bytes=self.limits.max_bytes)
            if status in (301, 302, 303, 307, 308):
                location = headers.get("location")
                if not location:
                    raise FetchError("http_status", f"HTTP {status} without Location", current)
                try:
                    target = urljoin(current, location)
                except ValueError:
                    raise FetchError("redirect_blocked", "malformed redirect Location", current) from None
                if not self.is_allowed(target):
                    raise FetchError("redirect_blocked", f"redirect to a non-allowlisted URL ({target})", current)
                hops.append(target)
                if len(hops) > self.limits.max_redirects:
                    raise FetchError("too_many_redirects", f"more than {self.limits.max_redirects} redirects", current)
                current = target
                continue
            if status != 200:
                raise FetchError("http_status", f"HTTP {status}", current)
            content_type = headers.get("content-type", "")
            if not any(t in content_type.lower() for t in ("html", "xml", "text/plain")):
                raise FetchError("bad_content_type", content_type or "missing content-type", current)
            charset = "utf-8"
            if "charset=" in content_type.lower():
                charset = content_type.lower().split("charset=", 1)[1].split(";")[0].strip() or "utf-8"
            try:
                text = body.decode(charset, "replace")
            except LookupError:
                text = body.decode("utf-8", "replace")
            return Page(
                url=current,
                requested_url=requested,
                status=status,
                content_type=content_type,
                text=text,
                n_bytes=len(body),
                fetched_at=utc_now_iso(),
                redirects=hops,
            )
