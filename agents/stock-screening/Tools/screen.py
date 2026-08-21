#!/usr/bin/env python3
"""Apply the screening criteria to cached sessions and rank the result.

The criteria are not in this file. They live in
``References/swing-criteria.md``, ``References/day-criteria.md`` and
``References/universe-and-exclusions.md``, in parameter tables that this
module parses. That indirection is the point: a threshold is edited in a
document a human can read, and the next run uses it, with no code change
and no prose left contradicting the value.

Standard library only, for the reasons given in ``bhavcopy.py``.
"""

from __future__ import annotations

import argparse
import json
import re
import statistics
import sys
from datetime import date, datetime, timedelta
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

import bhavcopy  # noqa: E402

AGENT_ROOT = Path(__file__).resolve().parent.parent
REFERENCES = AGENT_ROOT / "References"

# A parameter row is `| `name` | value | meaning |`. Anything else in a
# markdown table is prose and is ignored, so the criteria files stay
# readable documents rather than becoming config with headings.
PARAM_ROW = re.compile(r"^\|\s*`([a-z_][a-z0-9_]*)`\s*\|([^|]*)\|")


class CriteriaError(RuntimeError):
    """A criteria file could not be read or is missing a parameter."""


# --------------------------------------------------------------------------
# criteria
# --------------------------------------------------------------------------


def _coerce(raw: str):
    text = raw.strip().strip("`").strip()
    lowered = text.lower()
    if lowered in ("true", "yes"):
        return True
    if lowered in ("false", "no"):
        return False
    try:
        return int(text)
    except ValueError:
        pass
    try:
        return float(text)
    except ValueError:
        pass
    if "," in text:
        return [part.strip() for part in text.split(",") if part.strip()]
    return text


def parse_parameters(text: str) -> dict:
    """Pull the parameter tables out of a criteria document."""
    params: dict = {}
    for line in text.splitlines():
        match = PARAM_ROW.match(line.strip())
        if match:
            params[match.group(1)] = _coerce(match.group(2))
    return params


def load_criteria(name: str, references: Path = REFERENCES) -> dict:
    path = references / name
    if not path.exists():
        raise CriteriaError(f"missing criteria file: {path}")
    params = parse_parameters(path.read_text(encoding="utf-8"))
    if not params:
        raise CriteriaError(f"no parameter table found in {path}")
    return params


def require(params: dict, key: str):
    if key not in params:
        raise CriteriaError(f"criteria missing required parameter: {key}")
    return params[key]


def _as_list(value) -> list[str]:
    if isinstance(value, list):
        return [str(v).strip().upper() for v in value]
    return [str(value).strip().upper()]


# --------------------------------------------------------------------------
# indicators
# --------------------------------------------------------------------------


def sma(values: list[float], window: int) -> float | None:
    if len(values) < window or window <= 0:
        return None
    return sum(values[-window:]) / window


def true_ranges(bars: list[dict]) -> list[float]:
    """True range per bar, so that gaps count toward volatility.

    A stock that gaps 4% and then trades in a 1% band had a 4% day. The
    high-low range alone would call it a quiet one.
    """
    out = []
    for index, bar in enumerate(bars):
        if index == 0:
            out.append(bar["high"] - bar["low"])
            continue
        prior_close = bars[index - 1]["close"]
        out.append(
            max(
                bar["high"] - bar["low"],
                abs(bar["high"] - prior_close),
                abs(bar["low"] - prior_close),
            )
        )
    return out


def atr_pct(bars: list[dict], window: int) -> float | None:
    if len(bars) < window + 1 or window <= 0:
        return None
    ranges = true_ranges(bars)[-window:]
    close = bars[-1]["close"]
    if close <= 0:
        return None
    return (sum(ranges) / len(ranges)) / close * 100.0


