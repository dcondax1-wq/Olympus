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
