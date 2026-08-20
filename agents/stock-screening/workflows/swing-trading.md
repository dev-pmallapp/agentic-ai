---
name: swing-trading
agent: stock-screening
status: skeleton
---

# swing-trading

## Ideal State

A ranked shortlist of securities that meet stated multi-day trend,
volume, and volatility criteria, each traceable to the filter that
selected it, with the data's as-of timestamp reported alongside.

## TODO

A real implementation of this workflow needs:

- **A market-data source.** An API, MCP server, or local dataset
  providing daily OHLCV history deep enough for the trend and
  volatility windows below. Not yet chosen — the choice drives
  everything else here.
- **A screening criteria set** for a multi-day to multi-week holding
  period, defined concretely enough to be reproducible:
  - *Trend* — direction and strength over the holding horizon
    (moving-average relationships, higher-highs structure, or similar).
  - *Volume* — liquidity floor, plus volume behavior confirming the
    trend rather than contradicting it.
  - *Volatility bands* — a usable range: enough movement for the
    horizon to matter, not so much that the setup is noise.
  - Universe definition and exclusions (exchange, market cap, price
    floor, illiquid or halted names).
- **An output shortlist format** — ranked, with the qualifying values
  per name shown next to the criteria they satisfied.
- **Freshness and timestamp reporting** — the data's as-of time and
  whether it is live, delayed, or end-of-day, stated in the output
  rather than inferred by the reader.

Deliberately not specified yet: ranking weights, and whether ranking is
a composite score or a lexicographic sort. That decision belongs with
the criteria set, once a data source is chosen.
