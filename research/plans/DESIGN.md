# Plan ranking (2026-11-22): pre-registered design, committed BEFORE any run

Question (lead): rank every eval plan we could buy for LIT (Zlarior) + ATLAS by real money. Research only, nothing bought.
Code research/plans/rank.py -> research/plans/results.json; write-up research/writeups/plan-ranking-2026-11-22.md.

## Plans (allowed for automated NinjaTrader bots + copying, research/writeups/corvette-plan-2026-11-21.md)
| plan (research/props/firm_rules.json) | price used | source of the price |
|---|---|---|
| mffu_builder_25k | $63.00 | owner's real price |
| mffu_builder_50k | $91.80 | owner's real price |
| mffu_rapid_eod_25k | $97.20 | owner's real price (CLUB) |
| mffu_rapid_eod_50k | $165.00 | CLUB price (corvette buy list) |
| lucid_pro_50k (DLL on) | $126.00 | corvette: ~$126 with a 30% code (third-party, unconfirmed) |
| lucid_flex_50k | $134.40 | account4_sim stand-in (price set at checkout, unquoted) |
| fn_rapid_daily_50k | $149.99 | FundedNext's own RAPID code (help center, Oct 2026) |
Not ranked (rules say no): Apex (bots banned), Take Profit Trader (bots banned), Alpha Futures (bots banned), Tradeify (one
strategy across firms banned), Topstep (TopstepX only = a paid API), Bulenox (bots need approval, cross-firm copy banned).
Not ranked (rules incomplete in firm_rules.json: no buffer / payout caps verified): lucid_pro_25k, lucid_flex_25k, fn_rapid_*_25k,
fn_rapid_pro_*.

## Engine (fixed)
- Trades: LIT + ATLAS per session (tools/money/stack_one_account.mix_by(("LIT","ATLAS"))), ATLAS re-priced at 10 ticks a side
  (tools/atlas_risk.rapid_patch(T_at(10)) = its measured real fills), LIT as stored. MFFU Rapid funded: Tier-1 news ban (mix_by news=True).
- Eval: tools/money/rapid_levers.Ev (= the live LIT two_week sizing on the plan's numbers + ATLAS's lane: $ = min($250 on a 25K /
  $500 on a 50K, 30% of the room, the soft day left) + the best-day guard where the plan has an eval consistency rule).
  Soft day: the firm's daily loss, else $500 (25K) / $1,000 (50K).
- Funded: tools/account4_sim.Lucid's generic payout logic on the plan's own rules (tools/account4_sim.rules: buffer, min, caps,
  consistency, win days, days a request, share, max payouts, split, LucidScale), with ATLAS sized on its own lane
  (rapid_levers.q_add) and LIT on the MFFU funded preset (UP25 / UP50). Request: the full cap where the plan has one, else
  as soon as the minimum is available (Rapid: + $250 / $500 since the last payout as MFFU's rule).
- One account slot per plan, 126 sessions (6 months), a failed eval or a lost funded account is re-bought the next session;
  1,000 paths a market (5-session week blocks, seed 23): H1 = 2026 Jan-Jun-like, H2 = Jul-Oct-like, REF = 2021-25-like.
  Every plan on the SAME paths.
## Reported per plan x market
first eval: pass % within 60 sessions, median sessions to pass, fail %; 6 months: $ to the owner (after the split), fees paid,
net $, $ to the owner per $ spent, chance of no payout, funded accounts lost, chance of losing >= 1 funded account.
## Ranking and buy rule (fixed)
Rank by H2 net $ in 6 months per slot. A plan is a BUY candidate only if net > 0 in H1 AND H2 and the REF loss is at most
2 x its price. Decide cards for the top 2 candidates (recommend yes / no with the honest risk); firm-level open questions
(Lucid's written OK for bots at two firms, live-move rules) go in the card.

## Addendum after a 60-path smoke run (mechanics only, before the scored run): the funded account never "died" because the
sizer trades 0 micros at a tiny room. As every repo funded model (atlas_health / account_b MIN_ROOM), a funded account whose
room to the floor is under $100 (25K) / $200 (50K) is STUCK = dead (counted lost, re-bought). Nothing else changed.
Addendum 2 (same smoke run, before the scored run): MFFU Rapid payouts follow the bot's own built rule (engine/rapid.py: keep
$1,000 above the buffer on the 50K, $500 on the 25K), not "everything above the buffer" - uncapped daily payouts otherwise
leave the account at the stuck line. Capped plans request their cap as designed.
