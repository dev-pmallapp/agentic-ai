#!/usr/bin/env python3
"""Fetch company fundamentals for names a technical screen already passed.

This module exists because ``screen.py`` answers "is this stock moving
the way a swing entry wants?" and cannot answer "is the business behind
it worth holding for three weeks?". The second question needs data the
bhavcopy feed does not carry.

**Why this fetches per name rather than per universe.** The gate runs
*after* the technical screen, so it only ever sees the few dozen names
that already passed. That ordering is not a convenience — it is what
makes per-company fetching from third-party sites polite enough to do at
all. Screening the full liquid universe this way would be a thousand
requests for an answer about twenty-five names.

Standard library only, and no credential of any kind, for the same
reasons as ``bhavcopy.py``. Fetching, caching and backoff are reused from
that module rather than reimplemented: there is one polite-fetch
discipline in this agent, not two.

The criteria are not in this file. They live in
``References/fundamental-criteria.md`` and are parsed by
``screen.load_criteria`` — the same code path every other criteria file
goes through, so a threshold is edited in a document a human can read.
"""

from __future__ import annotations

import argparse
import html
import json
import re
import sys
import urllib.parse
from datetime import date, datetime
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

import bhavcopy  # noqa: E402
import screen  # noqa: E402

AGENT_ROOT = Path(__file__).resolve().parent.parent
REFERENCES = AGENT_ROOT / "References"

# Cached fundamentals live beside the session data, under their own key.
# Quarterly results change once a quarter, so the staleness window is
# measured in days rather than the seconds a price feed would need.
FUNDAMENTALS_DIR = "fundamentals"

SCREENER_COMPANY = "https://www.screener.in/company/{symbol}/consolidated/"
TICKERTAPE_SEARCH = "https://api.tickertape.in/search?text={q}&types=stock"
TICKERTAPE_INFO = "https://api.tickertape.in/stocks/info/{sid}"
MONEYCONTROL_PRICEFEED = (
    "https://priceapi.moneycontrol.com/pricefeed/nse/equitycash/{sc_id}"
)
NSE_RESULTS = (
    "https://www.nseindia.com/api/results-comparision"
    "?symbol={symbol}&period=Quarterly"
)
NSE_RESULTS_REFERER = (
    "https://www.nseindia.com/companies-listing/"
    "corporate-filings-financial-results"
)

# Every field the gate can read. A provider returns the subset it knows;
# anything absent stays None, which is "unknown" and never "zero". See
# References/fundamental-criteria.md § Missing Data.
FIELDS = (
    "latest_quarter",
    "quarter_end",
    "eps_ttm",
    "pe",
    "revenue_growth_yoy",
    "pat_growth_yoy",
    "opm",
    "net_margin",
    "profitable_4q",
    "roe",
    "roce",
    "debt_equity",
    "promoter_holding",
    "promoter_pledge",
    "sector",
)

# Fields the gate actually tests. `min_fields_known` counts against this
# set, not against FIELDS — sector and latest_quarter are reported but
# never gated, so counting them would make a name look better covered
# than it is.
GATED_FIELDS = (
    "pe",
    "revenue_growth_yoy",
    "pat_growth_yoy",
    "opm",
    "profitable_4q",
    "roe",
    "debt_equity",
    "promoter_pledge",
)

MONTHS = {
    "jan": 1, "feb": 2, "mar": 3, "apr": 4, "may": 5, "jun": 6,
    "jul": 7, "aug": 8, "sep": 9, "oct": 10, "nov": 11, "dec": 12,
}


class ProviderError(RuntimeError):
    """A provider could not answer for this symbol.

    Deliberately not fatal. Every provider is allowed to fail; the run
    reports which ones did and carries on with what the others returned.
    """


# --------------------------------------------------------------------------
# small parsing helpers
# --------------------------------------------------------------------------


def _text(fragment: str) -> str:
    """Strip tags and entities out of an HTML fragment."""
    return html.unescape(re.sub(r"<[^>]+>", "", fragment)).replace("\xa0", " ").strip()


