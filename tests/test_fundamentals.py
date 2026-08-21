"""Tests for the stock-screening agent's Tools/fundamentals.py.

Agent *content*, loaded by path, following the precedent set in
``test_stock_screening_tools.py``.

The fixtures here are **trimmed real payloads**, for the same reason
that file uses real CSVs: only the genuine article carries the quirks
worth testing. screener.in's quarterly table nests its numbers in tag
soup, the NSE results feed pads its own history newest-first, and
moneycontrol returns its status code as the *string* ``"200"``. None of
those are things anyone would invent for a synthetic fixture, and each
one has already been the difference between a parser that works and one
that silently returns nothing.

Nothing here touches the network. Every cache is a ``tmp_path``.
"""

from __future__ import annotations

import importlib.util
import json
import sys
from datetime import date
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parents[1]
TOOLS = REPO_ROOT / "agents" / "stock-screening" / "Tools"
REFERENCES = REPO_ROOT / "agents" / "stock-screening" / "References"


def _load(name: str):
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
fundamentals = _load("fundamentals")


@pytest.fixture(autouse=True)
def no_network(monkeypatch):
    """Any test that reaches the network is a broken test."""

    def explode(*args, **kwargs):
        raise AssertionError("test attempted a network call")

    monkeypatch.setattr(bhavcopy.urllib.request, "urlopen", explode)


@pytest.fixture
def criteria():
    return screen.load_criteria("fundamental-criteria.md", REFERENCES)


# Reliance's real quarterly numbers, trimmed to the five quarters the
# derivation needs. Checked by hand against the rendered page: EPS over
# the last four sums to 55.22, and Jun 2026 revenue is 27.02% above Jun
# 2025 while profit is 24.65% below it.
SCREENER_HTML = """
<section id="quarters">
<table>
<thead><tr><th></th>
<th>Jun 2025</th><th>Sep 2025</th><th>Dec 2025</th><th>Mar 2026</th><th>Jun 2026</th>
</tr></thead>
<tbody>
<tr><td class="text">Sales&nbsp;+</td>
<td>243,632</td><td>254,623</td><td>264,905</td><td>294,059</td><td>309,468</td></tr>
<tr><td class="text">OPM %</td>
<td>18%</td><td>18%</td><td>17%</td><td>15%</td><td>15%</td></tr>
<tr><td class="text">Net Profit&nbsp;+</td>
<td>30,783</td><td>22,092</td><td>22,290</td><td>20,589</td><td>23,196</td></tr>
<tr><td class="text">EPS in Rs</td>
<td>19.95</td><td>13.42</td><td>13.78</td><td>12.54</td><td>15.48</td></tr>
</tbody>
</table>
</section>
<li><span class="name">ROCE</span><span class="nowrap value">
<span class="number">10.3</span>&nbsp;%</span></li>
<li><span class="name">ROE</span><span class="nowrap value">
<span class="number">8.91</span>&nbsp;%</span></li>
"""

TICKERTAPE_SEARCH = json.dumps(
    {
        "success": True,
        "data": {
            "stocks": [
                {"ticker": "RELIANCE", "sid": "RELI", "name": "Reliance Industries Ltd"},
                {"ticker": "RELIANCEPP", "sid": "RELIPP", "name": "Partly paid"},
            ]
        },
    }
)

TICKERTAPE_INFO = json.dumps(
    {
        "success": True,
        "data": {
            "info": {"sector": "Oil & Gas - Refining & Marketing", "ticker": "RELIANCE"},
            "ratios": {"pe": 45.41, "ttmPe": 23.83, "roe": 8.5, "pb": 3.15},
        },
    }
)

# moneycontrol returns its status as a string, and names the NSE ticker
# the payload belongs to — which is what makes a bad sc_id detectable.
MONEYCONTROL = json.dumps(
    {
        "code": "200",
        "data": {
            "company": "Reliance",
            "NSEID": "RELIANCE",
            "PECONS": 23.83,
            "PE": 45.41,
            "main_sector": "Oil & Gas",
        },
    }
)

