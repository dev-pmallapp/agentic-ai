"""Tests for the stock-screening agent's Tools/.

These test agent *content*, not the ``ai_agents`` package. The scripts
under ``agents/stock-screening/Tools/`` are shelled out to by a harness
and are not importable from ``ai_agents``, so they are loaded by path.
This is the first place in the repo that tests agent-tree code; the
loader below is the precedent.

Two kinds of fixture, deliberately:

* **Trimmed real CSVs** in ``fixtures/stock_screening/`` cover parsing.
  Only real files carry the quirks worth testing — the delivery feed
  pads every field with a leading space, and the NSE and BSE bhavcopies
  share a 34-column schema whose column names nobody would invent.
* **Synthetic bars** cover the arithmetic, so a test that says a moving
  average is 105.0 can be checked by hand.

Nothing here touches the network. Every cache used is a ``tmp_path``.
"""

from __future__ import annotations

import importlib.util
import sys
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parents[1]
TOOLS = REPO_ROOT / "agents" / "stock-screening" / "Tools"
REFERENCES = REPO_ROOT / "agents" / "stock-screening" / "References"
FIXTURES = Path(__file__).parent / "fixtures" / "stock_screening"


def _load(name: str):
    """Import a Tools script by path.

    ``screen`` imports ``bhavcopy`` as a sibling, so the directory has
    to be importable for the duration of the load.
    """
    sys.path.insert(0, str(TOOLS))
    try:
        spec = importlib.util.spec_from_file_location(name, TOOLS / f"{name}.py")
        module = importlib.util.module_from_spec(spec)
        sys.modules[name] = module
        spec.loader.exec_module(module)
        return module
    finally:
        sys.path.remove(str(TOOLS))


bhavcopy = _load("bhavcopy")
screen = _load("screen")


@pytest.fixture(autouse=True)
def no_network(monkeypatch):
    """Any test that reaches the network is a broken test."""

    def explode(*args, **kwargs):
        raise AssertionError("test attempted a network call")

    monkeypatch.setattr(bhavcopy.urllib.request, "urlopen", explode)


def bar(close, *, high=None, low=None, open_=None, volume=1000.0,
        turnover=None, delivery=50.0, exchange="NSE", series="EQ",
        isin="INE000A01001", symbol="TESTCO", prev_close=None):
    """One normalised session row, with sane defaults around ``close``."""
    return {
        "date": "2026-01-01",
        "isin": isin,
        "symbol": symbol,
        "series": series,
        "name": symbol,
        "exchange": exchange,
        "open": close if open_ is None else open_,
        "high": close * 1.01 if high is None else high,
        "low": close * 0.99 if low is None else low,
        "close": close,
        "prev_close": close if prev_close is None else prev_close,
        "volume": volume,
        "turnover": close * volume if turnover is None else turnover,
        "trades": 100.0,
        "delivery_pct": delivery,
    }


def sessions_from(bars_by_isin: dict[str, list[dict]]) -> list[dict]:
    """Transpose per-name bar lists into per-session row lists."""
    length = max(len(b) for b in bars_by_isin.values())
    out = []
    for index in range(length):
        rows = [
            bars[index] for bars in bars_by_isin.values() if index < len(bars)
        ]
        out.append({"date": f"2026-01-{index + 1:02d}", "rows": rows})
    return out


# --------------------------------------------------------------------------
# parsing real files
# --------------------------------------------------------------------------


def test_parses_nse_udiff_equity_rows():
    rows = bhavcopy.parse_udiff(
        (FIXTURES / "nse-udiff-sample.csv").read_text(), "NSE"
    )

    assert rows, "fixture produced no rows"
    assert all(r["exchange"] == "NSE" for r in rows)
    assert all(r["isin"] for r in rows)
    assert all(r["close"] > 0 for r in rows)
    # The series column survives parsing — exclusions depend on it.
    assert {"EQ", "BE", "SM", "GS", "BZ"} <= {r["series"] for r in rows}


def test_parses_bse_udiff_with_the_same_parser():
    # NSE and BSE publish the identical 34-column schema. If that ever
    # stops being true, this is the test that says so.
    rows = bhavcopy.parse_udiff(
        (FIXTURES / "bse-udiff-sample.csv").read_text(), "BSE"
    )

    assert rows
    assert all(r["exchange"] == "BSE" for r in rows)
    assert {"A", "B", "T", "Z", "X"} <= {r["series"] for r in rows}


