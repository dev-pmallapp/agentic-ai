# Day Criteria

The screening criteria for a single named trading session, used by
`Skills/day-trading-shortlist.md`. Universe eligibility is decided first
by `References/universe-and-exclusions.md`; everything here applies to
what survives that.

Every threshold below is in the parameter table at the end and is read
by `Tools/screen.py`.

## Read This First — The Screen Is Retrospective

The feed is end-of-day (`References/market-data.md` § Feed Type). This
screen therefore runs **on a completed session for a named date**. It
reads the open, high, low, close and volume of a day that has already
finished.

It is not a live screen, it does not run during market hours, and it
cannot tell anyone what to trade today. What it produces is a
reproducible answer to "which names showed a gap, unusual volume, and a
catalyst on that date" — useful for studying the criteria, checking a
day after the fact, and building a prior. Any output that lets a reader
believe otherwise is a defect.

## What This Screen Is Looking For

A stock that opened away from its previous close, traded far more than
it usually does, and had something published about it that day. The
three together are what distinguishes a real event from a thin stock
wobbling.

Gap and relative volume are required. A catalyst is scored, not
required, because the filings feed is incomplete and its absence is
weaker evidence than its presence.

## Gap

`gap_pct = (open - previous close) / previous close × 100`

Both fields are on the same UDiFF row — `OpnPric` and `PrvsClsgPric` —
so no cross-session join is needed and no adjustment is applied.

The threshold is on the **absolute** value: `min_abs_gap_pct`. A gap
down is as much an event as a gap up, and a screen that only looked up
would be a directional view smuggled in as a filter. Direction is
recorded and reported per name; it is not filtered on.

For scale: on a measured session the median absolute gap across EQ names
was about 0.6%, the 90th percentile 2.3%, and the 95th 3.0%. A 3%
threshold selected 133 names out of 2630 before any other filter. A
threshold much below that stops selecting events and starts selecting
the whole market.

## Relative Volume

Session volume against the median volume of the preceding
`relvol_window` sessions, at least `min_relative_volume`.

Median, not mean — one prior spike in the window would drag a mean
upward and hide the very behaviour being looked for.

The window is the sessions **before** the named date, never including
it. Including the session in its own baseline damps exactly the signal
being measured, and does so most for the largest spikes.

A name with no usable volume history in the window is not rankable and
is excluded for insufficient history, not scored as zero.

## Range

`range_pct = (high - low) / previous close × 100`, at least
`min_range_pct`.

A gap with no subsequent range is a stock that opened away and then did
not trade — common in thin names, and untradeable regardless of how
large the gap looks. This filter is what stops the shortlist filling
with names that gapped 6% on four hundred shares.

Circuit-locked sessions are already removed by
`References/universe-and-exclusions.md`; this catches the near-locked
cases that fall just short of it.

## Catalyst

Corporate filings published on the named date, from the NSE
announcements endpoint in `References/market-data.md`. Filings join to
the screen by NSE symbol.

A filing counts only if its `desc` category is material. NSE publishes
roughly 50 distinct categories on a normal day and most are
administrative — on one measured session, 602 filings across 426
symbols, of which the four largest categories were investor-meeting
updates, shareholder meetings, general updates, and newspaper
publication copies. Counting those would mark almost everything as
having a catalyst and the field would carry no information.

**Material categories** — an event that changes what the company is
worth or what is known about it:

`Outcome of Board Meeting`, `Financial Results`,
`Clarification - Financial Results`, `Acquisition`,
`Bagging/Receiving of orders/contracts`, `Credit Rating`,
`Credit Rating- New`, `Scheme of Arrangement`,
`Qualified Institutional Placement`, `Rights Issue`,
`Public Announcement-Open Offer`,
`Disclosure under SEBI Takeover Regulations`,
`Corporate Insolvency Resolution Process`, `Capacity addition`,
`Commencement of commercial production/operations`,
`Diversification/Disinvestment`, `Sale or disposal`,
`Disruption of Operations`, `Strikes/Lockouts/Disturbances`,
`Action(s) taken or orders passed`,
`Pendency of Litigation(s)/dispute(s) or the outcome impacting the Company`,
`Change in Auditors`, `Agreements`, `Disclosure of material issue`,
`Press Release`

