---
name: stock-screening
description: Screen Indian equities (NSE and BSE) down to a ranked, reproducible shortlist against explicit technical and fundamental criteria. USE WHEN screening Indian stocks, building a watchlist, running a daily pre-open shortlist, or checking named stocks on valuation, growth and margins. NOT FOR order execution, position sizing, portfolio accounting, or investment advice.
skills:
  - swing-trading
  - day-trading-shortlist
  - fundamental-gate
workflows:
  - morning-shortlist
---

# stock-screening

Narrow the listed universe of NSE and BSE equities down to a short,
ranked list of candidates that satisfy an explicit set of criteria — and
report the criteria and the data's freshness alongside the list, so a
name on it can always be traced back to why it qualified.

Screening produces *candidates*, not decisions. Every screen here ends
at a shortlist a human reviews.

## Scope — Indian Equities

This agent is specific to Indian markets, in its data sources and in its
criteria. It knows about NSE series codes and BSE group letters,
circuit limits, trade-to-trade and SME segments, rupees, IST sessions,
and delivery percentage — none of which generalise. A screen for another
market would be a different agent, not a flag on this one.

Data comes from public end-of-day bhavcopy files published by the two
exchanges. There is **no API key and no account**: nothing secret is
read from the environment and nothing secret can be committed, because
no credential exists. The full contract is in `References/market-data.md`.

## Routing

Each Skill runs end to end on its own and produces its result without
anything else having run first. The Workflow is cumulative: it sequences
two of them and owns the ordering between them.

| Kind | Name | Trigger | File |
|---|---|---|---|
| Skill | **swing-trading** | Multi-day to multi-week holding horizon; trend, volume, volatility and delivery criteria | `Skills/swing-trading.md` |
| Skill | **day-trading-shortlist** | A single named trading session; gap, relative-volume and catalyst criteria | `Skills/day-trading-shortlist.md` |
| Skill | **fundamental-gate** | A set of named stocks to test on business quality — valuation, growth, margins, returns | `Skills/fundamental-gate.md` |
| Workflow | **morning-shortlist** | The daily pre-open run: screen, gate the survivors, return ten | `Workflows/morning-shortlist.md` |

`morning-shortlist` composes `swing-trading` and `fundamental-gate`
rather than reimplementing either, and the order is the point:
fundamentals are fetched only for names the technical screen already
passed, which is what keeps a per-company data source affordable.
Neither Skill depends on the Workflow, so a stalled run can be resumed
a step at a time.

## References

Loaded on demand; the criteria files are read at run time by
`Tools/screen.py`, so their parameter tables are the live configuration
rather than documentation of it.

| Reference | Holds |
|---|---|
| `References/market-data.md` | The NSE/BSE data contract — endpoints, the mandatory request header, caching, dual-listing reconciliation, delivery enrichment, failure modes |
| `References/universe-and-exclusions.md` | Which securities are eligible at all: series and group keep-lists, price and liquidity floors, circuit-locked detection |
| `References/swing-criteria.md` | Trend, volume, volatility and delivery thresholds, and the composite ranking |
| `References/day-criteria.md` | Gap, relative-volume and range thresholds, the material-catalyst category list, and the composite ranking |
| `References/fundamental-criteria.md` | The quality gate — provider precedence, valuation, growth, margin and return thresholds, and the missing-data rule |
| `References/moneycontrol-sc-ids.json` | Ticker to moneycontrol id, maintained by hand because no public endpoint derives one |

Change a threshold by editing the parameter table in the relevant
Reference. The next run uses it. There is no separate config file, and
no code change is needed — which is the point: the criteria a run
applied are the criteria a human can read.

## Why This Agent Has Tools

`Tools/` here is filled, where `dev-lifecycle`'s is deliberately empty.
That agent's bar was that a Tool must express something plain shell
cannot, and a wrapper around `gh` did not clear it. This does:

- A sixty-session window is roughly half a million rows across two
  exchanges and three file formats, one of which pads every field with a
  leading space. Parsing that is not a shell one-liner.
- Moving averages, true range, median turnover and delivery windows are
  arithmetic over that history, per name.
- The dual-listing rule requires choosing one venue per ISIN across the
  whole window by total turnover — a join, not a filter.

The alternative was asking a model to do the arithmetic over half a
million rows in context, which would be slower, unreproducible, and
wrong in ways nobody could audit. Three scripts, standard library only:
`Tools/bhavcopy.py` fetches, caches and normalises; `Tools/screen.py`
applies the criteria and ranks; `Tools/fundamentals.py` merges company
fundamentals across four providers and applies the quality gate.

`fundamentals.py` clears the same bar for its own reasons: four sources
disagree about which fields they publish, so merging them is a
first-hit-wins resolution per field with provenance attached, and the
trailing-twelve arithmetic behind a P/E spans four quarterly filings.

## Boundaries

- Output is a candidate list with stated criteria, never a
  recommendation to buy or sell.
- Fundamentals gate, they never rank. Membership of a shortlist is
  decided by the quality gate; the order is the technical composite's.
  Blending the two would let a cheap multiple compensate for a broken
  setup.
- Fundamental sources are **weaker than the price feed** and are treated
  as such. Three of the four are commercial sites whose unversioned
  pages can change without notice; the exchange's own filings are kept
  as the credential-free floor beneath them. A missing fundamental is
  unknown — never zero, and never a pass.
- Data freshness is reported, never assumed. A screen run against
  stale data is labeled as such rather than presented as current.
- Criteria are stated explicitly in the output. A shortlist whose
  filters are unstated cannot be checked or reproduced.
- The feed is **end-of-day only**. There is no live, intraday, or
  pre-market path here, and `day-trading-shortlist` screens a completed
  session for a named date rather than the session in progress.
- Prices are unadjusted for corporate actions. A split, bonus or large
  dividend inside a window distorts the numbers that cross it.