def _number(raw) -> float | None:
    """Parse a display number, or return None.

    Returning None rather than 0.0 is load-bearing throughout this
    module: a field nobody published and a field that is genuinely zero
    must not collapse into the same value.
    """
    if raw is None:
        return None
    if isinstance(raw, (int, float)) and not isinstance(raw, bool):
        return float(raw)
    text = str(raw).strip().replace(",", "").replace("%", "").replace("₹", "")
    if not text or text in ("-", "--", "NA", "N/A"):
        return None
    negative = text.startswith("(") and text.endswith(")")
    if negative:
        text = text[1:-1]
    try:
        value = float(text)
    except ValueError:
        return None
    return -value if negative else value


def _quarter_end(label: str) -> str | None:
    """'Jun 2026' -> '2026-06-30', so quarters sort and age correctly."""
    parts = label.strip().split()
    if len(parts) != 2:
        return None
    month = MONTHS.get(parts[0][:3].lower())
    try:
        year = int(parts[1])
    except ValueError:
        return None
    if not month:
        return None
    if month == 12:
        return f"{year}-12-31"
    last = date(year, month + 1, 1).toordinal() - 1
    return date.fromordinal(last).isoformat()


def _growth(latest: float | None, year_ago: float | None) -> float | None:
    """Percent change, guarding the sign trap a loss-making base creates.

    Growth off a negative base is not meaningful — a swing from -10 to
    -5 is a 50% "improvement" by the arithmetic and a 150% "decline" by
    the same formula depending on which way you write it. Report unknown
    rather than a number that reads as fact.
    """
    if latest is None or year_ago is None or year_ago <= 0:
        return None
    return (latest - year_ago) / year_ago * 100.0


def _derive_from_quarters(
    labels: list[str],
    sales: list[float | None],
    profit: list[float | None],
    eps: list[float | None],
    opm: list[float | None],
) -> dict:
    """Turn a quarterly series into the fields the gate reads.

    Quarters arrive oldest-first, which is how both sources publish
    them. Five are needed for a full answer: four for a trailing-twelve
    total, and the fifth so the latest quarter has a year-ago
    counterpart to grow against.
    """
    out: dict = {}
    if not labels:
        return out

    out["latest_quarter"] = labels[-1]
    out["quarter_end"] = _quarter_end(labels[-1])

    recent_eps = [v for v in eps[-4:] if v is not None]
    if len(recent_eps) == 4:
        out["eps_ttm"] = round(sum(recent_eps), 2)

    if len(sales) >= 5:
        out["revenue_growth_yoy"] = _round(_growth(sales[-1], sales[-5]))
    if len(profit) >= 5:
        out["pat_growth_yoy"] = _round(_growth(profit[-1], profit[-5]))

    if opm and opm[-1] is not None:
        out["opm"] = _round(opm[-1])
    if sales and profit and sales[-1] and profit[-1] is not None and sales[-1] > 0:
        out["net_margin"] = _round(profit[-1] / sales[-1] * 100.0)

    recent_profit = [v for v in profit[-4:] if v is not None]
    if len(recent_profit) == 4:
        out["profitable_4q"] = all(v > 0 for v in recent_profit)

    return out


def _round(value: float | None, places: int = 2) -> float | None:
    return None if value is None else round(value, places)


# --------------------------------------------------------------------------
# providers
# --------------------------------------------------------------------------
#
# Each takes (cache, symbol) and returns the subset of FIELDS it knows.
# A provider that cannot address the symbol, or whose page changed shape,
# raises ProviderError — it never returns partially-invented values.


