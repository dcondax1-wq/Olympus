# Decide cards: from 15 shown to 2 real decisions (2026-11-23)

The Decide list (tools/web_public/business/decisions.json) had 12 open cards, plus 1 "later" (the brief's count of 15 also counted
cards marked done: fixed). Each was checked against tonight's research. Nothing was deleted. Every card keeps its history:
`superseded` cards point at what replaced them (`superseded_by`), and `waiting` cards say what they wait for (`waiting_on`).
Nothing live changed.

## The 2 decisions for you
| # | Card | $ a month: Jan-Jun-like / Jul-Oct-like / 2021-25-like | Recommendation | What YES does |
|---|---|---|---|---|
| 1 | **plan-rapid50k-max2-rebuys**: buy one Rapid EOD 50K, at most 2 re-buys | **+$5,001 / +$2,282 / -$52** (worst case: 3 evals = $495) | **YES** | You buy it on MFFU (CLUB **$165**). The PC's Start page offers "New Rapid EOD 50K eval: Zlarior + ATLAS?": one tap adds it NOT armed. START BOT, then you type the phrase. Today's approved sizing. If it fails or dies: re-buy at most twice, then the slot stops (the fleet manager counts). |
| 2 | **fast-entry**: send orders on the minute's first trade, not 2 s later | about **+$100** (range $0-$161; no per-half split: 4 real fills, modelled) | **YES, as a 2-week test** | On the PC, once: `python -X utf8 -m engine.fast_entry --on` (undo: `--off`). No code change. Check ATLAS's next ~8 fills; if they are not better, switch it off. |

## Waiting on someone else (not a decision now)
| Card | Waiting on |
|---|---|
| plan-fundednext50k-max2-rebuys (+$1,679 / +$1,546 / -$28) | **FundedNext's written answer.** Its FAQ: "Using an EA that incorporates third-party applications such as Telegram or WhatsApp is strictly prohibited", and the bot's phone alerts are exactly that. |
| lucid-3-at-500-budget (+$1,786 / +$2,215 / -$112) | **Lucid's written OK** for a NinjaTrader bot (docs/LUCID_SETUP.md step 1), the Lucid red team, and the unverified $126 price. |
| rapid-funded-refit (+$541 / +$314 / -$1) | **The Rapid EOD 25K passing** (median about Jan 4). It changes the funded stage only, and comes back as a card that day. |

## Merged / retired (status superseded, history kept)
| Card | Replaced by | Why |
|---|---|---|
| buy-rapid50-now | plan-rapid50k-max2-rebuys | The same purchase, now with the 2-re-buy stop |
| refill-25k-with-rapid50 | plan-rapid50k-max2-rebuys | The fleet plan already makes the Rapid EOD 50K the buy for any open slot; engine/fleet_mgr offers it when a 25K dies |
| second-50k-eval-now | plan-rapid50k-max2-rebuys | The same slot is worth ~$2,282 a month as a Rapid 50K vs ~$63 as a 2nd Builder 50K eval; MFFU funds one Builder 50K |
| keep-1000-rapid | rapid-funded-refit | The same cushion knob, decided together |
| rapid25-lit-bank | research/writeups/rapid25-slot-2026-11-22.md | Tonight's study: the bank lane stays NO (eval fail 0.5% -> 3.1% at real fills); stays OFF |

## Later (not money-plan now)
- copilot-test: revisit after the first payout lands.
- kalshi-k8-gold-only: Claude's advice is no (about -$17 a month); nothing changes unless you ask.

Already answered before tonight (unchanged): payout-ping-1000 (no), zlarior-funded25 (no), atlas-on-50k-funded (done), atlas-on-rapid,
ask-mffu-parallel, cloud-alerts, atlas-funded-room-40, drop-lucid-account4, atlas-funded-keep-trading, atlas-funded-streak-1micro,
rapid-atlas-size-10t (yes), kalshi-stake-ladder (done), zlarior-atlas-50k (later, your answer).

Separate owner yes / no, not a card: the Rapid 50K's "LIT at half size in the eval" (research/handoff/2026-11-23/RAPID50K_SETTINGS.md).