def test_udiff_parser_drops_non_equity_instruments():
    header = (
        "TradDt,BizDt,Sgmt,Src,FinInstrmTp,FinInstrmId,ISIN,TckrSymb,"
        "SctySrs,XpryDt,FininstrmActlXpryDt,StrkPric,OptnTp,FinInstrmNm,"
        "OpnPric,HghPric,LwPric,ClsPric,LastPric,PrvsClsgPric,UndrlygPric,"
        "SttlmPric,OpnIntrst,ChngInOpnIntrst,TtlTradgVol,TtlTrfVal,"
        "TtlNbOfTxsExctd,SsnId,NewBrdLotQty,Rmks,Rsvd1,Rsvd2,Rsvd3,Rsvd4"
    )
    body = (
        "2026-08-20,2026-08-20,CM,NSE,IDX,1,INE000A01001,NIFTY,EQ,,,,,IDX,"
        "1,1,1,1,1,1,,1,,,1,1,1,F1,1,,,,,"
    )
    assert bhavcopy.parse_udiff(header + "\n" + body + "\n", "NSE") == []


def test_delivery_parser_strips_the_leading_space_padding():
    # Every field name and value in this feed is padded with a leading
    # space. Without stripping, every lookup misses silently.
    raw = (FIXTURES / "nse-delivery-sample.csv").read_text()
    assert " SERIES" in raw.splitlines()[0], "fixture lost its padding"

    delivery = bhavcopy.parse_delivery(raw)

    assert delivery, "padded header defeated the parser"
    assert all(isinstance(v, float) for v in delivery.values())
    assert all(not k.startswith(" ") for k in delivery)


def test_number_coercion_treats_blanks_and_dashes_as_missing():
    assert bhavcopy._number("") is None
    assert bhavcopy._number("-") is None
    assert bhavcopy._number("12.5") == 12.5


# --------------------------------------------------------------------------
# reconciliation
# --------------------------------------------------------------------------


def test_reconcile_keeps_the_higher_turnover_venue():
    rows = [
        bar(100.0, exchange="NSE", turnover=500.0),
        bar(100.0, exchange="BSE", turnover=900.0),
    ]

    merged = bhavcopy.reconcile(rows)

    assert len(merged) == 1
    assert merged[0]["exchange"] == "BSE"
    assert merged[0]["also_on"] == "NSE"


def test_reconcile_uses_turnover_not_volume():
    # A stock can trade more shares on the cheaper venue while the money
    # goes through the other one. Turnover is the comparable figure.
    rows = [
        bar(100.0, exchange="NSE", volume=10.0, turnover=900.0),
        bar(100.0, exchange="BSE", volume=99.0, turnover=500.0),
    ]

    assert bhavcopy.reconcile(rows)[0]["exchange"] == "NSE"


def test_reconcile_keeps_distinct_isins_apart():
    rows = [
        bar(100.0, isin="INE000A01001", turnover=100.0),
        bar(200.0, isin="INE000A01002", turnover=100.0),
    ]

    assert len(bhavcopy.reconcile(rows)) == 2


# --------------------------------------------------------------------------
# series assembly — the window-level venue rule
# --------------------------------------------------------------------------


UNIVERSE_DEFAULTS = {
    "keep_nse_series": "EQ",
    "keep_bse_groups": ["A", "B"],
    "min_close": 50,
    "min_median_turnover": 50000000,
    "min_sessions": 3,
    "exclude_circuit_locked": True,
}


