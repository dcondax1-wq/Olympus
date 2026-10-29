"""Road to $10K / Stingray 3LT (engine/money_goal.py, engine/money_api.py, 2026-10-26): the stored per-account rates, the
owner's local figures file, "My goals" ($10K month, the Stingray 3LT by Feb 22 2027, the Z06), the 9-account stack and its
states, the next action, the goals / heartbeat / cloud / live.json wiring, the local-only form, and both dashboards' UI.

  python -X utf8 -m tests.test_money_goal          # ~5 s; every file it writes is in a temp dir
"""
from __future__ import annotations

import datetime as dt
import hashlib
import json
import os
import shutil
import subprocess
import sys
import tempfile
from zoneinfo import ZoneInfo

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)
from engine import money_goal as MG  # noqa: E402

ET = ZoneInfo("America/New_York")
RES = []


def check(name, cond, info=""):
    RES.append(bool(cond))
    print(("[PASS] " if cond else "[FAIL] ") + name + ("" if cond else f"  -> {str(info)[:400]}"), flush=True)


def ts(y, mo, d, h=12, mi=0):
    return int(dt.datetime(y, mo, d, h, mi, tzinfo=ET).timestamp())


def rd(p):
    with open(os.path.join(ROOT, p), encoding="utf-8") as fh:
        return fh.read()


NOW = ts(2026, 10, 26)                       # Monday 2026-10-26, the day of the owner's figures
REAL = os.path.join(ROOT, "data", "goals_money.json")


def digest(p):
    try:
        return hashlib.sha256(open(p, "rb").read()).hexdigest()
    except OSError:
        return None


def lit_pc(status="open", **kw):
    ev = {"start_balance": 50000.0, "balance": 49710.8, "profit": -289.2, "to_target": 3289.2, "target_balance": 53000.0,
          "floor": 48168.2, "room": 1542.6, "mll": 2000.0, "session": 6, "status": status, "start": "2026-10-19"}
    ev.update(kw)
    return {"id": "mffu50k_eval", "source": "pc", "kind": "eval", "conn": {"connected": True}, "eval": ev, "trades": []}


def extra(i, firm, plan, kind="eval", status="open", payouts=None, preset=None):
    a = {"id": i, "name": i, "source": "pc", "kind": kind, "extra": True, "firm": firm, "plan": plan, "eval": {"status": status}}
    if kind == "funded":
        a["funded"] = {"start": "2026-10-01", "preset": preset, "payouts": payouts or {}}
    return a


# ------------------------------------------------------------------------------------------------ a. the stored rates
def rate_checks():
    from tools import money_goal_rates as RT
    R = MG.load_rates()
    check("a. rates file read: MFFU 50K $915, 25K ATLAS $517, LucidPro $938, FundedNext $629 a month (H2 2026)",
          {k: R[k]["usd_month"] for k in MG.ORDER} == {"lit_b50": 915, "atlas_b25": 517, "lit_l50": 938, "lit_fn50": 629}, R)
    check("a. the fallback equals the file", all(R[k]["usd_month"] == MG.FALLBACK_RATES[k] and R[k]["usd_month_ref"] == MG.FALLBACK_REF[k]
                                                  for k in MG.ORDER), R)
    try:
        fresh = RT.build()
        stored = json.load(open(RT.OUT, encoding="utf-8"))
        check("a. money_goal_rates.json still equals the research files (uprisk_wincap, atlas_funded, funded_combo)", RT.same(stored, fresh),
              (stored.get("types"), fresh.get("types")))
    except FileNotFoundError as e:             # a sparse checkout without research/lit
        check("a. research files missing here: rates check skipped", True, e)
    with tempfile.TemporaryDirectory() as td:
        F = MG.load_rates(os.path.join(td, "none.json"))
        check("a. a missing rates file falls back to the stored numbers", F["lit_l50"]["usd_month"] == 938 and "fallback" in F["_meta"]["file"], F)