# The exchange feed publishes newest-first, and uses lakhs where the
# rendered sites use crore. Two quarters is enough to prove the reversal.
NSE_RESULTS = json.dumps(
    {
        "resCmpData": [
            {
                "re_to_dt": "31-DEC-2024",
                "re_net_sale": "12826000",
                "re_net_profit": "872100",
                "re_basic_eps_for_cont_dic_opr": "6.44",
                "re_oth_tot_exp": "11987700",
                "re_debt_eqt_rat": "0",
            },
            {
                "re_to_dt": "30-SEP-2024",
                "re_net_sale": "13405400",
                "re_net_profit": "771300",
                "re_basic_eps_for_cont_dic_opr": "11.4",
                "re_oth_tot_exp": "12764100",
                "re_debt_eqt_rat": "0",
            },
        ]
    }
)


@pytest.fixture
def cache(tmp_path, monkeypatch):
    """A cache pre-seeded with every provider's payload.

    Seeding the cache rather than stubbing the fetch means the real
    ``fetch_cached`` path runs, so a change to how paths are keyed shows
    up here instead of passing against a mock that agreed with itself.

    ``offline=True`` because a symbol that is *not* seeded here should
    fail as an uncached provider rather than reaching the network — that
    is what the missing-provider tests are asserting about.
    """
    root = tmp_path / "cache"
    store = bhavcopy.Cache(root, offline=True)
    base = root / fundamentals.FUNDAMENTALS_DIR
    store.write(base / "screener" / "RELIANCE.html", SCREENER_HTML.encode())
    store.write(base / "tickertape" / "search-RELIANCE.json", TICKERTAPE_SEARCH.encode())
    store.write(base / "tickertape" / "RELI.json", TICKERTAPE_INFO.encode())
    store.write(base / "moneycontrol" / "RI.json", MONEYCONTROL.encode())
    store.write(base / "exchange" / "RELIANCE.json", NSE_RESULTS.encode())
    return store


# --------------------------------------------------------------------------
# parsing helpers
# --------------------------------------------------------------------------


def test_number_distinguishes_missing_from_zero():
    """The whole missing-data rule rests on this one function."""
    assert fundamentals._number("0") == 0.0
    assert fundamentals._number("-") is None
    assert fundamentals._number("") is None
    assert fundamentals._number(None) is None
    assert fundamentals._number("1,234.5") == 1234.5
    assert fundamentals._number("15%") == 15.0
    assert fundamentals._number("(120)") == -120.0


def test_quarter_end_resolves_month_ends():
    assert fundamentals._quarter_end("Jun 2026") == "2026-06-30"
    assert fundamentals._quarter_end("Dec 2025") == "2025-12-31"
    assert fundamentals._quarter_end("Feb 2024") == "2024-02-29"
    assert fundamentals._quarter_end("nonsense") is None


def test_growth_off_a_negative_base_is_unknown():
    """A loss-making base makes the percentage meaningless, not negative."""
    assert fundamentals._growth(150.0, 100.0) == 50.0
    assert fundamentals._growth(-5.0, -10.0) is None
    assert fundamentals._growth(10.0, 0.0) is None
    assert fundamentals._growth(None, 100.0) is None


# --------------------------------------------------------------------------
# providers
# --------------------------------------------------------------------------


def test_screener_derives_the_quarterly_fields(cache):
    out = fundamentals.provider_screener(cache, "RELIANCE", 86400.0)
    assert out["latest_quarter"] == "Jun 2026"
    assert out["quarter_end"] == "2026-06-30"
    assert out["eps_ttm"] == 55.22
    assert out["revenue_growth_yoy"] == 27.02
    assert out["pat_growth_yoy"] == -24.65
    assert out["opm"] == 15.0
    assert out["net_margin"] == 7.5
    assert out["profitable_4q"] is True
    assert out["roe"] == 8.91
    assert out["roce"] == 10.3


