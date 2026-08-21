#!/usr/bin/env python3
"""Fetch, cache and normalise NSE and BSE end-of-day equity data.

The data contract this implements is documented in
``References/market-data.md``; the exclusions applied downstream are in
``References/universe-and-exclusions.md``. Read those first — this module
is the mechanism, not the decisions.

Standard library only, deliberately. These tools are agent content that a
harness shells out to, not part of the ``ai_agents`` package, and the
catalog keeps its runtime dependency list to ``click`` alone. Pulling in
``requests`` or ``pandas`` here would quietly make that false.

Two facts drive most of the design:

* A browser-like ``User-Agent`` is mandatory. Without it the exchanges do
  not answer at all — no status code, no body.
* A past trading session is immutable, so it is fetched once and cached
  forever. A sixty-session history costs sixty fetches the first time and
  nothing after that.
"""

from __future__ import annotations

import argparse
import csv
import io
import json
import os
import sys
import time
import urllib.error
import urllib.request
import zipfile
from datetime import date, datetime, timedelta, timezone
from pathlib import Path

# NSE and BSE both reject requests without a browser-like agent, and the
# failure is a dropped connection rather than an HTTP error, so a missing
# header looks like a network outage. See References/market-data.md.
USER_AGENT = (
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
    "(KHTML, like Gecko) Chrome/124.0 Safari/537.36"
)

NSE_UDIFF = (
    "https://nsearchives.nseindia.com/content/cm/"
    "BhavCopy_NSE_CM_0_0_0_{ymd}_F_0000.csv.zip"
)
BSE_UDIFF = (
    "https://www.bseindia.com/download/BhavCopy/Equity/"
    "BhavCopy_BSE_CM_0_0_0_{ymd}_F_0000.CSV"
)
NSE_DELIVERY = (
    "https://nsearchives.nseindia.com/products/content/"
    "sec_bhavdata_full_{dmy}.csv"
)
NSE_EQUITY_L = (
    "https://nsearchives.nseindia.com/content/equities/EQUITY_L.csv"
)
NSE_FO_LOTS = "https://nsearchives.nseindia.com/content/fo/fo_mktlots.csv"
NSE_ANNOUNCEMENTS = (
    "https://www.nseindia.com/api/corporate-announcements"
    "?index=equities&from_date={d}&to_date={d}"
)
NSE_HOLIDAYS = "https://www.nseindia.com/api/holiday-master?type=trading"

IST = timezone(timedelta(hours=5, minutes=30))

# Reference files describe the current listing state rather than a past
# session, so they go stale; sessions never do.
REFERENCE_MAX_AGE_SECONDS = 24 * 60 * 60


class FetchError(RuntimeError):
    """A source could not be retrieved."""


class OfflineError(RuntimeError):
    """Offline mode was requested and the cache could not satisfy it."""


# --------------------------------------------------------------------------
# cache
# --------------------------------------------------------------------------


def default_cache_dir() -> Path:
    base = os.environ.get("XDG_CACHE_HOME")
    root = Path(base) if base else Path.home() / ".cache"
    return root / "ai-agents" / "india-market-data"


class Cache:
    """Files on disk, keyed the way References/market-data.md describes."""

    def __init__(self, root: Path, offline: bool = False) -> None:
        self.root = Path(root)
        self.offline = offline

    def session_path(self, day: date, name: str) -> Path:
        return self.root / "sessions" / day.isoformat() / name

    def reference_path(self, name: str) -> Path:
        return self.root / "reference" / name

    def announcements_path(self, day: date) -> Path:
        return self.root / "announcements" / f"{day.isoformat()}.json"

    def read(self, path: Path) -> bytes | None:
        if path.exists():
            return path.read_bytes()
        return None

    def write(self, path: Path, payload: bytes) -> None:
        path.parent.mkdir(parents=True, exist_ok=True)
        # Write-then-rename so an interrupted run never leaves a
        # half-written file that later looks like a valid cache hit.
        tmp = path.with_suffix(path.suffix + ".partial")
        tmp.write_bytes(payload)
        tmp.replace(path)

    def is_stale(self, path: Path, max_age: float) -> bool:
        if not path.exists():
            return True
        return (time.time() - path.stat().st_mtime) > max_age


# --------------------------------------------------------------------------
# fetching
# --------------------------------------------------------------------------