# ------------------------------------------------------------------------------------------------ b. defaults
def default_checks():
    D = MG.DEFAULTS
    check("b. defaults: $10K month by 2027-02", D["month_goal"] == 10000 and D["goal_by"] == "2027-02", D)
    check("b. defaults: 2024 Stingray 3LT, target $38,000, stretch $46,000, by 2027-02-22, ~$78K",
          D["car"]["name"] == "2024 Stingray 3LT" and D["car"]["target"] == 38000 and D["car"]["stretch"] == 46000
          and D["car"]["by"] == "2027-02-22" and D["car"]["price"] == 78000, D["car"])
    check("b. defaults: C8 Z06 $60,000, start $20,000 on 2026-10-26", D["z06"]["target"] == 60000 and D["start"] == {"usd": 20000.0, "day": "2026-10-26"}, D)
    c = MG.build({}, None, NOW)
    g1, g2, g3 = c["goals"]
    check("b. card title + three goals in order", c["title"] == "Road to $10K / Stingray 3LT" and [g["k"] for g in c["goals"]] == ["month", "car", "z06"], c["title"])
    check("b. goal titles", g1["title"] == "$10K month by February 2027" and g2["title"] == "2024 Stingray 3LT before I turn 19 (Feb 22, 2027)"
          and g3["title"] == "C8 Z06", [g["title"] for g in c["goals"]])
    check("b. no file: saved = the $20,000 start, 119 days left, $1,059 a week needed, pace unknown",
          g2["saved"] == 20000 and g2["days_left"] == 119 and abs(g2["need_week"] - 18000 / 17) < 0.01 and g2["status"] == "unknown", g2)
    check("b. the stretch marker sits at 38/46 of the bar", abs(g2["target_at"] - 38 / 46) < 1e-3 and g2["scale"] == 46000, g2)
    check("b. Z06: $20,000 of $60,000, no date", abs(g3["frac"] - 1 / 3) < 1e-3 and "no date" in g3["sentence"], g3)
    check("b. no figures: no summary lines, the month bar says to type them in", c["lines"] == [] and "nothing entered" in g1["sentence"], g1)
    check("b. card JSON < 12 KB", len(json.dumps(c, separators=(",", ":"))) < 12000, len(json.dumps(c)))


# ------------------------------------------------------------------------------------------------ c. the owner's file
def file_checks():
    with tempfile.TemporaryDirectory() as td:
        p = os.path.join(td, "data", "goals_money.json")
        r = MG.save({"jobs": 2900, "kalshi": 640}, p, now=NOW)
        check("c. save the month: jobs + Kalshi", r["ok"] and MG.load(p)["months"]["2026-10"] == {"jobs": 2900.0, "kalshi": 640.0}, r)
        r = MG.save({"savings": 21400, "savings_day": "2026-11-02"}, p, now=ts(2026, 11, 2))
        check("c. save a savings balance", r["ok"] and MG.load(p)["savings"] == [{"day": "2026-11-02", "usd": 21400.0}], r)
        r = MG.save({"savings": 21500, "savings_day": "2026-11-02"}, p, now=ts(2026, 11, 2))
        check("c. same day again replaces it", MG.load(p)["savings"] == [{"day": "2026-11-02", "usd": 21500.0}], MG.load(p)["savings"])
        r = MG.save({"settings": {"car": {"target": 40000, "stretch": 48000, "name": "2023 Stingray 3LT"}, "z06": {"target": 65000}, "publish": False}},
                    p, now=ts(2026, 11, 2))
        S = MG.load(p)["settings"]
        check("c. targets editable (car target / stretch / name, Z06, publish)", r["ok"] and S["car"]["target"] == 40000 and S["car"]["stretch"] == 48000
              and S["car"]["name"] == "2023 Stingray 3LT" and S["z06"]["target"] == 65000 and S["publish"] is False and S["car"]["by"] == "2027-02-22", S)
        before = digest(p)
        bad = [MG.save({"savings": -5}, p, now=NOW), MG.save({"savings": 100, "savings_day": "2027-05-01"}, p, now=NOW),
               MG.save({"savings": 100, "savings_day": "26/10/2026"}, p, now=NOW), MG.save({"arm": True}, p, now=NOW),
               MG.save({"settings": {"car": {"stretch": 1000}}}, p, now=NOW), MG.save({"settings": {"car": {"name": "<script>x</script>"}}}, p, now=NOW),
               MG.save({"settings": {"plan": {"kalshi_day_lo": 500, "kalshi_day_hi": 100}}}, p, now=NOW), MG.save({"jobs": "lots"}, p, now=NOW),
               MG.save({"month": "2026-13", "jobs": 5}, p, now=NOW), MG.save({}, p, now=NOW), MG.save({"settings": {"publish": "yes"}}, p, now=NOW)]
        check("c. bad input refused: negative, future day, bad day, unknown field, stretch < target, HTML, Kalshi lo > hi, text, bad month, empty, publish",
              all(not b["ok"] and b.get("error") for b in bad), [b.get("error") for b in bad])
        check("c. a refused save writes nothing", digest(p) == before)
        r = MG.save({"savings_delete": "2026-11-02"}, p, now=NOW)
        check("c. delete a savings entry", r["ok"] and MG.load(p)["savings"] == [], r)
        open(p, "w").write("{not json")
        check("c. a broken file reads as the defaults", MG.load(p)["settings"]["car"]["target"] == 38000 and MG.load(p)["savings"] == [])
        check("c. heartbeat block: None before the first save", MG.heartbeat_block(os.path.join(td, "none.json")) is None)
        q = os.path.join(td, "b.json")
        MG.save({"savings": 22000, "jobs": 1000}, q, now=NOW)
        hb = MG.heartbeat_block(q)
        check("c. default: the public phone site gets no savings / jobs / Kalshi (privacy, until the owner switches it on)",
              hb["hidden"] and "savings" not in hb["inputs"], hb)
        MG.save({"settings": {"publish": True}}, q, now=NOW)
        hb = MG.heartbeat_block(q)
        check("c. heartbeat block: the figures + targets", hb["inputs"]["savings"][-1]["usd"] == 22000 and hb["inputs"]["settings"]["car"]["target"] == 38000, hb)
        MG.save({"settings": {"publish": False}}, q, now=NOW)
        hb = MG.heartbeat_block(q)
        check("c. publish off: the heartbeat carries no savings / jobs / Kalshi", hb["hidden"] and "savings" not in hb["inputs"] and "months" not in hb["inputs"], hb)
        c = MG.build({}, hb, NOW)
        check("c. hidden card: no saved $ anywhere, targets still shown", c["hidden"] and c["saved"] is None and c["goals"][1]["saved"] is None
              and c["goals"][1]["target"] == 38000 and "20,000" not in json.dumps(c) and "22,000" not in json.dumps(c), c["goals"][1])
        g = MG.build({}, MG.local_block(q), NOW)
        check("c. the PC's local block always shows the figures", g["saved"] == 22000 and not g["hidden"], g["saved"])
    check("c. data/goals_money.json is gitignored", "data/goals_money.json" in rd(".gitignore"))


