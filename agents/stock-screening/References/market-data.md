# Market Data — NSE and BSE

The data contract both screens run on. Load this before any fetch, and
whenever a run has to explain where a number came from or how fresh it
is. `References/universe-and-exclusions.md` decides which rows survive;
this file only says how the rows are obtained and what they mean.

Every endpoint here is a **public file published by the exchange**.
There is no API key, no account, and no signup. Nothing secret is read
from the environment and nothing secret can be committed, because no
credential exists to commit.

## The One Rule That Breaks Everything

Both exchanges reject requests that do not carry a browser-like
`User-Agent`. With no `User-Agent` header the connection does not
return 403 — it **fails outright with no response at all**. A fetch
that mysteriously returns nothing is almost always this.

`Tools/bhavcopy.py` sets the header on every request. Anything else
reaching these hosts must do the same.

## Feed Type — End of Day, Always

Every source below is **end-of-day**. NSE publishes the day's bhavcopy
in the evening IST, after the 15:30 close; BSE publishes on a similar
schedule.

Consequences that must be stated in output, never assumed away:

- A screen run for today, before that evening publication, has **no
  data for today**. It screens the previous session. Say so.
- `day-trading-shortlist` is therefore **retrospective**. It screens a
  completed session for a named date. It is not a live intraday feed
  and must never be presented as one.
- There is no quote, no order book, no tick data, and no intraday bar
  anywhere in this contract.

## Sources

`{YYYYMMDD}` is the session date; `{DDMMYYYY}` and `{DDMM}` are the
same date in the other orders these endpoints inconsistently use.

| What | URL | Notes |
|---|---|---|
| NSE daily OHLCV | `https://nsearchives.nseindia.com/content/cm/BhavCopy_NSE_CM_0_0_0_{YYYYMMDD}_F_0000.csv.zip` | Zipped, one CSV inside |
| BSE daily OHLCV | `https://www.bseindia.com/download/BhavCopy/Equity/BhavCopy_BSE_CM_0_0_0_{YYYYMMDD}_F_0000.CSV` | Plain CSV, not zipped |
| NSE delivery | `https://nsearchives.nseindia.com/products/content/sec_bhavdata_full_{DDMMYYYY}.csv` | Different schema — see below |
| BSE delivery | `https://www.bseindia.com/BSEDATA/gross/{YYYY}/SCBSEALL{DDMM}.zip` | Optional enrichment |
| NSE universe | `https://nsearchives.nseindia.com/content/equities/EQUITY_L.csv` | Symbol, ISIN, series, listing date |
| F&O eligibility | `https://nsearchives.nseindia.com/content/fo/fo_mktlots.csv` | Lot sizes; F&O names have no price band |
| Corporate filings | `https://www.nseindia.com/api/corporate-announcements?index=equities&from_date={DD-MM-YYYY}&to_date={DD-MM-YYYY}` | JSON; the catalyst source |
| Trading holidays | `https://www.nseindia.com/api/holiday-master?type=trading` | JSON; needed to walk back N sessions |

The two `www.nseindia.com/api/...` endpoints are a website's internal
JSON API, not a published contract. They are the most likely thing here
to change shape or start demanding a session cookie. Treat a failure on
either as a **degraded run**, not a fatal one: a shortlist without
catalyst annotation is still a shortlist, provided the output says the
catalyst field is unavailable rather than showing it as empty.

## UDiFF — One Schema, Both Exchanges

NSE and BSE publish daily OHLCV in the **same 34-column UDiFF format**.
One parser handles both. The columns that matter:

| Column | Meaning |
|---|---|
| `TradDt` | Session date |
| `ISIN` | **The join key across exchanges** |
| `TckrSymb` | Exchange-local ticker — differs between NSE and BSE |
| `SctySrs` | NSE series (`EQ`, `BE`, …) or BSE group (`A`, `B`, `T`, …) |
| `FinInstrmTp` | `STK` for equity |
| `OpnPric` `HghPric` `LwPric` `ClsPric` | Session OHLC |
| `PrvsClsgPric` | Previous close — the gap denominator |
| `TtlTradgVol` | Volume in shares |
| `TtlTrfVal` | Turnover in rupees |
| `TtlNbOfTxsExctd` | Trade count |

Never join on `TckrSymb`. The same company carries different tickers on
the two exchanges, and some BSE tickers collide with unrelated NSE ones.
`ISIN` is the only safe key.

## Reconciling Dual Listings

Roughly 2300 companies list on both exchanges. For a measured example
session, 2337 ISINs appeared on both, 2109 on BSE only, and 293 on NSE
only. Counts drift; the shape does not.

The rule depends on whether one session or a series is being built.

**For a single session:** one row per ISIN, from the venue with the
higher `TtlTrfVal` for that session. Turnover, not volume — volume is
not comparable across venues when a stock is thin on one of them.