def test_screener_supplies_no_leverage_figure(cache):
    """The ratio strip carries no debt/equity, so none may be invented."""
    out = fundamentals.provider_screener(cache, "RELIANCE", 86400.0)
    assert "debt_equity" not in out


def test_screener_raises_rather_than_half_parsing(cache):
    cache.write(
        cache.root / fundamentals.FUNDAMENTALS_DIR / "screener" / "BROKEN.html",
        b"<html><body>the page changed shape</body></html>",
    )
    with pytest.raises(fundamentals.ProviderError):
        fundamentals.provider_screener(cache, "BROKEN", 86400.0)


def test_tickertape_requires_an_exact_ticker_match(cache):
    """A near-match is a different security, not a fallback."""
    assert fundamentals._tickertape_sid(cache, "RELIANCE", 86400.0) == "RELI"
    cache.write(
        cache.root / fundamentals.FUNDAMENTALS_DIR / "tickertape" / "search-RELI.json",
        json.dumps({"data": {"stocks": [{"ticker": "RELIANCEPP", "sid": "X"}]}}).encode(),
    )
    with pytest.raises(fundamentals.ProviderError):
        fundamentals._tickertape_sid(cache, "RELI", 86400.0)


def test_tickertape_prefers_the_trailing_multiple(cache):
    out = fundamentals.provider_tickertape(cache, "RELIANCE", 86400.0)
    assert out["pe"] == 23.83
    assert out["roe"] == 8.5
    assert out["sector"] == "Oil & Gas - Refining & Marketing"


def test_moneycontrol_rejects_a_mismapped_sc_id(cache, tmp_path, monkeypatch):
    """A wrong sc_id resolves to a real but different company.

    The payload names its own NSE ticker, so the mismatch is detectable
    — and must be detected, or the gate silently reads another
    company's ratios.
    """
    mapping = tmp_path / "moneycontrol-sc-ids.json"
    mapping.write_text(json.dumps({"HINDUNILVR": "HU"}), encoding="utf-8")
    monkeypatch.setattr(fundamentals, "REFERENCES", tmp_path)
    cache.write(
        cache.root / fundamentals.FUNDAMENTALS_DIR / "moneycontrol" / "HU.json",
        json.dumps(
            {"code": "200", "data": {"company": "Unimers India", "NSEID": "UNIMERS"}}
        ).encode(),
    )
    with pytest.raises(fundamentals.ProviderError, match="not HINDUNILVR"):
        fundamentals.provider_moneycontrol(cache, "HINDUNILVR", 86400.0)


def test_moneycontrol_reports_an_unmapped_symbol(cache):
    with pytest.raises(fundamentals.ProviderError, match="not in the sc_id mapping"):
        fundamentals.provider_moneycontrol(cache, "NOTMAPPED", 86400.0)


def test_exchange_reverses_the_feeds_ordering(cache):
    """The feed is newest-first; everything downstream expects oldest-first."""
    out = fundamentals.provider_exchange(cache, "RELIANCE", 86400.0)
    assert out["latest_quarter"] == "Dec 2024"
    assert out["quarter_end"] == "2024-12-31"


def test_exchange_never_reports_its_zero_leverage_field(cache):
    """re_debt_eqt_rat is 0 for companies carrying real debt."""
    out = fundamentals.provider_exchange(cache, "RELIANCE", 86400.0)
    assert "debt_equity" not in out


# --------------------------------------------------------------------------
# merge
# --------------------------------------------------------------------------


def test_merge_is_first_hit_wins_per_field(cache):
    """Per field, not per provider.

    screener answers first and owns the quarterly fields; tickertape
    still contributes the sector, which screener never supplies.
    """
    record = fundamentals.fetch_fundamentals(
        cache, "RELIANCE", ["screener", "tickertape", "moneycontrol"], 86400.0
    )
    assert record["provenance"]["eps_ttm"] == "screener"
    assert record["provenance"]["roe"] == "screener"
    assert record["provenance"]["sector"] == "tickertape"
    assert record["values"]["sector"] == "Oil & Gas - Refining & Marketing"