# ------------------------------------------------------------------------------------------------ d. My goals
def goal_checks():
    blk = {"v": 1, "t": NOW, "inputs": {"savings": [{"day": "2026-11-09", "usd": 21400}], "months": {"2026-11": {"jobs": 2900, "kalshi": -120}}}}
    data = {"accounts": [lit_pc(), extra("lucid2", "Lucid Trading", "LucidPro 50K", "funded", payouts={"2026-11-03": 2000}, preset="lucid_pro_50k")],
            "second": {"account_b": {"account": "FUND25K", "stage": "funded", "label": "ATLAS FUND25K",
                                     "funded": {"status": "funded", "payouts_n": 1, "payouts": {"2026-11-05": 500, "2026-10-20": 400}}}}}
    c = MG.build(data, blk, ts(2026, 11, 9))
    g1, g2, _ = c["goals"]
    check("d. month: jobs $2,900 + Kalshi -$120 + payouts to you (Lucid $2,000 x 90% + MFFU $500 x 80%) = $4,980",
          g1["jobs"] == 2900 and g1["kalshi"] == -120 and g1["prop"] == 2200 and g1["total"] == 4980 and abs(g1["frac"] - 0.498) < 1e-9, g1)
    check("d. month bar: a negative Kalshi month draws no segment, the legend keeps its $", [p["frac"] for p in g1["parts"]] == [0.29, 0.0, 0.22]
          and g1["parts"][1]["usd"] == -120, g1["parts"])
    check("d. month: October's payout is not November's", g1["prop_n"] == 2, g1)
    check("d. plan line: jobs $2,900 + Kalshi $2,250 + props $6,959 = $12,109 a month", g1["plan"]["full"] == 12109 and g1["plan"]["reaches_goal"], g1["plan"])
    check("d. car: pace from the $20,000 start to $21,400 two weeks later = $700 a week", g2["pace"]["usd_week"] == 700 and g2["pace"]["from"] == "2026-10-26", g2["pace"])
    check("d. car: behind by $6,100 at the current pace (15 weeks x $700 + $21,400 = $31,900)",
          g2["status"] == "behind" and g2["projected"] == 31900 and g2["gap"] == -6100 and "Behind by $6,100" in g2["sentence"], g2)
    fast = {"v": 1, "t": NOW, "inputs": {"savings": [{"day": "2026-11-09", "usd": 24000}]}}
    g = MG.build({}, fast, ts(2026, 11, 9))["goals"][1]
    check("d. car: on pace at $2,000 a week (+$16,000 over)", g["status"] == "on_pace" and g["gap"] == 16000 and "On pace" in g["sentence"], g)
    rich = {"v": 1, "t": NOW, "inputs": {"savings": [{"day": "2026-11-09", "usd": 39000}]}}
    g = MG.build({}, rich, ts(2026, 11, 9))["goals"][1]
    check("d. car: target reached, $7,000 to the stretch", g["status"] == "reached" and g["stretch_left"] == 7000 and g["frac"] == 1.0, g)
    g = MG.build({}, blk, ts(2027, 3, 1))["goals"][1]
    check("d. car: after Feb 22 2027 the date has passed", g["status"] == "late" and g["days_left"] == 0, g)
    check("d. summary lines once the owner saved figures", [x["k"] for x in c["lines"]] == ["money", "money_next"], c["lines"])


