"""The Order Flow LANE: of_paper's lane A decisions routed to a NinjaTrader SIMULATION account (night-of-lane 2026-11-27).

OFF by default. Built so "next week on Sim101" is one switch; an eval / funded account is NOT possible from this file: any
account that is not a NinjaTrader simulation account (Sim101, SimNNN, PlaybackNNN) is refused, whatever the switch says. A
future owner switch + phrase for a real account is deliberately not built (owner's yes + the forward gate first).

Decisions: the SAME code as the paper bot. Each run feeds the live tick file (Documents\\NinjaTrader 8\\le_ticks\\NQ_<day>.csv)
through engine.of_paper (read_live -> summary_of -> step), into the lane's own copy of the paper state
(data/of_lane_state.json "paper"; of_paper's own data/of_paper.json is never touched). Every lane A row of_paper marks
"taken" is a routing candidate; nothing else ever is. No second implementation of the rule.

Guards, in order (any one = not routed, logged in plain words; the paper row is unchanged):
  switch        data/of_lane.json {"on": true}; absent / unreadable = OFF
  sim only      the account must be a NinjaTrader simulation account (engine.ninjatrader.is_sim); the adapter config never
                carries the arming keys or the live phrase, so its own live gate refuses a real account a second time
  kill          data/live_state.json "kill" (the owner's kill) or data/of_lane_kill: no new entry, an open trade is flattened
  calendar      CME full closure, weekend, and the half-day cut (engine.cme_calendar.entry_cut: 15 min before an early close)
  late          the decision is acted on only within MAX_LATE_S of the signal bar's close (a stale signal is never chased)
  news          no entry within news_min (2) minutes of a Tier-1 release (engine.guards.news_hit)
  one position  the lane's own open trade, or ANY position NinjaTrader shows on the account's NQ instruments
  hedge         another account (any account in NinjaTrader's outgoing folder) holds the opposite NQ side (engine.firms)
  size          engine.sizing.second_qty at a fixed $ risk (risk_usd, default $200; 1 micro's stop-out above it = skip)
  firm rules    engine.firms.check with the plan the lane is held to (default the MFFU Builder 50K eval): the soft daily
                loss (DLL), the EOD trailing max-loss floor, contracts, flat time; the lane's own closed trades are its book
Exits: the adapter's OCO bracket (stop 1 tick beyond the signal bar = the paper stop, target 2R from the estimated fill), its
flat-time close (15:55 ET, or 5 min before a CME early close), a kill flatten. One position at a time.

Files: data/of_lane.json (switch), data/of_lane_state.json (lane book), data/ninjatrader_state_oflane.json (the adapter's
write-ahead state: an open bracket survives a restart; engine.fill_audit reads every ninjatrader_state_*.json as a lane),
logs/ninjatrader_oif_oflane.log (every order line; engine.datapipe.day_fills reads it as lane "oflane" into the unified fill
log). All gitignored.

    python -X utf8 -m engine.of_lane --sim on|off|status     the switch (plain words)
    python -X utf8 -m engine.of_lane tick                     one run (nothing happens while OFF and flat)
    python -X utf8 -m engine.of_lane loop                     every 15 s until 16:10 ET (the PC: a detached child)
"""
from __future__ import annotations

import argparse
import datetime as dt
import json
import os
import sys
import time
from zoneinfo import ZoneInfo

import numpy as np

from . import of_paper as OP

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
ET = ZoneInfo("America/New_York")
CFG_NAME, STATE_NAME, NT_STATE_NAME, KILL_NAME = "of_lane.json", "of_lane_state.json", "ninjatrader_state_oflane.json", "of_lane_kill"
AUDIT_NAME = "ninjatrader_oif_oflane.log"           # engine.datapipe._lane_of -> lane "oflane"
LANE = "oflane"
DEFAULT_CFG = {"on": False, "account": "Sim101", "risk_usd": 200.0, "max_micros": 10, "plan": "mffu_builder_50k",
               "stage": "eval", "news_min": 2}
MAX_LATE_S = 120            # act on a decision only within 2 min of the signal bar's close
STEP_EVERY = 20             # s between two paper steps inside a 5m bar (a new bar close always steps)
FLAT_MOD = 955
SESSION_FROM = 9 * 60 + 45  # of_paper lane A: 09:45-15:00 bar opens
PV, COMM = 2.0, 1.90        # MNQ $ a point, the live commission a micro round trip (engine.sizing.LIVE_COMM)
MAX_ROWS = 400