def test_precedence_order_decides_the_winner(cache):
    """Reversing precedence moves ownership of a contested field."""
    record = fundamentals.fetch_fundamentals(
        cache, "RELIANCE", ["tickertape", "screener"], 86400.0
    )
    assert record["provenance"]["roe"] == "tickertape"
    assert record["values"]["roe"] == 8.5


def test_pe_is_computed_from_the_screened_close(cache):
    """A vendor's multiple is priced off whenever they recomputed it."""
    record = fundamentals.fetch_fundamentals(
        cache, "RELIANCE", ["screener", "tickertape"], 86400.0, close=1313.20
    )
    assert record["values"]["pe"] == 23.78
    assert "computed from close" in record["provenance"]["pe"]


def test_a_failing_provider_is_recorded_not_swallowed(cache):
    record = fundamentals.fetch_fundamentals(
        cache, "NOTMAPPED", ["moneycontrol", "screener"], 86400.0
    )
    assert "moneycontrol" in record["failures"]
    assert "screener" in record["failures"]
    assert all(value is None for value in record["values"].values())


def test_unknown_provider_name_is_reported(cache):
    record = fundamentals.fetch_fundamentals(cache, "RELIANCE", ["nosuch"], 86400.0)
    assert record["failures"]["nosuch"] == "unknown provider"


def test_offline_with_nothing_cached_fails_rather_than_returning_blanks(tmp_path):
    """An empty answer and an uncached one must not look identical."""
    store = bhavcopy.Cache(tmp_path / "empty", offline=True)
    record = fundamentals.fetch_fundamentals(store, "RELIANCE", ["screener"], 86400.0)
    assert "screener" in record["failures"]
    assert "offline and not cached" in record["failures"]["screener"]


# --------------------------------------------------------------------------
# gate
# --------------------------------------------------------------------------


def _record(**values):
    merged = {field: None for field in fundamentals.FIELDS}
    merged.update(values)
    return {
        "symbol": "TESTCO",
        "values": merged,
        "provenance": {},
        "failures": {},
        "known": sorted(
            f for f in fundamentals.GATED_FIELDS if merged.get(f) is not None
        ),
    }


def test_a_clean_name_passes(criteria):
    record = _record(
        pe=20.0, revenue_growth_yoy=15.0, pat_growth_yoy=12.0, opm=18.0,
        profitable_4q=True, roe=22.0, quarter_end="2026-06-30",
    )
    verdict = fundamentals.evaluate(record, criteria, date(2026, 8, 21))
    assert verdict["passed"] is True
    assert verdict["reasons"] == []


def test_an_unknown_field_is_not_evaluated(criteria):
    """Neither passes nor fails — and does not count as a rule cleared."""
    record = _record(
        pe=20.0, revenue_growth_yoy=15.0, pat_growth_yoy=12.0,
        quarter_end="2026-06-30",
    )
    verdict = fundamentals.evaluate(record, criteria, date(2026, 8, 21))
    assert verdict["checked"] == 3
    assert verdict["reasons"] == []


def test_absence_alone_cannot_pass_the_gate(criteria):
    """The open door min_fields_known exists to close.

    A name nobody published data for clears every rule by having none of
    them evaluated. Coverage is what stops it reaching the shortlist.
    """
    record = _record(quarter_end="2026-06-30")
    verdict = fundamentals.evaluate(record, criteria, date(2026, 8, 21))
    assert verdict["reasons"] == []
    assert verdict["gateable"] is False
    assert verdict["passed"] is False