# ------------------------------------------------------------------------------------------------ e. the stack + next action
def stack_checks():
    from engine import scale_plan as SP
    st = MG.build({}, None, NOW)["stack"]
    check("e. empty data: 9 slots, all not bought, $6,959 a month once all funded, $404 in a 2021-25-like year",
          st["of"] == 9 and all(s["state"] == "not bought" for s in st["slots"]) and st["usd_month_all"] == 6959 and st["usd_month_ref_all"] == 404, st)
    check("e. slot counts: MFFU 50K x1, MFFU 25K x2 (ATLAS), LucidPro x4, FundedNext x2",
          [(g["label"], g["count"], g["bot"]) for g in st["groups"]] == [("MFFU Builder 50K", 1, "Zlarior"), ("MFFU Builder 25K", 2, "ATLAS"),
                                                                       ("LucidPro 50K", 4, "Zlarior"), ("FundedNext Rapid Daily 50K", 2, "Zlarior")], st["groups"])
    check("e. the 2nd ATLAS 25K says the bot runs ATLAS on one 25K today", "one 25K today" in (st["slots"][2]["note"] or "") and not st["slots"][2]["runnable"], st["slots"][2])
    c = MG.build({}, None, NOW)
    check("e. next with nothing bought: buy the MFFU 50K first", c["next"]["kind"] == "buy" and c["next"]["type"] == "lit_b50"
          and c["next"]["text"].startswith("Buy an MFFU Builder 50K eval (about $92)"), c["next"])
    # the owner today: the 50K eval runs (PC), ATLAS's 25K is in its eval (account B), business.json lists the 25K as planned
    data = {"accounts": [lit_pc()], "second": {"account_b": {"account": "MFFUEVBLD602936017", "eval": {"status": "open", "balance": 25100}}},
            "scale": {"accounts": [{"id": "mffu_50k", "strategy": "LIT", "type": "lit_b50", "stage": "eval", "src": "business.json"},
                                   {"id": "mffu_25k", "strategy": "ATLAS", "type": "atlas_b25", "stage": "eval", "src": "business.json + account B"}]}}
    c = MG.build(data, None, NOW)
    st = c["stack"]
    check("e. today: 50K eval + ATLAS 25K eval, no double count from the owner's list", [s["state"] for s in st["slots"][:3]] == ["eval", "eval", "not bought"]
          and st["bought"] == 2 and st["funded"] == 0, [s["state"] for s in st["slots"]])
    check("e. next: \"Buy 2 LucidPro 50K evals (about $231): code VIBES or ETFPROMO, check the total at checkout.\"",
          c["next"]["text"] == "Buy 2 LucidPro 50K evals (about $231): code VIBES or ETFPROMO, check the total at checkout."
          and "engine.multi_account --add" in c["next"]["how"] and "lucid_pro_50k" in c["next"]["how"], c["next"])
    # the owner's list alone (no bot data): business.json rows through the real scale_plan overlay
    rows = SP.overlay([{"id": "mffu_25k", "strategy": "ATLAS", "plan": "mffu_builder_25k", "label": "MFFU Builder 25K", "stage": "planned",
                        "start": "2026-10-26", "src": "business.json"}])
    sc = {"accounts": [{k: r.get(k) for k in ("id", "strategy", "plan", "type", "label", "stage", "src", "start")} for r in rows]}
    st = MG.build({"scale": sc}, None, NOW)["stack"]
    check("e. a planned account stays not bought with its planned day", st["slots"][1]["state"] == "not bought" and st["slots"][1]["note"] == "planned 2026-10-26", st["slots"][1])
    # later: Lucid x2 eval + 1 paying, FundedNext passed, the 50K failed, ATLAS funded with a payout ready
    data = {"accounts": [lit_pc("failed", room=0), extra("lucid1", "Lucid Trading", "LucidPro 50K (daily loss option on)"),
                         extra("lucid3", "Lucid Trading", "LucidPro 50K"),
                         extra("lucid2", "Lucid Trading", "LucidPro 50K", "funded", payouts={"2026-11-03": 2000}, preset="lucid_pro_50k"),
                         extra("fn1", "FundedNext Futures", "Rapid Daily 50K", status="passed"),
                         extra("b25", "MFFU", "Builder 25K")],                     # a Zlarior 25K: outside the plan
            "second": {"account_b": {"account": "FUND25K", "stage": "funded", "label": "ATLAS FUND25K",
                                     "funded": {"status": "ready", "ready": True, "max_request": 1000, "to_you": 800, "payouts_n": 1,
                                                "payouts": {"2026-11-05": 500}, "record_cmd": "python -X utf8 -m engine.account_b --payout <day>=<$>"}}}}
    c = MG.build(data, None, ts(2026, 11, 10))
    S = {(s["type"], s["n"]): s for s in c["stack"]["slots"]}
    check("e. states: 50K failed = not bought (buy again), ATLAS paying, Lucid paying + 2 eval, FundedNext passed",
          S[("lit_b50", 1)]["state"] == "not bought" and "failed" in S[("lit_b50", 1)]["note"] and S[("atlas_b25", 1)]["state"] == "paying"
          and [S[("lit_l50", i)]["state"] for i in (1, 2, 3, 4)] == ["paying", "eval", "eval", "not bought"] and S[("lit_fn50", 1)]["state"] == "passed",
          {k: v["state"] for k, v in S.items()})
    check("e. funded count 2 of 9, $ a month now = $517 + $938", c["stack"]["funded"] == 2 and c["stack"]["usd_month_now"] == 1455 and c["stack"]["paying"] == 2, c["stack"])
    check("e. next: the payout ready comes first", c["next"]["kind"] == "payout" and c["next"]["text"].startswith("Request $1,000 on ATLAS FUND25K")
          and "$800 to you" in c["next"]["text"], c["next"])
    data["second"]["account_b"]["funded"].update(ready=False, status="funded")
    c = MG.build(data, None, ts(2026, 11, 10))
    check("e. next: then the passed eval's switch to funded (FundedNext, its own words)", c["next"]["kind"] == "funded" and "FundedNext Rapid Daily 50K #1" in c["next"]["text"]
          and "FundedNext gives it" in c["next"]["text"] and "multi_account --set" in c["next"]["how"], c["next"])
    full = {"accounts": [extra("m50f", "MFFU", "Builder 50K", "funded", payouts={"2026-11-03": 1500}, preset="mffu_builder_50k")]
            + [extra(f"l{i}", "Lucid Trading", "LucidPro 50K", "funded", preset="lucid_pro_50k") for i in range(4)]
            + [extra(f"f{i}", "FundedNext Futures", "Rapid Daily 50K", "funded", preset="fn_rapid_daily_50k") for i in range(2)],
            "second": {"account_b": {"account": "FUND25K", "stage": "funded", "funded": {"status": "funded"}}},
            # the owner's list: ATLAS's first 25K (overlaid with account B) + a 2nd one he logged in business.json
            "scale": {"accounts": [{"type": "atlas_b25", "stage": "funded", "label": "MFFU 25K", "src": "business.json + account B"},
                                   {"type": "atlas_b25", "stage": "funded", "label": "MFFU 25K #2", "src": "business.json"}]}}
    c = MG.build(full, None, ts(2026, 12, 10))
    check("e. all 9 funded: $6,959 a month now, next = keep requesting the payouts", c["stack"]["funded"] == 9 and c["stack"]["usd_month_now"] == 6959
          and c["next"]["kind"] == "done", (c["stack"]["funded"], c["next"]))
    waits = {"accounts": [lit_pc()] + [extra(f"l{i}", "Lucid Trading", "LucidPro 50K") for i in range(4)]
             + [extra(f"f{i}", "FundedNext Futures", "Rapid Daily 50K") for i in range(2)],
             "second": {"account_b": {"account": "EV25K", "eval": {"status": "open", "balance": 25000}}}}
    c = MG.build(waits, None, NOW)
    check("e. everything the bot can run is bought: wait (the 2nd ATLAS 25K note as the how)", c["next"]["kind"] == "wait"
          and "Nothing to buy now" in c["next"]["text"] and "one 25K today" in c["next"]["how"], c["next"])