def _p(root, *a):
    return os.path.join(root, *a)


def _rj(p, default=None):
    try:
        with open(p, encoding="utf-8") as fh:
            return json.load(fh)
    except Exception:  # noqa: BLE001
        return default


def _wj(p, obj):
    os.makedirs(os.path.dirname(p), exist_ok=True)
    tmp = p + ".tmp"
    with open(tmp, "w", encoding="utf-8") as fh:
        json.dump(obj, fh, indent=1, default=float)
    from . import fsutil
    fsutil.replace(tmp, p)


def _et(t) -> dt.datetime:
    return dt.datetime.fromtimestamp(int(t), ET)


# ------------------------------------------------------------------------------------------------ the switch
def load_cfg(root: str = ROOT) -> dict:
    c = _rj(_p(root, "data", CFG_NAME))
    out = dict(DEFAULT_CFG)
    if isinstance(c, dict):
        out.update({k: v for k, v in c.items() if k in DEFAULT_CFG or k in ("set_at", "nt_folder")})
    else:
        out["on"] = False                       # absent / unreadable = OFF
    out["on"] = out.get("on") is True
    return out


def sim_problem(account) -> str | None:
    """None when the account is a NinjaTrader simulation account, else why it is refused (no switch can change that here)."""
    from .ninjatrader import is_sim
    a = str(account or "").strip()
    if not a:
        return "no account named"
    if not is_sim(a):
        return (f"account '{a}' is not a NinjaTrader simulation account (Sim101 / SimNNN / PlaybackNNN): the order-flow lane "
                "trades simulation only until the forward test passes and the owner says yes")
    return None


def set_switch(on: bool, account: str | None = None, root: str = ROOT) -> tuple[bool, str]:
    c = load_cfg(root)
    if account:
        c["account"] = str(account).strip()
    if on:
        bad = sim_problem(c["account"])
        if bad:
            return False, "NOT switched on: " + bad + "."
    c["on"] = bool(on)
    c["set_at"] = _et(time.time()).strftime("%Y-%m-%d %H:%M ET")
    _wj(_p(root, "data", CFG_NAME), {k: c[k] for k in list(DEFAULT_CFG) + ["set_at"]})
    if on:
        return True, (f"Order-flow lane ON for {c['account']} (simulation money). It trades the paper bot's absorbed level fades, "
                      f"${c['risk_usd']:,.0f} risk a trade, max {c['max_micros']} micros, one trade at a time, flat by 15:55 ET.")
    return True, "Order-flow lane OFF: no new trades. An open simulation trade keeps its stop and target and the 15:55 close."


# ------------------------------------------------------------------------------------------------ the book
def new_state(day=None) -> dict:
    return {"v": 1, "lane": LANE, "day": day, "paper": OP.new_state(day), "last_step": 0, "trades": [], "closes": [],
            "log": [], "killed_day": None}


def load_state(root: str = ROOT) -> dict:
    s = _rj(_p(root, "data", STATE_NAME))
    return s if isinstance(s, dict) and isinstance(s.get("trades"), list) else new_state()


def save_state(S: dict, root: str = ROOT):
    S["trades"] = S["trades"][-MAX_ROWS:]
    S["closes"] = S["closes"][-MAX_ROWS:]
    S["log"] = S["log"][-MAX_ROWS:]
    _wj(_p(root, "data", STATE_NAME), S)


def _note(S, now, text, **kw):
    S["log"].append({"t": int(now), "text": text, **kw})


def make_adapter(cfg: dict, root: str = ROOT, nd: str | None = None, clock=None):
    """The existing NinjaTrader adapter on the lane's (simulation) account, its own state + audit files. Never armed."""
    from .ninjatrader import NinjaTraderAdapter
    acfg = {"adapter": "ninjatrader", "sym": "NQ", "nt_account": cfg["account"], "nt_contract": "micro",
            "params": {"max_micros": int(cfg.get("max_micros") or 10), "flat_mod": FLAT_MOD},
            "nt_session_from": SESSION_FROM, "nt_all_hours": False, "nt_max_entries_day": 6, "nt_file_tag": LANE,
            "nt_state_path": _p(root, "data", NT_STATE_NAME), "nt_audit_log": _p(root, "logs", AUDIT_NAME)}
    if nd or cfg.get("nt_folder"):
        acfg["nt_folder"] = nd or cfg["nt_folder"]
    return NinjaTraderAdapter(acfg, clock=clock)