def test_min_fields_known_is_the_boundary(criteria):
    floor = screen.require(criteria, "min_fields_known")
    known = dict(zip(fundamentals.GATED_FIELDS, [20.0] * floor))
    below = _record(**dict(list(known.items())[: floor - 1]))
    at = _record(**known)
    assert fundamentals.evaluate(below, criteria, None)["gateable"] is False
    assert fundamentals.evaluate(at, criteria, None)["gateable"] is True


def test_stale_results_are_their_own_outcome(criteria):
    """Not folded in with a failing ratio — the company failed nothing."""
    record = _record(
        pe=20.0, revenue_growth_yoy=15.0, pat_growth_yoy=12.0, opm=18.0,
        profitable_4q=True, roe=22.0, quarter_end="2024-12-31",
    )
    verdict = fundamentals.evaluate(record, criteria, date(2026, 8, 21))
    assert verdict["passed"] is False
    assert verdict["reasons"] == ["results are stale"]
    assert record["result_age_quarters"] > 6


def test_each_filter_can_reject_on_its_own(criteria):
    base = dict(
        pe=20.0, revenue_growth_yoy=15.0, pat_growth_yoy=12.0, opm=18.0,
        profitable_4q=True, roe=22.0, quarter_end="2026-06-30",
    )
    for field, bad in (
        ("pe", 500.0),
        ("revenue_growth_yoy", -30.0),
        ("pat_growth_yoy", -30.0),
        ("opm", 1.0),
        ("profitable_4q", False),
        ("roe", 1.0),
    ):
        record = _record(**{**base, field: bad})
        verdict = fundamentals.evaluate(record, criteria, date(2026, 8, 21))
        assert verdict["passed"] is False, f"{field} should have rejected"
        assert len(verdict["reasons"]) == 1, f"{field} rejected for the wrong reason"


# --------------------------------------------------------------------------
# run_gate
# --------------------------------------------------------------------------


def _swing(*symbols):
    return {
        "envelope": {
            "as_of_session": "2026-08-21",
            "feed_type": "end-of-day",
            "fetched_at_ist": "2026-08-21 08:00:00 IST",
        },
        "candidates": [
            {"symbol": s, "isin": f"INE000A0100{i}", "close": 1313.20,
             "score": 0.9 - i / 100, "signals": ["breakout"]}
            for i, s in enumerate(symbols)
        ],
    }


def test_gate_splits_candidates_three_ways(cache, criteria):
    """Passed, gated out, and not gateable are distinct outcomes."""
    result = fundamentals.run_gate(cache, _swing("RELIANCE", "NOTMAPPED"), criteria)
    assert result["considered"] == 2
    ungated = [row["symbol"] for row in result["ungated"]]
    assert "NOTMAPPED" in ungated
    assert all(row["symbol"] != "NOTMAPPED" for row in result["candidates"])


def test_gate_respects_final_shortlist_size(cache, criteria):
    result = fundamentals.run_gate(cache, _swing("RELIANCE"), criteria, top=0)
    assert result["candidates"] == []


def test_gate_reports_provider_failures_per_run(cache, criteria):
    result = fundamentals.run_gate(cache, _swing("NOTMAPPED"), criteria)
    assert result["provider_failures"]
    assert result["gated_in"] == 0


def test_criteria_file_carries_every_parameter_the_gate_requires(criteria):
    """The tables are the contract; a removed row is a run-time error."""
    for key in (
        "provider_precedence", "max_pe", "min_pe", "min_revenue_growth_yoy",
        "min_pat_growth_yoy", "min_opm", "require_profitable", "min_roe",
        "max_debt_equity", "max_promoter_pledge_pct", "max_result_age_quarters",
        "min_fields_known", "cache_max_age_days", "final_shortlist_size",
    ):
        assert screen.require(criteria, key) is not None


def test_min_fields_known_stays_within_the_gated_set(criteria):
    """Setting it to 0 would restore the absence-passes-everything door."""
    floor = screen.require(criteria, "min_fields_known")
    assert 1 <= floor <= len(fundamentals.GATED_FIELDS)