def swing_signals(closes: list[float], short: float, criteria: dict) -> list[str]:
    """Name the setup a already-passing stock is showing.

    Classification, never a filter. This runs after every threshold has
    already been cleared, it cannot change who passes, and it carries no
    weight in the score — see References/swing-criteria.md § Signals.
    An empty list is a normal result for a stock quietly holding its
    trend, not a failure to classify.
    """
    found: list[str] = []
    close = closes[-1]

    window = require(criteria, "signal_breakout_window")
    if len(closes) >= window and close >= max(closes[-window:]):
        found.append("breakout")

    # A cross is read from history, not from the current stack: every
    # name here already has close > short > long, so the question is how
    # recently that became true. Walking back until the stack is absent
    # answers it without storing prior state.
    lookback = require(criteria, "signal_cross_lookback")
    sma_short = require(criteria, "sma_short")
    sma_long = require(criteria, "sma_long")
    for back in range(1, int(lookback) + 1):
        earlier = closes[:-back]
        was_short = sma(earlier, sma_short)
        was_long = sma(earlier, sma_long)
        if was_short is None or was_long is None:
            break
        if was_short <= was_long:
            found.append("cross")
            break

    if short > 0:
        distance = (close - short) / short * 100.0
        if distance <= require(criteria, "signal_pullback_pct"):
            found.append("pullback")
        elif distance >= require(criteria, "signal_extended_pct"):
            found.append("extended")

    return found


def median(values: list[float]) -> float | None:
    values = [v for v in values if v is not None]
    if not values:
        return None
    return statistics.median(values)


def scale(values: list[float]) -> list[float]:
    """Min-max to 0..1 so weights mean what they say.

    Without this, a component measured in percent would outweigh one
    measured as a ratio purely through its units.
    """
    if not values:
        return []
    low, high = min(values), max(values)
    if high - low < 1e-12:
        return [0.5] * len(values)
    return [(v - low) / (high - low) for v in values]


# --------------------------------------------------------------------------
# series assembly
# --------------------------------------------------------------------------


def build_series(sessions: list[dict], universe: dict) -> dict[str, dict]:
    """Group unreconciled session rows into a per-ISIN price series.

    The venue is chosen **once for the whole window**, not per session.
    A dual-listed stock can see the other exchange win a single session
    on a block deal — prices agree closely across venues, but volume
    does not, so a per-session choice splices one exchange's volume into
    the other's baseline and corrupts every volume ratio that spans the
    swap. It also drops delivery on the swapped bars, since delivery is
    published by NSE only.

    Circuit-locked sessions are dropped from the series rather than the
    stock being dropped entirely: a name that locked forty sessions ago
    is perfectly tradeable today, and removing it outright would quietly
    shorten every window that touched it.
    """
    by_venue: dict[tuple[str, str], list[dict]] = {}
    for session in sessions:
        for row in session["rows"]:
            if universe["exclude_circuit_locked"] and row["high"] == row["low"]:
                continue
            by_venue.setdefault((row["isin"], row["exchange"]), []).append(row)

    turnover: dict[str, dict[str, float]] = {}
    for (isin, exchange), bars in by_venue.items():
        turnover.setdefault(isin, {})[exchange] = sum(
            bar["turnover"] for bar in bars
        )

    series: dict[str, dict] = {}
    for isin, venues in turnover.items():
        # Sort key includes the name so a tie resolves the same way on
        # every run rather than following dict order.
        primary = max(venues, key=lambda ex: (venues[ex], ex))
        bars = by_venue[(isin, primary)]
        last = bars[-1]
        series[isin] = {
            "isin": isin,
            "symbol": last["symbol"],
            "name": last["name"],
            "series": last["series"],
            "exchange": primary,
            "also_on": sorted(ex for ex in venues if ex != primary),
            "bars": bars,
        }
    return series


def eligible(entry: dict, universe: dict) -> tuple[bool, str]:
    """Apply References/universe-and-exclusions.md to one name."""
    keep_nse = _as_list(require(universe, "keep_nse_series"))
    keep_bse = _as_list(require(universe, "keep_bse_groups"))
    last = entry["bars"][-1]

    code = (last["series"] or "").strip().upper()
    if last["exchange"] == "NSE":
        if code not in keep_nse:
            return False, f"nse series {code}"
    else:
        if code not in keep_bse:
            return False, f"bse group {code}"

    if len(entry["bars"]) < require(universe, "min_sessions"):
        return False, "insufficient history"

    if last["close"] < require(universe, "min_close"):
        return False, "below price floor"

    return True, ""


# --------------------------------------------------------------------------
# swing screen
# --------------------------------------------------------------------------