def test_series_picks_one_venue_for_the_whole_window():
    # Regression: choosing a venue per session splices BSE volume into an
    # NSE baseline the moment a block deal wins one day on the other
    # exchange, which corrupts every volume ratio spanning the swap and
    # drops delivery, since delivery is NSE-only.
    nse = [bar(100.0, exchange="NSE", turnover=1000.0, volume=10.0)
           for _ in range(5)]
    bse = [bar(100.0, exchange="BSE", turnover=10.0, volume=999.0)
           for _ in range(5)]
    # BSE wins this one session outright (2000 > 1000) but not the
    # window (2040 < 5000). Per-session selection would take the bait.
    bse[2]["turnover"] = 2000.0

    sessions = [
        {"date": f"d{i}", "rows": [nse[i], bse[i]]} for i in range(5)
    ]

    series = screen.build_series(sessions, UNIVERSE_DEFAULTS)
    entry = series["INE000A01001"]

    assert entry["exchange"] == "NSE"
    assert entry["also_on"] == ["BSE"]
    assert {b["exchange"] for b in entry["bars"]} == {"NSE"}
    assert all(b["volume"] == 10.0 for b in entry["bars"])
    # Every session survives. Reconciling per session first would hand
    # session 2 to BSE, and choosing NSE for the window would then drop
    # that bar entirely — a silently shorter history.
    assert len(entry["bars"]) == 5


def test_series_follows_total_turnover_when_the_other_venue_dominates():
    nse = [bar(100.0, exchange="NSE", turnover=10.0) for _ in range(4)]
    bse = [bar(100.0, exchange="BSE", turnover=1000.0) for _ in range(4)]
    sessions = [{"date": f"d{i}", "rows": [nse[i], bse[i]]} for i in range(4)]

    entry = screen.build_series(sessions, UNIVERSE_DEFAULTS)["INE000A01001"]

    assert entry["exchange"] == "BSE"


def test_series_drops_circuit_locked_sessions_not_the_stock():
    # A name locked forty sessions ago is tradeable today. Dropping it
    # outright would silently shorten every window that touched it.
    bars = [bar(100.0) for _ in range(5)]
    bars[1]["high"] = bars[1]["low"] = 100.0
    sessions = [{"date": f"d{i}", "rows": [bars[i]]} for i in range(5)]

    entry = screen.build_series(sessions, UNIVERSE_DEFAULTS)["INE000A01001"]

    assert len(entry["bars"]) == 4


# --------------------------------------------------------------------------
# indicators
# --------------------------------------------------------------------------


def test_sma_averages_the_trailing_window_only():
    assert screen.sma([1.0, 2.0, 3.0, 100.0], 3) == 35.0


def test_sma_returns_none_when_history_is_short():
    assert screen.sma([1.0, 2.0], 5) is None


def test_true_range_counts_the_gap():
    # A stock that gaps to 110 and trades 110-111 had an 11-point day,
    # not a 1-point one. High-low alone would call it quiet.
    bars = [bar(100.0, high=100.0, low=100.0),
            bar(110.5, high=111.0, low=110.0)]

    assert screen.true_ranges(bars)[1] == pytest.approx(11.0)


def test_atr_pct_is_relative_to_price():
    bars = [bar(100.0, high=102.0, low=98.0) for _ in range(10)]

    # Every bar has a 4-point range on a 100 close.
    assert screen.atr_pct(bars, 5) == pytest.approx(4.0)


def test_atr_pct_returns_none_without_enough_bars():
    assert screen.atr_pct([bar(100.0)], 14) is None


def test_median_ignores_missing_values():
    assert screen.median([1.0, None, 3.0]) == 2.0
    assert screen.median([None]) is None


def test_scale_maps_to_unit_range():
    assert screen.scale([10.0, 20.0, 30.0]) == [0.0, 0.5, 1.0]


def test_scale_of_identical_values_is_neutral():
    # Not 0.0 — an all-equal component should not zero out its weight.
    assert screen.scale([7.0, 7.0]) == [0.5, 0.5]


# --------------------------------------------------------------------------
# criteria parsing
# --------------------------------------------------------------------------


def test_parses_a_parameter_table():
    text = """
| Parameter | Value | Meaning |
|---|---|---|
| `min_close` | 50 | Price floor |
| `min_atr_pct` | 2.5 | Lower bound |
| `keep_bse_groups` | A, B | Groups |
| `exclude_circuit_locked` | true | Drop locked |
| `keep_nse_series` | EQ | Series |
"""
    params = screen.parse_parameters(text)

    assert params["min_close"] == 50
    assert isinstance(params["min_close"], int)
    assert params["min_atr_pct"] == 2.5
    assert params["keep_bse_groups"] == ["A", "B"]
    assert params["exclude_circuit_locked"] is True
    assert params["keep_nse_series"] == "EQ"


