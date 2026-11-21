"""Skeptic round 4: account_b.patch with FUNDED_ON ON vs OFF (never larger, eval untouched, scope). Run from the ROOT of a pc copy with the patch applied and FUNDED_ON flipped: python -X utf8 <this file>"""
import sys, json, os
sys.path.insert(0, os.getcwd())
import logging; logging.getLogger("engine.sizing").setLevel(logging.ERROR)
from engine import account_b as AB, second, combo50k as CB, rapid
from tests.test_account_b_funded import funded_block, eval_block
assert AB.FUNDED_ON == {"funded_room_pct": 0.4, "streak_shrink": 2}
sc = second.load_cfg(); base = json.load(open("live_model.json")).get("lit_sizing") or {}
on = AB.normalize(funded_block(), sc)
off = AB.normalize(funded_block(funded_room_pct=None, streak_shrink=None), sc)
print("spec on:", on.get("funded_room_pct"), on.get("streak_shrink"), "problem", on.get("problem"), "| off:", off.get("funded_room_pct"), off.get("streak_shrink"))
bigger, n, shrunk = [], 0, 0
for room in (20, 60, 99, 150, 300, 500, 887, 1200, 2000, 3500, 6000):
    for risk in (4.0, 8.0, 20.0, 35.0, 60.0, 120.0):
        for tgt in (None, 40.0, 120.0):
            for cum in (0.0, -250.0, -590.0, 300.0):
                for streak in (0, 1, 2, 5):
                    st = {"room": room, "cum": cum, "locked": False, "balance": 24000.0 + room - cum, "floor": 24000.0, "loss_streak": streak}
                    a = int(AB.funded_qty(on, {"risk_pts": risk, "tgt_pts": tgt}, dict(st), base=base)["qty"])
                    b = int(AB.funded_qty(off, {"risk_pts": risk, "tgt_pts": tgt}, dict(st), base=base)["qty"])
                    n += 1; shrunk += a < b
                    if a > b: bigger.append((room, risk, tgt, cum, streak, a, b))
print(f"funded grid {n} states: ON larger than OFF in {len(bigger)}; smaller in {shrunk}", bigger[:3])
# eval stage
se_on = AB.normalize(eval_block(), sc); se_off = AB.normalize(eval_block(funded_room_pct=None, streak_shrink=None), sc)
diff = 0
for room in (150, 500, 900, 1500):
    for risk in (8.0, 20.0, 40.0):
        st = {"room": room, "cum": 0.0, "locked": False, "balance": 25000.0, "floor": 25000.0 - room, "n_today": 0, "loss_streak": 9, "session": 3, "profit": 0.0, "target": 1500.0}
        diff += AB.qty(se_on, {"risk_pts": risk, "tgt_pts": 3 * risk}, dict(st), base=base)["qty"] != AB.qty(se_off, {"risk_pts": risk, "tgt_pts": 3 * risk}, dict(st), base=base)["qty"]
print("eval stage: sizes differing ON vs OFF:", diff, "of 12")
# combo50k funded (uses AB.normalize + AB.funded_qty): does the global switch reach it?
sp = CB.ab_spec({"account": "x"}, "2026-11-01", "funded")
print("combo50k funded spec gets:", sp.get("funded_room_pct"), sp.get("streak_shrink"))
# rapid ATLAS lane spec
rs = AB.normalize(rapid.atlas_block({"account": "Sim205", "plan": "rapideod25k", "stage": "funded", "funded_start": "2026-11-20"}))
print("rapid lane spec gets:", rs.get("funded_room_pct"), rs.get("streak_shrink"), "(RapidAtlas.size uses stack_qty, never funded_qty)")
# loss_streak robustness
for bad in (None, [], [["2026-11-20", None, -5.0, 1]], [["2026-11-20", 1795000000, None, 1]], [["2026-11-20", "1795000000", "-5", 1]]):
    try: print("loss_streak", repr(bad)[:50], "->", AB.loss_streak(bad, "2026-11-01"))
    except Exception as e: print("loss_streak", repr(bad)[:50], "-> CRASH", type(e).__name__, e)