def screen_swing(sessions: list[dict], criteria: dict, universe: dict) -> dict:
    series = build_series(sessions, universe)
    rejected: dict[str, int] = {}
    passing = []

    def reject(reason: str) -> None:
        rejected[reason] = rejected.get(reason, 0) + 1

    for entry in series.values():
        ok, reason = eligible(entry, universe)
        if not ok:
            reject(reason)
            continue

        bars = entry["bars"]
        closes = [b["close"] for b in bars]
        volumes = [b["volume"] for b in bars]
        turnovers = [b["turnover"] for b in bars]

        short = sma(closes, require(criteria, "sma_short"))
        long = sma(closes, require(criteria, "sma_long"))
        if short is None or long is None:
            reject("insufficient history")
            continue

        close = closes[-1]
        if not (close > short > long):
            reject("trend")
            continue

        window = require(criteria, "high_window")
        window_high = max(closes[-window:])
        pct_below = (window_high - close) / window_high * 100.0
        if pct_below > require(criteria, "max_pct_below_high"):
            reject("too far below high")
            continue

        med_turnover = median(turnovers[-require(criteria, "turnover_window"):])
        if med_turnover is None or med_turnover < require(
            criteria, "min_median_turnover"
        ):
            reject("liquidity")
            continue

        recent = sma(volumes, require(criteria, "volume_recent_window"))
        base = sma(volumes, require(criteria, "volume_base_window"))
        if not recent or not base:
            reject("insufficient history")
            continue
        volume_ratio = recent / base
        if volume_ratio < require(criteria, "min_volume_ratio"):
            reject("volume not confirming")
            continue

        atr = atr_pct(bars, require(criteria, "atr_window"))
        if atr is None:
            reject("insufficient history")
            continue
        low_band = require(criteria, "min_atr_pct")
        high_band = require(criteria, "max_atr_pct")
        if not (low_band <= atr <= high_band):
            reject("outside volatility band")
            continue

        # Delivery is NSE-only. A missing value means unknown, never
        # zero — see References/swing-criteria.md § Delivery.
        window = require(criteria, "delivery_window")
        recent_bars = bars[-window:]
        known = [
            b["delivery_pct"] for b in recent_bars if b["delivery_pct"] is not None
        ]
        if len(known) * 2 < len(recent_bars):
            reject("delivery data unavailable")
            continue
        delivery = sum(known) / len(known)
        if delivery < require(criteria, "min_delivery_pct"):
            reject("delivery")
            continue

        passing.append(
            {
                "isin": entry["isin"],
                "symbol": entry["symbol"],
                "name": entry["name"],
                "exchange": entry["exchange"],
                "close": round(close, 2),
                "sma_short": round(short, 2),
                "sma_long": round(long, 2),
                "pct_above_sma_long": round((close - long) / long * 100.0, 2),
                "pct_below_high": round(pct_below, 2),
                "median_turnover": round(med_turnover, 0),
                "volume_ratio": round(volume_ratio, 2),
                "atr_pct": round(atr, 2),
                "delivery_pct": round(delivery, 2),
                "delivery_partial": len(known) < len(recent_bars),
                "signals": swing_signals(closes, short, criteria),
            }
        )

    _rank_swing(passing, criteria)
    size = require(criteria, "shortlist_size")
    return {
        "candidates": passing[:size],
        "passing_total": len(passing),
        "screened": len(series),
        "rejected": dict(sorted(rejected.items(), key=lambda kv: -kv[1])),
    }


def _rank_swing(rows: list[dict], criteria: dict) -> None:
    if not rows:
        return
    trend = scale([r["pct_above_sma_long"] for r in rows])
    volume = scale([r["volume_ratio"] for r in rows])
    delivery = scale([r["delivery_pct"] for r in rows])

    # Volatility scores highest in the middle of the band. The ceiling
    # exists because more is worse, so rewarding the maximum would fight
    # the filter that produced this set.
    low = require(criteria, "min_atr_pct")
    high = require(criteria, "max_atr_pct")
    mid = (low + high) / 2.0
    span = max((high - low) / 2.0, 1e-9)
    fit = [1.0 - min(abs(r["atr_pct"] - mid) / span, 1.0) for r in rows]

    weights = (
        require(criteria, "weight_trend"),
        require(criteria, "weight_volume"),
        require(criteria, "weight_volatility"),
        require(criteria, "weight_delivery"),
    )
    for index, row in enumerate(rows):
        row["score"] = round(
            weights[0] * trend[index]
            + weights[1] * volume[index]
            + weights[2] * fit[index]
            + weights[3] * delivery[index],
            4,
        )
    rows.sort(key=lambda r: (-r["score"], -r["median_turnover"]))