def provider_screener(cache: bhavcopy.Cache, symbol: str, max_age: float) -> dict:
    """screener.in — a rendered quarterly table, addressed by NSE symbol.

    Symbol-addressable, which matters: the ticker is already on every
    bhavcopy row, so no lookup step stands between a screened name and
    its fundamentals.
    """
    path = cache.root / FUNDAMENTALS_DIR / "screener" / f"{symbol}.html"
    payload = bhavcopy.fetch_cached(
        cache,
        path,
        SCREENER_COMPANY.format(symbol=urllib.parse.quote(symbol)),
        max_age=max_age,
    )
    text = payload.decode("utf-8", "replace")

    section = re.search(r'id="quarters".*?</table>', text, re.S)
    if not section:
        raise ProviderError("no quarterly table on the page")
    block = section.group(0)

    labels = [h for h in (_text(h) for h in re.findall(r"<th[^>]*>(.*?)</th>", block, re.S)) if h]
    rows: dict[str, list[float | None]] = {}
    for row in re.findall(r"<tr[^>]*>(.*?)</tr>", block, re.S):
        cells = [_text(c) for c in re.findall(r"<td[^>]*>(.*?)</td>", row, re.S)]
        if not cells:
            continue
        rows[cells[0].rstrip(" +")] = [_number(c) for c in cells[1:]]

    out = _derive_from_quarters(
        labels,
        rows.get("Sales", []),
        rows.get("Net Profit", []),
        rows.get("EPS in Rs", []),
        rows.get("OPM %", []),
    )
    if not out:
        raise ProviderError("quarterly table parsed to nothing")

    # The ratio strip above the tables carries the return ratios the
    # quarterly table cannot. It carries no leverage figure — the strip
    # is Market Cap, Price, High/Low, Stock P/E, Book Value, Dividend
    # Yield, ROCE, ROE, Face Value and nothing else — so debt/equity is
    # left unknown here rather than sourced from somewhere it isn't.
    for label, field in (
        ("ROE", "roe"),
        ("ROCE", "roce"),
    ):
        match = re.search(
            rf"{re.escape(label)}\s*</span>.*?<span[^>]*class=\"number\"[^>]*>(.*?)</span>",
            text,
            re.S | re.I,
        )
        if match and field in FIELDS:
            value = _number(_text(match.group(1)))
            if value is not None:
                out[field] = value
    return out


def _tickertape_sid(cache: bhavcopy.Cache, symbol: str, max_age: float) -> str:
    """Resolve an NSE ticker to tickertape's internal id.

    tickertape addresses companies by its own `sid`, so unlike
    screener.in it needs this hop before any data can be asked for.
    """
    path = cache.root / FUNDAMENTALS_DIR / "tickertape" / f"search-{symbol}.json"
    payload = bhavcopy.fetch_cached(
        cache,
        path,
        TICKERTAPE_SEARCH.format(q=urllib.parse.quote(symbol)),
        max_age=max_age,
    )
    try:
        data = json.loads(payload.decode("utf-8", "replace"))
    except json.JSONDecodeError as exc:
        raise ProviderError("search did not return JSON") from exc
    for stock in (data.get("data") or {}).get("stocks") or []:
        if (stock.get("ticker") or "").strip().upper() == symbol.upper():
            sid = (stock.get("sid") or "").strip()
            if sid:
                return sid
    raise ProviderError(f"no exact ticker match for {symbol}")


def provider_tickertape(cache: bhavcopy.Cache, symbol: str, max_age: float) -> dict:
    """tickertape.in — JSON ratios, addressed by an internal sid."""
    sid = _tickertape_sid(cache, symbol, max_age)
    path = cache.root / FUNDAMENTALS_DIR / "tickertape" / f"{sid}.json"
    payload = bhavcopy.fetch_cached(
        cache, path, TICKERTAPE_INFO.format(sid=sid), max_age=max_age
    )
    try:
        data = json.loads(payload.decode("utf-8", "replace")).get("data") or {}
    except json.JSONDecodeError as exc:
        raise ProviderError("info did not return JSON") from exc

    ratios = data.get("ratios") or {}
    info = data.get("info") or {}
    out: dict = {}
    # ttmPe is preferred over pe: a trailing-twelve multiple is the one
    # comparable across companies with different year-ends.
    for source, field in (("ttmPe", "pe"), ("pe", "pe"), ("roe", "roe")):
        if field not in out:
            value = _number(ratios.get(source))
            if value is not None:
                out[field] = round(value, 2)
    if info.get("sector"):
        out["sector"] = str(info["sector"]).strip()
    if not out:
        raise ProviderError("no usable ratios in the payload")
    return out


