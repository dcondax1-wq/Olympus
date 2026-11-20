---
title: Skeptic check of the two live sizing patches (ATLAS funded switches in engine/account_b.py, ATLAS 10-tick sizing on the Rapid in engine/rapid.py) and card rapid-atlas-size-10t - both patches SAFE after one scope fix; the card HOLDS
family: second
date: 2026-11-20
status: account_b.patch FIX FIRST (one line: scope the repo-wide FUNDED_ON default to the builder25k plan, else it also cuts ATLAS on a funded combo 50K); engine/rapid.py atlas_slip patch SAFE; card rapid-atlas-size-10t HOLDS. Nothing live changed by this helper.
summary: Lead round 4 (owner said YES; the lead applies this weekend). (1) rapid-atlas-size-10t re-run with day-rapid's own tools/money/rapid25_launch.py on 1,000 paths at 10 ticks - week blocks (the card): lost Rapids 27.2 -> 24.0% / 38.0 -> 34.5%, -$141 / -$31 a month, DLL-pause days 1.13 -> 0 per 100 (exact); day blocks: 37.5 -> 32.2% / 40.7 -> 35.5%, -$93 / -$31; another seed: 26.5 -> 24.7% / 37.0 -> 32.5%, -$134 / -$38. Holds. Note: a flat $200 ATLAS cap is as safe or safer and pays more in a Jul-Oct-like market ($803 / 31.9%) but leaves 0.65 DLL-pause days per 100. (2) account_b.patch applied to a pc copy with FUNDED_ON = {funded_room_pct 0.4, streak_shrink 2}: never a larger size than today on 3,168 funded states (882 smaller), eval stage identical, Rapid lane untouched (RapidAtlas.size uses stack_qty), restart-safe (streak from saved closes), BE scratch books -$3.80 net = a loss (as the research). One real issue: FUNDED_ON is applied in account_b.normalize to EVERY spec, and engine/combo50k.ab_spec builds its funded ATLAS spec with that normalize -> room 40% would also cut ATLAS on a funded combo 50K, which no card covers. Exact fix given. The day-atlasedge test file fails 6 checks with the switch ON only because those checks assume OFF (APPLY_ON_YES step 3 says to update them); listed. (3) engine/rapid.py atlas_slip patch: loss1 only grows, PLANS key per plan, no crash path; SAFE.
runs: none (research/skeptic/rapid10t.py -> research/skeptic/rapid10t_{week,day,seed}.json; research/skeptic/on_check.py on a patched pc copy)
---

## For the owner

| What | Verdict | In $ |
|---|---|---|
| Card: Rapid 25K sizes ATLAS for its real fills (10-tick stop) | **HOLDS** | ~3-5 fewer lost Rapids per 100 in every test, for $31-38 a month (Jul-Oct-like) and $93-141 (Jan-Jun-like); no more days hitting MFFU's $500 pause |
| Patch: ATLAS funded 25K, room 40% + 2 losses -> 1 micro | **Safe after a one-line fix** | Can never trade bigger than today. Without the fix it would ALSO shrink ATLAS on a funded combo 50K, which you did not approve |
| Patch: Rapid ATLAS 10-tick sizing | **Safe** | Can only trade the same or smaller |

## 1. Card rapid-atlas-size-10t (1,000 paths, 10 ticks a side; $ a month / funded Rapid lost in 6 months / days over the $500 pause per 100)

| Paths | As built H1 | 10-tick H1 | As built H2 | 10-tick H2 | As built 2021-25 | 10-tick 2021-25 |
|---|---|---|---|---|---|---|
| week blocks (the card) | $1,883 / 27.2% / 1.13 | $1,742 / 24.0% / 0 | $800 / 38.0% / 0 | $769 / 34.5% / 0 | -$50 / 18.8% | -$46 / 17.1% |
| day blocks (funded paths) | $1,842 / 37.5% / 0.92 | $1,749 / 32.2% / 0 | $674 / 40.7% | $643 / 35.5% | -$50 / 18.4% | -$45 / 16.2% |
| other seed (101 / 11) | $1,853 / 26.5% / 1.15 | $1,719 / 24.7% / 0 | $773 / 37.0% | $735 / 32.5% | -$54 / 18.5% | -$50 / 15.8% |
| control: ATLAS flat $200 (week) | | $1,694 / 20.9% / 0.65 | | $803 / 31.9% | | -$49 / 17.1% |
| control: ATLAS flat $175 (week) | | $1,371 / 18.6% / 0.64 | | $846 / 30.2% | | -$49 / 15.8% |