def _nt_open(root) -> bool:
    """The adapter's write-ahead state holds an open bracket (then the lane keeps managing it even while OFF)."""
    from .ninjatrader import OPEN_STATUSES
    s = _rj(_p(root, "data", NT_STATE_NAME), {}) or {}
    return any(isinstance(lg, dict) and lg.get("status") in OPEN_STATUSES for lg in s.get("legs") or [])


def book(S: dict, P: dict, today: str, open_pnl: float = 0.0, open_micros: int = 0) -> dict:
    from . import firms
    return firms.book(float(P.get("start") or 0.0), [(c["day"], c["t"], c["pnl"]) for c in S["closes"]], today,
                      open_pnl=open_pnl, open_micros=open_micros)


def other_positions(ad) -> list:
    """Every NQ position NinjaTrader reports in its outgoing folder, ANY account: [{"account", "sym", "dir", "qty"}]. An
    unreadable folder raises (the caller refuses the entry: the hedge guard fails closed)."""
    out = []
    for n in os.listdir(ad.outgoing):
        if not n.lower().endswith("_position.txt"):
            continue
        stem = n[:-len("_position.txt")]
        if "_" not in stem:
            continue
        inst, acct = stem.split("_", 1)
        from .ninjatrader import _read_text, parse_position
        pos = parse_position(_read_text(os.path.join(ad.outgoing, n)))
        if not pos or pos["side"] == "FLAT":
            continue
        out.append({"account": acct, "sym": inst.split(" ")[0], "dir": 1 if pos["side"] == "LONG" else -1, "qty": pos["qty"],
                    "instrument": inst})
    return out


# ------------------------------------------------------------------------------------------------ guards
def entry_guards(S, cfg, ad, row, now, est, killed, news_events=None) -> tuple[list, int, dict]:
    """(reasons not to route, micros, the firm check) for one taken paper row. Pure reads."""
    from . import cme_calendar as CAL, firms, guards, sizing
    why = []
    d = int(row["d"])
    stop = float(row["stop"])
    day = row["day"]
    e = _et(now)
    mod = e.hour * 60 + e.minute
    if not cfg.get("on"):
        why.append("lane is OFF")
    bad = sim_problem(cfg.get("account"))
    if bad:
        why.append(bad)
    if killed:
        why.append("kill switch on")
    if e.weekday() >= 5 or CAL.full_closure(day):
        why.append("no CME session today")
    cut = CAL.entry_cut(day, FLAT_MOD)
    if mod >= cut:
        why.append(f"after the entry cut {cut // 60:02d}:{cut % 60:02d} ET" + (" (CME early close)" if cut < FLAT_MOD else ""))
    late = now - (int(row["t_sig"]) + 300)
    if late > MAX_LATE_S:
        why.append(f"decision {late:.0f} s after the signal bar closed (max {MAX_LATE_S} s): not chased")
    nm = cfg.get("news_min")
    if nm:
        hit = guards.news_hit(int(now), int(nm), events=news_events)
        if hit:
            why.append(f"news blackout: {hit}")
    open_tr = [t for t in S["trades"] if t["status"] in ("sending", "open")]
    if open_tr:
        why.append("the lane already has an open trade")
    try:
        pos = other_positions(ad)
    except Exception as ex:  # noqa: BLE001
        pos = None
        why.append(f"NinjaTrader positions unreadable ({ex.__class__.__name__}): hedge check fails closed")
    if pos is not None:
        mine = [p for p in pos if p["account"].lower() == str(cfg["account"]).lower()]
        if mine:
            why.append(f"{cfg['account']} already holds {'LONG' if mine[0]['dir'] == 1 else 'SHORT'} {mine[0]['qty']} "
                       f"{mine[0]['instrument']}: one position per account")
    risk = (est - stop) * d
    if risk <= 0:
        why.append("price is already through the stop")
        return why, 0, {}
    sz = sizing.second_qty(risk, usd=float(cfg.get("risk_usd") or 200.0), cfg={"mode": "normal"},
                           max_micros=int(cfg.get("max_micros") or 10))
    q = int(sz.get("qty") or 0)
    if q < 1:
        why.append("; ".join(sz.get("reasons") or ["size 0"]))
    P = firms.profile(cfg.get("plan") or DEFAULT_CFG["plan"], cfg.get("stage") or "eval") or {"kind": "prop"}
    st = book(S, P, day)
    order = {"side": "buy" if d == 1 else "sell", "dir": d, "qty": max(1, q), "sym": "MNQ", "entry": est, "stop": stop,
             "target": est + OP.RR * risk * d}
    others = [p for p in (pos or []) if p["account"].lower() != str(cfg["account"]).lower()]
    fc = firms.check(P, st, order, positions=others, now=int(now), releases=[])
    why += list(fc.get("block") or [])
    if q >= 1 and fc.get("ok"):
        q = min(q, int(fc.get("max_qty") or 0))
        if q < 1:
            why.append("the firm rules leave no size")
    return why, q, fc