# --------------------------------------------------------------------------
# day screen
# --------------------------------------------------------------------------

MATERIAL_CATEGORIES = {
    "outcome of board meeting",
    "financial results",
    "clarification - financial results",
    "acquisition",
    "bagging/receiving of orders/contracts",
    "credit rating",
    "credit rating- new",
    "scheme of arrangement",
    "qualified institutional placement",
    "rights issue",
    "public announcement-open offer",
    "disclosure under sebi takeover regulations",
    "corporate insolvency resolution process",
    "capacity addition",
    "commencement of commercial production/operations",
    "diversification/disinvestment",
    "sale or disposal",
    "disruption of operations",
    "strikes/lockouts/disturbances",
    "action(s) taken or orders passed",
    "pendency of litigation(s)/dispute(s) or the outcome impacting the company",
    "change in auditors",
    "agreements",
    "disclosure of material issue",
    "press release",
}

# The exchange asking a company to explain unusual activity. Reactive
# rather than causal, but a direct statement that the exchange flagged
# the session, so it counts and is labelled separately.
EXCHANGE_QUERY_CATEGORIES = {"spurt in volume", "price movement"}


def classify_catalysts(filings: list[dict]) -> dict:
    material, queries = [], []
    for filing in filings:
        category = filing.get("category", "").strip().lower()
        if category in MATERIAL_CATEGORIES:
            material.append(filing.get("category", ""))
        elif category in EXCHANGE_QUERY_CATEGORIES:
            queries.append(filing.get("category", ""))
    return {
        "has_catalyst": bool(material or queries),
        "material": sorted(set(material)),
        "exchange_query": sorted(set(queries)),
    }


def screen_day(
    target: dict,
    history: list[dict],
    criteria: dict,
    universe: dict,
    announcements: dict,
) -> dict:
    """Screen one completed session against the prior sessions.

    ``history`` must exclude the target session — including a session in
    its own volume baseline damps exactly the spike being measured, and
    does so most for the largest ones.
    """
    prior = build_series(history, universe)
    rejected: dict[str, int] = {}
    passing = []
    catalysts_available = announcements.get("available", False)
    by_symbol = announcements.get("by_symbol", {})

    def reject(reason: str) -> None:
        rejected[reason] = rejected.get(reason, 0) + 1

    keep_nse = _as_list(require(universe, "keep_nse_series"))
    keep_bse = _as_list(require(universe, "keep_bse_groups"))

    for row in target["rows"]:
        code = (row["series"] or "").strip().upper()
        if row["exchange"] == "NSE":
            if code not in keep_nse:
                reject(f"nse series {code}")
                continue
        elif code not in keep_bse:
            reject(f"bse group {code}")
            continue

        if universe["exclude_circuit_locked"] and row["high"] == row["low"]:
            reject("circuit locked")
            continue

        if row["close"] < require(universe, "min_close"):
            reject("below price floor")
            continue

        prev_close = row["prev_close"]
        if not prev_close or prev_close <= 0:
            reject("no previous close")
            continue

        gap = (row["open"] - prev_close) / prev_close * 100.0
        if abs(gap) < require(criteria, "min_abs_gap_pct"):
            reject("gap")
            continue

        range_pct = (row["high"] - row["low"]) / prev_close * 100.0
        if range_pct < require(criteria, "min_range_pct"):
            reject("range")
            continue

        entry = prior.get(row["isin"])
        if entry is None:
            reject("insufficient history")
            continue
        bars = entry["bars"]

        window = require(criteria, "relvol_window")
        baseline = median([b["volume"] for b in bars[-window:]])
        if not baseline:
            reject("insufficient history")
            continue
        relvol = row["volume"] / baseline
        if relvol < require(criteria, "min_relative_volume"):
            reject("relative volume")
            continue

        med_turnover = median(
            [b["turnover"] for b in bars[-require(criteria, "turnover_window"):]]
        )
        if med_turnover is None or med_turnover < require(
            criteria, "min_median_turnover"
        ):
            reject("liquidity")
            continue

        catalyst = classify_catalysts(
            by_symbol.get((row["symbol"] or "").upper(), [])
        )

        # Observed after the fact. Reported, never scored or filtered —
        # see References/day-criteria.md § The Outcome Column.
        held = (
            (row["close"] >= row["open"])
            if gap > 0
            else (row["close"] <= row["open"])
        )

        passing.append(
            {
                "isin": row["isin"],
                "symbol": row["symbol"],
                "name": row["name"],
                "exchange": row["exchange"],
                "prev_close": round(prev_close, 2),
                "open": round(row["open"], 2),
                "close": round(row["close"], 2),
                "gap_pct": round(gap, 2),
                "direction": "up" if gap > 0 else "down",
                "relative_volume": round(relvol, 2),
                "range_pct": round(range_pct, 2),
                "median_turnover": round(med_turnover, 0),
                "catalyst": (
                    catalyst if catalysts_available else {"available": False}
                ),
                "observed_gap_held": held,
            }
        )

    _rank_day(passing, criteria, catalysts_available)
    size = require(criteria, "shortlist_size")
    return {
        "candidates": passing[:size],
        "passing_total": len(passing),
        "screened": len(target["rows"]),
        "catalysts_available": catalysts_available,
        "rejected": dict(sorted(rejected.items(), key=lambda kv: -kv[1])),
    }