def provider_moneycontrol(cache: bhavcopy.Cache, symbol: str, max_age: float) -> dict:
    """moneycontrol.com — priced ratios, addressed by an sc_id.

    The sc_id is moneycontrol's own key ("RI" for Reliance) and there is
    no working public endpoint to derive it from a ticker: the documented
    autosuggest routes return 404. So this provider reads a mapping file
    the user maintains, and reports the symbol as unresolved when it is
    not in it. That is a real limitation, stated rather than papered over
    with a guessed endpoint.
    """
    mapping_path = REFERENCES / "moneycontrol-sc-ids.json"
    if not mapping_path.exists():
        raise ProviderError("no sc_id mapping file")
    try:
        mapping = json.loads(mapping_path.read_text(encoding="utf-8"))
    except json.JSONDecodeError as exc:
        raise ProviderError("sc_id mapping file is not valid JSON") from exc
    sc_id = mapping.get(symbol.upper())
    if not sc_id or not isinstance(sc_id, str):
        raise ProviderError(f"{symbol} is not in the sc_id mapping")

    path = cache.root / FUNDAMENTALS_DIR / "moneycontrol" / f"{sc_id}.json"
    payload = bhavcopy.fetch_cached(
        cache, path, MONEYCONTROL_PRICEFEED.format(sc_id=sc_id), max_age=max_age
    )
    try:
        body = json.loads(payload.decode("utf-8", "replace"))
    except json.JSONDecodeError as exc:
        raise ProviderError("pricefeed did not return JSON") from exc
    data = body.get("data") or {}
    if str(body.get("code")) != "200":
        raise ProviderError(f"pricefeed rejected sc_id {sc_id}")

    # The payload names the NSE ticker it belongs to, so a wrong mapping
    # entry is detectable rather than silently contributing another
    # company's ratios. sc_ids are not mnemonic: "HU" resolves to Unimers
    # India, not Hindustan Unilever.
    returned = (data.get("NSEID") or "").strip().upper()
    if returned and returned != symbol.upper():
        raise ProviderError(
            f"sc_id {sc_id} maps to {returned}, not {symbol.upper()}"
        )

    out: dict = {}
    # Consolidated first — it is the figure that describes the group a
    # buyer is actually taking a position in.
    for source, field in (("PECONS", "pe"), ("PE", "pe")):
        if field not in out:
            value = _number(data.get(source))
            if value is not None and value > 0:
                out[field] = round(value, 2)
    if data.get("main_sector"):
        out["sector"] = str(data["main_sector"]).strip()
    if not out:
        raise ProviderError("no usable ratios in the pricefeed")
    return out


