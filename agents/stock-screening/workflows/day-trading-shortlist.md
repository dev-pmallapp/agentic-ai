---
name: day-trading-shortlist
agent: stock-screening
status: skeleton
---

# day-trading-shortlist

## Ideal State

A ranked shortlist of intraday trade candidates for a given trading
day, each with the same-day signal that put it on the list, and an
explicit note on how fresh the underlying data is — because for an
intraday screen, a stale list is worse than no list.

## TODO

A real implementation of this workflow needs:

- **A live or delayed intraday data source.** Quote and volume data at
  intraday granularity, with the feed's delay known and reported. The
  acceptable delay is a real design constraint here, not a detail —
  a 15-minute-delayed feed supports a different workflow than a live
  one, and the workflow should state which it assumes.
- **Same-day screening criteria**, defined concretely:
  - *Gap %* — overnight gap relative to the prior close, with a
    threshold and a direction convention.
  - *Relative volume* — current volume against the same-time-of-day
    average, which requires an intraday volume baseline.
  - *Catalyst / news* — presence of a same-day driver (earnings,
    filing, headline), and a source for it.
  - Universe and exclusions (price floor, liquidity floor, halted
    names, illiquid tickers).
- **A ranked shortlist output format** with a timestamp and freshness
  note — as-of time, feed delay, and the trading-day session state
  (pre-market, regular hours, after hours) at the moment of the run.

Deliberately not specified yet: how a catalyst is sourced and scored.
That likely needs a second data source and possibly its own reference
file under `../references/`.