def _rank_day(rows: list[dict], criteria: dict, catalysts: bool) -> None:
    if not rows:
        return
    gap = scale([abs(r["gap_pct"]) for r in rows])
    relvol = scale([r["relative_volume"] for r in rows])
    range_ = scale([r["range_pct"] for r in rows])

    w_gap = require(criteria, "weight_gap")
    w_relvol = require(criteria, "weight_relvol")
    w_range = require(criteria, "weight_range")
    w_catalyst = require(criteria, "weight_catalyst")

    if not catalysts:
        # Redistribute rather than scoring every name zero: the ranking
        # would be unchanged but every score would be misleading.
        total = w_gap + w_relvol + w_range
        if total > 0:
            share = w_catalyst / total
            w_gap += w_gap * share
            w_relvol += w_relvol * share
            w_range += w_range * share
        w_catalyst = 0.0

    for index, row in enumerate(rows):
        catalyst_score = (
            1.0
            if catalysts and row["catalyst"].get("has_catalyst")
            else 0.0
        )
        row["score"] = round(
            w_gap * gap[index]
            + w_relvol * relvol[index]
            + w_range * range_[index]
            + w_catalyst * catalyst_score,
            4,
        )
    rows.sort(key=lambda r: (-r["score"], -r["median_turnover"]))


# --------------------------------------------------------------------------
# reporting
# --------------------------------------------------------------------------


def _rupees(value: float) -> str:
    crore = value / 1e7
    if crore >= 1:
        return f"{crore:,.1f} cr"
    return f"{value / 1e5:,.1f} L"


def _criteria_lines(criteria: dict, universe: dict, keys: list[str]) -> list[str]:
    merged = {**universe, **criteria}
    return [f"  {key} = {merged[key]}" for key in keys if key in merged]


def _rejection_lines(rejected: dict[str, int]) -> list[str]:
    """Summarise rejections, folding the long tail of series codes.

    There are over a hundred non-equity NSE series and BSE groups, and
    listing each one buries the reasons a reader can act on. Those are
    folded into a single labelled line carrying its own total.

    Criteria rejections are never truncated. They are a small fixed set,
    and dropping the smallest would make the printed counts fail to add
    up to the universe — a report that quietly does not reconcile is
    worse than a long one.
    """
    excluded, other = {}, {}
    for reason, count in rejected.items():
        target = (
            excluded
            if reason.startswith(("nse series ", "bse group "))
            else other
        )
        target[reason] = count

    lines = []
    for reason, count in sorted(other.items(), key=lambda kv: -kv[1]):
        lines.append(f"  {count:>6}  {reason}")
    if excluded:
        top = sorted(excluded.items(), key=lambda kv: -kv[1])[:3]
        codes = ", ".join(reason.split()[-1] for reason, _ in top)
        lines.append(
            f"  {sum(excluded.values()):>6}  ineligible series or group "
            f"({len(excluded)} codes; largest {codes})"
        )
    return lines