def provider_exchange(cache: bhavcopy.Cache, symbol: str, max_age: float) -> dict:
    """NSE's own quarterly results — the credential-free floor.

    This is the only provider whose data is published by the exchange
    rather than by a commercial site, so it is the one that cannot be
    withdrawn or reshaped by a vendor. It is kept for exactly that
    reason, and it is last in precedence for a measured one: as of
    2026-08-21 its freshest quarter across every symbol tested was the
    one ending 31-Dec-2024, while the price feed was current. See
    References/fundamental-criteria.md § Provider Precedence.

    `re_debt_eqt_rat` is deliberately NOT read. It returns 0 for
    companies carrying real debt, and a zero that means "not reported"
    is precisely the fabrication the missing-data rule exists to stop.
    """
    path = cache.root / FUNDAMENTALS_DIR / "exchange" / f"{symbol}.json"
    payload = bhavcopy.fetch_cached(
        cache,
        path,
        NSE_RESULTS.format(symbol=urllib.parse.quote(symbol)),
        referer=NSE_RESULTS_REFERER,
        max_age=max_age,
    )
    try:
        rows = json.loads(payload.decode("utf-8", "replace")).get("resCmpData") or []
    except json.JSONDecodeError as exc:
        raise ProviderError("results feed did not return JSON") from exc
    if not rows:
        raise ProviderError(f"no quarterly results published for {symbol}")

    # The feed lists newest first; everything downstream expects oldest
    # first, matching how the rendered tables read.
    rows = list(reversed(rows))
    labels, sales, profit, eps, opm = [], [], [], [], []
    for row in rows:
        end = (row.get("re_to_dt") or "").strip()
        try:
            parsed = datetime.strptime(end, "%d-%b-%Y").date()
        except ValueError:
            continue
        labels.append(f"{parsed.strftime('%b')} {parsed.year}")
        revenue = _number(row.get("re_net_sale"))
        pat = _number(row.get("re_net_profit"))
        sales.append(revenue)
        profit.append(pat)
        eps.append(_number(row.get("re_basic_eps_for_cont_dic_opr")))
        # No operating-margin field is published, so it is derived from
        # the two totals that are — and left unknown when either is not.
        expenses = _number(row.get("re_oth_tot_exp"))
        if revenue and expenses is not None and revenue > 0:
            opm.append((revenue - expenses) / revenue * 100.0)
        else:
            opm.append(None)

    out = _derive_from_quarters(labels, sales, profit, eps, opm)
    if not out:
        raise ProviderError("results parsed to nothing")
    return out


PROVIDERS = {
    "screener": provider_screener,
    "tickertape": provider_tickertape,
    "moneycontrol": provider_moneycontrol,
    "exchange": provider_exchange,
}


# --------------------------------------------------------------------------
# merge
# --------------------------------------------------------------------------


def fetch_fundamentals(
    cache: bhavcopy.Cache,
    symbol: str,
    precedence: list[str],
    max_age: float,
    close: float | None = None,
) -> dict:
    """Merge every provider's answer, first hit wins, per field.

    Per *field*, not per provider: a source that knows ROE but not
    growth should contribute the ROE without displacing a better
    source's growth. Every value records which provider produced it, so
    a number in the output can always be traced to where it came from.
    """
    values: dict = {field: None for field in FIELDS}
    provenance: dict[str, str] = {}
    failures: dict[str, str] = {}

    for name in precedence:
        fetcher = PROVIDERS.get(name)
        if fetcher is None:
            failures[name] = "unknown provider"
            continue
        try:
            answer = fetcher(cache, symbol, max_age)
        except (ProviderError, bhavcopy.FetchError, bhavcopy.OfflineError) as exc:
            failures[name] = str(exc)
            continue
        for field, value in answer.items():
            if field in values and values[field] is None and value is not None:
                values[field] = value
                provenance[field] = name

    # P/E is computed rather than trusted when both inputs are present:
    # the close is the one from the session actually screened, and a
    # vendor's multiple is priced off whenever they last recomputed it.
    if close and values.get("eps_ttm") and values["eps_ttm"] > 0:
        values["pe"] = round(close / values["eps_ttm"], 2)
        provenance["pe"] = f"computed from close and {provenance.get('eps_ttm', '?')}"

    return {
        "symbol": symbol,
        "values": values,
        "provenance": provenance,
        "failures": failures,
        "known": sorted(f for f in GATED_FIELDS if values.get(f) is not None),
    }


# --------------------------------------------------------------------------
# gate
# --------------------------------------------------------------------------