def test_prose_tables_are_not_mistaken_for_parameters():
    # The criteria files carry explanatory tables too. Only backticked
    # lowercase identifiers in the first cell are parameters.
    text = """
| Component | Weight | Normalised as |
|---|---|---|
| Trend strength | 0.35 | Percent above the average |
| `Series` | EQ | capitalised, not a parameter |
"""
    assert screen.parse_parameters(text) == {}


def test_every_shipped_criteria_file_parses():
    for name in (
        "universe-and-exclusions.md",
        "swing-criteria.md",
        "day-criteria.md",
    ):
        assert screen.load_criteria(name, REFERENCES)


def test_shipped_criteria_carry_every_parameter_the_code_requires():
    # A parameter row deleted from a Reference is a silent breakage
    # otherwise — the screen would fail only at run time, on live data.
    universe = screen.load_criteria("universe-and-exclusions.md", REFERENCES)
    swing = screen.load_criteria("swing-criteria.md", REFERENCES)
    day = screen.load_criteria("day-criteria.md", REFERENCES)

    for key in ("keep_nse_series", "keep_bse_groups", "min_close",
                "min_sessions", "exclude_circuit_locked"):
        assert key in universe, key
    for key in ("lookback_sessions", "sma_short", "sma_long", "high_window",
                "max_pct_below_high", "min_median_turnover", "turnover_window",
                "min_volume_ratio", "volume_recent_window",
                "volume_base_window", "atr_window", "min_atr_pct",
                "max_atr_pct", "min_delivery_pct", "delivery_window",
                "weight_trend", "weight_volume", "weight_volatility",
                "weight_delivery", "shortlist_size"):
        assert key in swing, key
    for key in ("lookback_sessions", "min_abs_gap_pct", "min_relative_volume",
                "relvol_window", "min_range_pct", "min_median_turnover",
                "turnover_window", "weight_gap", "weight_relvol",
                "weight_range", "weight_catalyst", "shortlist_size"):
        assert key in day, key


def test_swing_lookback_covers_its_longest_window():
    # Raising sma_long past lookback_sessions would silently compute the
    # average over a shorter history than the criteria claim.
    swing = screen.load_criteria("swing-criteria.md", REFERENCES)
    universe = screen.load_criteria("universe-and-exclusions.md", REFERENCES)

    for key in ("sma_long", "high_window", "volume_base_window"):
        assert swing["lookback_sessions"] >= swing[key], key
    assert swing["lookback_sessions"] >= universe["min_sessions"]


def test_missing_criteria_file_is_an_error():
    with pytest.raises(screen.CriteriaError):
        screen.load_criteria("nope.md", REFERENCES)


def test_file_without_a_parameter_table_is_an_error(tmp_path):
    (tmp_path / "empty.md").write_text("# Nothing here\n")
    with pytest.raises(screen.CriteriaError):
        screen.load_criteria("empty.md", tmp_path)


def test_require_names_the_missing_parameter():
    with pytest.raises(screen.CriteriaError, match="min_close"):
        screen.require({}, "min_close")


# --------------------------------------------------------------------------
# eligibility
# --------------------------------------------------------------------------


def _entry(**kwargs):
    bars = [bar(**kwargs) for _ in range(5)]
    return {
        "isin": bars[0]["isin"],
        "symbol": bars[0]["symbol"],
        "name": bars[0]["symbol"],
        "series": bars[0]["series"],
        "exchange": bars[0]["exchange"],
        "bars": bars,
    }


@pytest.mark.parametrize("series", ["BE", "BZ", "SM", "ST", "GS", "N1"])
def test_non_equity_nse_series_are_excluded(series):
    ok, reason = screen.eligible(
        _entry(series=series, close=100.0), UNIVERSE_DEFAULTS
    )
    assert not ok
    assert series.lower() in reason.lower()


@pytest.mark.parametrize("group", ["T", "Z", "X", "XT", "M", "F"])
def test_restricted_bse_groups_are_excluded(group):
    ok, reason = screen.eligible(
        _entry(series=group, exchange="BSE", close=100.0), UNIVERSE_DEFAULTS
    )
    assert not ok
    assert group.lower() in reason.lower()


