"""LIT learns from live (tools/lit_setups_learn.py, day-litlearn 2026-11-26). Research only.

  a. pure parts: sessions / Silver Bullet hours / bands, the first failing gate = engine/lit.setup_ok, "setups like it" drops a
     feature only when too few alike, the TESTED_AND_REJECTED search, the PC day folders' live words + trades (a fake gz folder)
  b. the real run into a temp folder (journal + brain_state copied in): every setup has one step, taken = the live model's trades,
     the gate ledger adds up (value = live net - opened net per span), every suggestion carries the 5 proof gates and only a full
     pass with no TESTED_AND_REJECTED hit is an owner card, the journal gets its lines and a 2nd run adds none, the Brain's LIT
     room is filled and the other pillars kept, no live file changed, market_learn_weekly takes --litlearn
Run: python -X utf8 -m tests.test_lit_setups_learn
"""
from __future__ import annotations

import gzip
import json
import os
import shutil
import sys
import tempfile

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)
from tests import agora_kit as AK  # noqa: E402
from tools import lit_setups_learn as LL  # noqa: E402

check = AK.check


def part_a():
    check("a. sessions: 02:00 London, 09:35 NY AM, 13:00 NY PM", [LL.sess_of(m) for m in (120, 575, 780)] == ["London", "NY AM", "NY PM"])
    check("a. Silver Bullet hours 03-04 / 10-11 / 14-15 ET only", [LL.sb_hour(m) for m in (179, 180, 239, 240, 600, 659, 840, 900)]
          == [False, True, True, False, True, True, True, False])
    check("a. VIX bands", [LL.vix_band(v) for v in (12, 15, 22, 25, None)] == ["VIX <15", "VIX 15-20", "VIX 20-25", "VIX 25+", None])
    from engine import lit
    P = {**lit.DEFAULTS, "depth": 0.5, "disp": 0.8, "idm_a": [1.0, 36, 1]}
    base = {"mod": 600, "depth": 1.0, "disp": 1.0, "idm": 1}
    got = [LL.first_gate({**base, **ch}, P) for ch in ({}, {"mod": 30}, {"depth": 0.4}, {"idm": 0}, {"disp": 0.7}, {"depth": 0.1, "disp": 0.1})]
    check("a. the first failing gate in setup_ok's order: none / hours 0 / sweep 2 / inducement 3 / displacement 4 / sweep before disp",
          got == [None, 0, 2, 3, 4, 2], got)
    # setup_ok agrees on 300 real candidates
    E = LL.Engine()
    vix = E.vix()
    vd = sorted(vix)
    zs = [z for z in E.C if z["day"] >= "2026-01-01"][:300]
    agree = sum((LL.first_gate(LL.features(E, z, vd, vix), E.P) is None) == lit.setup_ok(z, E.P, None) for z in zs)
    check("a. first_gate() == engine/lit.setup_ok on 300 real 2026 setups", agree == len(zs), (agree, len(zs)))
    rows = ([{"day": "2026-01-05", "r": 1.0, "sess": "London", "tdo": "discount", "depth": 1.0, "disp": 1.0, "vix_band": "VIX 15-20", "dir": 1}] * 20
            + [{"day": "2026-01-05", "r": -1.0, "sess": "London", "tdo": "discount", "depth": 1.0, "disp": 0.5, "vix_band": "VIX 15-20", "dir": 1}] * 3)
    s = LL.similar(rows, {"sess": "London", "tdo": "discount", "depth": 1.0, "disp": 1.0, "vix_band": "VIX 15-20", "dir": 1}, "2026-02-01")
    check("a. 'setups like it': all 6 features when >= 15 alike (20 won of 20)", s["n"] == 20 and s["won"] == 20 and len(s["on"]) == 6 and "long" in s["words"], s)
    s2 = LL.similar(rows, {"sess": "London", "tdo": "discount", "depth": 1.0, "disp": 0.5, "vix_band": "VIX 15-20", "dir": 1}, "2026-02-01")
    check("a. too few alike (3): it widens (drops dir, VIX, then displacement) to 23 setups, 20 won", s2["n"] == 23 and s2["won"] == 20 and "disp_b" not in s2["on"], s2)
    check("a. the future is never used (setups on / after the day are left out)", LL.similar(rows, rows[0], "2026-01-05")["n"] == 0)
    tmp = tempfile.mkdtemp(prefix="le_ll_")
    try:
        rp = os.path.join(tmp, "rej.md")
        open(rp, "w", encoding="utf-8").write("- intro\n- **More trades (2026-11-25):** depth 0.4/0.3, disp 0.7/0.6 ...\n")
        h = LL.rejected_hits(VAR := LL.VARIANTS["disp_0.6"][2], rp)
        check("a. TESTED_AND_REJECTED search finds 'disp 0.7/0.6' (line 2) for disp_0.6; nothing for idm_2",
              len(h) == 1 and h[0].startswith("line 2") and not LL.rejected_hits(LL.VARIANTS["idm_2"][2], rp), (VAR, h))
        d = os.path.join(tmp, "data", "pc_days", "2026-11-20")
        os.makedirs(d)
        with gzip.open(os.path.join(d, "decisions.jsonl.gz"), "wt", encoding="utf-8") as fh:
            fh.write(json.dumps({"t": 1795200000, "kind": "expired", "text": "SHORT limit 25,300 expired"}) + "\n")
            fh.write(json.dumps({"t": 1795200100, "kind": "box", "text": "ignored"}) + "\n")
        with gzip.open(os.path.join(d, "trades.jsonl.gz"), "wt", encoding="utf-8") as fh:
            fh.write(json.dumps({"bot": "lit", "mode": "live", "entry_t": 1795201000, "side": "SHORT", "pnl": -120.5}) + "\n")
            fh.write(json.dumps({"bot": "atlas", "mode": "live", "entry_t": 1795201000, "pnl": 50}) + "\n")
        L = LL.pc_live(["2026-11-20", "2026-11-19"], root=tmp)
        check("a. the PC's day folder: the Brain's 'expired' word + the live LIT short -$120 (ATLAS and boxes left out); a missing day = nothing",
              L == {"2026-11-20": {"words": [(1795200000, "expired", "SHORT limit 25,300 expired")], "trades": [(1795201000, -1, -120.0)]}}, L)
    finally:
        shutil.rmtree(tmp, ignore_errors=True)