def http_get(url: str, referer: str | None = None, timeout: int = 30) -> bytes:
    """GET with the mandatory agent header, retrying transient failures."""
    headers = {
        "User-Agent": USER_AGENT,
        "Accept": "*/*",
        "Accept-Language": "en-US,en;q=0.9",
    }
    if referer:
        headers["Referer"] = referer

    last: Exception | None = None
    for attempt in range(3):
        request = urllib.request.Request(url, headers=headers)
        try:
            with urllib.request.urlopen(request, timeout=timeout) as response:
                return response.read()
        except urllib.error.HTTPError as exc:
            # A missing bhavcopy means "not a trading session" far more
            # often than it means a broken URL, and retrying cannot help.
            if exc.code == 404:
                raise FetchError(f"404 {url}") from exc
            last = exc
        except (urllib.error.URLError, TimeoutError, OSError) as exc:
            last = exc
        # These are exchange file servers, not a paid API. Back off.
        time.sleep(1.5 * (attempt + 1))
    raise FetchError(f"{url}: {last}")


def fetch_cached(
    cache: Cache,
    path: Path,
    url: str,
    referer: str | None = None,
    max_age: float | None = None,
) -> bytes:
    """Return cached bytes, fetching only when the cache cannot serve."""
    cached = cache.read(path)
    fresh_enough = cached is not None and (
        max_age is None or not cache.is_stale(path, max_age)
    )
    if fresh_enough:
        return cached  # type: ignore[return-value]

    if cache.offline:
        if cached is not None:
            # Stale beats nothing when the network is off the table, but
            # say so rather than pretending the file is current.
            print(f"offline: using stale {path.name}", file=sys.stderr)
            return cached
        raise OfflineError(f"offline and not cached: {path}")

    payload = http_get(url, referer=referer)
    cache.write(path, payload)
    return payload


def _unzip_single(payload: bytes) -> bytes:
    with zipfile.ZipFile(io.BytesIO(payload)) as archive:
        names = [n for n in archive.namelist() if not n.endswith("/")]
        if not names:
            raise FetchError("empty archive")
        return archive.read(names[0])


# --------------------------------------------------------------------------
# parsing
# --------------------------------------------------------------------------


def _clean_rows(text: str) -> list[dict[str, str]]:
    """Parse CSV, stripping whitespace from every key and value.

    The delivery file pads every field name and value with a leading
    space. Stripping unconditionally costs nothing on the files that do
    not, and removes a whole class of silent lookup misses.
    """
    reader = csv.DictReader(io.StringIO(text))
    rows = []
    for raw in reader:
        row = {}
        for key, value in raw.items():
            if key is None:
                continue
            row[key.strip()] = value.strip() if isinstance(value, str) else ""
        rows.append(row)
    return rows


def _number(value: str) -> float | None:
    if value in ("", "-", "NA", "nan"):
        return None
    try:
        return float(value)
    except ValueError:
        return None


def parse_udiff(text: str, exchange: str) -> list[dict]:
    """Normalise a UDiFF bhavcopy into this tool's row shape.

    NSE and BSE publish the identical 34-column schema, so one parser
    serves both. Rows that are not equity, or that lack the fields any
    downstream calculation needs, are dropped here rather than being
    carried forward as None.
    """
    out = []
    for row in _clean_rows(text):
        if row.get("FinInstrmTp", "").upper() != "STK":
            continue
        isin = row.get("ISIN", "")
        if not isin:
            continue

        close = _number(row.get("ClsPric", ""))
        prev_close = _number(row.get("PrvsClsgPric", ""))
        high = _number(row.get("HghPric", ""))
        low = _number(row.get("LwPric", ""))
        open_ = _number(row.get("OpnPric", ""))
        volume = _number(row.get("TtlTradgVol", ""))
        turnover = _number(row.get("TtlTrfVal", ""))

        if None in (close, high, low, open_) or close <= 0:
            continue

        out.append(
            {
                "date": row.get("TradDt", ""),
                "isin": isin,
                "symbol": row.get("TckrSymb", ""),
                "series": row.get("SctySrs", ""),
                "name": row.get("FinInstrmNm", ""),
                "exchange": exchange,
                "open": open_,
                "high": high,
                "low": low,
                "close": close,
                "prev_close": prev_close,
                "volume": volume or 0.0,
                "turnover": turnover or 0.0,
                "trades": _number(row.get("TtlNbOfTxsExctd", "")) or 0.0,
                "delivery_pct": None,
            }
        )
    return out


def parse_delivery(text: str) -> dict[str, float]:
    """Map NSE symbol to delivery percentage for one session.

    NSE only, and a different schema from UDiFF. Turnover here is in
    lacs and is not carried forward — UDiFF's rupee figure is used
    everywhere so there is only ever one unit in play.
    """
    out: dict[str, float] = {}
    for row in _clean_rows(text):
        if row.get("SERIES", "") != "EQ":
            continue
        symbol = row.get("SYMBOL", "")
        pct = _number(row.get("DELIV_PER", ""))
        if symbol and pct is not None:
            out[symbol] = pct
    return out


