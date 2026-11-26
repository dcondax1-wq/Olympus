"""big-ofreal 2026-11-26: tools/of_realday_verdict.py (the one-command REAL-DATA verdict) + tools/build_of_room.py (the Order Flow
live room's JSON). Simulated days only (research/orderflow/of_sim.py), written in the exact pulled layout (data/pc_days/<day>/of +
trades.jsonl.gz) in a temp folder; no repo file written, no network, nothing that can trade.
    python -X utf8 -m tests.test_ofreal
"""
from __future__ import annotations

import datetime as dt
import gzip
import importlib.util
import json
import os
import sys
import tempfile
from zoneinfo import ZoneInfo

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)
ET = ZoneInfo("America/New_York")
RES: list = []


def check(name, ok, info=""):
    RES.append(bool(ok))
    print(("[PASS] " if ok else "[FAIL] ") + name + ("" if ok else f"  -> {str(info)[:400]}"), flush=True)


def load(path, name):
    sp = importlib.util.spec_from_file_location(name, os.path.join(ROOT, path))
    m = importlib.util.module_from_spec(sp); sp.loader.exec_module(m)
    return m


def main():
    from engine import ofsum
    V = load("tools/of_realday_verdict.py", "t_verdict")
    RB = load("tools/build_of_room.py", "t_room")
    Sim = load("research/orderflow/of_sim.py", "t_sim2")
    q = lambda *_: None
    with tempfile.TemporaryDirectory() as td:
        # no data
        o0 = V.run(src=os.path.join(td, "nothing"), out_json=os.path.join(td, "v0.json"), out_md=os.path.join(td, "v0.md"), say=q)
        check("no pulled day -> an honest 'no real day yet' line + the exact commands", o0["tick_days"] == 0 and "of_send_now" in o0["verdict_line"]
              and os.path.exists(os.path.join(td, "v0.md")), o0)
        # planted sim world written as pulled days (summaries + Zlarior ledger rows)
        W = Sim.world(45, "planted", seed=41, lvl=True)
        src = os.path.join(td, "pc_days")
        for d in W["days"]:
            od = os.path.join(src, d, "of")
            os.makedirs(od)
            R = W["R"][d]
            with gzip.open(os.path.join(od, "NQ_bars5m.csv.gz"), "wt") as fh:
                R["bars"].to_csv(fh, index=False)
            with gzip.open(os.path.join(od, "NQ_fp5m.csv.gz"), "wt") as fh:
                R["fp"].to_csv(fh, index=False)
            json.dump(R["meta"], open(os.path.join(od, "NQ_meta.json"), "w"))
            rows = []
            for t in W["lit"]:
                if t["day"] == d:
                    rows += [{"bot": "zlarior", "src": "main", "side": "buy" if t["dir"] == 1 else "sell", "entry_t": t["tn"], "stop": 1.0},
                             {"bot": "zlarior", "src": "main", "side": "exit", "entry_t": t["tn"], "t": t["tn"] + 900, "pnl": t["pnl"]}]
            rows.append({"bot": "atlas", "src": "acctb", "side": "buy", "entry_t": 5, "stop": 1.0})         # not Zlarior: ignored
            with gzip.open(os.path.join(src, d, "trades.jsonl.gz"), "wt") as fh:
                fh.write("\n".join(json.dumps(r) for r in rows))
        check("ledger_lit: Zlarior's entries + their $ from a pulled day (ATLAS rows ignored)",
              len(V.ledger_lit(os.path.join(src, W["days"][3]))) == sum(1 for t in W["lit"] if t["day"] == W["days"][3]))
        vj, vm = os.path.join(td, "v.json"), os.path.join(td, "v.md")
        o = V.run(src=src, lit=W["lit"], out_json=vj, out_md=vm, label="sim-planted", say=q)
        check("verdict on 45 pulled sim days: battery ran (look 1), lane A + both lane B scored", o["tick_days"] == 45 and (o["battery"] or {}).get("state") == "ran"
              and o["laneA"]["resolved"] >= 40 and o["laneB_replay"]["trades"] >= 20 and o["laneB_real"]["trades"] >= 20, {k: o.get(k) for k in ("battery", "laneA")})
        check("planted world: OF1 improves LIT in $ (paper lane B, replay) = YES", o["laneB_replay"]["verdict"].startswith("YES"), o["laneB_replay"])
        check("lane A has its pre-registered bar + p + both halves + taken/skipped R and $", all(k in o["laneA"] for k in ("p", "halves_diff_R", "taken", "skipped", "verdict"))
              and o["laneA"]["taken"].get("n"), o["laneA"])
        md = open(vm, encoding="utf-8").read()
        check("the one-page writeup: labelled SIMULATED, the decider (battery OF1) named, plain verdicts", "SIMULATED" in md and "decider" in md
              and "lane A" in md and "Forward score" in md, md[:300])
        check("forward score counts only days from 2026-11-27", o["forward_days"] == 0 and o["forward"]["taken_resolved"] == 0)
        # null world: no YES anywhere
        N = Sim.world(45, "null", seed=42, lvl=True)
        led = {}
        for t in N["lit"]:
            led.setdefault(t["day"], []).append({"t": t["tn"], "d": t["dir"], "stop": 0.0, "pnl": t["pnl"]})
        on = V.run(R=N["R"], lit=N["lit"], ledgers=led, out_json=os.path.join(td, "n.json"), out_md=os.path.join(td, "n.md"), label="sim-null", say=q)
        check("null world: no YES (lane A, lane B replay, lane B real, battery OF1)", not any(str(x).startswith(("YES", "PASS")) for x in
              (on["laneA"]["verdict"], on["laneB_replay"]["verdict"], on["laneB_real"]["verdict"], on.get("of1_decider"))), on["verdict_line"])
        # too few
        few = V.run(R={d: W["R"][d] for d in W["days"][:5]}, lit=W["lit"], ledgers={}, out_json=os.path.join(td, "f.json"), out_md=os.path.join(td, "f.md"), label="sim-few", say=q)
        check("5 days: TOO FEW (no verdict faked)", few["laneA"]["verdict"].startswith("TOO FEW") and few["laneB_real"]["verdict"].startswith("TOO FEW"), few["verdict_line"])
        # ---- the room JSON
        root = os.path.join(td, "root")
        os.makedirs(os.path.join(root, "data"))
        os.makedirs(os.path.join(root, "research", "orderflow"))
        os.symlink(src, os.path.join(root, "data", "pc_days"))
        json.dump(json.load(open(vj)), open(os.path.join(root, "research", "orderflow", "real_verdict.json"), "w"))
        r1 = RB.build(root)
        check("room (no live state): the newest pulled day through the paper bot, levels with reads", r1["source"].startswith("last recorded day")
              and r1["day"] == W["days"][-1] and r1["levels"] and all(L["read"] in ("absorbed", "not absorbed", "untouched") for L in r1["levels"]), r1)
        check("room: forward n / 20 + the verdict line from real_verdict.json", r1["forward"]["need"] == 20 and r1["verdict"]["line"], r1.get("forward"))
        txt = json.dumps(r1)
        check("room: Zlarior's lane B = take / skip + won / lost, no $ of a real trade (public site)", r1["lit"] and all(set(x) == {"t", "dir", "flow_says", "result"} for x in r1["lit"]),
              r1["lit"][:2])
        out = os.path.join(td, "of_room.json")
        n = RB.write(r1, out)
        check("room JSON small (< 40 KB)", n < RB.MAX_BYTES, n)
        # live state today wins
        from engine import of_paper as P
        S = P.replay_summary(W["R"][W["days"][-1]], W["days"][-1], W["R"][W["days"][-2]], W["days"][-2])
        today = dt.datetime.now(ET).strftime("%Y-%m-%d")
        S["day"] = today
        for r in S["rows"]:
            r["day"] = today
        json.dump(S, open(os.path.join(root, "data", "of_paper.json"), "w"), default=float)
        r2 = RB.build(root)
        check("room: today's live paper state wins over the replay", r2["source"] == "live" and r2["day"] == today and r2.get("rows") is not None, r2.get("source"))
    print(f"{sum(RES)}/{len(RES)} passed")
    return 0 if all(RES) else 1


if __name__ == "__main__":
    sys.exit(main())