# ------------------------------------------------------------------------------------------------ f. goals / heartbeat / cloud / live.json
def wiring_checks():
    from engine import goals as G
    g = G.build({}, now=NOW)
    check("f. goals.build has the money part, no extra lines without figures", isinstance(g.get("money"), dict) and g["money"].get("title")
          and not any(x["k"].startswith("money") for x in g["lines"]), g.get("money", {}).get("error"))
    blk = {"v": 1, "t": NOW, "inputs": {"savings": [{"day": "2026-10-26", "usd": 20000}], "months": {"2026-10": {"jobs": 2900}}}}
    g = G.site_block({}, now=NOW, money=blk)
    check("f. site_block(money=...) carries the figures + 2 summary lines", g["money"]["goals"][0]["jobs"] == 2900
          and [x["k"] for x in g["lines"]][-2:] == ["money", "money_next"], g["lines"][-2:])
    g = G.build({"money_in": blk}, now=NOW)
    check("f. data['money_in'] works too (the PC's goals_data)", g["money"]["goals"][0]["jobs"] == 2900)
    b = rd("tools/build_web_dashboard.py")
    check("f. build_web_dashboard: the heartbeat's money into goals, not left in data.json / live.pc",
          'data["money_in"] = (st.get("pc") or {}).get("money")' in b and 'data.pop("money_in", None)' in b and '"learn", "money")' in b)
    cm = rd("tools/cloud_monitor.py")
    check("f. cloud monitor keeps the heartbeat's money block in state pc", '"brain", "second", "blitz", "ai", "launch", "money")' in cm)
    hb = rd("engine/heartbeat.py")
    check("f. heartbeat payload carries money (money_goal.heartbeat_block)", '"money": _money()' in hb and "money_goal.heartbeat_block()" in hb)
    na = rd("engine/next_api.py")
    check("f. next_api: goals_data reads the local figures, the money router is mounted", 'data["money_in"] = MG.local_block()' in na
          and "include_router(_money_router)" in na)
    from engine import live_publish as LP
    with tempfile.TemporaryDirectory() as td:
        q = os.path.join(td, "g.json")
        MG.save({"savings": 20500, "jobs": 2900, "kalshi": 300, "settings": {"publish": True}}, q, now=NOW)
        hbp = {"t": NOW, "running": True, "host": "SURFACE", "money": MG.heartbeat_block(q),
               "second": {"route": {"account_b": {"account": "EV25K", "eval": {"status": "open", "balance": 25000}}}}}
        out = LP.build(hbp, now=NOW, lm={})
    m = out.get("money") or {}
    check("f. live.json money: the card from the heartbeat (figures, ATLAS's eval in the stack)", m.get("saved") == 20500 and m["goals"][0]["kalshi"] == 300
          and m["stack"]["slots"][1]["state"] == "eval", m.get("error") or m.get("stack", {}).get("slots", [{}])[:2])
    check("f. live.json under 64 KB with the money card", len(json.dumps(out, separators=(",", ":"), default=str)) < LP.MAX_BYTES)
    big = {"money": m, "accounts": [], "pc": {}, "pad": "x" * 5000}
    f = LP.fit(json.loads(json.dumps(big)), max_bytes=6000)
    check("f. live.json fit: the money card is dropped before the board when too big", "money" not in f and f.get("trimmed"), list(f))


