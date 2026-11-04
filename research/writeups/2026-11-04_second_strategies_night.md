---
title: Second strategies night - ATLAS and BLITZ on the 25K accounts (72 new versions, none beats today), how they correlate with LIT, and what 2 / 3 / 4 / 6 accounts would make a month after fees
family: other
date: 2026-11-04
status: no rule change for ATLAS or BLITZ (0 of 72 versions holds in both 2026 halves with the eval-speed and 2-week-fail tests); BLITZ is on a plateau and can go live on its own 25K as built; the best account set on MFFU is LIT 50K + ATLAS 25K + BLITZ 25K (3 funded accounts is the MFFU cap); a 4th or 6th MFFU account adds fees, not money; the Plutus app numbers (built 2026-10-19) are stale in 5 places
summary: Job 27. Part 1 - ATLAS (EMA + MACD + S/R) and BLITZ (noise-area scalp) re-tested for the 25K accounts with 43 BLITZ and 29 ATLAS versions (stop multiple, entry window, daily loss cap, trades a day, hold time, breakeven, trail, day filter, partials, fixed targets, time-of-day / weekday / LIT-result / LIT-direction size, member weights, risk caps, member subsets, the LIT-over-ATLAS-over-BLITZ rule). Part 2 - the same 2026 sessions drive every account (so a bad week hits all of them) through the MFFU Builder rules (eval, paperwork, funded, buffer, payouts at 80%, 50% best-day rule, funded caps) for 1 / 2 / 3 / 4 / 6 accounts. Part 3 - the Plutus plans.json is checked against the current numbers.
runs: sn_blitz_today, sn_blitz_half_off_1_5R, sn_blitz_hold_45, sn_blitz_stop_1_25atr, sn_atlas_armed_off
---

## For the owner (one minute)