def test_eq_series_and_ab_groups_are_kept():
    assert screen.eligible(_entry(close=100.0), UNIVERSE_DEFAULTS)[0]
    assert screen.eligible(
        _entry(series="A", exchange="BSE", close=100.0), UNIVERSE_DEFAULTS
    )[0]


def test_price_floor_excludes_penny_stocks():
    ok, reason = screen.eligible(_entry(close=10.0), UNIVERSE_DEFAULTS)
    assert not ok
    assert "price floor" in reason


def test_short_history_is_excluded():
    entry = _entry(close=100.0)
    entry["bars"] = entry["bars"][:1]

    ok, reason = screen.eligible(entry, UNIVERSE_DEFAULTS)

    assert not ok
    assert "history" in reason


# --------------------------------------------------------------------------
# swing screen
# --------------------------------------------------------------------------


SWING_CRITERIA = {
    "lookback_sessions": 60, "sma_short": 3, "sma_long": 5,
    "high_window": 5, "max_pct_below_high": 10.0,
    "min_median_turnover": 0, "turnover_window": 5,
    "min_volume_ratio": 1.0, "volume_recent_window": 2,
    "volume_base_window": 5, "atr_window": 3,
    "min_atr_pct": 0.0, "max_atr_pct": 100.0,
    "min_delivery_pct": 45.0, "delivery_window": 5,
    "weight_trend": 0.35, "weight_volume": 0.20,
    "weight_volatility": 0.20, "weight_delivery": 0.25,
    "shortlist_size": 25,
}


def _uptrend(n=8, **kwargs):
    return [bar(100.0 + i * 5, **kwargs) for i in range(n)]


def test_swing_selects_an_uptrend():
    sessions = sessions_from({"a": _uptrend()})

    result = screen.screen_swing(sessions, SWING_CRITERIA, UNIVERSE_DEFAULTS)

    assert result["passing_total"] == 1
    assert result["candidates"][0]["symbol"] == "TESTCO"


def test_swing_rejects_a_downtrend():
    bars = [bar(200.0 - i * 5) for i in range(8)]

    result = screen.screen_swing(
        sessions_from({"a": bars}), SWING_CRITERIA, UNIVERSE_DEFAULTS
    )

    assert result["passing_total"] == 0
    assert result["rejected"]["trend"] == 1


def test_swing_rejects_low_delivery():
    result = screen.screen_swing(
        sessions_from({"a": _uptrend(delivery=10.0)}),
        SWING_CRITERIA,
        UNIVERSE_DEFAULTS,
    )

    assert result["passing_total"] == 0
    assert result["rejected"]["delivery"] == 1


def test_swing_treats_missing_delivery_as_unknown_not_zero():
    # A BSE-primary name has no delivery figure. Scoring it zero would
    # both fabricate a number and systematically exclude the names the
    # reconciliation rule assigned to BSE.
    result = screen.screen_swing(
        sessions_from({"a": _uptrend(delivery=None)}),
        SWING_CRITERIA,
        UNIVERSE_DEFAULTS,
    )

    assert result["rejected"].get("delivery data unavailable") == 1
    assert "delivery" not in result["rejected"]


def test_swing_accepts_a_partial_delivery_window_and_flags_it():
    bars = _uptrend()
    # delivery_window is 5, so the window is the last five bars.
    bars[-2]["delivery_pct"] = None

    result = screen.screen_swing(
        sessions_from({"a": bars}), SWING_CRITERIA, UNIVERSE_DEFAULTS
    )

    assert result["passing_total"] == 1
    assert result["candidates"][0]["delivery_partial"] is True


def test_swing_rejects_outside_the_volatility_band():
    criteria = {**SWING_CRITERIA, "min_atr_pct": 50.0, "max_atr_pct": 90.0}

    result = screen.screen_swing(
        sessions_from({"a": _uptrend()}), criteria, UNIVERSE_DEFAULTS
    )

    assert result["rejected"]["outside volatility band"] == 1


def test_swing_rejects_illiquid_names():
    criteria = {**SWING_CRITERIA, "min_median_turnover": 10**12}

    result = screen.screen_swing(
        sessions_from({"a": _uptrend()}), criteria, UNIVERSE_DEFAULTS
    )

    assert result["rejected"]["liquidity"] == 1