def reconcile(rows: list[dict]) -> list[dict]:
    """Collapse dual listings to one row per ISIN.

    The venue with the higher turnover for that session wins. Turnover
    rather than volume: volume is not comparable across venues when a
    stock is thin on one of them.
    """
    best: dict[str, dict] = {}
    for row in rows:
        current = best.get(row["isin"])
        if current is None or row["turnover"] > current["turnover"]:
            row = dict(row)
            row["also_on"] = (
                current["exchange"] if current is not None else None
            )
            best[row["isin"]] = row
        else:
            current["also_on"] = row["exchange"]
    return sorted(best.values(), key=lambda r: r["isin"])


# --------------------------------------------------------------------------
# sessions
# --------------------------------------------------------------------------


def load_session(
    cache: Cache,
    day: date,
    quiet: bool = False,
    reconcile_rows: bool = True,
) -> dict | None:
    """Return one normalised, reconciled session, or None if not a session.

    A session is "not a session" when neither exchange published a
    bhavcopy for it — a weekend, a holiday, or a date whose file is not
    out yet. That is an ordinary outcome, not an error.

    ``reconcile_rows`` collapses dual listings to one row per ISIN. That
    is right for a single session but wrong for a series: the winning
    venue can change between sessions, which splices one exchange's
    volume into another's baseline and drops delivery for the swapped
    bars. Callers building a series pass False and choose a venue once
    across the whole window instead.

    That outcome is cached too. Without a negative marker, offline mode
    cannot tell a market holiday from a gap in the cache, and the first
    holiday in any window makes an otherwise complete cache look broken.
    Caching it means the trading calendar is derived from the data and
    survives without the network.
    """
    marker = cache.session_path(day, "no-session.marker")
    if marker.exists():
        return None

    ymd = day.strftime("%Y%m%d")
    dmy = day.strftime("%d%m%Y")
    rows: list[dict] = []
    sources: list[str] = []
    # "absent" means the exchange answered 404; "error" means we never
    # got an answer. Only the former proves there was no session.
    outcomes: list[str] = []

    try:
        payload = fetch_cached(
            cache,
            cache.session_path(day, "nse-udiff.csv.zip"),
            NSE_UDIFF.format(ymd=ymd),
        )
        rows += parse_udiff(_unzip_single(payload).decode("utf-8", "replace"), "NSE")
        sources.append("NSE")
    except FetchError as exc:
        outcomes.append("absent" if "404" in str(exc) else "error")
    except (zipfile.BadZipFile, OfflineError):
        outcomes.append("error")

    try:
        payload = fetch_cached(
            cache,
            cache.session_path(day, "bse-udiff.csv"),
            BSE_UDIFF.format(ymd=ymd),
            referer="https://www.bseindia.com/",
        )
        rows += parse_udiff(payload.decode("utf-8", "replace"), "BSE")
        sources.append("BSE")
    except FetchError as exc:
        outcomes.append("absent" if "404" in str(exc) else "error")
    except OfflineError:
        outcomes.append("error")

    if not rows:
        if cache.offline:
            # Offline and unmarked: we genuinely do not know whether this
            # was a holiday. Say so rather than silently skipping it.
            raise OfflineError(f"offline and not cached: session {day}")
        if outcomes and all(o == "absent" for o in outcomes):
            cache.write(marker, b"no session published\n")
        return None

    counts = {"NSE": 0, "BSE": 0}
    for row in rows:
        counts[row["exchange"]] += 1

    delivery: dict[str, float] = {}
    try:
        payload = fetch_cached(
            cache,
            cache.session_path(day, "nse-delivery.csv"),
            NSE_DELIVERY.format(dmy=dmy),
        )
        delivery = parse_delivery(payload.decode("utf-8", "replace"))
    except (FetchError, OfflineError):
        # Delivery is an enrichment. Its absence leaves the field None,
        # which downstream must read as "unknown" and never as zero.
        if not quiet:
            print(f"no delivery data for {day}", file=sys.stderr)

    # Delivery is joined before any reconciliation, so an NSE row keeps
    # its delivery figure even when a caller later prefers the BSE row.
    for row in rows:
        if row["exchange"] == "NSE":
            row["delivery_pct"] = delivery.get(row["symbol"])

    merged = reconcile(rows) if reconcile_rows else rows

    return {
        "date": day.isoformat(),
        "exchanges": sources,
        "raw_counts": counts,
        "reconciled": len(merged),
        "delivery_available": bool(delivery),
        "rows": merged,
    }


