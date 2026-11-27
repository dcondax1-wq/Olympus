"""day-ofready2 2026-11-27: a full MONDAY DRY RUN of the order-flow lane through the real path, on REPLAYED REAL days.
Fake NinjaTrader folder (engine.ninjatrader._FakeNT) + fake Telegram; temp repo root; Sim only; nothing real can trade.

Path, day by day (a simulated clock): the owner's Telegram /oflane on -> the 5-min ops task's of_lane_kick at 09:20 (its popen
runs the runner `engine.of_lane loop` in-process: the real run_lock, heartbeat, tick) -> the live tick CSV (LE_TickRec format,
rebuilt from the PC's real 5m summary by tools/of_replay_ticks.py: same bars + footprint) -> of_paper decisions -> guards (the day
cap, the real news file, the half-day cut) -> Sim orders in the fake NinjaTrader (E5 limit / market) -> exits -> the loop exits
flat after 16:10 -> the 16:15 kick -> /oflane status, the ladder line, the lane fields the dashboard reads (of_room.json "lane",
the Brain feed line, the exported day file the PC ships).
Days: Monday 2026-11-23 (a Sunday Globex file before it: the Monday fix), 2026-11-26 (Thanksgiving, CME halt 13:00), and
2026-11-27 (the day after the half day, CME halt 13:15: its ticks = 2026-11-25's real day re-dated, the only re-dated one).
--full also runs 2026-11-24 and 2026-11-25. Needs data/pc_days (the real summaries); without them: SKIP (exit 0).
    python -X utf8 -m tests.test_of_dryrun [--full]
"""
from __future__ import annotations

import datetime as dt
import json
import os
import shutil
import sys
import tempfile
import time
from zoneinfo import ZoneInfo

import numpy as np

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)
sys.path.insert(0, os.path.join(ROOT, "tools"))
ET = ZoneInfo("America/New_York")
RES: list = []
OWNER = "424242"
PCD = os.path.join(ROOT, "data", "pc_days")
NEED = ["2026-11-20", "2026-11-22", "2026-11-23", "2026-11-24", "2026-11-25", "2026-11-26"]


def check(name, ok, info=""):
    RES.append(bool(ok))
    print(("[PASS] " if ok else "[FAIL] ") + name + ("" if ok else f"  -> {str(info)[:700]}"), flush=True)


class FakeTG:
    def __init__(self):
        self.queue, self.sent, self.n = [], [], 900

    def say(self, poll, text):
        self.n += 1
        self.queue.append({"update_id": self.n, "message": {"message_id": self.n, "date": int(time.time()), "text": text,
                                                            "chat": {"id": int(OWNER), "type": "private"},
                                                            "from": {"id": int(OWNER), "is_bot": False}}})
        self.sent.clear()
        poll.tick()
        return "\n".join(self.sent)

    def __call__(self, method, url, body=None, headers=None):
        q = json.loads(body.decode()) if body else {}
        if url.endswith("/getUpdates"):
            off = int(q.get("offset") or 0)
            return 200, json.dumps({"ok": True, "result": [u for u in self.queue if u["update_id"] >= off]})
        if url.endswith("/sendMessage"):
            self.sent.append(q.get("text") or "")
            return 200, json.dumps({"ok": True})
        return 404, "{}"


class NoControl:
    busy, done_path, calls = False, os.devnull, []

    def run_external(self, cmds, now, reply=None, tg=None):
        self.calls.append(cmds)
        return []