# ------------------------------------------------------------------------------------------------ one run
def _last_px(x) -> float | None:
    return float(x.price.iloc[-1]) if x is not None and len(x) else None


def _sync_trades(S, ad, now, last_px):
    """Open lane trades vs the adapter: the real fill, and once the bracket is gone, the exit (stop / target fill, else the
    last trade for a flat-time / kill close, marked est) and $ after costs."""
    live = {int(lg["entry_t"]): lg for lg in ad.legs}
    for tr in S["trades"]:
        if tr["status"] not in ("sending", "open"):
            continue
        lg = live.get(int(tr["entry_t"]))
        if lg is not None:
            tr["status"] = "open"
            for k in ("entry_id", "stop_id", "target_id", "instrument"):
                tr[k] = lg.get(k)
            if lg.get("filled"):
                tr["filled"], tr["fill_px"] = int(lg["filled"]), lg.get("fill_px")
            continue
        if tr["status"] == "sending" and not tr.get("entry_id"):
            tr.update(status="unknown", why="restart while sending: the adapter holds no such order (not resent)")
            _note(S, now, "a send was interrupted by a restart; NinjaTrader shows no order of it: NOT resent")
            continue
        h = next((x for x in reversed(list(ad.history)) if int(x.get("entry_t") or 0) == int(tr["entry_t"])), None)
        if h is not None and h.get("filled"):
            tr["filled"], tr["fill_px"] = int(h["filled"]), h.get("fill_px")
        if not tr.get("filled"):
            ent = ad.read_order(tr["entry_id"]) if tr.get("entry_id") else None
            if ent and ent.get("filled"):
                tr["filled"], tr["fill_px"] = int(ent["filled"]), ent.get("avg")
        if not tr.get("filled"):
            tr.update(status="closed", why=(h or {}).get("closed") or "entry never filled", pnl=0.0, exit_t=int(now))
            continue
        ex, why, est = None, (h or {}).get("closed") or "closed", False
        for k, nm in (("stop_id", "stop"), ("target_id", "target")):
            o = ad.read_order(tr[k]) if tr.get(k) else None
            if o and o["state"] == "FILLED" and o.get("avg"):
                ex, why = float(o["avg"]), nm
        if ex is None:
            ex, est = (last_px if last_px is not None else float(tr["fill_px"])), True
        q = int(tr["filled"])
        pnl = round((ex - float(tr["fill_px"])) * tr["d"] * q * PV - COMM * q, 2)
        tr.update(status="closed", exit_px=round(ex, 2), exit_est=est, why=why, pnl=pnl, exit_t=int(now),
                  R=round((ex - float(tr["fill_px"])) * tr["d"] / max(1e-9, abs(float(tr["fill_px"]) - float(tr["stop"]))), 3))
        S["closes"].append({"day": tr["day"], "t": int(now), "pnl": pnl, "id": tr["id"]})
        _note(S, now, f"closed {tr['id']} ({why}{', price est.' if est else ''}): {'+' if pnl >= 0 else '-'}${abs(pnl):,.0f}")