def evaluate(record: dict, criteria: dict, as_of: date | None = None) -> dict:
    """Apply the gate to one name's fundamentals.

    A rule whose field is unknown is **not evaluated** — it neither
    passes nor fails. Coverage is judged separately, by `min_fields_known`,
    so a name nobody published data for is reported as ungateable rather
    than sailing through on absence. This mirrors the delivery rule in
    References/swing-criteria.md, and for the same reason: a missing
    number treated as a passing one is a fabrication.
    """
    values = record["values"]
    reasons: list[str] = []
    checked = 0

    def check(field: str, ok: bool, message: str) -> None:
        nonlocal checked
        if values.get(field) is None:
            return
        checked += 1
        if not ok:
            reasons.append(message)

    pe = values.get("pe")
    check("pe", pe is not None and pe > 0 and pe <= screen.require(criteria, "max_pe"),
          f"p/e {pe}")
    if pe is not None and pe > 0:
        floor = screen.require(criteria, "min_pe")
        if pe < floor:
            reasons.append(f"p/e {pe} below floor")

    growth = values.get("revenue_growth_yoy")
    check("revenue_growth_yoy",
          growth is not None and growth >= screen.require(criteria, "min_revenue_growth_yoy"),
          f"revenue growth {growth}%")

    pat = values.get("pat_growth_yoy")
    check("pat_growth_yoy",
          pat is not None and pat >= screen.require(criteria, "min_pat_growth_yoy"),
          f"pat growth {pat}%")

    opm = values.get("opm")
    check("opm", opm is not None and opm >= screen.require(criteria, "min_opm"),
          f"operating margin {opm}%")

    if screen.require(criteria, "require_profitable"):
        check("profitable_4q", values.get("profitable_4q") is True,
              "loss in the last four quarters")

    roe = values.get("roe")
    check("roe", roe is not None and roe >= screen.require(criteria, "min_roe"),
          f"roe {roe}%")

    de = values.get("debt_equity")
    check("debt_equity",
          de is not None and de <= screen.require(criteria, "max_debt_equity"),
          f"debt/equity {de}")

    pledge = values.get("promoter_pledge")
    check("promoter_pledge",
          pledge is not None and pledge <= screen.require(criteria, "max_promoter_pledge_pct"),
          f"promoter pledge {pledge}%")

    # Staleness is a property of the data, not of the company, so it is
    # reported as its own outcome rather than folded in with a failing
    # ratio. A name gated on results from six quarters ago has been
    # gated on history.
    stale = None
    end = values.get("quarter_end")
    if end and as_of:
        try:
            age_days = (as_of - date.fromisoformat(end)).days
        except ValueError:
            age_days = None
        if age_days is not None:
            quarters = age_days / 91.0
            stale = quarters > screen.require(criteria, "max_result_age_quarters")
            record["result_age_quarters"] = round(quarters, 1)

    known = len(record["known"])
    gateable = known >= screen.require(criteria, "min_fields_known")

    return {
        "gateable": gateable,
        "known": known,
        "checked": checked,
        "passed": gateable and not reasons and not stale,
        "reasons": reasons + (["results are stale"] if stale else []),
    }


# --------------------------------------------------------------------------
# reporting
# --------------------------------------------------------------------------


def _cell(value, suffix: str = "", width: int = 7) -> str:
    if value is None:
        return "—".rjust(width)
    if isinstance(value, bool):
        return ("yes" if value else "no").rjust(width)
    if isinstance(value, float):
        return f"{value:,.1f}{suffix}".rjust(width)
    return str(value).rjust(width)


