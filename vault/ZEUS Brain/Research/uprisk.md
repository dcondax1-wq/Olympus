---
tags:
  - zeus/research
  - family/risk
  - verdict/adopt-candidate
type: "research"
date: "2026-10-25"
status: "adopt-candidate"
source: "research/writeups/uprisk.md"
aliases:
  - "Uprisk"
---

# Uprisk

> [!success] Verdict: adopt-candidate
> adopt-candidate

**Full title:** Uprisk - where the funded money is capped, and what really pays more a month

## Summary

Owner (2026-10-25) - "that little bit per month doesn't seem normal, figure out what you're missing". On the 2026 LIT trades a funded MFFU Builder 50K already makes about $1,950 a month of trading profit, but only about $1,050 a month comes out ($835-889 to you). Risk per trade is not what holds it back. MFFU pays at most $2,000 a request, the 50% best-day rule holds the money about 38 of 126 sessions, and after 5 payouts ($8,000 to you) the account leaves the sim. So after 6 months about $5,400 is still sitting in the account. Doubling the per-trade risk from $800 to $1,500 adds only $3-62 a month. The one sizing lever that pays is the winner cap, the cap that keeps a day's best win small for the 50% rule. Raising it from $1,500 to $2,000 (one winner = one full request), with 60% of the room and at most $1,500 a trade, pays $929 / $915 a month instead of $889 / $835 (H1 pick / H2 check). The first payout comes after 23-26 sessions instead of 33, and 0% of accounts are lost. A more aggressive eval (room_f 0.8, weekly loss stop off) adds about $20-30 a month per account and fails about 1 eval in 5 within 2 weeks (today about 1 in 35). The real multiplier is the number of accounts, because each one pays about the same and they add up. MFFU 50K + two 25Ks pay about $1,410-1,540 a month net of evals; five 50K-type accounts pay about $3,750-3,950. They trade the same signals (correlation 0.86), and on 2021-25 every plan only loses eval fees. Paper only; nothing live changed.

## Money first

| Plan (LIT, MFFU, 6 months, net of every eval bought) | H1 Jan-Jun (pick) | **H2 Jul-Oct (check, quote this)** | 1 in 10 paths (H2) | 6 months lose money (H2) | 2021-25 (reference) |
|---|---:|---:|---:|---:|---:|
| Today: 1 x Builder 50K, today's eval + funded sizing | $740/mo | **$663/mo** | $171/mo | 9.6% | -$27/mo |
| Uprisk sizing on the 50K (step 1 + step 2 below) | $823/mo | **$798/mo** | | 7.6% | -$7/mo |
| MFFU in full: 50K + 2 x 25K, uprisk funded sizing | $1,536/mo | **$1,411/mo** | $301/mo | 5.7% | -$47/mo |
| 3 x 50K-type accounts (MFFU + 2 other firms), uprisk | $2,394/mo | **$2,304/mo** | $472/mo | 4.1% | -$40/mo |
| 5 x 50K-type accounts, uprisk | $3,955/mo | **$3,752/mo** | $883/mo | 2.4% | -$63/mo |

- "Net" = everything paid to you (MFFU's 80%) minus every eval bought ($91.80 / $63), over 6 months from buying the eval,
  including the eval itself, 2 sessions of MFFU paperwork and the wait for the first payout. A failed eval, a lost funded
  account or a finished one (5 payouts) is bought again at once.
- **What you were missing: the money is made, but it cannot come out faster.** The funded 50K makes about **$1,950 a month**
  of trading profit on the 2026 trades, but only about **$1,050 a month** is paid out ($835-889 to you). The rest piles up:
  after 6 months a typical account still holds about **$5,400** above its start. The limits are MFFU's payout rules, not the risk.
- **Uprisking the trade size alone barely helps:** $800 → $1,500 a trade adds $3 (H1) / $62 (H2) a month. The one sizing
  change that pays is a bigger **winner cap** ($1,500 → $2,000, so one winner is one full $2,000 request): +$40 / +$80 a month
  and the first payout about 2 weeks sooner. The big jump comes from **more accounts**.
- **Risk of ruin, plainly:** in 1,000 simulated 6-month funded accounts per setting, **no funded account was lost**, in either
  half or on 2021-25: the sizing shrinks with the room to the floor. The biggest single trade goes from $422 to $845 of risk
  (21% → 42% of a fresh account's $2,000 room; only reached once the account has built room). What you can really lose is **eval fees**. In a
  2021-25-like year (LIT PF ~1.0) 80-94% of 6-month windows lose money: about $7-63 a month in fees, never more.

## Links

- Family: [[Family risk]]
- Day: [[Day 2026-10-25]]
- Refers to: [[funded-path|The funded path]], [[lit-funded-combo|LIT funded accounts on the new live LIT]], [[lit-funded-firms|LIT on 3 funded accounts]], [[scale-plan|The scaling plan]]
- Runs: `uprisk_f50_today, uprisk_f50_up, uprisk_f50_nocap, uprisk_f50_need, uprisk_f50_harvest, uprisk_f25_today, uprisk_f25_up`
- Source: `research/writeups/uprisk.md`
- Back to [[ZEUS Home]]