# ------------------------------------------------------------------------------------------------ g. the API (local-only form)
def api_checks():
    try:
        from fastapi import FastAPI
        from fastapi.testclient import TestClient
    except ImportError as e:
        check("g. fastapi missing: API checks skipped", True, e)
        return
    from engine import cloud_guard as CG, money_api as MA
    real0 = digest(REAL)
    with tempfile.TemporaryDirectory() as td:
        MA.PATH = os.path.join(td, "goals_money.json")
        MA._bot = lambda: None
        app = FastAPI()
        app.include_router(MA.router)
        C = {"local": TestClient(app, base_url="http://127.0.0.1:8766", client=("127.0.0.1", 50001)),
             "phone": TestClient(app, base_url="http://192.168.1.20:8766", client=("192.168.1.50", 50003)),
             "tunnel": TestClient(app, base_url="http://127.0.0.1:8766", client=("127.0.0.1", 50005), headers={"X-Forwarded-For": "203.0.113.9"}),
             "rebind": TestClient(app, base_url="http://evil.example:8766", client=("127.0.0.1", 50006)),
             "origin": TestClient(app, base_url="http://127.0.0.1:8766", client=("127.0.0.1", 50007), headers={"Origin": "http://evil.example"})}
        posts = sorted(r.path for r in MA.router.routes if "POST" in getattr(r, "methods", set()))
        check("g. the one POST route is a MONEY write, CLOUD_BLOCKED", posts == ["/api/next/money"] and all(p in CG.CLOUD_BLOCKED for p in CG.MONEY_WRITES), posts)
        r = C["phone"].get("/api/next/money")
        d = r.json()
        check("g. phone: GET the card (read-only, local false)", r.status_code == 200 and d.get("local") is False and d.get("title"), r.text[:200])
        for who in ("phone", "tunnel", "rebind", "origin"):
            r = C[who].post("/api/next/money", json={"savings": 99999})
            check(f"g. {who}: POST refused (403), nothing written", r.status_code == 403 and not os.path.exists(MA.PATH), r.text[:120])
        os.environ["LE_CLOUD"] = "1"
        try:
            r = C["local"].post("/api/next/money", json={"savings": 99999})
            check("g. LE_CLOUD=1: even this PC refused", r.status_code == 403 and "cloud" in r.json().get("error", ""), r.text[:120])
        finally:
            os.environ.pop("LE_CLOUD", None)
        r = C["local"].post("/api/next/money", json={"savings": 20250, "savings_day": "2026-10-26"})
        d = r.json()
        check("g. this PC: POST saves to the temp file and answers with the new card", r.status_code == 200 and d["ok"] and d["card"]["saved"] == 20250
              and MG.load(MA.PATH)["savings"][-1]["usd"] == 20250, r.text[:300])
        r = C["local"].post("/api/next/money", json={"savings": "a lot"})
        check("g. this PC: a bad value is a 400 with the reason", r.status_code == 400 and "Savings" in r.json().get("error", ""), r.text[:200])
        r = C["local"].post("/api/next/money", content="savings=5", headers={"Content-Type": "application/x-www-form-urlencoded"})
        check("g. this PC: non-JSON refused", r.status_code == 400, r.text[:120])
        r = C["local"].get("/api/next/money")
        check("g. this PC: GET local true + the saved balance", r.json().get("local") is True and r.json().get("saved") == 20250, r.text[:200])
        MA.PATH = None
    check("g. the real data/goals_money.json untouched", digest(REAL) == real0)


