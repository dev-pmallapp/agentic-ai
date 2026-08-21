# Fundamental Criteria

The quality gate applied to names that have already passed a technical
screen, used by `Skills/fundamental-gate.md` and by
`Workflows/morning-shortlist.md`. Universe eligibility is decided first
by `References/universe-and-exclusions.md`; the technical filters by
`References/swing-criteria.md`; everything here applies to what survives
both.

Every threshold below is in the parameter table at the end and is read by
`Tools/fundamentals.py`. Change a number there and the next run uses it.
The prose explains why each filter exists — it is not a second copy of
the values.

## What This Gate Is For

The swing screen answers "is this stock moving the way an entry wants?".
It cannot answer "is the business behind it worth three weeks of
exposure?", because nothing in a bhavcopy file describes a business. A
stock can trend beautifully on expanding volume with excellent delivery
while its revenue shrinks and its margins collapse.

This gate is **pass/fail, never a ranking**. Names that clear it are
ordered by the technical composite exactly as `Tools/screen.py` ranked
them. That split is deliberate: a blended score would let a cheap
multiple compensate for a broken setup, and the resulting number would
mean neither one thing nor the other. It also keeps `SCORE` comparable
to the swing screen's own output.

## Why Fundamentals Are Fetched Last

The gate runs **after** the technical screen, so it only ever sees the
few dozen names that passed. That ordering is not an optimisation, it is
what makes the third-party sources usable at all: a few dozen cached
requests a day is a reasonable thing to do to someone's website, and
eleven hundred is not.

It also means the cost of the gate does not grow with the universe. A
looser liquidity floor makes the technical screen slower and leaves the
fundamental stage almost unchanged.

## Providers

Four sources, resolved **first hit wins per field** in the order given by
`provider_precedence`. Per field, not per provider: a source that knows
return-on-equity but publishes no growth figures contributes the ROE
without displacing a better source's growth.

| Provider | Addressed by | Supplies |
|---|---|---|
| `screener` | NSE symbol, directly | Quarterly sales, operating margin, net profit and EPS; ROE and ROCE |
| `tickertape` | Ticker → internal `sid` lookup | Trailing-twelve P/E, ROE, sector |
| `moneycontrol` | Ticker → `sc_id` from a local mapping | Consolidated P/E, sector |
| `exchange` | NSE symbol, from the exchange's own filings | Quarterly sales, net profit, EPS, derived operating margin |

**Every value records which provider produced it.** A number in the
output can always be traced to its source, and the `show` subcommand
prints the mapping directly. This is the same requirement the screens
already meet for criteria: a figure whose origin is unstated cannot be
checked.

### Provider Precedence

The default order is `screener, tickertape, moneycontrol, exchange`, and
the exchange being **last** is a measured decision rather than a
preference.

The exchange feed is the only source published by the exchange itself,
so it is the only one that cannot be withdrawn, rate-limited or reshaped
by a vendor. That argues for it being primary. Against it is a fact
observed on 2026-08-21: across every symbol tested — RELIANCE, TCS,
INFY, HDFCBANK, SUNPHARMA — the freshest quarter the
`results-comparision` feed returned ended **31-Dec-2024**, while the
price feed was current to that day. screener.in carried quarters through
**Jun 2026** for the same companies.

Gating a shortlist on results six quarters old would not be
conservative, it would be wrong: it would judge a company on a business
that no longer exists and would trip `max_result_age_quarters` for the
entire universe.

So the exchange provider is kept as the **floor** rather than the
primary. When every commercial source fails, the run still produces a
gated list from exchange filings alone — and `max_result_age_quarters`
then marks those names stale, which is the honest outcome rather than a
silent one. Flipping the order is a one-line edit to the parameter table
if the feed catches up.

Two fields are deliberately **not** read from the exchange feed:

- `re_debt_eqt_rat` returns `0` for companies carrying real debt. A zero
  that means "not reported" is exactly the fabrication the missing-data
  rule below exists to prevent.
- Bank filings use a different schema entirely (`bankNonBnking: Y`), and
  the EPS field non-banks use comes back empty. Banks are therefore
  gated on whatever the commercial providers supply, or reported as not
  gateable.

### Known Provider Limits

- **`moneycontrol` needs a mapping file.** It addresses companies by its
  own `sc_id` ("RI" for Reliance), and no working public endpoint
  derives one from a ticker — the documented autosuggest routes return
  404. `References/moneycontrol-sc-ids.json` holds the mapping, and a
  symbol absent from it is reported as unresolved. Stated plainly rather
  than papered over with a guessed endpoint.
- **The three commercial sources are unversioned.** They are HTML and
  internal JSON belonging to products that owe this agent nothing. They
  will change shape without notice. Each provider raises rather than
  returning half-parsed values, and the run reports which providers
  failed and for how many names.
- **Terms of use are the operator's call.** robots.txt permits the paths
  used here on screener.in (`/company/*`) and tickertape.in
  (`/stocks/*`); moneycontrol.com's could not be retrieved and is
  unverified. This is a few dozen cached requests a day for personal
  screening, not bulk extraction, but the distinction is one the person
  running it owns.

## The Filters

**Valuation.** P/E within `min_pe` to `max_pe`. The ceiling is the real
filter; the floor exists because a very low multiple on a trending stock
is more often a broken denominator — a one-off gain inflating trailing
earnings — than a bargain.

P/E is **computed** as the screened session's close over trailing-twelve
EPS whenever both are available, rather than taken from a provider. A
vendor's multiple is priced off whenever they last recomputed it, and
the whole point of the envelope is that every number belongs to a stated
session.

**Growth.** `min_revenue_growth_yoy` and `min_pat_growth_yoy`, measured
as the latest quarter against the same quarter a year earlier — never
against the previous quarter, which in Indian markets compares a
festival quarter to a monsoon one.

