---
name: fundamental-gate
agent: stock-screening
---

# fundamental-gate

Fetch company fundamentals for a set of NSE-listed names, merge them
across providers with per-field provenance, and report which names pass
an explicit quality gate — with the criteria, the sources and the
unknowns stated alongside the verdict.

This Skill selects. It does not rank, size, time, or recommend, and a
name passing the gate is a candidate for a human to review rather than a
business anybody here is vouching for.

## Purpose

A price screen cannot see a business. A stock can trend beautifully on
expanding volume with excellent delivery while its revenue shrinks, its
margins collapse, or its promoters pledge their holding. This Skill is
where those questions get asked.

It runs on **a list of names, not a universe**. Given the whole market
it would be a thousand requests to third-party sites for an answer about
twenty-five stocks. Given the output of a technical screen it is a few
dozen cached requests. That is why the gate comes second, and it is the
single most important thing to preserve about how it is used.

Every verdict traces to the rule that produced it and the provider that
supplied the number. A gate whose inputs are unstated cannot be checked,
and is a defect rather than a result.

## Preconditions

- `Tools/fundamentals.py` and `Tools/bhavcopy.py` present and runnable
  on Python 3.10 or newer. Standard library only; nothing to install.
- Network access to the provider hosts, unless the cache already covers
  the names and `--offline` is used.
- No credentials. If something asks for an API key, it is not this data
  path.

Read `References/fundamental-criteria.md` before the first run of a
session. Three facts in it change what the output means: **the exchange
feed is the stalest source rather than the freshest**, three gated
fields currently have no provider at all, and a missing fundamental is
unknown rather than a pass.

## Procedure

**1. Read the criteria.** Load `References/fundamental-criteria.md`.
It holds every threshold and the provider precedence. Do not restate its
values from memory — they are read at run time, and a paraphrase drifts
from what actually ran.

If the user asked for a different threshold, edit the parameter table
and say which value changed. Do not pass ad-hoc numbers around the file.

**2. Decide what is being gated.** Either a shortlist from a technical
screen, or an explicit list of symbols. If it is a shortlist, keep the
screen's JSON — the close it carries is what P/E is computed against,
and the envelope is what dates the whole run.

**3. Run the gate.**

For one name:

```bash
python Tools/fundamentals.py show --symbol {SYMBOL} --close {close}
```

For a technical shortlist:

```bash
python Tools/screen.py --json swing --as-of {as_of} > /tmp/swing.json
python Tools/fundamentals.py gate --json-in /tmp/swing.json
```

Add `--offline` to read only the cache and fail rather than fetch. Add
`--json` before the subcommand for the full structured result, including
the complete provenance map.

**4. Read the provider failures before reading the verdicts.** They are
printed for a reason. Three of the four providers are commercial sites
whose pages can change shape without notice, and a run where one failed
for every name is a run whose gate was decided by the remaining
providers. That may be perfectly fine — it is what the exchange floor
exists for — but it must be known rather than discovered later.

**5. Separate the three outcomes.** They are not degrees of the same
thing:

- **Passed** — every rule whose field was known was satisfied.
- **Gated out** — a rule was evaluated and failed. The reason is named.
- **Not gateable** — fewer than `min_fields_known` gated fields were
  known. Nothing was decided about this name. It is reported with what
  *was* known and must never be quietly folded into either of the other
  two.

Reporting a not-gateable name as "failed" blames a company for a
publisher's gap. Reporting it as "passed" is worse — it is exactly the
open door `min_fields_known` exists to close.

**6. Check staleness separately from quality.** A name marked stale did
not fail a test; its most recent published quarter is older than
`max_result_age_quarters`. Say which, because the two suggest completely
different follow-up.

**7. Report.** Present the verdicts together with the criteria, the
provider precedence, the failures, and the not-gateable list. Keep them
together. A gate forwarded without them has lost what made it checkable.

## Outputs

Per name: the merged fundamentals, the provider behind each field, the
verdict, and the rules that produced it.

| Field | Meaning |
|---|---|
| `pe` | Close over trailing-twelve EPS — computed from the screened session, not taken from a vendor |
| `revenue_growth_yoy` `pat_growth_yoy` | Latest quarter against the year-ago quarter, percent |
| `opm` `net_margin` | Latest quarter margins, percent |
| `profitable_4q` | No loss in any of the last four quarters |
| `roe` `roce` | Return ratios, percent |
| `debt_equity` `promoter_holding` `promoter_pledge` | Declared and gated — but no provider supplies them yet |
| `latest_quarter` | The quarter the figures describe |
| `sector` | For the concentration check, not gated |

Alongside: which provider produced each value, which providers failed
and why, how many gated fields were known, and the reasons behind any
rejection.

`pe` being **computed rather than fetched** is deliberate. A vendor's
multiple is priced off whenever they last recomputed it; this one
belongs to the session that was actually screened.

## Errors

| Symptom | Cause | Response |
|---|---|---|
| `criteria missing required parameter` | A row was removed or renamed in the criteria file | Restore it; the tables are the contract |
| `{symbol} is not in the sc_id mapping` | moneycontrol addresses companies by its own id | Add a verified entry to `References/moneycontrol-sc-ids.json`, or accept that provider contributing nothing |
| `sc_id X maps to Y, not Z` | A wrong mapping entry | Fix it. This check exists because a wrong `sc_id` resolves to a real but different company |
| `no quarterly table on the page` | A provider changed its markup | Report the provider as failed; do not hand-patch values in |
| `offline and not cached` | `--offline` for a name never fetched | Drop `--offline`, or accept the name as not gateable |
| Every name not gateable | A provider is down, not a market-wide event | Read the failure list before concluding anything about the names |
| Everything stale | The exchange feed is the only provider answering | Expected when the commercial sources fail; say so |

Two failures must never be papered over: a not-gateable name presented
as passing or failing, and a stale verdict presented as a current one.
Both produce a confident answer to a question nobody asked.

## Boundaries

- **Pass/fail, never a ranking.** This Skill decides who is eligible.
  Ordering belongs to the technical composite, and blending the two
  would make a cheap multiple compensate for a broken setup.
- **No recommendation.** A passing name is a candidate, not advice.
- **Quarterly data lags.** Even the freshest provider describes a
  quarter that ended weeks ago. This gate removes businesses that are
  visibly deteriorating; it cannot see one that started last month.
- **Third-party sources are not contracts.** Three of the four providers
  are commercial products that owe this agent nothing, and their pages
  are unversioned. Whether accessing them is appropriate is the
  operator's judgement, set out in `References/fundamental-criteria.md`
  § Known Provider Limits.
- **No sector-relative valuation.** One P/E ceiling across all sectors
  rejects profitable software companies and accepts cyclicals at the top
  of a cycle. Both limits are in that file § Known Limits and should be
  repeated when the list is handed on.