def render_swing(result: dict, env: dict, criteria: dict, universe: dict) -> str:
    out = [
        "SWING SHORTLIST — NSE/BSE equities",
        "",
        f"AS OF      {env['as_of_session']} close",
        f"FEED       {env['feed_type']} ({env['sessions_loaded']} sessions loaded)",
        f"FETCHED    {env['fetched_at_ist']}",
        f"UNIVERSE   {result['screened']} securities after reconciliation, "
        f"{result['passing_total']} passed all criteria",
        "",
        "CRITERIA (References/swing-criteria.md, "
        "References/universe-and-exclusions.md)",
    ]
    out += _criteria_lines(
        criteria,
        universe,
        [
            "keep_nse_series",
            "keep_bse_groups",
            "min_close",
            "min_sessions",
            "sma_short",
            "sma_long",
            "max_pct_below_high",
            "min_median_turnover",
            "min_volume_ratio",
            "min_atr_pct",
            "max_atr_pct",
            "min_delivery_pct",
            "signal_breakout_window",
            "signal_cross_lookback",
            "signal_pullback_pct",
            "signal_extended_pct",
        ],
    )
    out += ["", f"{'#':>3}  {'SYMBOL':<12} {'EX':<4} {'CLOSE':>9} "
            f"{'>SMA50':>7} {'<HIGH':>6} {'VOLx':>5} {'ATR%':>5} "
            f"{'DELIV':>6} {'TURNOVER':>10} {'SIGNALS':<22} SCORE"]
    out.append("  " + "-" * 110)
    for index, row in enumerate(result["candidates"], 1):
        mark = "*" if row["delivery_partial"] else " "
        signals = ",".join(row.get("signals") or []) or "-"
        out.append(
            f"{index:>3}  {row['symbol']:<12} {row['exchange']:<4} "
            f"{row['close']:>9,.2f} {row['pct_above_sma_long']:>6.1f}% "
            f"{row['pct_below_high']:>5.1f}% {row['volume_ratio']:>5.2f} "
            f"{row['atr_pct']:>5.2f} {row['delivery_pct']:>5.1f}{mark} "
            f"{_rupees(row['median_turnover']):>10} {signals:<22} "
            f"{row['score']:.3f}"
        )
    if any(r["delivery_partial"] for r in result["candidates"]):
        out.append("")
        out.append("  * delivery averaged over a partial window")
    out += ["", "REJECTED BY"]
    out += _rejection_lines(result["rejected"])
    out += [
        "",
        "Candidates, not recommendations. End-of-day data; no intraday",
        "or live prices. Prices are unadjusted for corporate actions.",
    ]
    return "\n".join(out)


def render_day(result: dict, env: dict, criteria: dict, universe: dict) -> str:
    out = [
        f"DAY SHORTLIST — NSE/BSE equities, session {env['as_of_session']}",
        "",
        f"AS OF      {env['as_of_session']} close (completed session)",
        f"FEED       {env['feed_type']} — RETROSPECTIVE, not a live screen",
        f"FETCHED    {env['fetched_at_ist']}",
        f"UNIVERSE   {result['screened']} securities after reconciliation, "
        f"{result['passing_total']} passed all criteria",
        f"CATALYSTS  {'available' if result['catalysts_available'] else 'UNAVAILABLE — filings feed did not respond'}",
        "",
        "CRITERIA (References/day-criteria.md, "
        "References/universe-and-exclusions.md)",
    ]
    out += _criteria_lines(
        criteria,
        universe,
        [
            "keep_nse_series",
            "keep_bse_groups",
            "min_close",
            "min_abs_gap_pct",
            "min_relative_volume",
            "relvol_window",
            "min_range_pct",
            "min_median_turnover",
        ],
    )
    out += ["", f"{'#':>3}  {'SYMBOL':<12} {'EX':<4} {'CLOSE':>9} "
            f"{'GAP%':>7} {'RVOL':>6} {'RNG%':>6} {'TURNOVER':>10} "
            f"{'CATALYST':<10} {'HELD':<5} SCORE"]
    out.append("  " + "-" * 96)
    for index, row in enumerate(result["candidates"], 1):
        catalyst = row["catalyst"]
        if not result["catalysts_available"]:
            tag = "n/a"
        elif catalyst.get("material"):
            tag = "filing"
        elif catalyst.get("exchange_query"):
            tag = "exch-query"
        else:
            tag = "-"
        out.append(
            f"{index:>3}  {row['symbol']:<12} {row['exchange']:<4} "
            f"{row['close']:>9,.2f} {row['gap_pct']:>+6.2f}% "
            f"{row['relative_volume']:>6.2f} {row['range_pct']:>5.2f}% "
            f"{_rupees(row['median_turnover']):>10} {tag:<10} "
            f"{('yes' if row['observed_gap_held'] else 'no'):<5} "
            f"{row['score']:.3f}"
        )
    out += ["", "REJECTED BY"]
    out += _rejection_lines(result["rejected"])
    out += [
        "",
        "Candidates, not recommendations. This screens a COMPLETED session",
        "from end-of-day data — it is not a live intraday screen and could",
        "not have been run before that session closed. HELD is observed",
        "after the fact and is excluded from the score. Prices are",
        "unadjusted for corporate actions.",
    ]
    return "\n".join(out)


