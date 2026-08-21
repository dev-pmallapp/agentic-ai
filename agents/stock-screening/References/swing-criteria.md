# Swing Criteria

The screening criteria for a multi-day to multi-week holding horizon,
used by `Skills/swing-trading.md`. Universe eligibility is decided first
by `References/universe-and-exclusions.md`; everything here applies to
what survives that.

Every threshold below is in the parameter table at the end and is read
by `Tools/screen.py`. Change a number there and the next run uses it.
The prose explains why each filter exists — it is not a second copy of
the values, and it does not need editing when a threshold moves.

## What This Screen Is Looking For

A stock already trending up, with liquidity deep enough to enter and
exit at size, moving enough for a multi-day hold to be worth the risk
but not so much that the move is noise, and with real delivery-based
buying behind the volume rather than intraday churn.

All four conditions are required. A name that trends beautifully on
volume nobody could trade is not a candidate.

## Trend

Direction and structure over the holding horizon.

**Moving-average stack.** Close above the short average, and the short
average above the long one. The second half matters more than the
first: price above a falling average is a bounce in a downtrend, and
the stack requirement excludes it.

**Proximity to the recent high.** Within `max_pct_below_high` of the
highest close in the lookback window. A stock 30% off its high is in a
recovery, which is a different trade with different risk than a
continuation.

The window is deliberately shorter than a year. A 52-week structure
says little about the next three weeks.

## Volume

Two separate jobs, often conflated.

**Liquidity** is a floor: `min_median_turnover` of median daily
turnover. This raises the baseline floor in
`References/universe-and-exclusions.md`, because a swing position needs
more depth than mere tradability.

**Confirmation** is a ratio: recent average volume against the longer
baseline, at least `min_volume_ratio`. A trend on declining volume is
weakening even while price still rises. This is the filter that catches
that, and it is why volume is not simply a floor.

## Volatility

A band, not a floor. `min_atr_pct` to `max_atr_pct`, measured as
average true range over `atr_window` sessions, expressed as a
percentage of price.

Below the floor, the horizon does not matter — the stock will not move
far enough in three weeks to pay for the risk taken. Above the ceiling,
the daily range swamps the signal and any stop placement is arbitrary.

True range is used rather than the high-low range, so that gaps count.
A stock that gaps 4% and then trades in a 1% range had a 4% day, and
pretending otherwise understates the risk.

## Delivery

Minimum `min_delivery_pct` of traded volume settling as delivery,
averaged over `delivery_window` sessions.

This is the criterion with no equivalent in most markets. Volume alone
cannot distinguish accumulation from a day of two-sided intraday churn
that nets to nothing. Delivery percentage separates them directly: it
is the fraction of volume that someone actually took ownership of.

On a measured session the EQ-series median was roughly 57%, with a
quarter of names below 46%. A floor in the mid-40s is therefore
selective without being exotic.

**Delivery data is NSE-only.** A name whose primary venue was BSE for a
session has no delivery figure for it. Treat a missing value as
*unknown*, never as zero:

- If more than half the window is missing, the name is **not rankable**
  on delivery. Exclude it and report it as excluded for missing data,
  not as failing the threshold.
- Otherwise average what exists and mark the value as partial in the
  output.

Reporting a BSE-primary stock as "delivery 0%" would be a fabrication,
and it would systematically exclude exactly the names the reconciliation
rule assigned to BSE.

## Ranking

A composite score, not a lexicographic sort — a name that is excellent
on three criteria and merely adequate on the fourth should outrank one
that barely clears all four.

Each passing name is scored on four normalised components, weighted:

| Component | Weight | Normalised as |
|---|---|---|
| Trend strength | `weight_trend` | Percent above the long moving average |
| Volume confirmation | `weight_volume` | Recent-to-baseline volume ratio |
| Volatility fit | `weight_volatility` | Closeness to the middle of the ATR band |
| Delivery quality | `weight_delivery` | Average delivery percentage |

Components are scaled to a common range across the passing set before
weighting, so no single component dominates on units alone. Volatility
scores highest in the *middle* of the band rather than at the top — the
band's ceiling exists because more is worse, and a score that rewarded
maximum volatility would fight its own filter.

Ties break on turnover, higher first.

The score orders a shortlist. It is not a prediction, a probability, or
a position size, and it is not comparable across runs with different
thresholds.

## Parameters

| Parameter | Value | Meaning |
|---|---|---|
| `lookback_sessions` | 60 | Sessions of history the screen loads |
| `sma_short` | 20 | Short moving average, sessions |
| `sma_long` | 50 | Long moving average, sessions |
| `high_window` | 60 | Lookback for the recent-high test, sessions |
| `max_pct_below_high` | 10.0 | Maximum percent below the window high |
| `min_median_turnover` | 100000000 | Median daily turnover floor in rupees — ₹10 crore |
| `turnover_window` | 20 | Sessions for the median turnover |
| `min_volume_ratio` | 1.1 | Recent average volume over baseline average volume |
| `volume_recent_window` | 10 | Recent volume window, sessions |
| `volume_base_window` | 50 | Baseline volume window, sessions |
| `atr_window` | 14 | Sessions for average true range |
| `min_atr_pct` | 2.0 | Lower volatility bound, percent of price |
| `max_atr_pct` | 8.0 | Upper volatility bound, percent of price |
| `min_delivery_pct` | 45.0 | Minimum average delivery percentage |
| `delivery_window` | 20 | Sessions averaged for delivery |
| `weight_trend` | 0.35 | Composite weight |
| `weight_volume` | 0.20 | Composite weight |
| `weight_volatility` | 0.20 | Composite weight |
| `weight_delivery` | 0.25 | Composite weight |
| `shortlist_size` | 25 | Names returned |

`lookback_sessions` must be at least `sma_long`, `high_window`,
`volume_base_window`, and `min_sessions` from
`References/universe-and-exclusions.md`. Raising the long average
without raising the lookback silently produces a shorter history than
the average needs.

## Known Limits

- **No fundamentals.** Nothing here reads earnings, valuation, debt, or
  ownership. This is a price-volume-delivery screen and nothing more.
- **No corporate-action adjustment.** A split, bonus, or large dividend
  inside the lookback distorts every moving average and range that
  crosses it. The bhavcopy feed carries unadjusted prices, so an
  affected name can appear with a fabricated trend or an absurd ATR.
  This is a real, unfixed gap: a name whose price series contains a
  single-session move far outside its own volatility band should be
  treated as suspect and verified before it is acted on.
- **No sector or correlation awareness.** A shortlist may be twenty
  names expressing one bet. Read the sector spread before treating the
  list as diversified.
- **Survivorship in the window.** A name delisted mid-window simply
  stops appearing, and is excluded for insufficient history rather than
  reported as delisted.