def test_swing_volatility_score_peaks_mid_band():
    # The band's ceiling exists because more volatility is worse, so a
    # score that rewarded the maximum would fight its own filter.
    criteria = {**SWING_CRITERIA, "min_atr_pct": 0.0, "max_atr_pct": 10.0,
                "weight_trend": 0.0, "weight_volume": 0.0,
                "weight_delivery": 0.0, "weight_volatility": 1.0}
    rows = [
        {"pct_above_sma_long": 1.0, "volume_ratio": 1.0, "delivery_pct": 50.0,
         "atr_pct": 5.0, "median_turnover": 1.0},
        {"pct_above_sma_long": 1.0, "volume_ratio": 1.0, "delivery_pct": 50.0,
         "atr_pct": 10.0, "median_turnover": 1.0},
    ]

    screen._rank_swing(rows, criteria)

    assert rows[0]["atr_pct"] == 5.0  # mid-band ranks first
    assert rows[0]["score"] > rows[1]["score"]


def test_swing_rejection_counts_reconcile_with_the_universe():
    # A report whose numbers do not add up is worse than a long one.
    sessions = sessions_from({
        "a": _uptrend(),
        "b": [bar(200.0 - i * 5, isin="INE000A01002", symbol="DOWN")
              for i in range(8)],
        "c": [bar(10.0, isin="INE000A01003", symbol="PENNY")
              for _ in range(8)],
    })

    result = screen.screen_swing(sessions, SWING_CRITERIA, UNIVERSE_DEFAULTS)

    assert sum(result["rejected"].values()) + result["passing_total"] == (
        result["screened"]
    )


# --------------------------------------------------------------------------
# day screen
# --------------------------------------------------------------------------


DAY_CRITERIA = {
    "lookback_sessions": 30, "min_abs_gap_pct": 3.0,
    "min_relative_volume": 2.0, "relvol_window": 5,
    "min_range_pct": 2.0, "min_median_turnover": 0, "turnover_window": 5,
    "weight_gap": 0.35, "weight_relvol": 0.30,
    "weight_range": 0.15, "weight_catalyst": 0.20,
    "shortlist_size": 25,
}

NO_CATALYSTS = {"available": True, "by_symbol": {}}


def _day_setup(open_=110.0, close=112.0, high=115.0, low=108.0, volume=5000.0):
    history = sessions_from({"a": [bar(100.0, volume=1000.0) for _ in range(6)]})
    target = {
        "date": "2026-01-07",
        "rows": [bar(close, open_=open_, high=high, low=low,
                     prev_close=100.0, volume=volume)],
    }
    return target, history


def test_day_selects_a_gap_on_heavy_volume():
    target, history = _day_setup()

    result = screen.screen_day(
        target, history, DAY_CRITERIA, UNIVERSE_DEFAULTS, NO_CATALYSTS
    )

    assert result["passing_total"] == 1
    row = result["candidates"][0]
    assert row["gap_pct"] == pytest.approx(10.0)
    assert row["relative_volume"] == pytest.approx(5.0)
    assert row["direction"] == "up"


def test_day_screens_gaps_in_both_directions():
    target, history = _day_setup(open_=90.0, close=88.0, high=92.0, low=85.0)

    result = screen.screen_day(
        target, history, DAY_CRITERIA, UNIVERSE_DEFAULTS, NO_CATALYSTS
    )

    assert result["passing_total"] == 1
    assert result["candidates"][0]["direction"] == "down"


def test_day_rejects_a_small_gap():
    target, history = _day_setup(open_=100.5, close=101.0)

    result = screen.screen_day(
        target, history, DAY_CRITERIA, UNIVERSE_DEFAULTS, NO_CATALYSTS
    )

    assert result["rejected"]["gap"] == 1


def test_day_rejects_ordinary_volume():
    target, history = _day_setup(volume=1000.0)

    result = screen.screen_day(
        target, history, DAY_CRITERIA, UNIVERSE_DEFAULTS, NO_CATALYSTS
    )

    assert result["rejected"]["relative volume"] == 1


def test_day_rejects_a_gap_with_no_range():
    target, history = _day_setup(open_=110.0, close=110.0,
                                 high=110.1, low=110.0)

    result = screen.screen_day(
        target, history, DAY_CRITERIA, UNIVERSE_DEFAULTS, NO_CATALYSTS
    )

    assert result["rejected"]["range"] == 1