Growth off a **negative base is reported as unknown**, not computed. A
swing from a ₹10 crore loss to a ₹5 crore loss is a 50% improvement or a
150% decline depending only on how the formula is written, and neither
number is a fact.

**Profitability.** `min_opm` on the latest quarter's operating margin,
and `require_profitable` demanding no loss in any of the last four
quarters. Four quarters rather than one, because a single profitable
quarter after a run of losses is a turnaround thesis, which is a
different trade with different risk.

**Balance sheet.** `max_debt_equity` and `min_roe`. Leverage is what
turns an ordinary drawdown into a solvency question over a multi-week
hold.

**Promoter pledge.** `max_promoter_pledge_pct`. Pledged promoter shares
are a forced-selling mechanism: a fall in price can trigger a margin
call that causes a further fall. It has no equivalent in most markets
and it is one of the few fundamentals that acts on exactly the horizon
this agent screens for.

**Result freshness.** `max_result_age_quarters` measures the gap between
the screened session and the end of the latest published quarter.
Staleness is reported as **its own outcome**, never folded in with a
failing ratio — a name gated on results from six quarters ago has been
gated on history, and the output should say so rather than implying the
company failed a test.

## Missing Data

The rule that governs everything above, and the same one
`References/swing-criteria.md` applies to delivery percentage:

**A missing fundamental is unknown. Never zero, and never a pass.**

- A rule whose field is unknown is **not evaluated**. It neither passes
  nor fails, and it does not count toward the rules a name cleared.
- Coverage is judged separately. A name knowing fewer than
  `min_fields_known` of the gated fields is **not gateable**: it is
  reported in its own section, with what was known about it, and is
  neither included in the shortlist nor silently dropped.

Without the second half, the first would be an open door — a name no
provider answered for would clear every rule by having none of them
evaluated, and would rank alongside names that actually passed. The
`min_fields_known` floor is what closes it.

Reporting a company as "debt/equity 0.0" because a page changed shape
would be the same class of error as reporting a BSE-primary stock as
"delivery 0%": a number that reads as measured when nothing was
measured.

## Caching

Quarterly results change once a quarter, so `cache_max_age_days` governs
refetching rather than the immutability rule the session files use. A
week of morning runs over a stable shortlist costs one fetch per name.

```
${XDG_CACHE_HOME:-~/.cache}/ai-agents/india-market-data/
  fundamentals/screener/{SYMBOL}.html
  fundamentals/tickertape/search-{SYMBOL}.json
  fundamentals/tickertape/{sid}.json
  fundamentals/moneycontrol/{sc_id}.json
  fundamentals/exchange/{SYMBOL}.json
```

`--offline` reads the cache and nothing else, and fails loudly rather
than returning a name with every field unknown — which would otherwise
look identical to a company nobody publishes data for.

## Parameters

| Parameter | Value | Meaning |
|---|---|---|
| `provider_precedence` | screener, tickertape, moneycontrol, exchange | Resolution order, first hit wins per field |
| `max_pe` | 60.0 | Valuation ceiling, trailing twelve months |
| `min_pe` | 3.0 | Valuation floor — below this, suspect the denominator |
| `min_revenue_growth_yoy` | 0.0 | Latest quarter revenue against the year-ago quarter, percent |
| `min_pat_growth_yoy` | 0.0 | Latest quarter profit against the year-ago quarter, percent |
| `min_opm` | 5.0 | Latest quarter operating margin, percent |
| `require_profitable` | true | No loss in any of the last four quarters |
| `min_roe` | 10.0 | Return on equity, percent |
| `max_debt_equity` | 2.0 | Debt to equity |
| `max_promoter_pledge_pct` | 20.0 | Maximum share of promoter holding pledged |
| `max_result_age_quarters` | 2.0 | Quarters between the screened session and the latest published result |
| `min_fields_known` | 3 | Gated fields that must be known for a name to be gateable at all |
| `cache_max_age_days` | 7 | Refetch a provider's answer after this many days |
| `final_shortlist_size` | 10 | Names the morning shortlist returns |

`min_fields_known` must be at least 1 and no greater than the number of
gated fields. Setting it to 0 would restore exactly the open door the
missing-data rule exists to close.

## Known Limits

- **Consolidated versus standalone is not reconciled across providers.**
  screener.in is read from its consolidated page and moneycontrol's
  consolidated multiple is preferred, but a merged record can still mix
  a consolidated growth figure with a standalone ratio. The provenance
  map shows when this has happened; the gate does not correct it.
- **Three gated fields have no provider yet.** `debt_equity`,
  `promoter_holding` and `promoter_pledge` are declared, and are gated
  the moment a provider supplies them, but nothing here currently does:
  screener.in's ratio strip carries Market Cap, Price, High/Low, Stock
  P/E, Book Value, Dividend Yield, ROCE, ROE and Face Value — no
  leverage figure — and no provider parses the quarterly shareholding
  filing. In practice these three are almost always unknown, so the
  leverage and pledge filters described above are **written but not yet
  biting**. They are declared so that adding a source is a provider
  change rather than a schema change, and `min_fields_known` is set
  against the fields that are actually answerable today.
- **No sector-relative valuation.** A P/E ceiling applied uniformly
  across sectors will reject profitable software companies and accept
  cyclical ones at the top of a cycle. Both tickertape and moneycontrol
  publish an industry P/E that would make this comparison possible; it
  is not used yet.
- **Fundamentals are quarterly and lag reality.** Even the freshest
  provider is describing a quarter that ended weeks ago. This gate
  removes businesses that are visibly deteriorating; it cannot see one
  that started deteriorating last month.