Eval pass is unchanged (80.5 / 85.5%), eval fail slightly lower (H2 2.0 -> 1.2%). Verdict **HOLDS**: safer in every test at about
the claimed price. Honest note: part of the gain is "ATLAS smaller" - a flat $200 cap is as safe in Jul-Oct-like markets and pays
more there, but it keeps some $500-pause days; the 10-tick rule is the one that removes them. (Day-block note: only the funded
paths were day-shuffled; the eval paths are the card's week blocks.)

## 2. account_b.patch (day-atlasedge) with FUNDED_ON = {"funded_room_pct": 0.4, "streak_shrink": 2}

Applied with `git apply` to a pc copy (clean), FUNDED_ON flipped, then:

| Hunt | Result |
|---|---|
| Can a size get LARGER than today? | **No.** 3,168 funded states (rooms $20-6,000, stops 4-120 pts, day P&L -$590..+$300, streak 0-5): ON > OFF in 0, smaller in 882. `funded_cfg` takes min(preset pct, 0.4); `streak_cap` only turns 2+ into 1; `dll_guard` still runs last |
| Eval stage by mistake | No: both keys are read only in funded_cfg / funded_qty; 12 eval states identical ON vs OFF (even with loss_streak 9 in the state) |
| Rapid lane | Its spec gets the keys, but RapidAtlas.size sizes with engine/rapid.stack_qty and its own _funded_state (no loss_streak): no effect |
| **combo 50K (funded)** | **Affected.** engine/combo50k.ab_spec -> AB.normalize -> picks up FUNDED_ON, then AB.funded_qty applies room 40% (streak inert: no loss_streak in its state). No card or test covers the 50K -> **FIX FIRST** below |
| Double counting across accounts | No: loss_streak reads only this AccountB's own closes (state file per account; another Name's file is never read - their test b) |
| Scratch / BE | Closes are booked net (`q x (pts x $2 - $1.90)` incl. 1 tick), so a BE scratch is -$3.80 = a loss, exactly as the research counted. A close whose price is unknown books $0 and RESETS the streak (less protective, never bigger) |
| Restart / first funded day | Streak comes from the saved closes since the funded start; empty or None closes = 0; no start = no funded state (unchanged early return) |
| Crash path | loss_streak raises TypeError only on a malformed saved row (exit_t or pnl None). The bot never writes such rows (`_close` writes ints / floats) and today's sizing_state would already fail on a None pnl; optional hardening below |
| dll_guard / keep-trading (min_room 0, YES) | Order is preset -> learned cost -> member weight -> streak cap -> dll_guard: every step only lowers. The research arms (stuck 0.0) assume the keep-trading card, which is YES: consistent. With room 40% a tiny room skips more often than at 60% (e.g. room $60, 15-pt stop: 0.4 x $60 < $33 -> 0), as the research modelled |
| Live vs research timing | Live counts each close at once (2 losses the same day = 2); the research counted at the session end: live shrinks sooner, never later |

**FIX FIRST (exact edit, in the patch's normalize hunk):** keep the repo default to the 25K ATLAS account the cards are about:

```diff
-    sw = {k: (ab.get(k) if k in ab else FUNDED_ON.get(k)) for k in FUNDED_ON}
+    sw = {k: (ab.get(k) if k in ab else (FUNDED_ON.get(k) if plan == "builder25k" else None)) for k in FUNDED_ON}
```

(A block key still works for any plan, as documented.) Optional hardening in loss_streak: skip rows whose exit_t / pnl is not a
number (`try: float(c[2]); int(c[1]) except (TypeError, ValueError): continue`) so a corrupt saved row cannot stop ATLAS sizing.

Tests on the patched copy with the switch ON: tests/test_atlas_funded_switches 29/35. The 6 failures are the checks that assume
OFF (a: "ships all OFF", "block without keys has neither", "OFF sizes like today"; b: "switch OFF: no loss_streak key"; c: its
"today's size" baseline is itself 40% when ON; d: "a block without the key keeps 0.6") - APPLY_ON_YES step 3 says to update
them; they are not behaviour bugs. All d replays: 0 mismatches vs the research engine (97-225 trades a path).
**Verdict: FIX FIRST (the one line above), then SAFE.**

## 3. engine/rapid.py atlas_slip patch (day-rapid LEAD_WIRES section 3)

- `stack_qty(..., slip=SLIP)`: loss1 = (risk + slip) x $2 + $1.90 with slip 2.5 >= 0.25, so micros can only go down; the day-left
  term is unchanged; the 30% best-day cap still runs after. Default arg = today's behaviour for every other caller.
- `self.P.get("atlas_slip", SLIP)`: plan_info returns the PLANS entry, so only the 25K (where the key is added) changes; the 50K
  needs its own key (R2-3) - nothing else picks it up. No None path (key present = 2.5, absent = SLIP).
- Same formula as the research q10 in rapid25_launch.cmd_sizing (ATLAS only, LIT keeps 0.25): the live patch = what was measured.
- Mind the LEAD_WIRES "..." in the PLANS line: add the key, do not drop the others (eval_min_room, mffu_dll, ...).
**Verdict: SAFE.**