| What | Result |
|---|---|
| BLITZ on its own 25K tomorrow | **Go as built.** 43 versions of the rule: none is better in both halves. Today (account C, never opposite LIT / ATLAS): Jan-Jun 217 trades (8.5 a week), Jul-Oct 106 (6.8 a week); eval 2-week pass / fail **36.1 / 37.8** and **36.2 / 34.8**; decided in 2 weeks 74 / 71%. Plan on **2 evals ($126)** before one passes. Money is small: slot $277 / $30 a month (research), model $191 / $140 after fees. |
| Stops on the 25K | BLITZ stop = 1.5 x ATR, median **61 pts = $125 risk per micro**. Eval size (40% of the $1,000 room = $400) is **3 micros** (1 to 5). At the funded $150 cap, **32% of trades already risk more than $150 with one micro** (min size 1 micro, so funded BLITZ risks $69-208 a trade). ATLAS: median stop 40 / 42 / 58 pts (EMA / MACD / S/R) = **5 / 5 / 4 micros at $500**; the 20-micro cap binds on 5% of EMA trades only. One ATLAS stop-out is half the $1,000 max loss; two in a day hit the $600 soft limit. |
| Anything better for BLITZ? | Best leads are neutral: half off at 1.5R (Jan-Jun -$117, Jul-Oct +$176 a month of the $500 view, slot unchanged); hold 45-60 min (Jul-Oct +$776 / +$10, Jan-Jun -$359 / -$1,079). Tighter stops (1.0-1.25 ATR), earlier last entry, fewer trades a day, 1R daily cap, other day filters all lose in one half or fail more evals. |
| Anything better for ATLAS? | **No.** 29 versions: members (all three is best in Jan-Jun), weights +-25%, risk caps $300-600, daily loss $300 / $450, time-of-day, weekday, size by LIT's result or direction. Nothing is better in both halves with no more 2-week fails. |
| LIT > ATLAS > BLITZ and no hedging | **Keep.** It costs BLITZ nothing (blocked: slot $277 / $30; not blocked: $241 / $2). For ATLAS the armed-LIT block gives up $570 / $1,086 of eval-path money in Jan-Jun / Jul-Oct, which is the price of the MFFU no-hedge rule: do not relax it. |
| Do they move together? | **No.** Daily correlation 2026: LIT x ATLAS **+0.14**, LIT x BLITZ **-0.06**, ATLAS x BLITZ **0.00** (R basis +0.20 / -0.06 / 0.00). All three lost on the same day 4 times in 206 sessions (independent: 2). Worst day of the three together -$1,616 (Jan-Jun), -$832 (Jul-Oct) vs -$2,257 / -$2,023 if their worst days coincided. |
| More accounts (model, after eval fees, owner's 80%) | **1 account** LIT 50K $718 / $477 a month (Jan-Jun / Jul-Oct); ATLAS 25K $623 / $519; BLITZ 25K $191 / $140. **2** (LIT + ATLAS) **$1,341 / $996**. **3** (LIT + ATLAS + BLITZ) **$1,532 / $1,136**, first payout median **19 / 29 sessions**, 0.5 fails and 0.9-1.0 evals bought a month ($56-59 a month in fees). **4** $1,635 / $1,175. **6** $1,669 / $1,203. |
| Why 4 and 6 do not pay | MFFU lets one person hold **1 funded Builder 50K and 2 funded Builder 25K**: 3 funded accounts. A 4th or 6th account waits or takes a slot from ATLAS (a LIT copy on a 25K earns $271 / $195 but pushes ATLAS from $623 to $480). Net: +$103 / +$39 (4) and +$137 / +$67 (6) over the 3, for $90 / $230 more fees in six months and **3x / 16x more weeks with two accounts failing together** (0.09 -> 0.29 -> 1.4 per six months). |
| Plutus app | **Stale in 5 places** (section 5): funded money understated about 20%, fail rate understated, 25K row is LIT not ATLAS / BLITZ, 0.85 correlation applies only to copies, first-payout definition differs. |

Tomorrow (max 5 lines):
1. Arm BLITZ on the new 25K as built (later-break size on). Expect 6-8 trades a week, about a 1-in-3 chance the first eval fails (budget $126), ~$140-190 a month after fees (model): it is the weak leg, keep it small.
2. Do not buy a 4th MFFU account: with LIT 50K + ATLAS 25K + BLITZ 25K you already hold the 3 funded accounts MFFU allows (model $1,136-1,532 a month after fees).
3. Keep LIT first, ATLAS second, BLITZ third and the armed-LIT block; change no ATLAS / BLITZ rule.
4. If you want more than 3 accounts, it has to be another firm (Lucid Pro 50K allows bots; price $115.40): copies of LIT there, not more ATLAS / BLITZ.
5. Do not use the Plutus numbers for decisions until plans.json is rebuilt (stale since 10-19).

## 1. Part 1 - the 25K strategies, version by version

Method: ATLAS = `tools/atlas_v2.score` (the real account-B rules, back-to-back evals from every 5th session) and BLITZ = `tools/blitz25k_lib` as account C with the MFFU Builder 25K eval / slot of `tools/blitz25k_size` (40% of the room then 100% from session 5, <= $600; $63 eval; 2 sessions paperwork; funded 10% / <= $150; payouts 80%; 300-path Monte Carlo, so a slot figure moves about +-$20 from noise). Pick on Jan-Jun 2026, check on Jul-Oct (2021-25 = reference only). Today's BLITZ size is the 10-30 pick (the later-break size on top was adopted 10-31 and is not in these rows; it is a size multiplier, rule unchanged). Costs in everywhere.

### 1a. New ideas (BLITZ) - Jan-Jun | Jul-Oct | 2021-25 ref

"$500 view" = $ a month if every trade risks $500; slot = whole 25K account $ a month after eval fees.

| Idea (version) | Trades/wk | $500 view $/mo | 2-week pass / fail | Slot $/mo | Verdict |
|---|---|---|---|---|---|
| **today** | 8.5 / 6.8 / 8.6 | +2,928 / +2,851 / +232 | 36.1 / 37.8 and 36.2 / 34.8 | +277 / +30 / -41 | bar |
| No LIT / ATLAS blocking at all | 8.6 / 7.0 | +2,713 / +2,508 | 35.3 / 38.7 and 31.9 / 33.3 | +241 / +2 | the rule helps a little |
| Stop 1.0 ATR / 1.25 ATR | 9.3 / 8.9 | +2,361 / +3,207 | 27.7 / 46.2 and 18.8 / 66.7 (1.25) | +67 / +254 | more fails |
| Stop 2.0 ATR / 2.5 ATR | 8.4 / 8.2 | +1,982 / +1,746 | 27.7 / 22.7 (2.0): slow, decided 50% | +241 / +198 | too slow |
| Last entry 13:00 / 14:00 / 14:30 / 15:00 | 4.4 / 5.9 / 6.6 / 7.5 | +1,937 / +2,090 / +2,238 / +3,047 | 26.9 / 21.0 ... 31.9 / 33.6 | +153 / +149 / +193 / +256 | the late checks earn; 15:00 equals today |
| Daily loss cap 1R / 1.5R / 2R | 7.5 / 8.4 / 8.4 | +2,439 / +2,990 / +3,010 | 35.3 / 40.3 (1R); same as today (1.5-2R) | +245 / +285 / +288 | 1.5-2R = today (never binds) |
| Max trades a day 2 / 3 / 4 | 4.3 / 5.8 / 7.1 | +1,586 / +1,898 / +2,545 | 21.8 / 37.8 ... 27.7 / 29.4 | +133 / +183 / +238 | fewer trades = slower and less |
| Hold 15 / 20 / 45 / 60 min | 10.6 / 10.6 / 8.4 / 6.8 | +1,924 / +2,585 / +2,569 / +1,849 | 27.7 / 23.5 ... 22.7 / 49.6 (60) | +114 / +162 / +195 / +68 | Jan-Jun worse |
| Hold 45 / 60 min (Jul-Oct) | | +3,627 / +2,861 | 33.3 / 43.5 and 37.7 / 36.2 | +39 / +73 (Jul-Oct); 2021-25 +581 / +587, slot -22 / -21 | Jul-Oct and 2021-25 up, Jan-Jun down: **lead, not a change** |
| Breakeven at 1R / 1.5R | 8.6 | +3,080 / +2,928 | 35.3 / 32.8 (1R); 1.5R = today | +290 / +277 | 1R: Jul-Oct slot +8 vs +30, passes 26% |
| Trail start 0.75 / 1.25 R, distance 1.0 / 2.0 ATR | 8.5-8.8 | +2,738 ... +2,820 | 31.9 / 42.0 (dist 1.0) | +263 ... +268 | today's trail is best |
| Day filter prior-range ratio >= 0.6 / 0.7 / 0.9 / 1.0 (today 0.8) | 10.8 / 10.1 / 7.5 / 6.2 | +2,286 / +2,612 / +2,597 / +2,119 | 36.1 / 50.4 (0.6); 34.5 / 47.9 (0.7) | +151 / +189 / +241 / +184 | more trades, more fails; 1.0 fails fewer in Jul-Oct (8.7%) but decides only 38% |
| **Half off at 1.5R** (partial on the 25K) | 8.5 / 6.8 | +2,811 / +3,027 | 37.8 / 37.8 and 36.2 / 31.9 | +274 / +34 | **neutral**: money -4% / +6%, fails 37.8 / 31.9 (Jul-Oct -2.9) |
| Half off at 0.75 / 1.0 / 2.0 R (1.0R then BE: slot +285 / +13) | | +2,448 / +2,686 / +2,854 | 33.6 / 35.3 ... | +265 / +267 / +275 | lose or equal |
| Fixed target 1.5 / 2.0 / 3.0 R instead of the clock | | +2,589 / +2,564 / +2,977 | 26.9 / 38.7 (1.5R) | +205 / +242 / +280 | 3R = today; shorter loses |
| Stop floor / ceiling in ATR units | 8.5 | = today (4 versions) | = today | = today | no effect: the stop is always 1.5 ATR; only a swing stop could be bounded |

(43 BLITZ versions in `research/scalp/sn_blitz.json`, the full table of every number.) **None holds in both halves with fails not up.** BLITZ's rule is on a plateau.

### 1b. New ideas (ATLAS) - 29 versions, `research/second/sn_atlas.json`

Test = the account-B v2 rule of `tools/atlas_v2.verdict`: 2-week pass not down, dead (fail + stuck) not up, eval-path $ up, in both halves; the 5-year line not worse. Today's ATLAS (25K, back-to-back evals): Jan-Jun 4.4 trades a week, 2-week pass / fail 65.5 / 0.0, path +$6,485 (eval-path $ less fees +$8,504 averaged over start days); Jul-Oct 3.3 a week, 43.5 / 0.0, +$4,434 (+$2,029).

| Idea | Jan-Jun 2w pass / eval-path $ less fees | Jul-Oct 2w pass / $ | Result |
|---|---|---|---|
| Members: EMA only / MACD only / S/R only | 42.9 / 41.2 / 40.3 ; $3.7k / $2.1k / $2.3k | 40.6 / 14.5 / 24.6 ; $2.5k / -$0 / $0.9k | each alone is worse and slower; all three is best in Jan-Jun |
| Members: MACD+S/R, EMA+S/R, EMA+MACD | 54.6 / 51.3 / 57.1 ; $5.1k / $5.6k / $6.0k | 24.6 / 43.5 / 44.9 ; $0.1k / $1.4k / $2.2k | dropping a member lowers money and trades a week (1.9-3.3) |
| Armed-LIT block off (hedge risk) | 62.2 ; $9.1k | 43.5 ; $3.1k | more money, **not allowed** (MFFU anti-hedge) |
| Member weight x0.75 / x1.25 (each) | EMA x1.25 68.1 ; $8.8k | 43.5 ; $2.1k | only EMA x1.25 is up in both halves, but 2025 and 2021-24 get worse (-$2.0k / -$4.3k vs -$1.8k / -$1.4k): fails the 5-year line |
| Risk cap per trade $300 / $400 / $500 / $600 | pass 32.8 / 47.1 / 57.1 / 63.9 ; med 11 / 10 / 8.5 / 7 sessions | 5.8 / 14.5 / 31.9 / 49.3 | a lower cap makes evals far too slow (the target cannot be reached in 2 weeks); $600 is Jul-Oct +5.8 pass but less money in both halves ($8.4k / $1.8k vs $8.5k / $2.0k) and Jan-Jun pass -1.6: no |
| Daily loss $300 / $450 | 58.0 / 65.5 | 40.6 / 43.5 | no gain |
| Size by time of day: London x1.25 + NY x0.75; NY x1.25; Tue/Wed x1.25; Monday x0.75 | 61.3 / 65.5 / 63.9 / 58.0 | 53.6 / 43.5 / 43.5 / 43.5 | London-up / NY-down: Jul-Oct pass +10 but Jan-Jun -4 and money lower: no |
| Size by LIT's result the same day: LIT already lost today x0.5 / x1.25; already won x1.25 / x0.75 | 58.0 / 63.9 / 65.5 / 65.5 | 43.5 all | LIT's result tells ATLAS nothing |
| Size by LIT's direction: with LIT x1.25; against LIT x0.75 | 65.5 / 65.5 | 43.5 / 43.5 | against x0.75: Jan-Jun fails 0 -> 3.4: no |

Nothing passes (0 of 29). ATLAS's earlier families (members, weights, orders, sizing, windows, weekdays, VIX bands, exits, entries: hundreds of versions in `atlas.md`, `atlas-edge-2026-10-30b.md`) are not repeated.

### 1c. Contribution, priority and correlation

- **Per strategy** (3-account model, Jan-Jun / Jul-Oct, net $ a month after eval fees): LIT 50K $718 / $477, ATLAS 25K $623 / $519, BLITZ 25K $191 / $140. ATLAS is the best use of a 25K account.
- **Daily correlation** (2026, 206 sessions): LIT x ATLAS +0.14 (Jan-Jun +0.15, Jul-Oct +0.06), LIT x BLITZ -0.06, ATLAS x BLITZ 0.00. Days LIT and ATLAS both traded: 75; both lost: 15 (12 if independent). LIT and BLITZ both traded 51 days, both lost 9 (9 if independent). All three lost 4 days (2 if independent).
- **Priority effects:** ATLAS and BLITZ never open against LIT; BLITZ is closed at LIT's opposite entry. 2026: blocked BLITZ trades are 4 of 221 (Jan-Jun) and 3 of 109; the rule is worth +$36 / +$28 a month of slot and lowers 2021-25 nothing.

## 2. Part 2 - the more-accounts plan (model)

What the model is (`tools/second_plan.py`, 400 paths of 126 sessions per row, 5-session blocks of 2026 sessions): every account sees the **same sampled sessions**, so a bad week hits all accounts that trade that day. One account = eval (MFFU Builder target / trailing max loss locked at start + $100 / soft daily loss), 2 sessions of paperwork, funded (buffer $2,100 / $1,100, first payout when the balance clears buffer + the minimum, payouts $500-2,000 / $250-1,000 at 80%, best day <= 50% of the cycle, 2 trading days a cycle, 5 payouts, the floor fixed at +$100 after the first payout), a breach buys a new eval ($91.80 for 50K, $63 for BLITZ and the LIT 25K copy, $43 for ATLAS 25K). Funded caps per person: 1 Builder 50K, 2 Builder 25K at once (`research/lit/mffu_rules.json`); an account that passes over the cap waits. Daily $ from the stored runs: LIT = run `lit_live` (LIT size rule), LIT 25K copy = 0.6 x, ATLAS = $500 risk a trade, BLITZ = $450 in the eval and $150 funded (a day capped at +$400); funded winner caps as the live presets ($2,000 on 50K, $1,000 on 25K).

Net $ a month = owner's 80% payouts minus every eval bought, averaged over 400 paths (Jan-Jun sessions | Jul-Oct sessions):

| Accounts | $ / month | 6-month net, 10th percentile | Paths with a net loss | Evals bought / fails a month (Jan-Jun) | First payout (median, sessions from purchase) | 6-month fees | Weeks with 2 accounts failing together (per 6 months) |
|---|---|---|---|---|---|---|---|
| 1: LIT 50K | 718 / 477 | +1,325 / -184 | 5.5% / 13.5% | 0.24 / 0.08 | 48 / 58 | $134 / $129 | - |
| 1: ATLAS 25K | 623 / 519 | +3,028 / +1,428 | 0% / 1% | 0.45 / 0.28 | 21 / 32 | $115 / $106 | - |
| 1: BLITZ 25K | 191 / 140 | -126 / -126 | 15% / 25% | 0.27 / 0.11 | 57 / 67 | $104 / $103 | - |
| 2: LIT 50K + ATLAS 25K | **1,341 / 996** | +5,168 / +2,930 | 0% / 0.2% | 0.69 / 0.36 | 20 / 30 | $249 / $235 | 0.03 / 0.02 |
| 2: LIT 50K + BLITZ 25K | 909 / 616 | +1,598 / +1,156 | 3% / 3.5% | 0.52 / 0.18 | 40 / 50 | $238 / $232 | 0.04 / 0.01 |
| **3: LIT 50K + ATLAS 25K + BLITZ 25K** | **1,532 / 1,136** | +5,292 / +3,549 | 0% / 0.5% | 0.96 / 0.46 | **19 / 29** | $353 / $337 | 0.09 / 0.07 |
| 4: + a LIT copy on a 25K | 1,635 / 1,175 | +5,092 / +3,180 | 0% / 0.5% | 1.19 / 0.53 | 19 / 29 | $445 / $426 | 0.29 / 0.23 |
| 6: + a 2nd ATLAS 25K + a 2nd BLITZ 25K | 1,669 / 1,203 | +4,596 / +2,748 | 0.5% / 1.5% | 1.65 / 0.65 | 21 / 30 | $587 / $578 | 1.42 / 1.40 |

Reading:
- **The 3-account mix is the MFFU ceiling.** Each step from 3 to 4 and 6 adds only $103 / $39 and $137 / $67 a month, takes funded slots from ATLAS (ATLAS falls from $623 to $480 with a LIT copy; a second ATLAS account makes the two together $637, only $14 more than one), and raises same-week failures 3x and 16x. The 10th-percentile 6-month net gets worse (+5,292 -> +5,092 -> +4,596 in Jan-Jun).
- **Fees are small against payouts:** about $56-59 a month for the 3 accounts (5.7-5.5 evals in six months), $96 a month for 6.
- **Time to first payout** (from the purchase): ATLAS 21 / 32 sessions; the 3-account set 19 / 29 (the first account to pay). LIT alone is slow here (48 / 58) because the model gives LIT its daily LIT-size-rule P&L, not the live two_week eval size; the repo's own numbers (uprisk.md) are 23-26 sessions from the start of the funded stage (add the eval sessions for a count from purchase). BLITZ alone: 57 / 67 and 15-25% of 6-month paths lose money after fees.
- **Model limits (read before using the $):** daily resolution, no stuck-room rule, sessions of 2026 only (no 2021-25 edge: those years lose, see `blitz-25k.md`, `atlas-funded.md`); LIT is under-modelled (sim $718 / $477 vs the repo's funded LIT 50K $929 / $915); ATLAS matches (sim $623 / $519 vs stored $582 / $517); BLITZ sim $191 / $140 vs stored slot $286 / $52 (later-break size) is in the same range. Treat the 3-account figure as $1,100-1,800 a month, not a promise: a flat or losing market (2021-25) makes every account lose.
- **Cap check:** the 6-account model buys 9.9 evals in six months and 3.9 of them fail (Jan-Jun), against 5.8 and 2.8 for the 3 accounts.

## 3. Part 3 - Plutus (`tools/web_public/plutus/plans.json`, built 2026-10-19) against today's numbers

| # | What Plutus says | What the repo says now | Verdict |
|---|---|---|---|
| 1 | MFFU Builder 50K funded $758 / $736 a month, steady $837 / $781 (Jan-Jun / Jul-Oct), net 6 months $618 / $562 a month | Funded 50K to the owner **$929 / $915** a month (uprisk.md, 2026-10-25: 60% of the room, <= $1,500, winner <= $2,000) | **Stale** (built before the 10-25 funded preset): Plutus is about 20% low |
| 2 | 2-week pass / fail 48.1 / 4.1 and 53.9 / 6.3 | Live eval (room 0.8, no weekly stop): 2-week pass / fail **52.9 / 17.8 and 58.6 / 20.9** (Monte Carlo, uprisk.md); the eval path in these tools 57.1 / 1.7 and 52.2 / 5.8 | **Inconsistent**: fail rate shown is far below what the live setting gives (the faster eval fails more) |
| 3 | First payout 43 / 47 sessions | Docs quote 23-26 (from the start of the funded stage); my model from purchase 48 / 58 for LIT alone | **Different definitions** (Plutus counts from purchase); make the label explicit |
| 4 | Builder 25K row: $293 / $219 a month, price $63 | That row is LIT on a 25K; the 25K accounts you run are **ATLAS $582 / $517 (price $43)** and **BLITZ $286 / $52 (price $63)** | **Missing rows**; the $63 ATLAS eval is $20 too expensive in the app |
| 5 | `corr` 0.85 between two accounts, "every account takes the same trades" | LIT x ATLAS +0.14, LIT x BLITZ -0.06, ATLAS x BLITZ 0.00 (2026 daily $) | **True only for copies of one strategy**; for the 3-strategy set diversification is real (joint-failure weeks 0.07-0.09 per six months, not near 1) |
| 6 | `trio` net $2,315 / $1,754 a month (months 4-6 $2,944 / $2,373) from the plans' LIT trades (composition not stated) | My 3-account MFFU mix $1,532 / $1,136 (conservative LIT) to $1,797 / $1,484 (sum of the repo's single-account figures, before fees) | Not comparable: composition not stated in the file; trio assumes three accounts on one strategy at 0.85 correlation |
| 7 | Caps: Builder 50K 1, 25K 2; split 0.8; 21 sessions a month | `mffu_rules.json`: same | **Consistent** |
| 8 | Lucid Pro / FundedNext rows | Only the Lucid Pro 50K and FundedNext Rapid Daily 50K figures are verified; caps are this app's assumption (noted in the file) | Consistent with the repo's own warning |

Fix (not done, out of scope): rebuild plans.json from `tools/funded_path.py` with the 10-25 presets and the live eval, add ATLAS 25K ($43) and BLITZ 25K rows, label first payout "from purchase".

## 4. Files and rerun

- `tools/second_night.py` (`blitz`, `atlas`, `corr`): results `research/scalp/sn_blitz.json` (43 BLITZ versions, 3 spans each: n, trades a week, $500 view, PF, 2-week pass / fail, decided, median pass, slot), `research/second/sn_atlas.json` (29 ATLAS versions with the v2 verdict), `research/second/sn_corr.json` (correlations, co-loss days, stop-fit), `research/second/sn_daily.npz` (the three 2026 daily series).
- `tools/second_plan.py` -> `research/second/sn_plan.json` (every plan, every span, per-account split). `PLAN_PATHS=1000` for more paths.
- Nothing in `engine/`, `second_model.json` or `live_model*.json` was touched; nothing armed.