# --------------------------------------------------------------------------
# cli
# --------------------------------------------------------------------------


def _parse_date(text: str) -> date:
    return datetime.strptime(text, "%Y-%m-%d").date()


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        prog="screen.py",
        description=(
            "Rank NSE/BSE equities against the criteria in References/."
        ),
    )
    parser.add_argument("--cache-dir")
    parser.add_argument("--offline", action="store_true")
    parser.add_argument("--json", action="store_true", help="emit JSON")
    parser.add_argument(
        "--references",
        help="override the References directory (for testing)",
    )
    sub = parser.add_subparsers(dest="command", required=True)

    swing = sub.add_parser("swing", help="multi-day horizon")
    swing.add_argument("--as-of", required=True)

    day = sub.add_parser("day", help="one completed session")
    day.add_argument("--date", required=True)

    args = parser.parse_args(argv)
    references = Path(args.references) if args.references else REFERENCES
    root = (
        Path(args.cache_dir) if args.cache_dir else bhavcopy.default_cache_dir()
    )
    cache = bhavcopy.Cache(root, offline=args.offline)

    try:
        universe = load_criteria("universe-and-exclusions.md", references)

        if args.command == "swing":
            criteria = load_criteria("swing-criteria.md", references)
            end = _parse_date(args.as_of)
            sessions = bhavcopy.load_history(
                cache,
                end,
                require(criteria, "lookback_sessions"),
                quiet=True,
                reconcile_rows=False,
            )
            if not sessions:
                print(f"no sessions found ending {end}", file=sys.stderr)
                return 1
            result = screen_swing(sessions, criteria, universe)
            env = bhavcopy.envelope(sessions[-1]["date"], len(sessions))
            payload = {"envelope": env, "criteria": criteria, **result}
            print(
                json.dumps(payload, indent=2)
                if args.json
                else render_swing(result, env, criteria, universe)
            )

        else:
            criteria = load_criteria("day-criteria.md", references)
            target_date = _parse_date(args.date)
            target = bhavcopy.load_session(cache, target_date, quiet=True)
            if target is None:
                print(
                    f"no session published for {target_date} "
                    "(weekend, holiday, or not yet released)",
                    file=sys.stderr,
                )
                return 1
            history = bhavcopy.load_history(
                cache,
                target_date - timedelta(days=1),
                require(criteria, "lookback_sessions"),
                quiet=True,
                reconcile_rows=False,
            )
            announcements = bhavcopy.load_announcements(cache, target_date)
            result = screen_day(
                target, history, criteria, universe, announcements
            )
            env = bhavcopy.envelope(target["date"], len(history) + 1)
            payload = {"envelope": env, "criteria": criteria, **result}
            print(
                json.dumps(payload, indent=2)
                if args.json
                else render_day(result, env, criteria, universe)
            )

    except CriteriaError as exc:
        print(f"criteria error: {exc}", file=sys.stderr)
        return 2
    except bhavcopy.OfflineError as exc:
        print(f"offline: {exc}", file=sys.stderr)
        return 2
    except bhavcopy.FetchError as exc:
        print(f"fetch failed: {exc}", file=sys.stderr)
        return 2

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
