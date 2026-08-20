---
name: stock-screening
description: Identify candidate securities matching a set of screening criteria. USE WHEN screening stocks, building a watchlist, or shortlisting trade candidates for a horizon. NOT FOR order execution, position sizing, portfolio accounting, or investment advice.
skills:
  - swing-trading
  - day-trading-shortlist
---

# stock-screening

Narrow a universe of securities down to a short, ranked list of
candidates that satisfy an explicit set of criteria — and report the
criteria and the data's freshness alongside the list, so a name on it
can always be traced back to why it qualified.

Screening produces *candidates*, not decisions. Every screen here
ends at a shortlist a human reviews.

## Routing

Both screens are **Skills**: each runs end to end on its own and
produces a shortlist without anything else having run first. Neither
sequences the other, so neither is a Workflow.

| Kind | Name | Trigger | File |
|---|---|---|---|
| Skill | **swing-trading** | Multi-day to multi-week holding horizon; trend, volume, and volatility criteria | `Skills/swing-trading.md` |
| Skill | **day-trading-shortlist** | Same-day intraday candidates; gap, relative volume, and catalyst criteria | `Skills/day-trading-shortlist.md` |

`Workflows/` is empty by design. A cumulative run — screening both
horizons and reconciling the two shortlists, say — would belong there
and would compose these Skills rather than reimplement them. None
exists yet, so none is claimed.

## Boundaries

- Output is a candidate list with stated criteria, never a
  recommendation to buy or sell.
- Data freshness is reported, never assumed. A screen run against
  stale data is labeled as such rather than presented as current.
- Criteria are stated explicitly in the output. A shortlist whose
  filters are unstated cannot be checked or reproduced.

## Status

**Skeleton.** This agent is a structural placeholder from the initial
scaffold. Nothing here is wired up yet:

- No market-data source is configured — no API, no MCP server, no
  local dataset.
- No screening logic is implemented. Both Skill files are TODO
  outlines, not procedures.
- `References/` and `Tools/` are empty placeholders for the
  criteria definitions and data-access helpers a real implementation
  will need.

Do not run this agent expecting results. See each Skill's `## TODO`
section for what a real implementation requires.
