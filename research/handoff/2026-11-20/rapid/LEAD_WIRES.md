# LEAD_WIRES (day-rapid, 2026-11-20)

## 1. Register the new test (tests infra = day-quality's file)
tests/run_area.py, "fleet" list: add "rapid_launch" after "rapid25":
    "fleet": ["fleet_mffu", "copy_accounts", "firms", "fleet", "rapid", "rapid25", "rapid_launch", "news_official", ...
Proof: `python -X utf8 -m tests.test_rapid_launch` -> 11/11.

## 2. New Decide card (optional, owner yes/no) - append to tools/web_public/business/decisions.json "items"
{"id": "rapid-atlas-size-10t", "question": "Rapid 25K: size ATLAS for its real fills (assume a 10-tick worse stop)?",
 "why": "ATLAS's real fills are ~10 ticks worse than its backtest, so a full stop costs up to a third more than planned and can push the day past MFFU's $500 pause.",
 "impact": "-$31 a month in a Jul-Oct-like market (-$141 Jan-Jun-like, +$4 2021-25-like); fewer Rapids lost; same first payout date.",
 "impact_usd": -31, "options": ["yes", "no", "later"], "status": "open",
 "source": "research/writeups/rapid-launch-2026-11-20.md",
 "applies": "engine/rapid.py patch below (ATLAS's Rapid lane sizes on stop + 10 ticks); LIT unchanged",
 "added": "2026-11-20", "usd_month": -31, "usd_month_by": {"jan_jun": -141, "jul_oct": -31, "y2021_25": 4},
 "risk": "Funded Rapid lost in 6 months 27.2% -> 24.0% (Jan-Jun-like), 38.0% -> 34.5% (Jul-Oct-like); days over MFFU's $500 pause 1.1 per 100 -> 0; eval pass unchanged.",
 "recommend": "yes", "recommend_why": "Safer for a small cost: about 3-4 fewer Rapids lost per 100 for $31-141 a month.",
 "valued": "2026-11-20 tools/money/rapid25_launch.py sizing (ATLAS 10 ticks a side, 1,000 paths)"}
(If added: put "rapid-atlas-size-10t" in research/lab/rapid25_launch.json "cards" with recommend yes / usd_month -31 /
usd_month_by above, so tests.test_money_plan part b stays green; or leave "valued" without the tool name.)

## 3. Patch, ONLY after the owner's YES on rapid-atlas-size-10t (engine/rapid.py - live sizing)
    -    "mffu_rapid_eod_25k": {... "eval_min_room": 100.0,
    +    "mffu_rapid_eod_25k": {... "eval_min_room": 100.0, "atlas_slip": 2.5,   # owner yes 2026-11-xx: ATLAS sizes on stop + 10 ticks
    -def stack_qty(risk, room, cum, maxq, dll=1000.0, cap=ATLAS_USD) -> tuple:
    -    loss1 = (float(risk) + SLIP) * PV + COMM
    +def stack_qty(risk, room, cum, maxq, dll=1000.0, cap=ATLAS_USD, slip=SLIP) -> tuple:
    +    loss1 = (float(risk) + float(slip)) * PV + COMM
     (RapidAtlas sizing, ~line 540)
    -        q, usd, loss1 = stack_qty(risk, room, float(state.get("cum") or 0.0), int(R["max_micros"]), float(R["dll"]), cap)
    +        q, usd, loss1 = stack_qty(risk, room, float(state.get("cum") or 0.0), int(R["max_micros"]), float(R["dll"]), cap,
    +                                  float(self.P.get("atlas_slip", SLIP)))
Test to add to tests/test_rapid_launch.py f:
    q, usd, l1 = rapid.stack_qty(5.0, 1000.0, -400.0, 20, 500.0, 250.0, 2.5)
    check("f. 10-tick sizing: a real-fill full stop keeps the day >= -$500", -400.0 - q * ((5.0 + 2.5) * 2 + 1.9) >= -500.0)
Then Sim check (`tools/rehearse_day.py --rapid`), tests.test_rapid25.

## 4. STATE.md line (Recent findings)
- 2026-11-20 Rapid EOD 25K launch check (day-rapid, rapid-launch-2026-11-20.md, tools/money/rapid25_launch.py): MFFU rules = code (DLL $500 soft pause, resets 6 PM ET). Real fills: LIT + ATLAS $1,883 / $800 a month vs LIT $221 / $191, ATLAS alone $707 / $141; eval passes ~Dec 29-Jan 8, 1st payout ~Feb 10-18; 12-26% lose the first Rapid before a payout. atlas-on-rapid stays YES; rapid25-lit-bank -> NO (eval fail 0.5 -> 3.1%). New optional card rapid-atlas-size-10t (LEAD_WIRES). tests.test_rapid_launch 11/11 (START BOT, Board, PC report, alerts labels).

## 5. Regenerate research/writeups/INDEX.md (`python tools/writeups_index.py`) after merging (new write-up).

## 6. Cosmetic (not changed): the trades page / PC report call it "Rapid 25K" (tools/live_trades.ACCOUNTS), the phone alerts
"Rapid EOD 25K". Same account, both clearly the Rapid; unify only if the owner asks.

---------------------------------------------------------------------------------------------------------------------------
# ROUND 2 (2026-11-20, Rapid EOD 50K readiness; write-up research/writeups/rapid50-ready-2026-11-20.md)

## R2-1 BLOCKER before the owner buys the 50K (~late Dec): two Rapids at once
Today: engine/account_cli._add_rapid refuses a 2nd Rapid ("one Rapid only"); data/rapid.json = one block; LiveBot.acct_r = one
RapidAtlas; LIT lane id "rapid"; ATLAS order tag "acctr_", state live_state_acctr.json, push suffix ":acctr". With the 25K added
today, `/add-account/` -> Rapid EOD 50K answers NOT ADDED. Worth it: the 25K keeps ATLAS (+$609-1,662/mo vs LIT alone) AND the
50K gets it (+$1,500-4,100/mo vs LIT alone). Live code (engine/live.py, engine/rapid.py) = the lead's, Sim first. Spec:
  a. engine/rapid.py: slots "rapid" (data/rapid.json, unchanged = the 25K today, nothing migrates) and "rapid2"
     (data/rapid2.json). read/save/path/off take slot=; LANE_ID per slot ("rapid" / "rapid2"); RapidAtlas per slot with tag
     "acctr_" / "acctr2_", PUSH_SUFFIX ":acctr" / ":acctr2", state suffix "_acctr" / "_acctr2". Name must differ from every
     other account incl. the other Rapid (name_problem already takes others).
  b. engine/live.py: acct_r -> list self.acct_rs (one RapidAtlas per slot) at 372 / 651 (_start_rapid loops slots) / 721
     (tick each) / 772 (flatten each) / 2732-2780 (_rapid_block -> blocks; lane_spec per slot) / 2841. One position per
     NinjaTrader account is per Rapid (each pair LIT lane + RapidAtlas shares only its own account).
  c. engine/account_cli._add_rapid: when slot "rapid" is taken by another Name, use "rapid2" (refuse only when both are taken;
     MFFU caps 3 per size, 5 funded in all, already checked); remove() frees the right slot.
  d. labels: tools/live_trades.ACCOUNTS: acct_key maps ANY id starting "rapid" to "Rapid 25K" (line 46) -> map by the slot's
     plan: add ("rapid50", ("Rapid 50K", None, ("rapid2", "acctr2"))) or read the block's plan; engine/go.py:602 and
     launch_check.py:202 list every slot; board accounts.json row "Rapid EOD 50K" pc id "rapid2".
  e. tests: tests/test_rapid_launch.py pattern with TWO blocks (25K "Sim205" + 50K "Sim206"): both LIT lanes and both ATLAS
     lanes start; ATLAS on one never blocked by LIT on the other; one position per account each; alerts "Rapid EOD 25K" /
     "Rapid EOD 50K"; PC report labels "Rapid 25K" / "Rapid 50K"; removing one leaves the other; old single data/rapid.json =
     byte-identical behaviour (tests.test_rapid, test_rapid25, test_trade_alerts, test_cross_hedge green); tools/rehearse_day.py
     --rapid with both.
  Fallback if not built in time: buy the 50K anyway and make IT the Rapid (LIT + ATLAS), the 25K becomes a LIT-only extra
  account (preset mffu_rapid_eod_25k): $4,944 + $221 vs $1,883 + $803 a month (Jan-Jun-like) / $2,274 + $191 vs $800 + $791
  (Jul-Oct-like). Needs a CLI path to move the 25K to an extra (account_cli has none for a Rapid preset).

## R2-2 if the owner buys the DLL version of the 50K: engine/rapid.PLANS["mffu_rapid_eod_50k"] add "mffu_dll": 1000.0
(= the bot's own $1,000 day stop; the [OK] line then says "MFFU daily loss $1,000 = a pause"). No sizing change. Test: the
25K pattern in tests/test_rapid_launch f with plan_info("mffu_rapid_eod_50k")["mffu_dll"] == 1000.0.

## R2-3 10-tick ATLAS sizing on the 50K too (passes the pre-set bar: lost 22.7 -> 19.4% / 26.6 -> 22.7%, $ -3% / -1%)
Same patch as section 3 above, plus "atlas_slip": 2.5 in PLANS["mffu_rapid_eod_50k"]; covered by the existing
rapid-atlas-size-10t card if its text says "Rapid 25K and 50K" (suggested: question "Rapid accounts: size ATLAS for its real
fills (assume a 10-tick worse stop)?", risk + "50K: lost 22.7% -> 19.4% / 26.6% -> 22.7% for -$149 / -$21 a month").

## R2-4 changed on this branch (no live file)
tools/money/money_book.py USD_MONTH re-set to real fills (rapideod50 2,812 -> 2,295; rapideod25 972 -> 800): next_buy still
waits for the 50K (tests.test_money_ideas 17/17). tools/money/rapid25_launch.py r50 -> research/lab/rapid50_launch.json.
money-ideas-2026-11-20.md's "-$1,840 a month" is ~-$1,495 at real fills (H2); its text not edited (another helper's write-up).

## R2-5 STATE.md line
- 2026-11-20 Rapid EOD 50K ready check (day-rapid, rapid50-ready-2026-11-20.md): 5th slot stays the Rapid 50K at real fills ($4,944 / $2,274 a month with ATLAS on a 10-tick stop vs a 2nd Rapid 25K $1,742 / $769); eval ~23 trading days (92-94%), 1st payout ~40-48 trading days after the buy, 9-16% lose it first. Rules = code. BLOCKER: bot runs one Rapid only -> multi-Rapid build (LEAD_WIRES R2-1) before the buy.
