# Account rules: every MFFU rule for every account we have or are buying

Owner 2026-11-20: "make sure you have all the rules for each account memorized". One page per account, plain words.
Source of truth: `research/lit/mffu_rules.json` (MFFU's public help center + plan pages, each value with its URL and the
date checked). `python -X utf8 -m tests.test_account_rules` fails if a number the bot uses drifts from it.
Last full check: **2026-11-20**. Re-check anything older than 7 days before a buy or a payout.
**Daily watcher** (tools/rules_watch.py, 2026-11-23): every weekday after 17:05 ET the PC reads MFFU's own help pages (46 rules: DLL,
MLL, consistency, buffers, payout min / max, accounts per user, inactivity, news window, the Rapid $10,000 live day) and compares them
with this file. A real change = ONE phone alert "MFFU rule changed: <rule> was X, now Y (source); the bot still uses X until Claude
updates it" + a board line. A page that moved or did not load is reported, never called a change. Nothing is changed automatically.

Common to every MFFU account
| Rule | Value | Source |
|---|---|---|
| Day | opens 18:00 ET, everything auto-closed at **16:10 ET** (the bot is flat by **15:55**) | [permitted times](https://help.myfundedfutures.com/en/articles/9558251) |
| End-of-day trailing max loss | moves only at the close, up only; **open losses count** during the day (a dip through the floor fails it) | [EOD drawdown](https://help.myfundedfutures.com/en/articles/8348565) |
| Inactivity | **7 calendar days** with no trade = can be closed (sim profits forfeited, accounts bought from 2026-08-25) | [inactivity](https://help.myfundedfutures.com/en/articles/16596524) |
| Bots | allowed with your own settings; no high-frequency trading, nothing exploiting sim fills; only you trade it | [fair play](https://help.myfundedfutures.com/en/articles/8444599) |
| Hedging | banned: never long and short the same market (NQ + MNQ = one) at once, across all your accounts | rulebook `hedging` |
| Copy trading | allowed between your own accounts only | rulebook `multi_account` |
| Account limits | 10 evals at once; sim funded: Builder 50K x1, Builder 25K x2, Rapid EOD 25K x3, Rapid EOD 50K x3, **5 in all**; 1 live | [eval to funded](https://help.myfundedfutures.com/en/articles/16498635) |
| Limit conflict | the Builder 50K guide (2026-10-21) says "Only one Sim Funded account may be active per user at any time on the Builder Plan" | [Builder 50K guide](https://help.myfundedfutures.com/en/articles/14290805-builder-plan-50k-a-comprehensive-guide) |

## 1. Zlarior: Builder 50K EVAL (LIT)
| Rule | Value | Checked |
|---|---|---|
| Price | $91.80 (CLUB 40% off $153), one time, $0 activation | 2026-11-17 |
| Start / target | $50,000 -> pass at **$53,000** (+$3,000) | 2026-11-20 |
| Max loss | **$2,000** EOD trailing, stops at **$50,100** (start + $100) | 2026-11-20 |
| Daily loss | **$1,000 soft**: trading paused for the day, never a fail | 2026-11-20 |
| Size | max **4 minis / 40 micros** | 2026-11-20 |
| Consistency / min days | none in the eval / 1 day | 2026-11-17 |
| News | allowed (Builder is news-unrestricted) | 2026-11-20 |
| Bot extras (stricter) | flat 15:55; two_week sizing 40% of the room to session 80 (owner-approved) | - |

## 2. Zlarior: Builder 25K #2 EVAL (LIT)
| Rule | Value | Checked |
|---|---|---|
| Price | $63 (CLUB 40% off $105); one was $43 | 2026-11-17 |
| Start / target | $25,000 -> pass at **$26,500** (+$1,500) | 2026-11-20 |
| Max loss | **$1,000** EOD trailing, stops at **$25,100** | 2026-11-20 |
| Daily loss | **$600 soft** (pause) | 2026-11-20 |
| Size | max **2 minis / 20 micros** | 2026-11-20 |
| Consistency / news | none in the eval / allowed | 2026-11-20 |
| Bot extras (stricter) | stops trading when the room is under $100 (stuck) | - |

## 3. ATLAS: Builder 25K SIM FUNDED
| Rule | Value | Checked |
|---|---|---|
| Balance | MFFU shows it **from $0** (profit only); NinjaTrader shows $25,000 + profit | 2026-11-20 |
| Max loss | **$1,000** EOD trailing: the floor starts at -$1,000 and stops at **+$100**, then stays there (also after the 1st payout) | 2026-11-20 |
| Daily loss | **$600 soft** (pause) | 2026-11-20 |
| Size | max 2 minis / 20 micros, no scaling | 2026-11-20 |
| Buffer | **$1,100** must stay in the account | 2026-11-20 |
| First payout | profit at least **$250 above the buffer** ($1,350), **48 h** after the first funded trade | 2026-11-20 |
| Every payout | **$250 min, $1,000 max** a request; at least **2 traded days** in the cycle; the **best day <= 50%** of the cycle's profit (not a breach, trade more days); as often as every 2 days | 2026-11-20 |
| Split | **80%** to you ($1,000 asked = $800 lands) | 2026-11-20 |
| Payouts | **5 sim payouts, then MFFU moves you to live**; your other sim accounts go **dormant** (see 6) | 2026-11-20 |
| News / inactivity | allowed / 7 days | 2026-11-20 |
| Bot extras | the payout push waits for the max request: **$1,000 at $2,100 MFFU profit** ($27,100 on NinjaTrader; MFFU may allow less earlier, the bot says "MFFU would pay $X; your plan waits for $1,000 at $2,100"); ATLAS 1 micro under $100 room (owner yes) | - |

## 4. Builder 50K SIM FUNDED (when Zlarior passes)
| Rule | Value |
|---|---|
| Balance | from $0 on MFFU; floor starts at -$2,000, stops at +$100 |
| Daily loss / size | $1,000 soft / 4 minis, 40 micros |
| Buffer | **$2,100** (with the $1,500-max-loss add-on: $1,600) |
| First payout | **$500 above the buffer**, 48 h after the first trade |
| Every payout | **$500 - $2,000**, 2 traded days a cycle, best day <= 50%, every 2 days |
| Split / count | 80% / 5 sim payouts then live |
| Bot extras | funded sizing 60% of the room, <= $1,500 a trade, a winner <= $2,000; the payout push waits for the max request: **$2,000 at $4,100 MFFU profit** ($54,100 on NinjaTrader) |
All checked 2026-11-20 ([Builder 50K guide](https://help.myfundedfutures.com/en/articles/14290805-builder-plan-50k-a-comprehensive-guide)).

## 5. Rapid EOD 25K: EVAL and SIM FUNDED (LIT + ATLAS lanes)
| Rule | Eval | Sim funded |
|---|---|---|
| Price | **$97.20** (40% off $162), $0 activation | - |
| Balance | $25,000 -> pass at **$26,500** | from $0 on MFFU |
| Max loss | **$1,000** EOD trailing, stops at +$100 | the same; always keep **at least $100** (under = breached) |
| Daily loss | none at MFFU; **ours has the $500 option** = a soft pause until 18:00 ET | the same option |
| Size | **2 minis / 20 micros** (the plain Rapid 25K is 3/30: not ours) | 2 / 20 |
| Consistency | best day **<= 30%** of the profit | **none** |
| Min days | **4** trading days | not stated |
| News | allowed | **banned**: flat, no orders, **2 min before to 2 min after** FOMC, minutes, jobs, CPI |
| Payouts | - | **daily**, **$500 min, no max**, above the **$1,100 buffer**, each later one needs **$250 net since the last**, **90%** to you |
| Live | - | path not published for Rapid EOD |
| Bot extras (stricter) | soft day stop $500, a winning day kept under 30% x $1,500 x 0.95 | news window 3 min before / 2.5 min after; keeps $500 above the buffer; ATLAS $250 a trade |
Checked 2026-11-20 ([Rapid EOD 25K](https://help.myfundedfutures.com/en/articles/16727601-rapid-eod-25k-a-comprehensive-look),
[DLL version](https://help.myfundedfutures.com/en/articles/18337038-rapid-eod-with-dll-a-detailed-look),
[news policy](https://help.myfundedfutures.com/en/articles/8230009), [plan page](https://myfundedfutures.com/plans/rapid-eod)).

## 6. LIVE (Builder after its 5th payout)
| Rule | Value |
|---|---|
| Trigger | the **5th approved sim payout** (or the $100k sim cap, or the risk team); you cannot refuse |
| Your other accounts | sim funded -> **dormant** (not closed), evals dormant (a just-passed eval can be refunded); no sim and live at once |
| Max loss | $2,000 EOD trailing, static once the floor reaches $0 |
| Daily loss | $1,000 soft (50K) / $600 (25K) |
| Payouts | **daily**, $250 min, 80%; no consistency rule; no inactivity rule |
| Costs | CME pro data, commissions and platform come out of the live balance |
| Bots | allowed, must follow CME rules; nothing public about unattended |
| After a live breach | **21 days**: no sim trading, no new evals or resets |
| Rapid live | plain Rapid: automatic at $10,000 net in one day; up to $5,000 to a Reserve; several Rapids combined; all sims and new buys suspended |
Checked 2026-11-20 ([live FAQ](https://help.myfundedfutures.com/en/articles/12109396-comprehensive-faq-live-accounts-at-myfunded-futures),
[going live](https://help.myfundedfutures.com/en/articles/10101257), [Rapid live](https://help.myfundedfutures.com/en/articles/13134718-understanding-rapid-live)).

## Payout autopilot (engine/payout_autopilot.py, 2026-11-22)
Claude never requests a payout: the phone says when and how much, you click it in MFFU, then TRADE_HOME -> **P** records it.
How to request (MFFU help center, checked 2026-11-23): dashboard left menu **Payouts** ("Request and track your earnings",
[dashboard](https://help.myfundedfutures.com/en/articles/8229980-navigating-your-dashboard)). First payout only: **Personal Settings >
KYC**, a **Riseworks** account, then sign the Riseworks agreements MFFU emails you; paid in **6-12 business hours**
([first payout](https://help.myfundedfutures.com/en/articles/11542406-guide-to-your-first-payout-quick-and-easy-process)).
Not on those pages: the request button's name, the account picker, fees.
| What | When | Alert |
|---|---|---|
| Payout ready (Builder) | after the close (16:10 ET; half days 13:00 / 13:15), MFFU's rules met AND the max request ($1,000 25K / $2,000 50K) | "Payout ready: ATLAS 25K can request $1,000 now" + the MFFU clicks, once a cycle |
| Payout ready (Rapid EOD) | after the close, $500+ above the buffer + the bot's cushion, 25K: $250 net since the last | once a day (daily payouts), 90% to you |
| Builder payout #4 | the 4th ready | "(payout #4, the LAST)": after it close the account |
| Builder payout #5 | 4 recorded | ONE "do not take payout #5: close after payout 4"; when MFFU would pay a 5th: "do NOT take it" (5th = live, every sim sleeps) |
| Rapid $10,000 day | a Rapid day at $6,000+ net (one $10k day = MFFU moves it live) | at once, in the session |
| Record | TRADE_HOME -> P (pick, $, Y) | the account's own record + data/payout_ledger.json -> the Money pipeline / Corvette fund |

## Where the bot and MFFU differ (all stricter on our side, on purpose)
| Rule | MFFU | Bot |
|---|---|---|
| Flat time | 16:10 ET | 15:55 ET |
| Rapid funded news window | -2 / +2 min | -3 / +2.5 min |
| Rapid day stop | none / $500 option (25K) | $500 (25K), $1,000 (50K) soft |
| Rapid kept above the buffer | $100 minimum | $500 (25K), $1,000 (50K) |
| Builder 25K eval | runs to the floor | stops when the room is under $100 |
**Open conflict (MFFU's own pages):** one Builder funded account per user (50K guide) vs 1 x 50K + 2 x 25K (limits article). Today's
setup (ATLAS 25K funded + Zlarior's 50K and 25K #2 evals) is fine under both, but under the strict reading **Zlarior's 50K could
not become funded while ATLAS's 25K is** (expected about Dec 24). We follow the limits article; MFFU decides at the pass.
