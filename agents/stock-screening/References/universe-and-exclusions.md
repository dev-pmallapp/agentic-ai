# Universe and Exclusions

Which securities are eligible to be screened at all, before any strategy
applies. Both `Skills/swing-trading.md` and
`Skills/day-trading-shortlist.md` filter through this file first, so a
name excluded here can never reach either shortlist.

The distinction this file draws is **tradability, not opportunity**.
A stock is excluded here because it cannot be traded normally — it is a
bond, an SME scrip, under surveillance, frozen at a circuit, or too thin
to enter and exit. Whether it is a *good* candidate is decided later, by
`References/swing-criteria.md` or `References/day-criteria.md`.

Parameter tables in this file are read directly by `Tools/screen.py`.
Edit a value here and the next run uses it — no code change, no prose
rewrite.

## NSE Series

The `SctySrs` column on an NSE row. On a measured session the EQ series
held 2630 of about 3600 NSE rows; almost everything else is a bond, a
government security, or an SME listing.

| Series | Meaning | Kept |
|---|---|---|
| `EQ` | Normal rolling settlement equity | **yes** |
| `BE` | Trade-to-trade — no intraday netting, delivery compulsory | no |
| `BZ` | Surveillance, trade-to-trade | no |
| `SM` `ST` | SME platform — thin, wide lots, different rules | no |
| `GS` `GB` `TB` | Government securities, gold bonds, treasury bills | no |
| `N0`–`N9` `NA`–`NZ` `Y*` `Z*` | Debt, NCDs, and other non-equity series | no |
| `IV` `MF` `RR` `E1` `P1` | Institutional, mutual-fund, rights and other special series | no |

`BE` is excluded rather than merely flagged. A trade-to-trade scrip
cannot be squared off intraday at all, which makes it meaningless for
`day-trading-shortlist`, and its wider spreads distort the swing
ranking. If a future screen wants it, it should turn it on explicitly.

## BSE Groups

The same `SctySrs` column on a BSE row carries a group letter instead.

| Group | Meaning | Kept |
|---|---|---|
| `A` | Most liquid, largest companies | **yes** |
| `B` | Normal equity outside the A list | **yes** |
| `T` | Trade-to-trade — no intraday netting | no |
| `Z` | Non-compliant with listing requirements | no |
| `M` `MT` `MS` | SME platform | no |
| `X` `XT` | Illiquid and restricted scrips | no |
| `F` `G` | Debt and government securities | no |
| `E` `IF` `P` | ETFs, InvITs, and preference shares | no |

Most BSE-only listings are `X`-group. They are excluded by group and
would in any case not survive the liquidity floor.

## Hard Exclusions

Applied after the series and group filters, in this order.

**Circuit-locked sessions.** A stock frozen at its upper or lower price
band trades with `HghPric == LwPric` for the whole session — there is no
range, and no willing counterparty at any other price. Roughly 18 EQ
names hit this on a measured session. Such a row is unusable: its ATR
contribution is zero, its gap is untradeable, and a screen that ranks it
highly is ranking something nobody could have bought.

Exclude the row for that session. Do **not** exclude the stock from
history — a name that was locked forty sessions ago is fine today, and
dropping it entirely would silently shorten every window it appears in.

**Insufficient history.** A name needs at least `min_sessions` sessions
of data in the window to have a meaningful moving average or volume
baseline. Recently listed stocks fail this and are excluded rather than
ranked on a partial window.

**Price floor.** Below `min_close`, tick size becomes a large fraction
of the price and percentage moves stop meaning what they normally mean.

**Liquidity floor.** Below `min_median_turnover`, a shortlist entry is
not actionable at any size. This is the baseline; each strategy may
raise it.

**Non-equity instruments.** Only `FinInstrmTp == STK` rows are
considered, which removes derivatives and index rows that share the
file.

## Parameters

| Parameter | Value | Meaning |
|---|---|---|
| `keep_nse_series` | EQ | NSE series retained |
| `keep_bse_groups` | A, B | BSE groups retained |
| `instrument_type` | STK | UDiFF `FinInstrmTp` retained |
| `min_close` | 50 | Price floor in rupees |
| `min_median_turnover` | 50000000 | Baseline liquidity floor in rupees — ₹5 crore median daily turnover |
| `min_sessions` | 45 | Sessions of history required to be rankable |
| `exclude_circuit_locked` | true | Drop sessions where high equals low |

For scale on the price floor: on a measured session, a ₹50 floor kept
2040 of 2630 EQ names, while a ₹100 floor kept 1743. On liquidity, a
₹5 crore median turnover floor kept about 1125 names and ₹10 crore kept
889 — against a median EQ turnover of roughly ₹2.9 crore, meaning the
baseline floor already removes more than half the market.

## What Is Deliberately Not Excluded

- **F&O names are not preferred or penalised.** `fo_mktlots.csv`
  identifies them, and they differ in that they carry no price band, but
  that is a fact to report rather than a filter.
- **Sector and index membership are not filtered.** No index constituent
  list is consulted. A screen that only ever returns index names is
  measuring the index, not the market.
- **Market capitalisation is not filtered**, because it is not in this
  data. Turnover is the liquidity proxy in use, and it is the more
  relevant one for whether a position can actually be entered.
- **ASM and GSM surveillance lists are not consulted.** The `BZ` series
  and `Z` group catch the most restricted names. The full graded
  surveillance lists are published separately and are not part of this
  contract; a name under ASM that still trades in `EQ` will appear.
  Say so rather than implying the list is surveillance-clean.