def part_b():
    from engine import market_learn as M
    tmp = tempfile.mkdtemp(prefix="le_ll_")
    try:
        for f in ("journal.json", "brain_state.json"):
            shutil.copy(os.path.join(ROOT, "research", "learn", f), tmp)
        j0 = json.load(open(os.path.join(tmp, "journal.json"), encoding="utf-8"))
        before = M.hashes(ROOT)
        lines = []
        r = LL.step(tmp, say=lines.append)
        check("b. the step ran and said so", r.get("ok") and any("lit_setups: built" in x for x in lines), lines[-3:])
        if not r.get("ok"):
            return
        doc = r["doc"]
        E = LL.Engine()
        T = E.run()
        check("b. every setup has exactly one step; the steps add up to all setups", sum(s["n"] for s in doc["steps"]) == doc["setups"] > 5000, doc["steps"])
        check("b. taken = the live model's trades (same sessions)", doc["taken"] == len(T), (doc["taken"], len(T)))
        check("b. the setups run to the newest bar on disk (the live twin's weeks after the baseline list)", doc["data_end"] >= "2026-11-20", doc["data_end"])
        g = {x["gate"]: x for x in doc["gates"]}
        check("b. the 11 pre-registered gates, each with Jan-Jun / Jul-Oct / 2021-25", set(g) == set(LL.GATES) and all(set(x["spans"]) == {"H1", "H2", "2021-25"} for x in g.values()))
        Td = E.run(LL.GATES["disp"][2])
        F = E.F
        v = round(sum(t["pnl"] for t in LL._sp(F, T, "H2")) - sum(t["pnl"] for t in LL._sp(F, Td, "H2")))
        check("b. the ledger adds up: displacement gate Jul-Oct value = live net - opened net", g["disp"]["spans"]["H2"]["value"] == v, (g["disp"]["spans"]["H2"], v))
        S = doc["suggestions"]
        ok = all(set(s["gates"]) == {"pick_h1", "check_jul_oct", "y2021_25", "walk_forward", "trades_week"} and len(s["walk"]) == 7 for s in S)
        card = all((s["status"] == "adopted-needs-owner-yes") == (s["pass"] and not s["already_tested"]) for s in S)
        check("b. 13 suggestions, each through the 5 proof gates (7 walk-forward blocks); owner card only on a full pass + not already rejected",
              len(S) == len(LL.VARIANTS) and ok and card, [(s["name"], s["status"]) for s in S])
        check("b. the review: the newest 3 sessions, one plain sentence a setup", doc["review"] and len({x["day"] for x in doc["review"]}) == 3
              and all(x["words"].count(".") >= 1 and "setups like it" in x["words"] or "no alike" in x["words"] for x in doc["review"]), doc["review"][:2])
        J = json.load(open(os.path.join(tmp, "journal.json"), encoding="utf-8"))
        keys = {e["key"] for e in J}
        check("b. journal: a line per gate + suggestion + reviewed day, the old lines kept",
              all(f"litlearn|gate|{n}" in keys for n in LL.GATES) and all(f"litlearn|prop|{n}" in keys for n in LL.VARIANTS)
              and sum(k.startswith("litlearn|day|") for k in keys) == 3 and {e["key"] for e in j0} <= keys)
        r2 = LL.step(tmp, say=lambda *_: None)
        check("b. a 2nd run the same night adds no new journal line (same status = refreshed in place)", r2.get("ok") and r2["added"] == [], r2.get("added"))
        B = json.load(open(os.path.join(tmp, "brain_state.json"), encoding="utf-8"))
        room = B["pillars"]["lit"].get("setups") or {}
        check("b. the Brain's LIT room: funnel, costs / earns most, recent sentences; the other pillars kept",
              room.get("funnel") and room.get("recent") and "earns_most" in room and set(B["pillars"]) >= {"lit", "atlas"}, room)
        check("b. no live file changed (live_model*.json, engine/, ...)", M.hashes(ROOT) == before)
        size = os.path.getsize(os.path.join(tmp, "lit_setups.json"))
        check("b. lit_setups.json stays small (< 400 KB)", size < 400_000, size)
    finally:
        shutil.rmtree(tmp, ignore_errors=True)
    src = open(os.path.join(ROOT, "tools", "market_learn_weekly.py"), encoding="utf-8").read()
    check("b. market_learn_weekly --nightly --litlearn runs it after M.nightly", '"--litlearn"' in src and src.index("LL.step(") > src.index("br = M.nightly("))
    own = open(os.path.join(ROOT, "tools", "lit_setups_learn.py"), encoding="utf-8").read()
    check("b. lit_setups_learn never opens a live file for writing", "live_model" not in own.replace("live_model*.json", ""))


def main():
    part_a()
    part_b()
    return AK.finish()


if __name__ == "__main__":
    sys.exit(main())
