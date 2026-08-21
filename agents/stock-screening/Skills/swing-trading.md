---
name: swing-trading
agent: stock-screening
---

# swing-trading

Produce a ranked shortlist of NSE and BSE equities that satisfy stated
trend, volume, volatility and delivery criteria over a multi-day to
multi-week horizon, with the criteria and the data's as-of session
reported alongside the list.

The output is a list of candidates for a human to review. It is not a
recommendation to buy or sell anything, and nothing in this Skill sizes
a position or places an order.

## Purpose

Narrow roughly seven thousand listed securities down to a few dozen that
are already trending, liquid enough to trade at size, moving enough for
the horizon to matter, and backed by real delivery-based buying rather
than intraday churn.

Every name on the resulting list can be traced to the filter that
selected it and the value it cleared that filter with. A shortlist whose
filters are unstated cannot be checked or reproduced, and is a defect
rather than a result.

## Preconditions

- `Tools/bhavcopy.py` and `Tools/screen.py` are present and runnable
  with a Python 3.10 or newer interpreter. They use the standard library
  only — there is nothing to install.
- Network access to `nsearchives.nseindia.com` and `www.bseindia.com`,
  unless the cache already covers the window and `--offline` is used.
- No credentials of any kind. The sources are public exchange files.
  If something asks for an API key, it is not this data path.

Read `References/market-data.md` before the first run of a session. Two
facts in it change what the output means: the feed is **end-of-day**, so
a run before the evening publication screens the previous session; and
requests without a browser-like `User-Agent` fail with no response at
all rather than an error.

## Procedure

**1. Fix the as-of date.** Decide which session the screen is for. If
the user named one, use it. If not, use the most recent published
session — which, before the evening publication, is yesterday, not
today. Never silently screen a different session from the one asked
for.

**2. Read the criteria.** Load `References/swing-criteria.md` and
`References/universe-and-exclusions.md`. These hold every threshold the
screen applies. Do not restate their values in your own words from
memory — they are read at run time, and a paraphrase drifts from what
actually ran.

If the user asked for a different threshold, edit the parameter table in
the relevant Reference and say which value changed. Do not pass ad-hoc
numbers around the criteria files; the whole point of them is that the
run is reproducible from what is written down.

**3. Warm the cache.** Fetch the history the criteria ask for:

```bash
python Tools/bhavcopy.py history --end {as_of} --sessions {lookback_sessions}
```

A past session is immutable, so this is a one-time cost per window. It
fetches sequentially and backs off on failure — these are exchange file
servers, not a paid API. Expect the first run over a fresh window to
take a few minutes and later runs to take seconds.

Non-trading days are discovered and cached as such. A weekday with no
bhavcopy is a market holiday, and the walk-back handles it without a
holiday list.

**4. Run the screen.**

```bash
python Tools/screen.py swing --as-of {as_of}
```

Add `--offline` to read only the cache and fail rather than fetch. Add
`--json` for the full structured result, including the complete
rejection breakdown rather than the summarised one.

**5. Check the run before reading the list.** Three things in the header
decide whether the shortlist means anything:

- **Sessions loaded.** Fewer than `lookback_sessions` means a short
  window, and every moving average in the output is computed over less
  history than the criteria specify. Say so or re-run.
- **As-of session.** Confirm it is the session intended.
- **Universe and pass count.** A pass count of zero is a result, not a
  failure — report it as "nothing met these criteria on this date" and
  show the rejection breakdown, which localises why.

**6. Sanity-check the top of the list.** Prices are **unadjusted for
corporate actions**. A split, bonus or large dividend inside the window
fabricates a trend and distorts every average that crosses it. A name
whose numbers look impossible — an ATR far outside its band's spirit, a
move no liquid stock makes — deserves a check against the corporate
actions record before it is passed on.

**7. Report.** Present the ranked list together with the criteria, the
universe, and the as-of session, as `Tools/screen.py` prints them.
Keep them together. A shortlist forwarded without its criteria has lost
the thing that made it checkable.

## Outputs

A ranked table, at most `shortlist_size` names, each row carrying:

| Column | Meaning |
|---|---|
| `SYMBOL` `EX` | Ticker and the exchange chosen as primary for the window |
| `CLOSE` | Close on the as-of session, in rupees |
| `>SMA50` | Percent above the long moving average — the trend measure |
| `<HIGH` | Percent below the window's highest close |
| `VOLx` | Recent average volume over the longer baseline |
| `ATR%` | Average true range as a percent of price |
| `DELIV` | Average delivery percentage; `*` marks a partial window |
| `TURNOVER` | Median daily turnover, in crore |
| `SCORE` | Weighted composite, for ordering only |

Above the table: the as-of session, the feed type, sessions loaded, the
fetch timestamp in IST, the universe size, and every threshold applied.
Below it: the rejection breakdown, and the standing note that these are
candidates and the data is end-of-day and unadjusted.

`SCORE` orders the list. It is not a probability, a target, a position
size, or a return estimate, and scores from runs with different
thresholds are not comparable.

## Errors

| Symptom | Cause | Response |
|---|---|---|
| No response, no status code | Missing `User-Agent` | Use `Tools/bhavcopy.py`, which sets it |
| `offline and not cached` | `--offline` with an incomplete window | Drop `--offline`, or pick a covered date |
| `asked for N sessions, found M` | Window runs past available history, or a fetch failed | Re-run; if it persists, report the shorter window rather than presenting the result as a full one |
| `criteria missing required parameter` | A parameter row was removed or its name changed in a Reference | Restore the row; the tables are the contract |
| `no session published for {date}` | Weekend, holiday, or the file is not out yet | Use the previous session and say which |
| Everything rejected for one reason | A threshold, not the feed | Check that reason's parameter before re-fetching |
| Delivery unavailable for many names | The NSE delivery file failed, or the names are BSE-primary | Report as unknown; never treat missing delivery as zero |

Two failures must never be papered over: a shorter history than the
criteria ask for, and a different as-of session than the one requested.
Both produce a plausible-looking list that answers a question nobody
asked.

## Boundaries

- **Candidates, not advice.** This Skill selects and ranks. It does not
  recommend, size, time, or execute.
- **No fundamentals.** Nothing here reads earnings, valuation, debt or
  ownership. It is a price, volume and delivery screen.
- **No intraday data.** Everything is end-of-day. There is no quote, no
  order book, and no live price anywhere in this path.
- **No corporate-action adjustment**, and no sector or correlation
  awareness — a shortlist can be twenty names expressing one bet. Both
  limits are set out in `References/swing-criteria.md` § Known Limits
  and should be repeated when the list is handed on.