def load_history(
    cache: Cache,
    end: date,
    sessions: int,
    quiet: bool = False,
    reconcile_rows: bool = True,
) -> list[dict]:
    """Walk back from ``end`` until ``sessions`` real sessions are found.

    The calendar is derived from which dates actually published a
    bhavcopy, which needs no holiday list and cannot disagree with the
    data. The walk-back limit is generous enough for a long festival
    cluster and finite so a wrong date cannot loop forever.
    """
    found: list[dict] = []
    day = end
    max_calendar_days = sessions * 3 + 30
    for _ in range(max_calendar_days):
        if len(found) >= sessions:
            break
        if day.weekday() < 5:  # skip weekends without a fetch
            session = load_session(
                cache, day, quiet=quiet, reconcile_rows=reconcile_rows
            )
            if session is not None:
                found.append(session)
        day -= timedelta(days=1)

    if len(found) < sessions:
        message = (
            f"asked for {sessions} sessions ending {end}, found {len(found)}"
        )
        if cache.offline:
            raise OfflineError(
                message + " — offline, cache does not cover this window"
            )
        print("warning: " + message, file=sys.stderr)

    return list(reversed(found))


# --------------------------------------------------------------------------
# reference data
# --------------------------------------------------------------------------


def load_universe(cache: Cache) -> dict[str, dict]:
    payload = fetch_cached(
        cache,
        cache.reference_path("equity-l.csv"),
        NSE_EQUITY_L,
        max_age=REFERENCE_MAX_AGE_SECONDS,
    )
    out = {}
    for row in _clean_rows(payload.decode("utf-8", "replace")):
        isin = row.get("ISIN NUMBER", "")
        if isin:
            out[isin] = {
                "symbol": row.get("SYMBOL", ""),
                "name": row.get("NAME OF COMPANY", ""),
                "series": row.get("SERIES", ""),
                "listed": row.get("DATE OF LISTING", ""),
            }
    return out


def load_fo_symbols(cache: Cache) -> set[str]:
    try:
        payload = fetch_cached(
            cache,
            cache.reference_path("fo-mktlots.csv"),
            NSE_FO_LOTS,
            max_age=REFERENCE_MAX_AGE_SECONDS,
        )
    except (FetchError, OfflineError):
        return set()
    symbols = set()
    for row in _clean_rows(payload.decode("utf-8", "replace")):
        for key in ("SYMBOL", "Symbol", "UNDERLYING"):
            if row.get(key):
                symbols.add(row[key].strip().upper())
                break
    return symbols


def load_announcements(cache: Cache, day: date) -> dict:
    """Corporate filings for one date, keyed by NSE symbol.

    Best-effort by design. This is a website's internal JSON API rather
    than a published contract, so a failure degrades the run instead of
    ending it — but the caller is told, so it can label the field
    unavailable rather than empty.
    """
    stamp = day.strftime("%d-%m-%Y")
    try:
        payload = fetch_cached(
            cache,
            cache.announcements_path(day),
            NSE_ANNOUNCEMENTS.format(d=stamp),
            referer=(
                "https://www.nseindia.com/companies-listing/"
                "corporate-filings-announcements"
            ),
        )
        records = json.loads(payload.decode("utf-8", "replace"))
    except (FetchError, OfflineError, json.JSONDecodeError, ValueError):
        return {"available": False, "by_symbol": {}}

    if not isinstance(records, list):
        return {"available": False, "by_symbol": {}}

    by_symbol: dict[str, list[dict]] = {}
    for record in records:
        symbol = (record.get("symbol") or "").strip().upper()
        if not symbol:
            continue
        by_symbol.setdefault(symbol, []).append(
            {
                "category": (record.get("desc") or "").strip(),
                "at": (record.get("an_dt") or "").strip(),
                "text": (record.get("attchmntText") or "").strip()[:200],
            }
        )
    return {"available": True, "by_symbol": by_symbol}


def load_holidays(cache: Cache) -> list[str]:
    try:
        payload = fetch_cached(
            cache,
            cache.reference_path("holidays.json"),
            NSE_HOLIDAYS,
            referer="https://www.nseindia.com/",
            max_age=REFERENCE_MAX_AGE_SECONDS,
        )
        data = json.loads(payload.decode("utf-8", "replace"))
    except (FetchError, OfflineError, json.JSONDecodeError, ValueError):
        return []
    dates = []
    for entries in data.values() if isinstance(data, dict) else []:
        for entry in entries or []:
            if isinstance(entry, dict) and entry.get("tradingDate"):
                dates.append(entry["tradingDate"])
    return sorted(set(dates))


