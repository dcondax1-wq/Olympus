"""day-oflearn 2026-11-26: the Order Flow pillar's PAPER bot (engine/of_paper.py, research/orderflow/DESIGN_paper.md).
Synthetic ticks only (research/orderflow/of_sim.py, planted absorption at the opening-range levels), written as LE_TickRec live
CSVs in a temp NinjaTrader folder; no data/ written in the repo, no network, nothing that can trade.
  a. replay = the research's own LVL entries + of_study._sim_df, trade for trade, over many days
  b. the live path (CSV -> tick() every 5 min, late decisions) = the same candidates; fills at / after the decision
  c. the planted edge shows: taken (absorbed) mean R > skipped
  d. kill switch, off switches, the window; e. Zlarior lane B; f. depth timing lane C
  g. engine/ops_checks hook (detached, locked), EOD line, Brain room line; h. safety (imports, files, nothing in the bot imports it)
    python -X utf8 -m tests.test_of_paper
"""
from __future__ import annotations

import ast
import datetime as dt
import importlib.util
import json
import os
import subprocess
import sys
import tempfile
from zoneinfo import ZoneInfo

import numpy as np

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)
ET = ZoneInfo("America/New_York")
RES: list = []
BANNED = ("engine.ninjatrader", "engine.live", "engine.tradovate", "engine.lit_live", "engine.account_b", "engine.account_c",
          "engine.multi_account", "engine.fleet", "server", "engine.guards")


def check(name, ok, info=""):
    RES.append(bool(ok))
    print(("[PASS] " if ok else "[FAIL] ") + name + ("" if ok else f"  -> {str(info)[:400]}"), flush=True)


def write_csv(x, path):
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with open(path, "w", encoding="utf-8") as fh:
        fh.write("t_ms,price,size,bid,ask\n")
        t = x.t_ns.to_numpy(np.int64) // 1_000_000
        for a, p, s, b, k in zip(t, x.price.to_numpy(), x["size"].to_numpy(), x.bid.to_numpy(), x.ask.to_numpy()):
            fh.write(f"{a},{p:.2f},{s},{b:.2f},{k:.2f}\n")


def write_depth(dp, path):
    os.makedirs(os.path.dirname(path), exist_ok=True)
    dp.to_csv(path, index=False)