# ------------------------------------------------------------------------------------------------ h. read-only + UI
def readonly_ui_checks():
    for p in ("engine/money_goal.py", "engine/money_api.py"):
        src = rd(p)
        check(f"h. {p} is read-only to trading (no NinjaTrader / sizing / live model / routing)",
              not any(x in src for x in ("import ninjatrader", "from .ninjatrader", "from . import sizing", "live_model.json", "place_order",
                                         "set_route", "arm_b", "from .live import BOT\n        BOT.start")), p)
    src = rd("engine/money_goal.py")
    check("h. money_goal.py writes only its own file (one open for writing)", src.count('open(tmp, "w"') == 1 and src.count("os.replace(") == 1)
    a = rd("tools/web_public/moneycore.js")
    check("h. moneycore.js byte-identical on both apps", a == rd("web_next/js/next/moneycore.js"))
    idx = rd("tools/web_public/index.html")
    check("h. phone loads moneycore.js before goals.js v3", 0 < idx.find("moneycore.js?v=1") < idx.find("goals.js?v=3"))
    sw = rd("tools/web_public/sw.js")
    check("h. phone service worker bumped (le-public-v39+)", int(__import__("re").search(r"le-public-v(\d+)", sw).group(1)) >= 39)
    gj = rd("tools/web_public/goals.js")
    check("h. phone goals.js: My goals at the bottom of Home + the card at the bottom of #/goals, live.json preferred when newer",
          "${moneyHome()}</div>`" in gj and 'id="glMoney"' in gj and "window.LIVE.j.money" in gj and "MoneyUI.pick" in gj)
    cc = rd("web_next/js/next/cc.js")
    check("h. PC Goals page: the money card at the bottom (fillMoney)", "import { fillMoney } from './money.js'" in cc and 'id="ccMoney"' in cc
          and cc.index('id="ccMoney"') > cc.index("fundedCards(g.payout)"))
    mj = rd("web_next/js/next/money.js")
    check("h. PC money.js: the form only when the server says local, POST /api/next/money", "M.local ?" in mj and "method: 'POST'" in mj and "/api/next/money" in mj)
    node = shutil.which("node")
    if not node:
        check("h. node missing: JS checks skipped", True)
        return
    errs = []
    for p in ("tools/web_public/moneycore.js", "tools/web_public/goals.js", "tools/web_public/features.js"):
        r = subprocess.run([node, "--check", os.path.join(ROOT, p)], capture_output=True, text=True)
        if r.returncode:
            errs.append(p + ": " + r.stderr[-300:])
    for p in ("web_next/js/next/money.js", "web_next/js/next/cc.js"):
        r = subprocess.run([node, "--input-type=module", "--check"], input=rd(p), capture_output=True, text=True)
        if r.returncode:
            errs.append(p + ": " + r.stderr[-300:])
    check("h. node --check: moneycore.js, goals.js, features.js, PC money.js / cc.js parse", not errs, errs)
    blk = {"v": 1, "t": NOW, "inputs": {"savings": [{"day": "2026-11-09", "usd": 21400}], "months": {"2026-11": {"jobs": 2900, "kalshi": 640}}}}
    M = MG.build({"accounts": [lit_pc()]}, blk, ts(2026, 11, 9))
    with tempfile.TemporaryDirectory() as td:
        mp = os.path.join(td, "m.json")
        json.dump(M, open(mp, "w"))
        js = r"""
global.window = global;
global.document = { getElementById: () => ({}), head: { appendChild() {} }, createElement: () => ({}) };
require(process.argv[1]);
const M = JSON.parse(require('fs').readFileSync(process.argv[2], 'utf8'));
const U = window.MoneyUI;
const c = U.card(M, { where: 'phone' }), g = U.goals(M, { compact: true }), f = U.form(M);
const out = { title: c.includes('Road to $10K / Stingray 3LT'), next: c.includes('Next') && c.includes('Buy '), stack: c.includes('The stack') && c.includes('LucidPro 50K'),
  mygoals: c.lastIndexOf('My goals') > c.indexOf('The stack'), m: c.includes('$10K month by February 2027') && c.includes('mg-seg jobs') && c.includes('mg-seg kalshi'),
  car: c.includes('2024 Stingray 3LT before I turn 19 (Feb 22, 2027)') && c.includes('stretch $46K') && c.includes('goal $38K') && c.includes('behind by'),
  z06: c.includes('C8 Z06') && c.includes('no date'), compact: g.includes('compact') && !g.includes('The stack'),
  form: f.includes('data-mg-save="savings"') && f.includes('data-mg-save="month"') && f.includes('data-mg-save="settings"') && f.includes('mgCStretch'),
  pick: U.pick({ t: 1, goals: [] }, { t: 2, goals: [] }).t === 2 && U.pick({ t: 3, goals: [] }, { error: 'x' }).t === 3,
  err: U.card({ error: 'boom' }).includes('boom'), none: U.card(null).includes('no data'),
  esc: !U.card({ ...M, title: '<img src=x onerror=alert(1)>' }).includes('<img') };
console.log(JSON.stringify(out));
"""
        r = subprocess.run([node, "-e", js, os.path.join(ROOT, "tools", "web_public", "moneycore.js"), mp], capture_output=True, text=True)
        try:
            o = json.loads(r.stdout.strip().splitlines()[-1])
        except Exception:
            o = {"stderr": r.stderr[-400:]}
        check("h. node render: title, next, the stack, My goals at the bottom ($10K bar, Stingray with goal / stretch marks, Z06), Home cut, form, pick, errors, escaping",
              all(o.get(k) for k in ("title", "next", "stack", "mygoals", "m", "car", "z06", "compact", "form", "pick", "err", "none", "esc")), o)


def main(argv=None):
    real0 = digest(REAL)
    rate_checks()
    default_checks()
    file_checks()
    goal_checks()
    stack_checks()
    wiring_checks()
    api_checks()
    readonly_ui_checks()
    check("the real data/goals_money.json never touched by the tests", digest(REAL) == real0)
    n, ok = len(RES), sum(RES)
    print(f"\n{ok}/{n} passed")
    return 0 if ok == n else 1


if __name__ == "__main__":
    raise SystemExit(main())