def main(argv=None):
    argv = sys.argv[1:] if argv is None else argv
    if not all(os.path.exists(os.path.join(PCD, d, "of", "NQ_meta.json")) for d in NEED):
        print("SKIP: the real summaries are not here (data/pc_days; tools/of_backfill.py --restore-only)")
        return 0
    from engine import of_lane as L, of_paper as P, ops_checks as OC, tg_cmd as T, atlas_exec as AX, ofsum, datapipe
    from engine.ninjatrader import _FakeNT
    import of_replay_ticks as RT
    import build_of_room as ROOM
    AX.is_on, AX.lanes = (lambda *a, **k: False), (lambda: [])          # no ATLAS Sim101 week in the temp world
    days = [("2026-11-23", None), ("2026-11-26", None), ("2026-11-27", "2026-11-25")]
    if "--full" in argv:
        days = [("2026-11-23", None), ("2026-11-24", None), ("2026-11-25", None), ("2026-11-26", None), ("2026-11-27", "2026-11-25")]
    td = tempfile.mkdtemp(prefix="of_dryrun_")
    root, nd = os.path.join(td, "repo"), os.path.join(td, "NinjaTrader 8")
    for sub in ("data", os.path.join("research", "evalplan"), os.path.join("research", "orderflow")):
        os.makedirs(os.path.join(root, sub), exist_ok=True)
    for f in (os.path.join("research", "evalplan", "ladder.json"), os.path.join("research", "orderflow", "real_verdict.json")):
        if os.path.exists(os.path.join(ROOT, f)):
            shutil.copy(os.path.join(ROOT, f), os.path.join(root, f))
    fake = _FakeNT(nd, price=25000.0)
    os.makedirs(os.path.join(nd, "le_feed"), exist_ok=True)
    R = {}
    for d in NEED:
        R[d] = ofsum.read(os.path.join(PCD, d))
        RT.write_rec_csv(RT.ticks_from_summary(R[d]), os.path.join(nd, "le_ticks", f"NQ_{d}.csv"))
    xs = RT.ticks_from_summary(R["2026-11-25"], RT.shift_seconds("2026-11-25", "2026-11-27"))
    RT.write_rec_csv(xs, os.path.join(nd, "le_ticks", "NQ_2026-11-27.csv"))
    tapes = {}
    from engine import tickrec
    for d, _ in days:
        x = tickrec.read_rec_csv(os.path.join(nd, "le_ticks", f"NQ_{d}.csv"))
        tapes[d] = (x.t_ns.to_numpy(np.int64) // 1_000_000, x.price.to_numpy(float))
    clock = [0.0]
    alerts = []
    orig_make = L.make_adapter

    def make(cfg, root_=None, nd_=None, clock=None):
        ad = orig_make(cfg, root_, nd_, clock=clock)
        ad._sleep = lambda s: (fake.process(), _adv(s))
        ad._alert_fn = alerts.append
        return ad
    L.make_adapter = make
    k_state = {"day": None, "k": 0, "last_kick": 0}
    kicks = []

    def market_to(t):
        d = k_state["day"]
        tt, px = tapes[d]
        j = int(np.searchsorted(tt, int(t * 1000), side="right"))
        if j > k_state["k"]:
            seg_t, seg_p = tt[k_state["k"]:j], px[k_state["k"]:j]
            b = seg_t // 5000
            for g in np.unique(b):
                p = seg_p[b == g]
                for i in sorted({int(np.argmax(p)), int(np.argmin(p))}):
                    fake.move(float(p[i]))
                fake.move(float(p[-1]))
            k_state["k"] = j
        fake.process()

    def _adv(s):
        clock[0] += s
        market_to(clock[0])

    runner = {"ran": 0, "why": []}

    def popen(argv_, **kw):                                   # the detached child, run here on the simulated clock
        assert argv_[-3:] in (["-m", "engine.of_lane", "loop"], ["-m", "engine.of_paper", "tick"]), argv_
        if argv_[-1] == "tick":
            return None
        runner["ran"] += 1

        def sleep(s):
            _adv(s)
            if int(clock[0]) // 300 != k_state["last_kick"] // 300:          # the 5-min ops task keeps running meanwhile
                k_state["last_kick"] = int(clock[0])
                kicks.append((int(clock[0]), OC.of_lane_kick(clock[0], root=root, popen=popen)))
                P.tick(now=clock[0], root=root, nd=nd)                        # the paper bot (its own detached child on the PC)
        runner["why"].append(L.loop(root, every=60.0, clock=lambda: clock[0], sleep=sleep,
                                    tick_fn=lambda **k: L.tick(**k, nd=nd, clock=lambda: clock[0])))
        return None

    # ---- the owner switches it on from Telegram (Sunday evening)
    fk = FakeTG()
    poll = T.TgCommands(NoControl(), cfg_fn=lambda: {"telegram": {"token": "1:a", "chat_id": OWNER}}, http=fk,
                        path=os.path.join(root, "data", "tg.json"), env={}, started_at=time.time())
    poll.oflane_root = root
    with open(os.path.join(nd, "le_feed", "accounts.csv"), "w") as fh:
        fh.write(f"name,t,cash\nSim101,{int(time.time()) + 10**9},100000\n")     # a fresh account list without Sim102
    json.dump({**L.DEFAULT_CFG, "nt_folder": nd}, open(os.path.join(root, "data", L.CFG_NAME), "w"))
    rep_on = fk.say(poll, "/oflane on")
    cfg = L.load_cfg(root)
    check("tg. /oflane on: ON, on Sim101 (Sim102 missing, Sim101 free), said plainly", cfg["on"] and cfg["account"] == "Sim101"
          and "Sim101" in rep_on and "Sim102" in rep_on, rep_on)
    per_day = {}
    for d, src in days:
        k_state.update(day=d, k=0, last_kick=0)
        e0 = dt.datetime.fromisoformat(d).replace(tzinfo=ET)
        clock[0] = e0.replace(hour=9, minute=10).timestamp()
        market_to(clock[0])
        r_early = OC.of_lane_kick(clock[0], root=root, popen=popen)
        n0 = runner["ran"]
        t = e0.replace(hour=9, minute=20).timestamp()
        clock[0] = t
        market_to(t)
        r_start = OC.of_lane_kick(t, root=root, popen=popen)          # runs the whole day inside (the runner)
        t_end = clock[0]
        r_1615 = OC.of_lane_kick(e0.replace(hour=16, minute=15).timestamp(), root=root, popen=popen)
        S = L.load_state(root)
        st = fk.say(poll, "/oflane status")
        per_day[d] = {"early": r_early, "start": r_start, "ran": runner["ran"] - n0, "why": runner["why"][-1] if runner["why"] else None,
                      "end": t_end, "S": S, "status": st, "pos": {k: v for k, v in fake.pos.items() if v[0]}, "src": src}
    L.make_adapter = orig_make
    # ---- checks per day
    for d, src in days:
        x = per_day[d]
        S = x["S"]
        lim = __import__("engine.cme_calendar", fromlist=["route_limits"]).route_limits(d)
        lab = f"{d}{' (2026-11-25 re-dated)' if src else ''}"
        check(f"{lab}: kick 09:10 = not due, 09:20 = started the runner once; it ran the day and left flat after 16:10",
              x["early"] is None and x["start"] == "started" and x["ran"] == 1 and x["why"] == "after 16:10 ET", (x["early"], x["start"], x["ran"], x["why"]))
        prev_d, Rp = P._prev_summary(d, nd, root)
        ref = P.replay_summary(R[src or d] if not src else ofsum.read(os.path.join(PCD, src)), d, Rp, prev_d) if not src else None
        rows = [r for r in S["paper"]["rows"] if r.get("lane") == "A" and r.get("day") == d]
        if ref is not None:
            a = {r["id"]: (r["d"], r["absorbed"], r["stop"], r["level"]) for r in ref["rows"]}
            b = {r["id"]: (r["d"], r["absorbed"], r["stop"], r["level"]) for r in rows}
            check(f"{lab}: lane decisions = the paper bot on the REAL summary (levels, side, absorbed, stop): {len(a)} candidates",
                  a == b, (sorted(set(a) ^ set(b)), [(k, a.get(k), b.get(k)) for k in a if a.get(k) != b.get(k)][:3]))
        if d == "2026-11-23":
            check("2026-11-23 Monday: the previous day = Friday 2026-11-20 (the Sunday Globex file joins the overnight range)",
                  prev_d == "2026-11-20" and [e[0] for e in (Rp or {}).get("extra") or []] == ["2026-11-22"], (prev_d, (Rp or {}).get("extra") and [e[0] for e in Rp["extra"]]))
        if d == "2026-11-27":
            check("2026-11-27 (the day after the Thanksgiving half day): the previous day = 2026-11-26 (its 09:30-13:00 range)",
                  prev_d == "2026-11-26", prev_d)
        tr = [t for t in S["trades"] if t.get("day") == d]
        taken = sorted((r for r in rows if r.get("taken")), key=lambda r: r["t_sig"])
        sent = [t for t in tr if t["status"] not in ("refused",)]
        ok_cap = len({L._ekey(t["entry_t"]) for t in sent if t.get("filled")}) <= 1 and all(
            t["row_id"] == taken[0]["id"] for t in sent) if taken else not sent
        check(f"{lab}: Sim orders only for the day's FIRST taken signal (day cap 1); later ones 'skipped: day cap'",
              ok_cap and all("day cap" in t.get("why", "") for t in tr if t["status"] == "refused" and taken and t["row_id"] != taken[0]["id"]),
              [(t["row_id"], t["status"], t.get("why")) for t in tr])
        late = [t for t in tr if t.get("filled") and (dt.datetime.fromtimestamp(t["decided_t"], ET).hour * 60 + dt.datetime.fromtimestamp(t["decided_t"], ET).minute) >= lim["entry_cut"]]
        check(f"{lab}: no entry at / after the entry cut {lim['entry_cut'] // 60}:{lim['entry_cut'] % 60:02d} ET"
              + (" (CME early close)" if lim["halt"] else ""), not late, late)
        opn = [t for t in tr if t["status"] in ("sending", "open", "fallback")]
        check(f"{lab}: every Sim trade closed (stop / target / flat time), no position left", not opn and not x["pos"], (opn, x["pos"]))
        if lim["halt"]:
            fl = [t for t in tr if t.get("filled") and t.get("exit_t") and (dt.datetime.fromtimestamp(t["exit_t"], ET).hour * 60
                                                                             + dt.datetime.fromtimestamp(t["exit_t"], ET).minute) > lim["flat"] + 1]
            check(f"{lab}: an open Sim trade is out by {lim['flat'] // 60}:{lim['flat'] % 60:02d} ET (5 min before the halt)", not fl, fl)
        check(f"{lab}: /oflane status names the account, today's trades and the ladder step",
              "Sim101" in x["status"] and "ladder" in x["status"].lower() and "today" in x["status"].lower(), x["status"])
        print(f"   {lab}: {len(rows)} paper candidates, {len(taken)} taken, lane trades: "
              + "; ".join(f"{t['row_id'].split('|')[-1]} {t['status']} {t.get('how', '')} {t.get('why', '')[:60]} "
                          f"{'' if t.get('pnl') is None else ('+' if t['pnl'] >= 0 else '-') + '$' + format(abs(t['pnl']), ',.0f')}"
                          for t in tr), flush=True)
    kk = [k for k in kicks if k[1] not in ("running", None, "off")]
    check("runner: every 5-min kick while it ran said 'running' (never a 2nd start)", not kk, kk[:5])
    check("runner: the 16:15 kick finds it already gone (it exits flat after 16:10), nothing stray",
          all(per_day[d]["S"] is not None for d, _ in days) and not os.path.exists(os.path.join(root, "data", L.RUN_NAME)))
    # ---- the dashboard fields
    room = ROOM.build(root, now=per_day[days[-1][0]]["end"])
    ln = room.get("lane") or {}
    check("dashboard: of_room.json carries the lane (on, Sim account, today's Sim trades, the plain line, no $)",
          ln.get("on") is True and ln.get("account") == "Sim101" and ln.get("sim") is True and isinstance(ln.get("today"), dict)
          and ln.get("line") and "$" not in json.dumps(ln), ln)
    from engine import brain_feed
    bf = json.dumps(brain_feed.of_bot(root, {}))
    check("dashboard: the Brain's order-flow room shows the lane line", "OF lane" in bf or "Sim" in bf, bf[:400])
    ex = os.path.join(root, "logs", "datapipe", "days", days[-1][0], "of", L.EXPORT_NAME)
    check("PC -> cloud: the lane's day file is exported next to the summaries (the nightly 'of' answer carries it)",
          os.path.exists(ex) and L.EXPORT_NAME in __import__("engine.datafeed", fromlist=["x"]).DAY_FILE.pattern, ex)
    fills = [r for r in datapipe.day_fills(days[0][0], root=root) if r.get("lane") == "oflane"]
    check("fill log: the Sim orders are lane 'oflane' in the unified fill log", fills or not any(
        t.get("filled") for t in per_day[days[0][0]]["S"]["trades"] if t.get("day") == days[0][0]), fills[:1])
    check("no alert about a real account, nothing named a non-Sim account in any order line",
          not any("MFFU" in ln_ for f in fake.files for ln_ in f[1]), [ln_ for f in fake.files for ln_ in f[1] if "Sim101" not in ln_ and ln_.startswith("PLACE")][:2])
    shutil.rmtree(td, ignore_errors=True)
    print(f"\n{sum(RES)}/{len(RES)} passed")
    return 0 if all(RES) else 1


if __name__ == "__main__":
    sys.exit(main())