**Exchange-query categories** — `Spurt in Volume` and `Price movement`
are the exchange asking the company to explain unusual activity. They
are reactive rather than causal, but they are a direct statement that
the exchange itself flagged the session, so they count as material and
are labelled distinctly in the output.

Everything else is noise for this purpose: newspaper copies, general
updates, investor presentations, trading-window notices, record dates,
share-certificate losses, ESOP allotments, corrigenda, and routine
appointments, resignations and directorate changes.

Governance categories are the closest call. A resignation can be the
most important thing that happens to a company all year, and the
category alone cannot tell that case from a routine retirement. They
are excluded because the common case dominates, and the full filing
list for any shortlisted name is one lookup away.

When the announcements endpoint is unavailable, run without it and
label the catalyst field **unavailable** for every name. Do not label it
absent — the two mean different things and only one of them is true.

## Ranking

A composite score over the passing set:

| Component | Weight | Normalised as |
|---|---|---|
| Gap magnitude | `weight_gap` | Absolute gap percent |
| Relative volume | `weight_relvol` | Session volume over median baseline |
| Range | `weight_range` | Range as percent of previous close |
| Catalyst | `weight_catalyst` | 1 if a material filing exists, else 0 |

Components are scaled across the passing set before weighting. Ties
break on turnover, higher first.

When the catalyst feed is unavailable its weight is redistributed
proportionally across the other three, and the output states that the
ranking was computed without it. Scoring every name zero on a missing
component would leave the ranking unchanged but the scores misleading.

## The Outcome Column Is Not A Criterion

Because the session is complete, the screen can see what happened after
the open — whether the gap held or filled by the close. That is
reported, as an observed fact, in a column marked as such.

It is deliberately **excluded from the score and from every filter.**
Ranking on it would be look-ahead: it would produce a beautiful
shortlist that could not have been constructed on the morning of that
date, and anyone reading the criteria as a template would inherit the
bias without seeing it. It is present to make the criteria checkable
against reality, and for no other purpose.

## Parameters

| Parameter | Value | Meaning |
|---|---|---|
| `lookback_sessions` | 30 | Sessions of history loaded, ending the session before the named date |
| `min_abs_gap_pct` | 3.0 | Minimum absolute gap, percent |
| `min_relative_volume` | 2.0 | Session volume over median baseline volume |
| `relvol_window` | 20 | Sessions in the volume baseline, excluding the named date |
| `min_range_pct` | 2.0 | Minimum session range as percent of previous close |
| `min_median_turnover` | 50000000 | Median daily turnover floor in rupees — ₹5 crore |
| `turnover_window` | 20 | Sessions for the median turnover |
| `weight_gap` | 0.35 | Composite weight |
| `weight_relvol` | 0.30 | Composite weight |
| `weight_range` | 0.15 | Composite weight |
| `weight_catalyst` | 0.20 | Composite weight |
| `shortlist_size` | 25 | Names returned |

The liquidity floor is lower than the swing screen's because a single
session needs less depth than a multi-week position, and because the
gap and range filters already remove most thin names on their own.

## Known Limits

- **No intraday data at all.** There is no opening range, no VWAP, no
  time-of-day volume profile, and no pre-market activity. Relative
  volume is a whole-session figure, so it is only knowable after the
  close — which is the core reason this screen is retrospective.
- **No corporate-action adjustment.** An ex-dividend, split or bonus
  date produces a large mechanical gap that is not an event. Such names
  can and do appear. A gap that is suspiciously close to a round
  fraction of the price deserves a check against the corporate-actions
  record before it is believed.
- **The filings feed is best-effort.** It is a website's internal JSON
  API, not a published contract, and a filing can be published late or
  under an unexpected category. Absence of a catalyst is weak evidence.
- **No news beyond exchange filings.** Sector moves, index rebalances,
  global cues, and press coverage that never became a filing are all
  invisible here.
