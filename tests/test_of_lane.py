"""night-of-lane 2026-11-27: the order-flow LANE (engine/of_lane.py) on a simulated NinjaTrader folder (engine.ninjatrader._FakeNT).
Synthetic tick days (research/orderflow/of_sim.py, planted absorption), written as LE_TickRec live CSVs; temp folders only, no
network, no repo data written, nothing real can trade (Sim102 in a temp folder; a non-Sim account is refused).
  a. a whole day driven every 60 s: the lane's paper rows = engine.of_paper.replay_frame's decisions; every routed trade is a
     taken paper row (side, stop); every taken row is routed or refused with a reason; exits close at the bracket / 15:55
  b. Sim-only refusal (switch, tick, adapter), OFF = nothing touched, the CLI words
  c. guards: kill (no entry + flatten), one position per account, the cross-account hedge, MFFU DLL, the EOD trailing floor,
     the half-day cut, news blackout, a stale decision, flat 15:55
  d. restart mid-trade: a new adapter + lane process picks the open bracket up, never sends twice, books the exit
  e. the unified fill log (engine.datapipe.day_fills) shows the lane as "oflane"; f. safety (no live words, gitignore)
    python -X utf8 -m tests.test_of_lane
"""
from __future__ import annotations

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


def check(name, ok, info=""):
    RES.append(bool(ok))
    print(("[PASS] " if ok else "[FAIL] ") + name + ("" if ok else f"  -> {str(info)[:600]}"), flush=True)


def write_csv(x, path):
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with open(path, "w", encoding="utf-8") as fh:
        fh.write("t_ms,price,size,bid,ask\n")
        t = x.t_ns.to_numpy(np.int64) // 1_000_000
        for a, p, s, b, k in zip(t, x.price.to_numpy(), x["size"].to_numpy(), x.bid.to_numpy(), x.ask.to_numpy()):
            fh.write(f"{a},{p:.2f},{s},{b:.2f},{k:.2f}\n")