def test_day_excludes_circuit_locked_sessions():
    target, history = _day_setup(open_=110.0, close=110.0,
                                 high=110.0, low=110.0)

    result = screen.screen_day(
        target, history, DAY_CRITERIA, UNIVERSE_DEFAULTS, NO_CATALYSTS
    )

    assert result["rejected"]["circuit locked"] == 1


def test_day_records_but_does_not_score_the_observed_outcome():
    # Ranking on it would be look-ahead: a beautiful shortlist that could
    # not have been built on the morning of the date it screens.
    #
    # Two names identical in every scored component — same gap, range,
    # relative volume and turnover — differing only in where the close
    # landed relative to the open. One held its gap, one faded it. If
    # the outcome leaked into the ranking, their scores would diverge.
    held = bar(114.0, open_=110.0, high=115.0, low=108.0, prev_close=100.0,
               volume=5000.0, isin="INE000A01001", symbol="HELD")
    faded = bar(105.0, open_=110.0, high=115.0, low=108.0, prev_close=100.0,
                volume=5000.0, isin="INE000A01002", symbol="FADED")
    target = {"date": "2026-01-07", "rows": [held, faded]}
    history = sessions_from({
        "a": [bar(100.0, volume=1000.0) for _ in range(6)],
        "b": [bar(100.0, volume=1000.0, isin="INE000A01002", symbol="FADED")
              for _ in range(6)],
    })

    result = screen.screen_day(
        target, history, DAY_CRITERIA, UNIVERSE_DEFAULTS, NO_CATALYSTS
    )

    by_symbol = {r["symbol"]: r for r in result["candidates"]}
    assert by_symbol["HELD"]["observed_gap_held"] is True
    assert by_symbol["FADED"]["observed_gap_held"] is False
    assert by_symbol["HELD"]["score"] == by_symbol["FADED"]["score"]


# --------------------------------------------------------------------------
# catalysts
# --------------------------------------------------------------------------


def test_material_filings_count_as_catalysts():
    result = screen.classify_catalysts(
        [{"category": "Bagging/Receiving of orders/contracts"}]
    )

    assert result["has_catalyst"]
    assert result["material"]


def test_administrative_filings_do_not_count():
    # A day's filings are mostly newspaper copies and general updates.
    # Counting them would mark almost everything as having a catalyst.
    result = screen.classify_catalysts([
        {"category": "Copy of Newspaper Publication"},
        {"category": "General Updates"},
        {"category": "Shareholders meeting"},
        {"category": "Investor Presentation"},
    ])

    assert not result["has_catalyst"]


def test_exchange_queries_are_counted_but_labelled_separately():
    result = screen.classify_catalysts([{"category": "Spurt in Volume"}])

    assert result["has_catalyst"]
    assert result["exchange_query"] == ["Spurt in Volume"]
    assert result["material"] == []


def test_catalyst_matching_ignores_case():
    assert screen.classify_catalysts(
        [{"category": "ACQUISITION"}]
    )["has_catalyst"]


def test_catalyst_presence_lifts_the_ranking():
    target, history = _day_setup()
    other = bar(112.0, open_=110.0, high=115.0, low=108.0, prev_close=100.0,
                volume=5000.0, isin="INE000A01002", symbol="OTHER")
    target["rows"].append(other)
    history = sessions_from({
        "a": [bar(100.0, volume=1000.0) for _ in range(6)],
        "b": [bar(100.0, volume=1000.0, isin="INE000A01002", symbol="OTHER")
              for _ in range(6)],
    })
    announcements = {
        "available": True,
        "by_symbol": {"OTHER": [{"category": "Acquisition"}]},
    }

    result = screen.screen_day(
        target, history, DAY_CRITERIA, UNIVERSE_DEFAULTS, announcements
    )

    assert result["candidates"][0]["symbol"] == "OTHER"