# --------------------------------------------------------------------------
# envelope
# --------------------------------------------------------------------------


def envelope(as_of: str | None, sessions: int, extra: dict | None = None) -> dict:
    """The freshness header every output carries.

    The agent's boundaries require freshness to be reported rather than
    assumed, so this is attached at the source instead of being left for
    prose to remember.
    """
    payload = {
        "source": "NSE and BSE end-of-day bhavcopy",
        "feed_type": "end-of-day",
        "live": False,
        "as_of_session": as_of,
        "sessions_loaded": sessions,
        "fetched_at_ist": datetime.now(IST).strftime("%Y-%m-%d %H:%M:%S IST"),
        "note": (
            "End-of-day data for a completed session. Not a live or "
            "intraday feed."
        ),
    }
    if extra:
        payload.update(extra)
    return payload


# --------------------------------------------------------------------------
# cli
# --------------------------------------------------------------------------


def _parse_date(text: str) -> date:
    return datetime.strptime(text, "%Y-%m-%d").date()


def _cache_from_args(args: argparse.Namespace) -> Cache:
    root = Path(args.cache_dir) if args.cache_dir else default_cache_dir()
    return Cache(root, offline=args.offline)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        prog="bhavcopy.py",
        description=(
            "Fetch and cache NSE/BSE end-of-day equity data. "
            "See References/market-data.md."
        ),
    )
    parser.add_argument("--cache-dir", help="override the cache location")
    parser.add_argument(
        "--offline",
        action="store_true",
        help="read the cache only; fail rather than fetch",
    )
    sub = parser.add_subparsers(dest="command", required=True)

    fetch = sub.add_parser("fetch", help="one session")
    fetch.add_argument("--date", required=True)

    history = sub.add_parser("history", help="N sessions ending at a date")
    history.add_argument("--end", required=True)
    history.add_argument("--sessions", type=int, default=60)

    sub.add_parser("universe", help="NSE listing master")
    sub.add_parser("calendar", help="declared trading holidays")

    announcements = sub.add_parser("announcements", help="filings for a date")
    announcements.add_argument("--date", required=True)

    args = parser.parse_args(argv)
    cache = _cache_from_args(args)

    try:
        if args.command == "fetch":
            day = _parse_date(args.date)
            session = load_session(cache, day)
            if session is None:
                print(
                    f"no session published for {day} "
                    "(weekend, holiday, or not yet released)",
                    file=sys.stderr,
                )
                return 1
            print(
                json.dumps(
                    {
                        "envelope": envelope(session["date"], 1),
                        "exchanges": session["exchanges"],
                        "raw_counts": session["raw_counts"],
                        "reconciled": session["reconciled"],
                        "delivery_available": session["delivery_available"],
                        "rows": session["rows"],
                    },
                    indent=2,
                )
            )

        elif args.command == "history":
            end = _parse_date(args.end)
            sessions = load_history(cache, end, args.sessions)
            if not sessions:
                print(f"no sessions found ending {end}", file=sys.stderr)
                return 1
            print(
                json.dumps(
                    {
                        "envelope": envelope(
                            sessions[-1]["date"], len(sessions)
                        ),
                        "sessions": [
                            {
                                "date": s["date"],
                                "exchanges": s["exchanges"],
                                "reconciled": s["reconciled"],
                                "delivery_available": s["delivery_available"],
                            }
                            for s in sessions
                        ],
                    },
                    indent=2,
                )
            )

        elif args.command == "universe":
            universe = load_universe(cache)
            print(
                json.dumps(
                    {"count": len(universe), "by_isin": universe}, indent=2
                )
            )

        elif args.command == "announcements":
            day = _parse_date(args.date)
            result = load_announcements(cache, day)
            print(
                json.dumps(
                    {
                        "date": day.isoformat(),
                        "available": result["available"],
                        "symbols": len(result["by_symbol"]),
                        "by_symbol": result["by_symbol"],
                    },
                    indent=2,
                )
            )

        elif args.command == "calendar":
            print(json.dumps({"holidays": load_holidays(cache)}, indent=2))

    except OfflineError as exc:
        print(f"offline: {exc}", file=sys.stderr)
        return 2
    except FetchError as exc:
        print(f"fetch failed: {exc}", file=sys.stderr)
        return 2

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