def tick(now: float | None = None, root: str = ROOT, nd: str | None = None, ad=None, force_step: bool = False,
         news_events=None) -> dict:
    """One lane run. Returns {"S", "routed": [...], "ad"}. While OFF and flat it touches nothing (no adapter, no lock)."""
    now = float(now or time.time())
    cfg = load_cfg(root)
    S = load_state(root)
    day = OP.et_day(now)
    if S.get("day") != day:
        keep = {k: S.get(k) for k in ("closes",)}
        S = new_state(day)
        S.update({k: v for k, v in keep.items() if v is not None})
    open_tr = [t for t in S["trades"] if t["status"] in ("sending", "open")]
    if not cfg["on"] and not open_tr and ad is None and not _nt_open(root):
        return {"off": True, "S": S, "routed": []}
    nd = nd or cfg.get("nt_folder") or OP.nt_dir()
    if ad is None:
        if sim_problem(cfg.get("account")) and not open_tr:
            return {"refused": sim_problem(cfg.get("account")), "S": S, "routed": []}
        ad = make_adapter(cfg, root, nd)
    out = {"S": S, "routed": [], "ad": ad}
    killed = OP._kill(root) or os.path.exists(_p(root, "data", KILL_NAME))
    ad.tick()
    x = OP._read_live(day, nd) if nd else None
    if x is not None and len(x):
        x = x[x.t_ns <= int(now * 1e9)]
    last_px = _last_px(x)
    _sync_trades(S, ad, now, last_px)
    if killed and (ad.legs or any(t["status"] == "open" for t in S["trades"])) and S.get("killed_day") != day:
        r = ad.kill(scope="account")
        S["killed_day"] = day
        _note(S, now, f"kill switch: lane flattened on {cfg['account']} ({'confirmed' if r.get('ok') else r.get('error')})")
        _sync_trades(S, ad, now, last_px)
    slot = int(now) // 300
    stepped = False
    if x is not None and len(x) and OP.in_window(now) and (force_step or slot != int(S.get("last_step") or 0) // 300
                                                           or now - float(S.get("last_step") or 0) >= STEP_EVERY):
        pday, Rp = OP._prev_summary(day, nd, root)
        R = OP.summary_of(x, day)
        if R:
            P = S["paper"] if (S.get("paper") or {}).get("day") == day else OP.new_state(day)
            P["live"] = True
            tt = x.t_ns.to_numpy(np.int64) // 1_000_000
            S["paper"] = OP.step(P, day, R, Rp, pday, tt, x.price.to_numpy(float), now, kill=killed)
            S["last_step"] = int(now)
            stepped = True
    if stepped:
        done = {t["row_id"] for t in S["trades"]}
        for row in S["paper"]["rows"]:
            if row.get("lane") != "A" or row.get("day") != day or not row.get("taken") or row["id"] in done:
                continue
            d = int(row["d"])
            est = round(float(last_px) + OP.SLIP * d, 2)
            why, q, fc = entry_guards(S, cfg, ad, row, now, est, killed, news_events)
            risk = (est - float(row["stop"])) * d
            tr = {"id": f"L|{row['id']}", "row_id": row["id"], "day": day, "d": d, "t_sig": row["t_sig"],
                  "entry_t": int(row["t_sig"]) + 300, "level": row["level"], "stop": row["stop"], "est": est,
                  "target": round(est + OP.RR * risk * d, 2) if risk > 0 else None, "qty": q, "decided_t": int(now)}
            if why:
                tr.update(status="refused", why="; ".join(why))
                S["trades"].append(tr)
                _note(S, now, f"not routed {row['id']}: {tr['why']}")
                continue
            tr["status"] = "sending"                        # write-ahead: a restart never sends it twice
            S["trades"].append(tr)
            save_state(S, root)
            res = ad.send({"side": "buy" if d == 1 else "sell", "qty": q, "stop": row["stop"], "target": tr["target"],
                           "entry": est, "sym": "NQ", "entry_t": tr["entry_t"]})
            tr["send"] = {"ok": bool(res.get("ok")), "error": res.get("error")}
            if not any(int(lg["entry_t"]) == tr["entry_t"] for lg in ad.legs) and not any(
                    int(h.get("entry_t") or 0) == tr["entry_t"] for h in ad.history):
                tr.update(status="refused", why="adapter: " + str(res.get("error") or "not placed"))
                _note(S, now, f"adapter refused {row['id']}: {res.get('error')}")
            else:
                tr["status"] = "open"
                _note(S, now, f"routed {row['id']}: {'BUY' if d == 1 else 'SELL'} {q} MNQ, stop {row['stop']}, target {tr['target']}"
                              f" ({cfg['account']})")
                out["routed"].append(tr)
            _sync_trades(S, ad, now, last_px)
    S["t"] = int(now)
    S["line"] = line(S, cfg)
    save_state(S, root)
    return out


