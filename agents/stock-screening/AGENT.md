---
name: stock-screening
description: Identify candidate securities matching a set of screening criteria. USE WHEN screening stocks, building a watchlist, or shortlisting trade candidates for a horizon. NOT FOR order execution, position sizing, portfolio accounting, or investment advice.
workflows:
  - swing-trading
  - day-trading-shortlist
---

# stock-screening

Narrow a universe of securities down to a short, ranked list of
candidates that satisfy an explicit set of criteria — and report the
criteria and the data's freshness alongside the list, so a name on it
can always be traced back to why it qualified.

Screening produces *candidates*, not decisions. Every workflow here
ends at a shortlist a human reviews.

## Workflow Routing

| Workflow | Trigger | File |
|---|---|---|
| **swing-trading** | Multi-day to multi-week holding horizon; trend, volume, and volatility criteria | `workflows/swing-trading.md` |
| **day-trading-shortlist** | Same-day intraday candidates; gap, relative volume, and catalyst criteria | `workflows/day-trading-shortlist.md` |

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
- No screening logic is implemented. Both workflow files are TODO
  outlines, not procedures.
- `references/` and `tools/` are empty placeholders for the
  criteria definitions and data-access helpers a real implementation
  will need.

Do not run this agent expecting results. See each workflow's `## TODO`
section for what a real implementation requires.