def main():
    from engine import of_paper as P, ops_checks as OC, brain_feed
    B, M, _ = P._mods()
    sp = importlib.util.spec_from_file_location("t_sim", os.path.join(ROOT, "research", "orderflow", "of_sim.py"))
    Sim = importlib.util.module_from_spec(sp); sp.loader.exec_module(Sim)
    check("of_paper selftest (one day: paper = research)", P.selftest())
    # ---- a. replay parity + c. planted edge, 30 days
    W = Sim.world(30, "planted", depth_last=3, seed=31, lvl=True, keep_ticks=True)
    days = W["days"]
    n_ref = n_mine = bad = 0
    taken, skipped = [], []
    allrows = {}
    for k in range(1, len(days)):
        d0, d1 = days[k - 1], days[k]
        x = W["ticks"][d1][0]
        S = P.replay_frame(x, d1, W["R"][d0], d0)
        allrows[d1] = S["rows"]
        D = {d0: B.Day(d0, W["R"][d0]), d1: B.Day(d1, W["R"][d1])}
        ref = [r for r in M.entry_rows(D, [d0, d1], [], []) if r[0] == "LVL" and r[1] == d1]
        mine = [r for r in S["rows"] if r.get("usd_500") is not None]
        n_ref += len(ref); n_mine += len(mine)
        bad += sum(1 for a, b in zip(ref, mine) if abs(a[4] - b["usd_500"]) > 0.02 or a[3] != b["d"]) + abs(len(ref) - len(mine))
        for r in S["rows"]:                     # the planted sweeps: the opening-range level at the 10:00 bar
            if r.get("R") is not None and r["level"] in ("orh", "orl") and P._mod(r["t_sig"]) == 600:
                (taken if r["absorbed"] else skipped).append(r["R"])
    check(f"a. replay = research LVL entries + _sim_df over {len(days) - 1} days, trade for trade", bad == 0 and n_ref > 40, (n_ref, n_mine, bad))
    check("c. planted sweeps: absorbed mean R > not absorbed mean R (the gate sees the planted effect)",
          len(taken) >= 10 and len(skipped) >= 5 and np.mean(taken) > np.mean(skipped) + 0.5,
          (len(taken), round(float(np.mean(taken)), 2), len(skipped), round(float(np.mean(skipped)), 2)))
    one = all(sum(1 for r in rows if r["taken"] and r["t_sig"] < q["t_sig"] and (r.get("exit_t") or 1e12) > q["t_sig"]) == 0
              for rows in allrows.values() for q in rows if q["taken"])
    check("a. one paper position at a time (a signal while one is open = 'busy')", one)
    rr = [r for rows in allrows.values() for r in rows]
    check("a. every candidate logged with its gate read + v2/v3 readings", rr and all("absorbed" in r and isinstance(r.get("f"), dict)
          and "B10" in r["f"] and "K4" in r["f"] for r in rr if r.get("exit_t")), rr[:1])
    # ---- b. the live path on CSV files, late decisions (every 5 min at +97 s)
    with tempfile.TemporaryDirectory() as td:
        nd, root = os.path.join(td, "nt"), os.path.join(td, "repo")
        os.makedirs(os.path.join(root, "data"))
        d0, d1 = days[-2], days[-1]
        write_csv(W["ticks"][d0][0], os.path.join(nd, "le_ticks", f"NQ_{d0}.csv"))
        write_csv(W["ticks"][d1][0], os.path.join(nd, "le_ticks", f"NQ_{d1}.csv"))
        write_depth(W["ticks"][d1][1], os.path.join(nd, "le_ticks", "depth", f"NQ_{d1}.csv"))
        led = [{"side": "buy", "entry_t": 0, "stop": 0}]
        st = os.path.join(root, "data", "of_paper.json")
        e0 = dt.datetime.fromisoformat(d1).replace(tzinfo=ET)
        t_first = int((e0.replace(hour=9, minute=25)).timestamp())
        # Zlarior's ledger: one long at 11:00 (its sweep = the lowest low of the 6 bars before), result +$150
        te = int(e0.replace(hour=11).timestamp())
        led = [{"side": "buy", "entry_t": te, "stop": 1.0, "entry": 2.0, "result": {"ok": True}},
               {"side": "exit", "entry_t": te, "t": te + 900, "pnl": 150.0}]
        json.dump({"ledger": led}, open(os.path.join(root, "data", "live_state.json"), "w"))
        outs = []
        for now in range(t_first + 97, int(e0.replace(hour=16, minute=10).timestamp()), 300):
            outs.append(P.tick(now=now, root=root, nd=nd))
        S = json.load(open(st))
        ref = {r["id"]: r for r in allrows[d1]}
        live = {r["id"]: r for r in S["rows"]}
        check("b. live tick() ran every 5 min without error and wrote data/of_paper.json", all("error" not in o for o in outs) and S["runs"] > 70,
              [o for o in outs if "error" in o][:2])
        check("b. live candidates = the replay's (same levels, sides, gate reads)", set(ref) == set(live)
              and all(ref[i]["d"] == live[i]["d"] and ref[i]["absorbed"] == live[i]["absorbed"] for i in ref), (sorted(ref), sorted(live)))
        lat = [r for r in live.values() if r["fill"] is not None]
        check("b. live fills at / after the decision (decision = the first run after the close: +97 s late)",
              lat and all(r["fill_t_ms"] >= r["t_dec"] * 1000 and r["t_dec"] >= r["t_sig"] + 300 + 90 for r in lat), lat[:1])
        check("b. live outcomes resolved by the close (no open paper trade after 16:00)", all(r.get("exit_t") for r in live.values()), [r["id"] for r in live.values() if not r.get("exit_t")])
        lb = S["lit"]
        check("e. lane B: Zlarior's entry got an OF read at its sweep + its real result", len(lb) == 1 and lb[0]["decision"] in ("take", "skip", "no read")
              and lb[0]["pnl"] == 150.0, lb)
        tm = [r.get("timing") for r in live.values() if r.get("timing")]
        check("f. lane C (depth day): queue lean / alt price vs the paper fill logged", tm and all(("ticks_better" in t) or t.get("read") for t in tm), tm[:2])
        check("b. the plain line names trades, R and $", S.get("line", "").startswith("OF paper ") and "R" in S["line"], S.get("line"))
        # d. kill switch mid-day: no new taken trade after it, an open one closes "KILL"
        os.remove(st)
        x1 = W["ticks"][d1][0]
        Sk = P.replay_frame(x1, d1, W["R"][d0], d0, kill_at=int(e0.replace(hour=10, minute=2).timestamp()))
        check("d. kill switch: no paper entry after the kill", not any(r["taken"] for r in Sk["rows"] if r["t_dec"] >= e0.replace(hour=10, minute=2).timestamp())
              and any(r["why_not"] == "kill" for r in Sk["rows"]) or not Sk["rows"], [(r["id"], r["taken"], r["why_not"]) for r in Sk["rows"]])
        os.environ["LE_OFPAPER"] = "0"
        check("d. LE_OFPAPER=0 -> off", P.tick(now=t_first + 3600, root=root, nd=nd).get("off") is True)
        os.environ.pop("LE_OFPAPER")
        open(os.path.join(root, "data", "of_paper_off"), "w").close()
        check("d. data/of_paper_off -> off", P.tick(now=t_first + 3600, root=root, nd=nd).get("off") is True)
        os.remove(os.path.join(root, "data", "of_paper_off"))
        check("d. outside 09:25-16:10 ET -> no run", "skipped" in P.tick(now=t_first - 7200, root=root, nd=nd))
        check("d. no live file today -> skipped, nothing written", "skipped" in P.tick(now=t_first + 86400 * 3, root=root, nd=nd))
        # g. ops hook + EOD + Brain
        noon = int(e0.replace(hour=12).timestamp())
        calls = []
        r1 = OC.of_paper_kick(noon, real=True, root=root, popen=lambda *a, **k: calls.append((a, k)))
        r2 = OC.of_paper_kick(noon + 60, real=True, root=root, popen=lambda *a, **k: calls.append((a, k)))
        check("g. ops hook starts `-m engine.of_paper tick` detached, then locked for 4 min", r1 == "started" and r2 == "locked" and len(calls) == 1
              and calls[0][0][0][-3:] == ["engine.of_paper", "tick"][-3:] if False else (r1 == "started" and r2 == "locked" and len(calls) == 1
              and calls[0][0][0][-2:] == ["engine.of_paper", "tick"] and calls[0][1]["stdout"] == subprocess.DEVNULL), (r1, r2, calls))
        check("g. ops hook: weekend / night = not due", OC.of_paper_kick(int(e0.replace(hour=20).timestamp()), real=False, root=root) is None)
        S["day"] = dt.datetime.now(ET).strftime("%Y-%m-%d")
        json.dump(S, open(st, "w"))
        ln = OC.of_paper_line(dt.datetime.now(ET).timestamp(), root=root)
        check("g. EOD notice line = today's OF paper line", ln and ln.startswith("OF paper"), ln)
        ob = brain_feed.of_bot(root, {})
        check("g. Brain Order Flow room shows the OF paper line", "OF paper" in json.dumps(ob), ob)
    # ---- h. safety
    src = open(os.path.join(ROOT, "engine", "of_paper.py"), encoding="utf-8").read()
    t = ast.parse(src)
    imp = {a.name for n in ast.walk(t) if isinstance(n, ast.Import) for a in n.names} | \
          {("engine." if n.level else "") + (n.module or "") for n in ast.walk(t) if isinstance(n, ast.ImportFrom)} | \
          {f"engine.{a.name}" for n in ast.walk(t) if isinstance(n, ast.ImportFrom) and n.level for a in n.names}
    check("h. of_paper imports nothing that can trade", not any(i.startswith(b) for i in imp for b in BANNED), sorted(imp))
    check("h. no order words / order files in of_paper", not any(w in src for w in ("_route(", "order_file", "PLACE", "CLOSEPOSITION", "adapter.")))
    users = subprocess.run(["git", "grep", "-l", "of_paper", "--", "engine/live.py", "engine/lit_live.py", "server.py", "engine/ninjatrader.py",
                            "engine/bg_worker.py", "engine/account_b.py", "engine/account_c.py"], cwd=ROOT, capture_output=True, text=True).stdout.strip()
    check("h. nothing in the bot / live loop imports of_paper", users == "", users)
    ig = subprocess.run(["git", "check-ignore", "-q", "data/of_paper.json"], cwd=ROOT).returncode == 0 and \
        subprocess.run(["git", "check-ignore", "-q", "data/of_paper_cache/x.json"], cwd=ROOT).returncode == 0
    check("h. data/of_paper.json + its cache are gitignored (never block the PC's update)", ig)
    print(f"{sum(RES)}/{len(RES)} passed")
    return 0 if all(RES) else 1


if __name__ == "__main__":
    sys.exit(main())