def render_gate(result: dict, criteria: dict) -> str:
    env = result["envelope"]
    out = [
        "MORNING SHORTLIST — NSE/BSE equities, technical screen gated on fundamentals",
        "",
        f"AS OF      {env.get('as_of_session')} close",
        f"FEED       {env.get('feed_type')} — a pre-open run screens the PREVIOUS session",
        f"FETCHED    {env.get('fetched_at_ist')}",
        f"GATE       {result['gated_in']} of {result['considered']} technical "
        f"candidates passed; {len(result['ungated'])} could not be gated",
        "",
        "FUNDAMENTAL CRITERIA (References/fundamental-criteria.md)",
    ]
    for key in (
        "provider_precedence", "max_pe", "min_pe", "min_revenue_growth_yoy",
        "min_pat_growth_yoy", "min_opm", "min_roe", "max_debt_equity",
        "max_promoter_pledge_pct", "require_profitable",
        "max_result_age_quarters", "min_fields_known",
    ):
        if key in criteria:
            out.append(f"  {key} = {criteria[key]}")

    out += [
        "",
        f"{'#':>3}  {'SYMBOL':<12} {'CLOSE':>9} {'SIGNALS':<22} {'P/E':>7} "
        f"{'REV%':>7} {'PAT%':>7} {'OPM%':>7} {'ROE%':>7}  QUARTER",
        "  " + "-" * 104,
    ]
    for index, row in enumerate(result["candidates"], 1):
        values = row["fundamentals"]["values"]
        out.append(
            f"{index:>3}  {row['symbol']:<12} {row['close']:>9,.2f} "
            f"{','.join(row.get('signals') or ['—']):<22} "
            f"{_cell(values.get('pe'))} {_cell(values.get('revenue_growth_yoy'))} "
            f"{_cell(values.get('pat_growth_yoy'))} {_cell(values.get('opm'))} "
            f"{_cell(values.get('roe'))}  {values.get('latest_quarter') or '—'}"
        )

    if result["ungated"]:
        out += [
            "",
            "NOT GATEABLE — too few fundamentals published to judge, reported "
            "rather than dropped",
        ]
        for row in result["ungated"]:
            known = ", ".join(row["fundamentals"]["known"]) or "nothing"
            out.append(f"  {row['symbol']:<12} known: {known}")

    if result["rejected"]:
        out += ["", "GATED OUT"]
        for row in result["rejected"][:20]:
            out.append(f"  {row['symbol']:<12} {'; '.join(row['reasons'])}")

    if result["sectors"]:
        out += ["", "SECTOR SPREAD"]
        for sector, count in result["sectors"]:
            out.append(f"  {count:>3}  {sector}")

    if result["provider_failures"]:
        out += ["", "PROVIDERS THAT FAILED"]
        for name, count in sorted(result["provider_failures"].items()):
            out.append(f"  {name}: {count} of {result['considered']} names")

    out += [
        "",
        "Candidates, not recommendations. Fundamentals come from third-party",
        "sites and the exchange's own filings; every number's source is in the",
        "JSON output. End-of-day prices, unadjusted for corporate actions.",
    ]
    return "\n".join(out)


# --------------------------------------------------------------------------
# cli
# --------------------------------------------------------------------------


def _sector_spread(rows: list[dict]) -> list[tuple[str, int]]:
    counts: dict[str, int] = {}
    for row in rows:
        sector = row["fundamentals"]["values"].get("sector") or "unknown"
        counts[sector] = counts.get(sector, 0) + 1
    return sorted(counts.items(), key=lambda kv: (-kv[1], kv[0]))


