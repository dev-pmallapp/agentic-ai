---
name: day-trading-shortlist
agent: stock-screening
---

# day-trading-shortlist

Produce a ranked shortlist of NSE and BSE equities that gapped, traded
unusual volume, and had a material exchange filing on **one named
trading session**, with the criteria and the data's as-of session
reported alongside the list.

## Purpose

For a given date, identify the names where something actually happened:
the stock opened away from its previous close, traded far more than it
normally does, and had a filing published that could explain it. Any one
of those alone is noise. Together they isolate a real event.

## Read This Before Anything Else

**This screen is retrospective.** The feed is end-of-day
(`References/market-data.md` § Feed Type). It reads the open, high, low,
close and volume of a session that has already finished.

It cannot tell anyone what to trade today. It could not have been run on
the morning of the date it screens — relative volume is a whole-session
figure and is not knowable until the close.

What it is good for: studying which criteria actually select eventful
names, reviewing a session after the fact, and building a prior from
many dates. What it must never do is present itself as a live or
pre-market screen. If a user asks for today's intraday candidates, say
plainly that this data path cannot produce them, rather than running
this Skill on yesterday and letting the date go unnoticed.

## Preconditions

- `Tools/bhavcopy.py` and `Tools/screen.py`, runnable with Python 3.10
  or newer. Standard library only; nothing to install.
- Network access to `nsearchives.nseindia.com`, `www.bseindia.com` and
  `www.nseindia.com`, unless the window is cached and `--offline` is
  used.
- No credentials. The sources are public exchange files.
- A **named date** that is a real trading session. A weekend or holiday
  has no data and is not an error to be worked around.

## Procedure

**1. Establish the date, explicitly.** This Skill screens one session.
Get it from the user. If they said "today" and today's file is not
published yet, do not silently substitute yesterday — tell them what is
available and confirm.

**2. Read the criteria.** Load `References/day-criteria.md` and
`References/universe-and-exclusions.md`. Every threshold and the full
catalyst category list live there. Adjust by editing the parameter
table, and say which value changed.

**3. Warm the cache.** The screen needs the named session plus the
sessions before it for the volume baseline:

```bash
python Tools/bhavcopy.py history --end {date} --sessions {lookback_sessions}
```

**4. Run the screen.**

```bash
python Tools/screen.py day --date {date}
```

`--offline` restricts to the cache; `--json` gives the full result.

The volume baseline uses the sessions **before** the named date and
never the date itself. Including a session in its own baseline damps
exactly the spike being measured, and damps the largest spikes most.

**5. Check the catalyst line in the header.** It reads either
`available` or `UNAVAILABLE`. The filings endpoint is a website's
internal JSON API rather than a published contract, and it does fail.

When it is unavailable the run still produces a shortlist, the catalyst
column reads `n/a`, and the catalyst weight is redistributed across the
other components. Report that the ranking was computed without
catalysts. Do not report the names as having no catalyst — unavailable
and absent are different claims and only one of them is true.

**6. Read the outcome column as what it is.** `HELD` records whether the
gap held into the close. It is observed after the fact, is excluded from
every filter and from the score, and exists so the criteria can be
checked against reality. Never rank on it, never filter on it, and never
present it as something the screen predicted.

**7. Watch for mechanical gaps.** Prices are unadjusted for corporate
actions. An ex-dividend, split or bonus date produces a large gap that
is not an event at all. A gap suspiciously close to a round fraction of
the price — a half, a fifth, a tenth — should be checked against the
corporate actions record before it is believed.

**8. Report.** Present the ranked list with the criteria, the universe,
the as-of session, and the retrospective note, as `Tools/screen.py`
prints them.

## Outputs

A ranked table, at most `shortlist_size` names, each row carrying:

| Column | Meaning |
|---|---|
| `SYMBOL` `EX` | Ticker and the exchange chosen as primary |
| `CLOSE` | Close on the named session, in rupees |
| `GAP%` | Open against previous close, signed |
| `RVOL` | Session volume over the median of the baseline window |
| `RNG%` | Session range as a percent of previous close |
| `TURNOVER` | Median daily turnover, in crore |
| `CATALYST` | `filing`, `exch-query`, `-` for none, or `n/a` when the feed failed |
| `HELD` | Whether the gap held into the close — observed, not scored |
| `SCORE` | Weighted composite, for ordering only |

`exch-query` means the exchange asked the company to explain a volume
spurt or price movement — reactive rather than causal, and labelled
separately for that reason.

Above the table: the as-of session, the retrospective warning, the fetch
timestamp in IST, the universe size, catalyst availability, and every
threshold applied. Below it: the rejection breakdown and the standing
notes.

## Errors

| Symptom | Cause | Response |
|---|---|---|
| `no session published for {date}` | Weekend, holiday, or not yet released | Not an error to route around — say the date had no session |
| `CATALYSTS UNAVAILABLE` | The filings endpoint failed or changed | Report the ranking as computed without catalysts |
| `offline and not cached` | `--offline` with an incomplete window | Drop `--offline`, or pick a covered date |
| `asked for N sessions, found M` | Baseline window is short | Report the shorter baseline; relative volume is less reliable |
| Very few or no names pass | Gap and relative-volume thresholds are strict by design | A quiet session is a real answer; show the rejection breakdown |
| A name with an absurd gap | Probably a corporate action, not an event | Check before passing it on |

## Boundaries

- **Retrospective, always.** This screens a completed session. It is not
  a live, pre-market, or intraday tool, and no amount of running it on a
  recent date makes it one.
- **Candidates, not advice.** No recommendation, sizing, timing, or
  execution.
- **No intraday granularity.** No opening range, no VWAP, no time-of-day
  volume profile, no pre-market activity.
- **Filings only, not news.** Sector moves, index rebalances, global cues
  and press coverage that never became an exchange filing are invisible.
  Absence of a catalyst is weak evidence.
- Further limits are set out in `References/day-criteria.md` § Known
  Limits and should travel with the list.
