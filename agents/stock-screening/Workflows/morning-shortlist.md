---
name: morning-shortlist
agent: stock-screening
---

# morning-shortlist

The daily run: screen NSE and BSE equities on trend, volume, volatility
and delivery, gate the survivors on business quality, and return
`final_shortlist_size` names — each carrying the setup it is showing,
its fundamental standing, and the provenance of every number.

Composes `swing-trading` and `fundamental-gate`. No human gate mid-run:
the whole output is the thing a human reviews.

## Purpose

A swing shortlist and a quality gate answer different questions, and
running them separately every morning means reconciling two lists by
hand and re-deriving which session each belongs to. This sequences them
once, in the order that makes the second one affordable.

**The order is the design.** Fundamentals are fetched only for names
that already passed the technical screen — a few dozen a day rather than
the eleven hundred names that clear the liquidity floor. Reversed, the
same answer would cost a thousand requests to third-party sites. Any
change to this Workflow that gates before it screens is a mistake, not
an optimisation.

## Preconditions

- Both Skills' preconditions: `Tools/bhavcopy.py`, `Tools/screen.py`,
  `Tools/fundamentals.py`, Python 3.10+, no credentials.
- Network access, or a cache already covering the window and the names.

## The End-of-Day Lag, Stated Once

This is a **morning** run against an **end-of-day** feed, so it screens
**yesterday's close**. That is correct for a swing entry — the decision
is made before the open on the most recent completed session — but it is
never allowed to read as though it were current.

Concretely: a run at 08:00 IST on a Tuesday screens Monday's close. A
run at 08:00 on a Monday screens Friday's. A run after the evening
publication screens that same day. The Workflow states which session it
used, every time, and `References/market-data.md` § Feed Type is the
contract.

## Why The Pool Is Larger Than Ten

The technical screen truncates to `shortlist_size` before returning. If
the gate were handed that truncated list, a name ranked below the cut
could never reach the final ten no matter how good its fundamentals
were — and nothing in the output would say it had been dropped, because
it was cut before the gate ever saw it.

That matters because the gate is severe. On the measured 2026-08-21
session it passed 9 of 25 offered, rejected 11 and could not judge 5. A
pool of ten would have returned three or four names, and would have
looked like a market with few opportunities rather than a pipeline
throwing away most of its input before the second stage.

So step 3 passes `--top {gate_pool_size}` and the pool is sized to the
technical screen's whole passing set. The extra cost is bounded — the
gate caches per quarter, so a larger pool is more fetches on the first
run of a quarter and none afterwards.

## Procedure

**1. Fix the as-of session.** Take the most recent published session,
which before the evening publication is the previous trading day. If the
user named a session, use that one. Never silently screen a different
session from the one asked for, and say in the output which was used.

**2. Warm the cache.**

```bash
python Tools/bhavcopy.py history --end {as_of} --sessions {lookback_sessions}
```

A past session is immutable, so this is a one-time cost per window. The
first run over a fresh window takes a few minutes; later runs are
served from disk. Non-trading days are discovered, not looked up.

**3. Run the technical screen** — `Skills/swing-trading.md`, whose
procedure applies in full. Keep the JSON:

```bash
python Tools/screen.py --json swing --as-of {as_of} --top {gate_pool_size} \
  > /tmp/swing.json
```

`--top` is not optional here, and § Why The Pool Is Larger Than Ten
explains why.

**4. Check the screen before gating.** Sessions loaded, as-of session,
and pass count, exactly as `swing-trading` step 5 requires. A short
window makes every moving average wrong, and gating a wrong list
produces a confident wrong answer more slowly. A pass count of zero ends
the run here: report "nothing met the technical criteria on this date"
with the rejection breakdown, and do not fetch fundamentals for an empty
list.

**5. Gate the survivors** — `Skills/fundamental-gate.md`, whose
procedure applies in full:

```bash
python Tools/fundamentals.py gate --json-in /tmp/swing.json
```

**6. Read the provider failures first.** If a provider failed for every
name, the gate was decided by whatever remained. That is a legitimate
run — the exchange floor exists for exactly this — but it changes what
the list means and must be said rather than discovered.

**7. Report the ten with everything they need to be checked.** Ordering
is the technical composite's, untouched: the gate decides who is on the
list, never the order.

The report carries, and none of these is optional:

- The as-of session and the end-of-day lag.
- Both sets of criteria, technical and fundamental.
- Each name's signals and its fundamentals, with per-field provenance.
- The **not-gateable** names, with what was known about them. They are
  neither passes nor failures and are reported separately.
- Which providers failed, and for how many names.
- The **sector spread** of the ten.

**8. Read the sector spread before treating the list as a list.** Ten
names in one sector is one bet expressed ten ways, and the position
sizing that would be prudent for ten independent ideas is reckless for
that. The screen has no correlation awareness at all, so this line is
the only thing standing between the reader and that mistake.

**9. Sanity-check the top of the list.** Prices are unadjusted for
corporate actions: a split, bonus or large dividend inside the window
fabricates a trend and distorts every average crossing it. A name whose
numbers look impossible deserves a check against the corporate actions
record before it is passed on.

## Outputs

A ranked table of at most `final_shortlist_size` names:

| Column | Meaning |
|---|---|
| `SYMBOL` `CLOSE` | Ticker and the as-of session's close, in rupees |
| `SIGNALS` | `breakout`, `cross`, `pullback`, `extended`, or `-` |
| `P/E` | Close over trailing-twelve EPS |
| `REV%` `PAT%` | Year-on-year quarterly growth |
| `OPM%` `ROE%` | Latest margin and return on equity |
| `QUARTER` | The quarter the fundamentals describe |

Then the not-gateable names, the gated-out names with their reasons, the
sector spread, and any provider failures.

A dash is **unknown**, never zero. It means no provider published that
figure, which is a different statement from the figure being bad.

## State Transitions

None. This Workflow reads public data and writes nothing outside the
cache. It opens no issue, moves no label, and places no order. Re-running
it is always safe, and re-running it against the same session with a warm
cache produces the same list.

## Errors

Both Skills' error tables apply unchanged. Three failures specific to
running them in sequence:

| Symptom | Cause | Response |
|---|---|---|
| Fewer than `final_shortlist_size` names | The gate rejected more than expected, or providers failed | A short list is a result. Report the count and the reasons; never loosen a threshold to fill the table |
| Zero names after the gate, many before | A fundamental threshold, not the market | Check the gated-out reasons before touching anything else |
| Every name not gateable | A provider is down | Read the failure list. This is not a market event |
| The list is one sector | The screen has no correlation awareness | Say so plainly. It is not a defect in the run, it is what the run cannot see |

## Boundaries

- **Candidates, not recommendations.** This produces a list to review.
  It does not size a position, time an entry, set a stop, or place an
  order.
- **Yesterday's close.** Everything here is end-of-day. There is no
  quote, no order book, and no live price in this path.
- **Gate then rank, never blend.** The fundamental verdict decides
  membership; the technical composite decides order. Blending them would
  let a cheap multiple compensate for a broken setup, and `SCORE` would
  stop meaning what it means in `swing-trading`.
- **No corporate-action adjustment, and no sector or correlation
  awareness** beyond the spread line. Both limits carry forward from
  `References/swing-criteria.md` § Known Limits and should be repeated
  when the list is handed on.