**For a series, choose the venue once for the whole window** — the one
with the higher total turnover across it — and use that venue's bars
throughout. Do not re-decide per session.

This second rule is not a refinement; ignoring it produces wrong
numbers. A dual-listed stock regularly loses a single session to the
other exchange on a block deal. Prices agree closely across venues, so
trend and volatility barely move, but **volume does not agree at all**,
and a per-session choice splices one exchange's volume into the other's
baseline. A measured case: `SUNDRMFAST` traded higher on BSE in 5 of 60
sessions, which shifted its volume ratio and, because delivery is
NSE-only, silently dropped 4 of its 20 delivery observations.

Record which venue won, and which others the ISIN also traded on,
because it changes what else is knowable: delivery percentage comes
from the NSE file, so an NSE-primary row carries it and a BSE-primary
row does not.

Most BSE-only names are illiquid `X`-group scrips. They are not
special-cased — the liquidity floor in
`References/universe-and-exclusions.md` removes them for the same
reason it removes any thin name.

## Delivery Percentage

`sec_bhavdata_full` is **NSE only** and uses a different, older schema
from UDiFF: `SYMBOL`, `SERIES`, `DATE1`, `PREV_CLOSE`, `OPEN_PRICE`,
`HIGH_PRICE`, `LOW_PRICE`, `LAST_PRICE`, `CLOSE_PRICE`, `AVG_PRICE`,
`TTL_TRD_QNTY`, `TURNOVER_LACS`, `NO_OF_TRADES`, `DELIV_QTY`,
`DELIV_PER`.

Two traps:

- **Every field name and value is padded with a leading space.** Strip
  both keys and values before use, or every lookup misses.
- Turnover here is in **lacs**, while UDiFF `TtlTrfVal` is in rupees.
  One crore = 100 lacs = 10,000,000 rupees. Normalize to rupees on
  read and keep one unit internally.

`DELIV_PER` is the share of traded volume that settled as delivery
rather than being squared off intraday. It has no US equivalent and is
the single most useful signal here for separating genuine accumulation
from day-trader churn. On a measured session the EQ-series median was
about 57%, with a quarter of names below 46%.

Delivery is an **enrichment, not a requirement**. It joins on `SYMBOL`
against the NSE ticker. A row that cannot be matched — a BSE-primary
row, or a session whose delivery file failed to fetch — carries a null
delivery percentage. Criteria that use it must treat null as "unknown"
and say so, never as zero.

## Caching

A past trading session is **immutable**. Once fetched it is never
refetched.

```
${XDG_CACHE_HOME:-~/.cache}/ai-agents/india-market-data/
  sessions/{YYYY-MM-DD}/nse-udiff.csv
  sessions/{YYYY-MM-DD}/bse-udiff.csv
  sessions/{YYYY-MM-DD}/nse-delivery.csv
  reference/equity-l.csv
  reference/fo-mktlots.csv
  reference/holidays.json
  announcements/{YYYY-MM-DD}.json
```

Override with `--cache-dir`. A 60-session history is 60 sessions ×
2 or 3 files, fetched once; every later run over the same window is
served entirely from disk.

The `reference/` files describe the *current* listing state, not a
historical one, so they are refetched when older than a day.
Announcements for a past date are immutable and cached like sessions.

`--offline` reads the cache and nothing else. It **fails loudly** when
the requested window is not fully cached. It must never quietly return
a shorter history than asked for — a 20-session SMA computed from 11
cached sessions is wrong in a way nobody will notice.

## Trading Calendar

"60 sessions back" is not "60 days back". Indian markets close on
weekends and on a long, irregular holiday list that includes state
holidays and occasional special sessions.

Derive the calendar from the sessions that actually exist. The holiday
endpoint above is the intended source; the fallback, when it is
unavailable, is that a session for which no bhavcopy is published was
not a trading day. Both approaches agree in practice, and the fallback
needs no network call beyond the fetch already being attempted.

Do not assume settlement or session times beyond this: regular trading
is 09:15–15:30 IST, pre-open 09:00–09:15, and settlement is T+1. None
of that is observable in end-of-day data — it is context for reading
the output, not something the screens measure.

## Failure Modes

| Symptom | Cause | Response |
|---|---|---|
| No response at all, no status code | Missing `User-Agent` | Set the header |
| 404 on a bhavcopy for a weekday | Trading holiday, or the file is not published yet | Treat as a non-session; do not retry forever |
| 404 on today's file after hours | Publication lag | Fall back to the previous session and say so |
| Announcements or holidays endpoint fails | Internal JSON API changed or is rate-limiting | Degrade: run without catalyst annotation and label the field unavailable |
| Delivery file missing for a session | Publication gap | Null delivery for that session, stated in output |
| Sudden empty result for every name | An exclusion list or a threshold, not the feed | Check `References/universe-and-exclusions.md` before re-fetching |

Be polite. These are exchange file servers, not a paid API. Fetch
sequentially, back off on failure, and let the cache do the work.