# ------------------------------------------------------------------------------------------------ words
def line(S: dict, cfg: dict | None = None) -> str:
    cfg = cfg or {}
    day = S.get("day")
    tr = [t for t in S.get("trades") or [] if t.get("day") == day]
    done = [t for t in tr if t["status"] == "closed" and t.get("pnl") is not None and t.get("filled")]
    opn = [t for t in tr if t["status"] in ("sending", "open")]
    ref = [t for t in tr if t["status"] == "refused"]
    usd = sum(t["pnl"] for t in done)
    s = f"OF lane ({cfg.get('account') or 'Sim101'}, {'ON' if cfg.get('on') else 'OFF'}): {len(done)} closed today " \
        f"{'+' if usd >= 0 else '-'}${abs(usd):,.0f}"
    if opn:
        s += f", 1 open ({'LONG' if opn[0]['d'] == 1 else 'SHORT'} {opn[0].get('qty')} MNQ)"
    if ref:
        s += f", {len(ref)} not routed (last: {ref[-1]['why'][:80]})"
    return s


def status_text(root: str = ROOT) -> str:
    cfg = load_cfg(root)
    S = load_state(root)
    allc = S.get("closes") or []
    tot = sum(c["pnl"] for c in allc)
    bad = sim_problem(cfg["account"])
    lines = [f"Order-flow lane: {'ON' if cfg['on'] else 'OFF'} | account {cfg['account']}"
             + (" (simulation)" if not bad else " (REFUSED: not a simulation account)"),
             f"Risk ${float(cfg['risk_usd']):,.0f} a trade, max {cfg['max_micros']} micros, held to {cfg['plan']} {cfg['stage']} rules, "
             f"news blackout {cfg['news_min']} min.",
             f"All lane trades so far: {len(allc)}, {'+' if tot >= 0 else '-'}${abs(tot):,.0f} (simulation money)."]
    if S.get("day"):
        lines.append(line(S, cfg))
    for n in (S.get("log") or [])[-3:]:
        lines.append(f"  {_et(n['t']):%m-%d %H:%M} {n['text']}")
    return "\n".join(lines)


def loop(root: str = ROOT, every: float = 15.0):
    ad = None
    while True:
        try:
            r = tick(root=root, ad=ad)
            ad = r.get("ad") or ad
            for tr in r.get("routed") or []:
                print(_et(time.time()).strftime("%H:%M:%S"), "routed", tr["id"], flush=True)
        except Exception as e:  # noqa: BLE001
            print("of_lane tick error:", e.__class__.__name__, str(e)[:200], flush=True)
        e = _et(time.time())
        if e.hour * 60 + e.minute > 16 * 60 + 10 and not (ad is not None and ad.legs):
            if ad is not None:
                ad.release_lock()
            return
        time.sleep(every)


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(prog="engine.of_lane", description="Order-flow lane on a NinjaTrader SIMULATION account (OFF by default)")
    ap.add_argument("cmd", nargs="?", choices=("tick", "loop", "status"), default="status")
    ap.add_argument("--sim", choices=("on", "off", "status"))
    ap.add_argument("--account")
    a = ap.parse_args(argv)
    if a.sim in ("on", "off"):
        ok, msg = set_switch(a.sim == "on", a.account)
        print(msg)
        return 0 if ok else 1
    if a.sim == "status" or a.cmd == "status":
        print(status_text())
        return 0
    if a.cmd == "tick":
        r = tick()
        print(r.get("refused") or ("OFF: nothing to do" if r.get("off") else r["S"].get("line")))
        return 0
    loop()
    return 0


if __name__ == "__main__":
    sys.exit(main())
