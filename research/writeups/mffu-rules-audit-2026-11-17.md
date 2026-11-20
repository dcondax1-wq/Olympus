---
title: MFFU rules audit (2026-11-17): can anything the bots do void an eval or a payout?
family: other
date: 2026-11-17
status: finding - nothing the bots do today voids an eval or a payout; two gaps fixed, the 2% price-limit guard still missing
summary: 78 MFFU help-center articles and the plan pages checked against what the bots do (values in research/lit/mffu_rules.json). Hedging across accounts, max contracts, EOD trailing max loss, daily loss, flat time, holiday half-days, Rapid eval consistency, payouts and account limits are enforced. Fixed: the Rapid funded tier-1 news window had no safety margin and no December / 2027 CPI and jobs dates, and inactivity could cost the ATLAS 25K funded account all its profits with no warning. Missing: no guard for the 2% CME price-limit rule (rare; stand aside on crash days).
---

# MFFU rules audit (2026-11-17): can anything the bots do void an eval or a payout?

Sources: MFFU's help center (78 articles read directly, help.myfundedfutures.com) and plan pages (myfundedfutures.com/plans/builder,
/plans/rapid-eod), all reachable from the sandbox today. Values: research/lit/mffu_rules.json (each with source, status, checked
2026-11-17; the list of changes is in its "changes_2026_11_17").

## Owner table

| Rule | MFFU says | Bot does | Status |
|---|---|---|---|
| Hedging across accounts | No long + short on the same underlying at the same time, "of any kind" (NQ = MNQ). Across one person's accounts: not spelled out, read the strict way | Every pair blocked: Zlarior 50K, ATLAS 25K (eval and funded), the Rapid's LIT lane and ATLAS lane, BLITZ (paper), fleet copies. The later trade waits or the other one is closed first, and must be confirmed flat | **Enforced** (re-proved: tests/test_rapid g, test_multi_account, test_account_b_local) |
| Same strategy on several accounts / trade copier | **Allowed** on all account types (own accounts). Banned: copying another person, shared devices, coordinating with others | LIT on several accounts = same side | OK |
| Max contracts | Builder 50K 4 minis / 40 micros, 25K 2 / 20, Rapid EOD 50K 3 / 30. Minis + micros count together; going over can breach | 40 / 20 / 30 micro caps. The Rapid's two lanes are never open together (ATLAS is closed before LIT enters) | Enforced |
| Max loss (EOD trailing) | Moves only at the close; open losses count; stops at start + $100. Builder: after the 1st payout the floor is $100 | Size fits the full stop inside the room; funded skips a trade that could touch the floor; floor = +$100 after a payout | Enforced |
| Daily loss | Soft pause: Builder 50K $1,000, 25K $600. Rapid EOD none (the DLL add-on version has $1,000) | Pause at -$1,000 / -$600; Rapid: the bot's own -$1,000 | Enforced (it can't void an account) |
| Flat time | Flat by 16:10 ET (auto-closed); forcing orders after 16:10 can disqualify | Flat 15:55, no entry after the cutoff, safety flatten | Enforced |
| Holiday half-days | NO auto-close at the early halt; still open = **breach** | Flat 5 min before the CME early close (Thanksgiving 13:00, Nov 27 + Dec 24 13:15), no entry in the last 15 min | Enforced (if MFFU emails an earlier time, that wins) |
| Tier-1 news (Rapid **funded** only) | FOMC, FOMC minutes, jobs report, CPI: no position AND no order from 2 min before to 2 min after (8:30 -> flat by 8:28:00, reopen after 8:32:00). Builder + all evals: unrestricted | Was: flat exactly at -2:00 (no margin); December CPI / jobs and every 2027 CPI / jobs date missing; the weekly feed's jobs-report name not matched. **Now:** flat from -3:00, no entry until +2:30, Dec 2026 dates added (MFFU's own calendar), 2027 minutes added, any month without known CPI / jobs dates treats 8:30 ET every weekday as Tier-1 | **Fixed** (was partly) |
| Inactivity | No trade for 7 calendar days -> account can be closed; on sim funded **all profits are lost** | Was: only Zlarior's eval warned. **Now:** ATLAS 25K (eval + funded) and the Rapid (both lanes count) push from day 5 | **Fixed** (was partly) |
| Rapid eval: 4 days, 30% best day | 4 trading days; best day <= 30% of profit (just trade more days) | Pass waits for 4 days + 30%; winners capped at 30% x $3,000 x 0.95 | Enforced |
| Payouts | Builder: buffer $2,100 / $1,100, then $500 / $250, max $2,000 / $1,000, 2 days, 50% best day, 48 h, 80%. Rapid: $2,100 buffer, $500 min, daily, 90%, no consistency | Tracker tells you when to ask; never requests by itself; Rapid keeps $1,000 extra | Enforced (advice only) |
| Account limits | 10 evals; 5 sim funded (25K/50K); Builder 50K 1, 25K 2, Rapid EOD 50K 3 | Plan = 50K + 25K + 1 Rapid funded = 3. A 2nd Builder 50K eval may run, but it can't go funded while Zlarior's 50K is funded | OK |
| 2% price limit | Sim funded + live: no trading within 2% of a CME limit (stop at a 5% overnight move) | No guard | **Missing** (rare: NQ +/-5% day). Stand aside on crash days |
| Passing | Instant "Upgrade" in the dashboard (same day; review < 24 h). Funded Name contains "SIM". $0 activation | Bot stops the eval at pass; funded switch is the owner's one line | OK |
| Live (later) | Builder: after 5 payouts; Rapid: a $10,000 day or risk team. Sim + live never together | "Graduated" stops the bot on that account | OK |

## What could void money right now
Nothing found that the bots do today. Hedging: every pair of accounts is already blocked (LIT's own account refuses an order
opposite any extra account in `live._route`; ATLAS / BLITZ / the Rapid lanes check each other). Two gaps were fixed: the Rapid's funded news window had no safety margin and no December or
2027 CPI / jobs dates, and inactivity could cost the ATLAS 25K funded account all its profits with no warning. Still missing:
the 2% price limit. It needs a +/-5% NQ day, so on a crash day leave the funded accounts alone.

## Fixes (offline tests: tests/test_rapid.py part g; test_rapid 49/49)
- `engine/multi_account.py`: `NEWS_PRE_S/POST_S` 120/120 -> 180/150. The jobs report under the weekly feed's name ("Non-Farm Employment
  Change", not ADP) now counts. A month without known CPI and jobs dates treats 08:30 ET as Tier-1 from 2026-11-17 on (past replays unchanged).
- `engine/rapid.py`: ATLAS's news window uses the same constants.
- `engine/account_b.py`: 7-day inactivity warning (pushed once a day from day 5) on ATLAS's 25K and the Rapid (whose count covers both lanes).
- `data/news/events.csv`: 2026-12-04 jobs, 2026-12-10 CPI, 2026-12-30 FOMC minutes (MFFU 2026 T1 calendar); 2027 FOMC minutes
  (Fed: 3 weeks after each meeting, derived).
- `research/props/firm_rules.json` rebuilt (min days now verified); tests/test_firms updated to match.

## Prices / promo (2026-11-17)
CLUB = 40% off any plan (site banner). Builder 50K $153 -> $91.80, 25K $105 -> $63 (= the owner's prices). **Rapid EOD 50K: list
$275, $165 with CLUB** (the ~$94 in STATE.md was 40% off the old August $157 list). New customers get 50% off a first eval (not the
owner). engine/account_b PLANS still says $94 for the Rapid: update it to the real price once it is bought.