class Rig:
    """A temp repo root + NinjaTrader folder with the fake NinjaTrader, a shared clock, the lane adapter."""

    def __init__(self, td, W, d0, d1, cfg=None, news=None):
        self.news = news if news is not None else []
        from engine import of_lane as L
        from engine.ninjatrader import _FakeNT
        self.L, self.W, self.d0, self.d1 = L, W, d0, d1
        self.nd, self.root = os.path.join(td, "NinjaTrader 8"), os.path.join(td, "repo")
        os.makedirs(os.path.join(self.root, "data"), exist_ok=True)
        write_csv(W["ticks"][d0][0], os.path.join(self.nd, "le_ticks", f"NQ_{d0}.csv"))
        write_csv(W["ticks"][d1][0], os.path.join(self.nd, "le_ticks", f"NQ_{d1}.csv"))
        x = W["ticks"][d1][0]
        self.tt = x.t_ns.to_numpy(np.int64) // 1_000_000
        self.px = x.price.to_numpy(float)
        self.fake = _FakeNT(self.nd, price=float(self.px[0]))
        self.now = [0.0]
        self.alerts = []
        json.dump({**L.DEFAULT_CFG, "on": True, "nt_folder": self.nd, **(cfg or {})},
                  open(os.path.join(self.root, "data", L.CFG_NAME), "w"))
        self.ad = None
        self.k = 0
        self.e0 = dt.datetime.fromisoformat(d1).replace(tzinfo=ET)

    def new_adapter(self):
        if self.ad is not None:
            self.ad.release_lock()
        self.ad = self.L.make_adapter(self.L.load_cfg(self.root), self.root, self.nd, clock=lambda: self.now[0])
        self.ad._sleep = lambda s: (self.fake.process(), self.now.__setitem__(0, self.now[0] + s))
        self.ad._alert_fn = self.alerts.append
        return self.ad

    def market_to(self, t):
        """Walk the fake NinjaTrader's price through the ticks up to t (each 5 s slice's extremes, in time order)."""
        j = int(np.searchsorted(self.tt, int(t * 1000), side="right"))
        if j <= self.k:
            return
        seg_t, seg_p = self.tt[self.k:j], self.px[self.k:j]
        b = (seg_t // 5000)
        for g in np.unique(b):
            m = b == g
            p, tm = seg_p[m], seg_t[m]
            i_hi, i_lo = int(np.argmax(p)), int(np.argmin(p))
            for i in sorted({i_hi, i_lo}):
                self.fake.move(float(p[i]))
            self.fake.move(float(p[-1]))
        self.k = j

    def run(self, t_from, t_to, every=60, hook=None):
        outs = []
        for t in range(int(t_from), int(t_to), every):
            self.now[0] = float(t)
            self.market_to(t)
            self.fake.process()
            if hook:
                hook(self, t)
            if self.ad is None:
                self.new_adapter()
            r = self.L.tick(now=t, root=self.root, nd=self.nd, ad=self.ad, news_events=self.news)
            outs.append(r)
            self.fake.process()
        return outs

    def hm(self, h, m=0):
        return int(self.e0.replace(hour=h, minute=m).timestamp())

    def S(self):
        return json.load(open(os.path.join(self.root, "data", self.L.STATE_NAME)))


def main():
    from engine import of_lane as L, of_paper as P, datapipe
    sys.path.insert(0, os.path.join(ROOT, "tools"))
    import fill_audit as tfa
    L.STEP_EVERY = 25                     # every 60 s run steps (the PC: 20 s, a 15 s loop)
    sp = importlib.util.spec_from_file_location("t_sim_lane", os.path.join(ROOT, "research", "orderflow", "of_sim.py"))
    Sim = importlib.util.module_from_spec(sp); sp.loader.exec_module(Sim)
    W = Sim.world(7, "planted", seed=31, lvl=True, keep_ticks=True)
    days = W["days"]
    # ---- a. whole days, same decisions as the paper bot
    n_taken = n_routed = n_closed = 0
    bad_dec, bad_route, bad_close, refusals, fill_rows = [], [], [], [], []
    hows, bad_tgt, nofill = {}, [], 0
    for k in range(1, len(days)):
        d0, d1 = days[k - 1], days[k]
        with tempfile.TemporaryDirectory() as td:
            g = Rig(td, W, d0, d1, cfg={"max_per_day": 9})   # every taken row routed (the day cap: tests.test_of_daycap)
            outs = g.run(g.hm(9, 25), g.hm(16, 6))
            S = g.S()
            ref = P.replay_frame(W["ticks"][d1][0], d1, W["R"][d0], d0)
            a = {r["id"]: (r["d"], r["absorbed"], r["taken"], r["stop"], r["level"]) for r in ref["rows"]}
            b = {r["id"]: (r["d"], r["absorbed"], r["taken"], r["stop"], r["level"]) for r in S["paper"]["rows"]}
            if a != b:
                bad_dec.append((d1, a, b))
            taken = {r["id"]: r for r in S["paper"]["rows"] if r["taken"]}
            n_taken += len(taken)
            for tr in S["trades"]:
                row = taken.get(tr["row_id"])
                if row is None or tr["d"] != row["d"] or tr["stop"] != row["stop"]:
                    bad_route.append((d1, tr))
                if tr["status"] == "refused":
                    refusals.append(tr["why"])
                elif tr["status"] == "closed" and not tr.get("filled") and str(tr.get("why")).startswith("no fill"):
                    nofill += 1
                    hows["limit, stop first (no trade)"] = hows.get("limit, stop first (no trade)", 0) + 1
                elif tr.get("filled"):
                    n_routed += 1
                    hows[tr["how"]] = hows.get(tr["how"], 0) + 1
                    o = g.fake.orders.get(tr.get("target_id") or "")
                    want = tr["fill_px"] + 2 * (tr["fill_px"] - tr["stop"])      # 2R from the fill
                    if not o or abs(o["limit"] - want) > 0.25 + 1e-9:
                        bad_tgt.append((tr["id"], o and o["limit"], want))
                    if tr["how"] == "limit" and abs(tr["fill_px"] - tr["limit"]) > 1e-9:
                        bad_tgt.append((tr["id"], "limit fill off the level", tr["fill_px"], tr["limit"]))
                    if tr["status"] == "closed" and tr.get("pnl") is not None and tr.get("why") in ("stop", "target", "flat time", "closed"):
                        n_closed += 1
                    else:
                        bad_close.append((d1, tr))
            if set(taken) != {t["row_id"] for t in S["trades"]}:
                bad_route.append((d1, "taken rows not all handled", sorted(taken), [t["row_id"] for t in S["trades"]]))
            if g.ad.legs or g.fake.pos and any(v[0] for v in g.fake.pos.values()):
                bad_close.append((d1, "still open after 16:05", g.ad.legs, g.fake.pos))
            tfa.archive(folder=g.nd, path=os.path.join(g.root, "logs", "exec_audit", "orders.jsonl"))   # the PC's 16:05 archive
            fill_rows += [r for r in datapipe.day_fills(d1, root=g.root) if r.get("lane") == "oflane"]
            g.ad.release_lock()
    check(f"a. lane decisions = of_paper replay, row for row ({len(days) - 1} days)", not bad_dec, bad_dec[:1])
    check(f"a. every lane trade is a TAKEN paper row, same side + stop; every taken row handled ({n_taken} taken)",
          not bad_route and n_taken >= 4, bad_route[:2])
    check(f"a. routed trades filled on Sim102 and closed by stop / target / 15:55 ({n_routed} routed, {n_closed} closed, "
          f"{len(refusals)} refused)", n_routed >= 3 and n_closed == n_routed and not bad_close, (bad_close[:2], refusals))
    check(f"a. E5 entries: {hows}; every target = 2R from the ACTUAL fill, limit fills at the level", not bad_tgt
          and hows.get("limit", 0) >= 1, bad_tgt[:3])
    check("a. refusals only for 'already an open trade' / one position (the real bracket can outlive the paper one)",
          all("open trade" in w or "one position" in w for w in refusals), refusals)
    check("e. unified fill log: the lane's entries / stops / targets are lane 'oflane' with fills",
          fill_rows and all(r.get("fill_px") for r in fill_rows if r["leg"] == "entry" and r.get("state") == "FILLED")
          and any(r.get("exit_fill_px") for r in fill_rows if r["leg"] == "entry"), [r for r in fill_rows if r["leg"] == "entry"][:2])
    check("e. engine.fill_audit picks the lane's adapter state up (data/ninjatrader_state_*.json = a lane)",
          L.NT_STATE_NAME.startswith("ninjatrader_state_") and L.NT_STATE_NAME[len("ninjatrader_state_"):-5] == "oflane")

    # ---- one day with a taken trade early, for the guard tests
    d0, d1 = days[-2], days[-1]
    ref = P.replay_frame(W["ticks"][d1][0], d1, W["R"][d0], d0)
    first = min((r for r in ref["rows"] if r["taken"]), key=lambda r: r["t_sig"])
    t_dec = first["t_sig"] + 300

    def guard_day(cfg=None, hook=None, until=None, news=None):
        td = tempfile.mkdtemp(prefix="oflane_")
        g = Rig(td, W, d0, d1, cfg, news)
        g.run(g.hm(9, 25), until or (t_dec + 61), hook=hook)
        return g, g.S()

    # ---- b. Sim only
    with tempfile.TemporaryDirectory() as td:
        os.makedirs(os.path.join(td, "data"))
        ok, msg = L.set_switch(True, "MFFU-EVAL-1", root=td)
        check("b. --sim on for a real (non-Sim) account is refused in plain words, the switch stays OFF",
              not ok and "not a NinjaTrader simulation account" in msg and L.load_cfg(td)["on"] is False, msg)
        ok, msg = L.set_switch(True, "Sim102", root=td)
        check("b. --sim on for Sim102 works and says what it does", ok and L.load_cfg(td)["on"] is True and "simulation" in msg, msg)
        ok2, msg2 = L.set_switch(False, root=td)
        check("b. --sim off -> OFF, open trade keeps its bracket", ok2 and L.load_cfg(td)["on"] is False and "stop and target" in msg2, msg2)
        check("b. no switch file = OFF; OFF + flat = nothing touched (no adapter)", L.load_cfg(os.path.join(td, "nope"))["on"] is False
              and L.tick(now=1, root=td).get("off") is True)
        json.dump({"on": True, "account": "MFFU-EVAL-1"}, open(os.path.join(td, "data", L.CFG_NAME), "w"))
        r = L.tick(now=1, root=td)
        check("b. a hand-edited switch naming a real account: tick refuses, builds no adapter", "refused" in r and "ad" not in r, r.get("refused"))
        txt = L.status_text(td)
        check("b. status words name the account as REFUSED", "REFUSED" in txt, txt)
    # red team 2026-11-27: the lane's own Sim account (Sim102) and the plain words when NinjaTrader does not list it
    check("b. default account = Sim102 (its own Sim account, not Sim101)", L.DEFAULT_CFG["account"] == "Sim102"
          and L.load_cfg(os.path.join(tempfile.gettempdir(), "nope_of_lane"))["account"] == "Sim102")
    with tempfile.TemporaryDirectory() as td:
        nd = os.path.join(td, "NinjaTrader 8")
        os.makedirs(os.path.join(td, "data")); os.makedirs(os.path.join(nd, "le_feed")); os.makedirs(os.path.join(nd, "outgoing"))
        json.dump({**L.DEFAULT_CFG, "nt_folder": nd}, open(os.path.join(td, "data", L.CFG_NAME), "w"))
        acc = os.path.join(nd, "le_feed", "accounts.csv")
        import time as _t
        open(acc, "w").write(f"name,t,cash\nSim101,{int(_t.time())},100000\n")
        txt_missing = L.status_text(td)
        seen_missing = L.account_seen("Sim102", nd)
        ok_on, msg_on = L.set_switch(True, "Sim102", root=td)

        class _A:
            folder = nd
            outgoing = os.path.join(nd, "outgoing")
        why_m, _, _ = L.entry_guards(L.new_state("2026-11-25"), {**L.DEFAULT_CFG, "on": True}, _A(),
                                     {"d": 1, "stop": 100.0, "day": "2026-11-25", "t_sig": int(_t.time()) - 305}, _t.time(), 110.0, False, [])
        open(acc, "w").write(f"name,t,cash\nSim101,{int(_t.time())},100000\nSim102,{int(_t.time())},100000\n")
        txt_ok = L.status_text(td)
        seen_ok = L.account_seen("Sim102", nd)
        os.remove(acc)
        txt_unknown = L.status_text(td)
    want = "Sim102 must exist in NinjaTrader (Accounts tab > Add Sim account)"
    check("b. --sim status: NinjaTrader lists no Sim102 -> says plainly 'Sim102 must exist in NinjaTrader (Accounts tab > Add Sim account)'",
          seen_missing is False and want in txt_missing and want in msg_on, (txt_missing, msg_on))
    check("b. Sim102 missing from NinjaTrader's account list -> no entry (guard)", any("must exist in NinjaTrader" in w for w in why_m), why_m)
    check("b. Sim102 listed -> no warning; no accounts list -> 'could not check' + the same how-to",
          seen_ok is True and "must exist" not in txt_ok and "could not check" in txt_unknown.lower() and "Add Sim account" in txt_unknown,
          (txt_ok, txt_unknown))
    g, S = guard_day(cfg={"account": "Playback101"}, until=t_dec + 61)
    check("b. Playback101 is a simulation account too (routes)", any(t["status"] in ("open", "closed") for t in S["trades"]), S["trades"][:1])
    g.ad.release_lock()
    gx, Sx = guard_day(until=t_dec + 61)
    gx.ad.release_lock()
    adr = L.make_adapter({**L.DEFAULT_CFG, "account": "MFFUEVAL123"}, gx.root, gx.nd)
    check("b. the adapter itself refuses a real account (never armed by the lane)", bool(adr.disabled) and "refused" in adr.disabled.lower(), adr.disabled)
    routed = [t for t in Sx["trades"] if t["status"] in ("open", "closed")]
    check("b. the first taken signal is routed on Sim102 (bracket: side, stop = paper stop, 2R target)",
          routed and routed[0]["row_id"] == first["id"] and routed[0]["stop"] == first["stop"]
          and abs((routed[0]["target"] - routed[0]["est"]) - 2 * (routed[0]["est"] - routed[0]["stop"])) < 0.3, routed[:1])
    # ---- c. guards
    def refused_first(S):
        t = next((t for t in S["trades"] if t["row_id"] == first["id"]), None)
        return t is not None and t["status"] == "refused", (t or {}).get("why", "")

    def kill_hook(g, t):
        if t >= t_dec - 600:
            json.dump({"kill": True}, open(os.path.join(g.root, "data", "live_state.json"), "w"))
    g, S = guard_day(hook=kill_hook)
    t = next((t for t in S["paper"]["rows"] if t["id"] == first["id"]), {})
    check("c. kill switch: the paper row is 'kill' and nothing is routed", t.get("why_not") == "kill" and not any(
        x["status"] in ("open", "closed") for x in S["trades"]), (t.get("why_not"), S["trades"]))
    g.ad.release_lock()

    def kill_mid(g, t):
        if t >= t_dec + 120:
            open(os.path.join(g.root, "data", L.KILL_NAME), "w").close()
    g, S = guard_day(hook=kill_mid, until=t_dec + 300)
    tr = next((x for x in S["trades"] if x["row_id"] == first["id"]), {})
    check("c. kill while in a trade (or its limit still working): the lane flattens / cancels on Sim102, nothing re-entered",
          (tr.get("status") == "closed" or (tr.get("status") == "refused" and "kill switch" in tr.get("why", "")))
          and not any(v[0] for v in g.fake.pos.values()) and any("kill switch" in n["text"] for n in S["log"]), (tr, g.fake.pos))
    g.ad.release_lock()

    def pos_hook(g, t):                # the owner's hand trade on Sim102 (one position per account)
        if t >= t_dec - 300 and not g.fake.pos:
            inst = g.ad._instruments()["micro"]
            g.fake.pos[("Sim102", inst)] = [1, 25000.0]
            g.fake._write_pos("Sim102", inst)
    g, S = guard_day(hook=pos_hook)
    r, w = refused_first(S)
    check("c. one position per account: Sim102 already LONG -> not routed", r and "one position per account" in w, w)
    g.ad.release_lock()

    def hedge_hook(g, t):              # another account (the MFFU eval) holds the opposite side
        inst = g.ad._instruments()["micro"] if g.ad else "MNQ 12-26"
        g.fake.pos[("MFFUEVAL123", inst)] = [-first["d"], 25000.0]
        g.fake._write_pos("MFFUEVAL123", inst)
    g, S = guard_day(hook=hedge_hook)
    r, w = refused_first(S)
    check("c. cross-account hedge: another account holds the opposite NQ side -> not routed", r and "hedging" in w, w)
    g.ad.release_lock()

    def same_side(g, t):
        inst = g.ad._instruments()["micro"] if g.ad else "MNQ 12-26"
        g.fake.pos[("MFFUEVAL123", inst)] = [first["d"], 25000.0]
        g.fake._write_pos("MFFUEVAL123", inst)
    g, S = guard_day(hook=same_side)
    r, w = refused_first(S)
    check("c. same side on another account is not a hedge (routed)", not r, w)
    g.ad.release_lock()

    def dll_hook(g, t):                # today's closed lane trades already lost $990 (MFFU 50K soft DLL $1,000)
        if t == g.hm(9, 25):
            S0 = g.L.load_state(g.root)
            S0.update(day=d1, closes=[{"day": d1, "t": g.hm(9, 26), "pnl": -999.5, "id": "x"}])
            g.L.save_state(S0, g.root)
    g, S = guard_day(hook=dll_hook)
    r, w = refused_first(S)
    check("c. MFFU daily loss: -$999.5 today -> 1 micro does not fit -> not routed", r and "daily loss" in w, w)
    g.ad.release_lock()

    def dd_hook(g, t):                 # the EOD trailing floor: earlier days -$1,990 (50K eval, $2,000 max loss)
        if t == g.hm(9, 25):
            S0 = g.L.load_state(g.root)
            S0.update(day=d1, closes=[{"day": d0, "t": g.hm(9, 26) - 86400, "pnl": -1995.0, "id": "y"}])
            g.L.save_state(S0, g.root)
    g, S = guard_day(hook=dd_hook)
    r, w = refused_first(S)
    check("c. EOD trailing max-loss floor: $5 of room left -> not routed", r and ("floor" in w or "max-loss" in w), w)
    g.ad.release_lock()
    news_t = t_dec + 30
    g, S = guard_day(news=[{"t": news_t, "event": "CPI"}])
    r, w = refused_first(S)
    check("c. news blackout: a Tier-1 release 30 s after the decision -> not routed", r and "news blackout" in w, w)
    g.ad.release_lock()
    # a stale decision (the lane process was down for the bar close: first run 4 min late)
    g = Rig(tempfile.mkdtemp(prefix="oflane_"), W, d0, d1)
    g.run(g.hm(9, 25), t_dec - 10)
    g.run(t_dec + 240, t_dec + 241)
    r, w = refused_first(g.S())
    check("c. a decision seen > 2 min after the bar close is not chased", r and "not chased" in w, w)
    g.ad.release_lock()
    # the half-day cut (the day after Thanksgiving, CME halts 13:15 ET: entries stop 13:00)
    from engine import cme_calendar as CAL
    hd = "2026-11-27"
    ec = CAL.early_close(hd)
    from engine import firms
    S0 = L.new_state(hd)
    t13 = int(dt.datetime(2026, 11, 27, 13, 5, tzinfo=ET).timestamp())
    row = {"d": 1, "stop": 100.0, "day": hd, "t_sig": t13 - 300 - 5}
    with tempfile.TemporaryDirectory() as td:
        from engine.ninjatrader import _FakeNT
        _FakeNT(os.path.join(td, "nt"))
        ad = L.make_adapter({**L.DEFAULT_CFG, "on": True}, td, os.path.join(td, "nt"))
        why, q, _ = L.entry_guards(S0, {**L.DEFAULT_CFG, "on": True}, ad, row, t13, 110.0, False, [])
        ad.release_lock()
    check(f"c. half-day {hd} (halt {ec // 60}:{ec % 60:02d}): 13:05 ET entry refused (cut 15 min before)",
          ec is not None and any("entry cut" in w and "early close" in w for w in why), (ec, why))
    check("c. the adapter flattens 5 min before an early close (engine.cme_calendar.flat_cut)", CAL.flat_cut(hd, 955) == ec - 5)
    # flat 15:55: a trade still open at 15:55 is closed by the adapter's flat time
    late = [r for r in ref["rows"] if r["taken"] and r.get("why") == "flat 15:55"]
    with tempfile.TemporaryDirectory() as td:
        from engine.ninjatrader import _FakeNT
        fk = _FakeNT(os.path.join(td, "nt"), price=25000.0)
        now = [float(int(dt.datetime(2026, 11, 25, 15, 40, tzinfo=ET).timestamp()))]
        ad = L.make_adapter({**L.DEFAULT_CFG, "on": True}, td, os.path.join(td, "nt"), clock=lambda: now[0])
        ad._sleep = lambda s: (fk.process(), now.__setitem__(0, now[0] + s))
        ad._alert_fn = lambda *_: None
        r1 = ad.send({"side": "buy", "qty": 2, "stop": 24990.0, "target": 25020.0, "entry": 25000.25, "sym": "NQ", "entry_t": int(now[0])})
        now[0] = float(int(dt.datetime(2026, 11, 25, 15, 56, tzinfo=ET).timestamp()))
        ad.tick(); fk.process(); ad.tick()
        flat = not any(v[0] for v in fk.pos.values())
        r2 = ad.send({"side": "buy", "qty": 1, "stop": 24990.0, "target": 25020.0, "entry": 25000.25, "sym": "NQ", "entry_t": int(now[0])})
        ad.release_lock()
    check("c. flat by 15:55: an open lane bracket is closed at the flat time; no new entry after it",
          r1.get("ok") and flat and not r2.get("ok") and "outside the session" in str(r2.get("error")), (r1, fk.pos, r2))
    # ---- E5 on the adapter (opt-in keys): limit working, 2R from the fill, timeout cancel, cancel_entry; no key = MARKET as before
    with tempfile.TemporaryDirectory() as td:
        from engine.ninjatrader import _FakeNT
        fk = _FakeNT(os.path.join(td, "nt"), price=20000.0)
        now = [float(int(dt.datetime(2026, 11, 25, 10, 5, tzinfo=ET).timestamp()))]
        ad = L.make_adapter({**L.DEFAULT_CFG, "on": True}, td, os.path.join(td, "nt"), clock=lambda: now[0])
        ad._sleep = lambda s: (fk.process(), now.__setitem__(0, now[0] + s))
        ad._alert_fn = lambda *_: None
        base = {"side": "sell", "qty": 2, "stop": 20010.0, "target": 19990.0, "entry": 20005.0, "sym": "NQ", "target_rr": 2.0}
        r = ad.send({**base, "entry_t": int(now[0]), "entry_limit": 20005.0, "entry_wait_s": 300})
        lines = [ln for f in fk.files for ln in f[1]]
        ok1 = r.get("ok") and ad.legs[0]["status"] == "pending" and any(";LIMIT;20005" in ln and ln.endswith(";;") or ";LIMIT;20005.00;" in ln for ln in lines)
        fk.move(20005.0); ad.tick(); fk.process(); ad.tick()
        lg = ad.legs[0]
        ok2 = lg["status"] == "protected" and abs(fk.orders[lg["target_id"]]["limit"] - 19995.0) < 1e-9
        ad.send({"side": "exit", "reason": "test"}); fk.process(); ad.tick()
        now[0] += 60
        r = ad.send({**base, "entry_t": int(now[0]), "entry_limit": 20008.0, "entry_wait_s": 300})
        now[0] += 301; ad.tick(); fk.process(); ad.tick()
        ok3 = not ad.legs and any(";20008" in ln or "CANCEL" in ln for f in fk.files for ln in f[1] if ln.startswith("CANCEL"))
        now[0] += 60
        r = ad.send({**base, "entry_t": int(now[0]), "entry_limit": 20008.0, "entry_wait_s": 300})
        c = ad.cancel_entry(int(now[0]), "stop first"); fk.process(); ad.tick()
        ok4 = c.get("ok") and not ad.legs
        now[0] += 60
        r = ad.send({k: v for k, v in base.items() if k != "target_rr"} | {"entry_t": int(now[0])})
        lg = ad.legs[0] if ad.legs else {}
        ok5 = r.get("ok") and lg.get("status") == "protected" and lg.get("target") == 19990.0 and "entry_limit" not in lg
        ad.release_lock()
    check("E5 adapter: a LIMIT entry rests (working, not an error)", ok1, lines[-2:])
    check("E5 adapter: on its fill the target is re-priced 2R from the ACTUAL fill", ok2)
    check("E5 adapter: an unfilled limit is cancelled after entry_wait_s (300 s), nothing left", ok3)
    check("E5 adapter: cancel_entry (the stop traded first) cancels the working limit", ok4)
    check("E5 adapter: no opt-in key = the MARKET entry + the given target, exactly as before", ok5)
    # ---- d. restart mid-trade
    g = Rig(tempfile.mkdtemp(prefix="oflane_"), W, d0, d1)
    g.run(g.hm(9, 25), t_dec + 61)
    eid0 = next((x.get("entry_id") for x in g.S()["trades"] if x["row_id"] == first["id"]), None)
    sent0 = [ln for f in g.fake.files for ln in f[1] if ln.startswith("PLACE") and eid0 and eid0 in ln]
    g.ad.release_lock()
    g.ad = None                                     # the process died: a fresh adapter restores from its write-ahead state
    g.run(t_dec + 61, g.hm(16, 6))
    S = g.S()
    tr = next(x for x in S["trades"] if x["row_id"] == first["id"])
    sent1 = [ln for f in g.fake.files for ln in f[1] if ln.startswith("PLACE") and eid0 and eid0 in ln]
    check("d. restart mid-trade: the open order is restored, the entry is never sent twice, the exit is booked",
          len(sent0) == 1 and len(sent1) == 1 and tr["status"] == "closed" and tr.get("pnl") is not None
          and not any(v[0] for v in g.fake.pos.values()), (len(sent0), len(sent1), tr))
    g.ad.release_lock()
    # red team 2026-11-27: data/of_lane.json edited to a REAL account mid-trade (+ a restart): the Sim trade is still managed on
    # Sim102 to its close, no order ever names the other account, no new trade is routed
    g = Rig(tempfile.mkdtemp(prefix="oflane_"), W, d0, d1)
    g.run(g.hm(9, 25), t_dec + 61)
    tr0 = next((x for x in g.S()["trades"] if x["row_id"] == first["id"]), {})
    json.dump({**L.DEFAULT_CFG, "on": True, "account": "MFFUEVAL123", "nt_folder": g.nd}, open(os.path.join(g.root, "data", L.CFG_NAME), "w"))
    g.run(t_dec + 61, t_dec + 181)
    g.ad.release_lock(); g.ad = None                        # and a restart while the switch names the real account
    g.now[0] = float(t_dec + 200)
    outs = [g.L.tick(now=t_dec + 200, root=g.root, nd=g.nd, news_events=[], clock=lambda: g.now[0])]
    g.ad = outs[0].get("ad")
    if g.ad is not None:
        g.ad._sleep = lambda s_: (g.fake.process(), g.now.__setitem__(0, g.now[0] + s_))
        g.ad._alert_fn = g.alerts.append
    g.run(t_dec + 241, g.hm(16, 6))
    S = g.S()
    tr = next(x for x in S["trades"] if x["row_id"] == first["id"])
    real = [ln for f in g.fake.files for ln in f[1] if "MFFUEVAL123" in ln]
    later = [x for x in S["trades"] if x["decided_t"] > t_dec + 61 and x["status"] not in ("refused",) and x["row_id"] != first["id"]]
    check("red team: switch edited to a real account mid-trade -> the Sim102 trade is still managed to its close, nothing sent "
          "to the real account, no new trade", tr0.get("account") == "Sim102" and tr["status"] == "closed"
          and not any(v[0] for v in g.fake.pos.values()) and not real and not later
          and (outs[0].get("ad") is not None and outs[0]["ad"].account == "Sim102"), (tr0.get("account"), tr["status"], real[:2], later, g.fake.pos))
    if g.ad:
        g.ad.release_lock()
    # a crash between the write-ahead mark and the order file: the lane never resends it
    with tempfile.TemporaryDirectory() as td:
        g = Rig(td, W, d0, d1)
        g.run(g.hm(9, 25), t_dec - 10)
        S0 = L.load_state(g.root)
        S0["trades"].append({"id": "L|" + first["id"], "row_id": first["id"], "day": d1, "d": first["d"], "t_sig": first["t_sig"],
                             "entry_t": t_dec, "stop": first["stop"], "status": "sending", "qty": 1})
        L.save_state(S0, g.root)
        g.ad.release_lock(); g.ad = None
        g.run(t_dec + 5, t_dec + 125)
        S = g.S()
        tr = [x for x in S["trades"] if x["row_id"] == first["id"]]
        placed = [f for f in g.fake.files if any(ln.startswith("PLACE") and ";MARKET;" in ln for ln in f[1])]
        check("d. crash while sending (no order at NinjaTrader): marked unknown, NOT resent",
              len(tr) == 1 and tr[0]["status"] == "unknown" and not placed, (tr, len(placed)))
        g.ad.release_lock()
    # ---- f. safety
    src = open(os.path.join(ROOT, "engine", "of_lane.py"), encoding="utf-8").read()
    check("f. the lane never arms / confirms / sets the live env (no live words in the adapter config)",
          not any(w in src for w in ('"armed"', '"confirm"', "NINJATRADER_LIVE", "LIVE_PHRASE", "allow_account", '"global"')))
    check("f. decisions come only from engine.of_paper (step), no second rule", "OP.step(" in src and "ABS_SHARE" not in src and "zone(" not in src)
    ig = all(subprocess.run(["git", "check-ignore", "-q", p], cwd=ROOT).returncode == 0
             for p in ("data/of_lane.json", "data/of_lane_state.json", "data/ninjatrader_state_oflane.json", "logs/ninjatrader_oif_oflane.log"))
    check("f. the switch, the lane book, the adapter state and the order log are gitignored", ig)
    users = subprocess.run(["git", "grep", "-l", "of_lane", "--", "engine/live.py", "engine/lit_live.py", "server.py",
                            "engine/ninjatrader.py", "engine/account_b.py"], cwd=ROOT, capture_output=True, text=True).stdout.strip()
    check("f. nothing in the live bot imports the lane (it runs as its own process, OFF)", users == "", users)
    r = subprocess.run([sys.executable, "-X", "utf8", "-m", "engine.of_lane", "--sim", "status"], cwd=ROOT, capture_output=True, text=True,
                       timeout=120)
    check("f. CLI --sim status prints plain words", r.returncode == 0 and "Order-flow lane:" in r.stdout, (r.stdout, r.stderr[-300:]))
    n = len(RES)
    print(f"\n{sum(RES)}/{n} passed")
    return 0 if all(RES) else 1


if __name__ == "__main__":
    sys.exit(main())