def run_gate(
    cache: bhavcopy.Cache,
    swing: dict,
    criteria: dict,
    top: int | None = None,
) -> dict:
    precedence = criteria.get("provider_precedence") or ["screener", "exchange"]
    if isinstance(precedence, str):
        precedence = [precedence]
    precedence = [str(p).strip().lower() for p in precedence]
    max_age = float(screen.require(criteria, "cache_max_age_days")) * 86400.0

    env = swing.get("envelope") or {}
    as_of = None
    if env.get("as_of_session"):
        try:
            as_of = date.fromisoformat(env["as_of_session"])
        except ValueError:
            as_of = None

    passed, rejected, ungated = [], [], []
    failures: dict[str, int] = {}

    for candidate in swing.get("candidates") or []:
        record = fetch_fundamentals(
            cache,
            candidate["symbol"],
            precedence,
            max_age,
            close=candidate.get("close"),
        )
        for name in record["failures"]:
            failures[name] = failures.get(name, 0) + 1

        verdict = evaluate(record, criteria, as_of)
        row = {
            "symbol": candidate["symbol"],
            "isin": candidate.get("isin"),
            "close": candidate.get("close"),
            "score": candidate.get("score"),
            "signals": candidate.get("signals"),
            "fundamentals": record,
            "reasons": verdict["reasons"],
        }
        if not verdict["gateable"]:
            ungated.append(row)
        elif verdict["passed"]:
            passed.append(row)
        else:
            rejected.append(row)

    # Order is the technical composite's, untouched. The gate decides who
    # is on the list; it deliberately does not decide the order, so a
    # SCORE keeps meaning exactly what it meant in the swing screen.
    size = top or screen.require(criteria, "final_shortlist_size")
    candidates = passed[:size]

    return {
        "envelope": env,
        "candidates": candidates,
        "considered": len(swing.get("candidates") or []),
        "gated_in": len(passed),
        "rejected": rejected,
        "ungated": ungated,
        "sectors": _sector_spread(candidates),
        "provider_failures": failures,
    }


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        prog="fundamentals.py",
        description=(
            "Fetch company fundamentals and gate a technical shortlist on "
            "them. See References/fundamental-criteria.md."
        ),
    )
    parser.add_argument("--cache-dir")
    parser.add_argument("--offline", action="store_true")
    parser.add_argument("--json", action="store_true", help="emit JSON")
    parser.add_argument("--references", help="override References/ (for testing)")
    sub = parser.add_subparsers(dest="command", required=True)

    show = sub.add_parser("show", help="fundamentals for one symbol")
    show.add_argument("--symbol", required=True)
    show.add_argument("--close", type=float, help="close, to compute P/E")

    gate = sub.add_parser("gate", help="gate a swing screen's JSON output")
    gate.add_argument(
        "--json-in",
        required=True,
        help="swing screen JSON; '-' reads stdin",
    )
    gate.add_argument("--top", type=int, help="override final_shortlist_size")

    args = parser.parse_args(argv)
    references = Path(args.references) if args.references else REFERENCES
    root = Path(args.cache_dir) if args.cache_dir else bhavcopy.default_cache_dir()
    cache = bhavcopy.Cache(root, offline=args.offline)

    try:
        criteria = screen.load_criteria("fundamental-criteria.md", references)

        if args.command == "show":
            precedence = criteria.get("provider_precedence") or ["screener"]
            if isinstance(precedence, str):
                precedence = [precedence]
            max_age = float(screen.require(criteria, "cache_max_age_days")) * 86400.0
            record = fetch_fundamentals(
                cache,
                args.symbol.upper(),
                [str(p).strip().lower() for p in precedence],
                max_age,
                close=args.close,
            )
            verdict = evaluate(record, criteria, date.today())
            if args.json:
                print(json.dumps({**record, "verdict": verdict}, indent=2))
            else:
                print(f"{record['symbol']}")
                for field in FIELDS:
                    value = record["values"][field]
                    source = record["provenance"].get(field, "—")
                    print(f"  {field:<20} {str(value):<16} {source}")
                if record["failures"]:
                    print("  providers that failed:")
                    for name, why in record["failures"].items():
                        print(f"    {name}: {why}")
                print(
                    f"  verdict: {'pass' if verdict['passed'] else 'fail'} "
                    f"({verdict['known']} gate fields known, "
                    f"{verdict['checked']} rules evaluated)"
                )
                for reason in verdict["reasons"]:
                    print(f"    - {reason}")
            return 0

        raw = sys.stdin.read() if args.json_in == "-" else Path(args.json_in).read_text(
            encoding="utf-8"
        )
        swing = json.loads(raw)
        result = run_gate(cache, swing, criteria, top=args.top)
        print(
            json.dumps(result, indent=2)
            if args.json
            else render_gate(result, criteria)
        )

    except screen.CriteriaError as exc:
        print(f"criteria error: {exc}", file=sys.stderr)
        return 2
    except bhavcopy.OfflineError as exc:
        print(f"offline: {exc}", file=sys.stderr)
        return 2
    except json.JSONDecodeError as exc:
        print(f"input is not valid JSON: {exc}", file=sys.stderr)
        return 2

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