def test_unavailable_catalysts_redistribute_the_weight():
    # Scoring every name zero on a missing component leaves the ranking
    # unchanged but makes every score misleading.
    rows = [
        {"gap_pct": 5.0, "relative_volume": 3.0, "range_pct": 4.0,
         "median_turnover": 1.0, "catalyst": {"available": False}},
        {"gap_pct": 3.0, "relative_volume": 2.0, "range_pct": 2.0,
         "median_turnover": 1.0, "catalyst": {"available": False}},
    ]

    screen._rank_day(rows, DAY_CRITERIA, catalysts=False)

    # Top row is maximal on all three surviving components, so its score
    # is the full redistributed weight.
    assert rows[0]["score"] == pytest.approx(1.0)


def test_day_reports_catalyst_availability():
    target, history = _day_setup()

    unavailable = screen.screen_day(
        target, history, DAY_CRITERIA, UNIVERSE_DEFAULTS,
        {"available": False, "by_symbol": {}},
    )

    assert unavailable["catalysts_available"] is False
    assert unavailable["candidates"][0]["catalyst"] == {"available": False}


# --------------------------------------------------------------------------
# caching and offline behaviour
# --------------------------------------------------------------------------


def test_offline_without_cache_raises_rather_than_fetching(tmp_path):
    cache = bhavcopy.Cache(tmp_path, offline=True)

    with pytest.raises(bhavcopy.OfflineError):
        bhavcopy.fetch_cached(
            cache, cache.reference_path("equity-l.csv"), bhavcopy.NSE_EQUITY_L
        )


def test_offline_serves_a_cached_file(tmp_path):
    cache = bhavcopy.Cache(tmp_path, offline=True)
    path = cache.reference_path("equity-l.csv")
    cache.write(path, b"cached")

    assert (
        bhavcopy.fetch_cached(cache, path, bhavcopy.NSE_EQUITY_L) == b"cached"
    )


def test_cache_write_is_atomic(tmp_path):
    # A half-written file must never survive to look like a cache hit.
    cache = bhavcopy.Cache(tmp_path)
    path = cache.session_path(bhavcopy.date(2026, 8, 20), "nse-udiff.csv")

    cache.write(path, b"payload")

    assert path.read_bytes() == b"payload"
    assert not list(path.parent.glob("*.partial"))


def test_a_cached_non_session_is_not_a_cache_miss(tmp_path):
    # Without the negative marker, offline mode cannot tell a market
    # holiday from a gap in the cache, and the first holiday in a window
    # makes an otherwise complete cache look broken.
    cache = bhavcopy.Cache(tmp_path, offline=True)
    holiday = bhavcopy.date(2026, 6, 26)
    cache.write(cache.session_path(holiday, "no-session.marker"), b"x")

    assert bhavcopy.load_session(cache, holiday) is None


def test_offline_gap_without_a_marker_is_an_error(tmp_path):
    cache = bhavcopy.Cache(tmp_path, offline=True)

    with pytest.raises(bhavcopy.OfflineError):
        bhavcopy.load_session(cache, bhavcopy.date(2026, 8, 20))


def test_offline_history_refuses_a_short_window(tmp_path):
    # Silently returning fewer sessions would make a 20-session average
    # quietly compute over 11 — wrong in a way nobody would notice.
    cache = bhavcopy.Cache(tmp_path, offline=True)

    with pytest.raises(bhavcopy.OfflineError):
        bhavcopy.load_history(cache, bhavcopy.date(2026, 8, 20), 10)


def test_default_cache_dir_follows_xdg(monkeypatch, tmp_path):
    monkeypatch.setenv("XDG_CACHE_HOME", str(tmp_path))

    assert bhavcopy.default_cache_dir() == (
        tmp_path / "ai-agents" / "india-market-data"
    )


# --------------------------------------------------------------------------
# freshness envelope
# --------------------------------------------------------------------------


def test_envelope_states_the_feed_is_not_live():
    # The agent's boundaries require freshness to be reported rather than
    # assumed, so it is attached at the source.
    env = bhavcopy.envelope("2026-08-20", 60)

    assert env["live"] is False
    assert env["feed_type"] == "end-of-day"
    assert env["as_of_session"] == "2026-08-20"
    assert env["sessions_loaded"] == 60
    assert "IST" in env["fetched_at_ist"]


def test_user_agent_is_sent_on_every_request():
    # With no User-Agent both exchanges drop the connection entirely —
    # no status code, no body. This is the single easiest way to break
    # the fetcher.
    assert "Mozilla" in bhavcopy.USER_AGENT
