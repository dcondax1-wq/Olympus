"""REAL FILL vs PLAN (Monday launch kit, 2026-11-14: Zlarior on the MFFU 50K eval and ATLAS on its 25K eval go live Monday
2026-11-16 02:00 ET). After each trade NinjaTrader filled, what really happened is set next to what the live loop intended,
and anything off is flagged: a high-priority phone push (tools/pc_report.py) and a line on the Launch card
(engine/live_site.py GET /api/site/launch.json, tools/launch_card.py).

READ ONLY. It reads the bots' own state files on the PC and the NinjaTrader order states the bot already archived. It never
writes a file, never sends, changes or cancels an order, never arms, never changes a setting or live_model*.json.

Sources (all on the main PC, all written by the running bot server):
  data/live_state.json              Zlarior's ledger (engine/live.py _route): every routed entry is the PLAN (the model's entry
                                    price, the stop, the target, the micros the sizer chose, the route time) + NinjaTrader's
                                    answer (result legs: filled, fill price, the bracket's stop / target and their states);
                                    the breakeven moves ("modify"); the exits (model reason, the $ the bot booked)
  data/live_state_acctb.json        ATLAS's ledger (engine/account_b.py), the same row shape
  data/live_state_acctc.json        BLITZ's ledger (engine/account_c.py), the same row shape
  data/ninjatrader_state*.json      each account's open NinjaTrader legs (late fills, bracket status protected / unprotected,
                                    the micros the stop covers)
  logs/exec_audit/legs.json         Zlarior's legs archive and logs/exec_audit/ledger.jsonl its ledger archive
                                    (engine/fill_audit.collect, every minute)
  logs/exec_audit/orders.jsonl      NinjaTrader's outgoing order states of every account (entry / stop / target: state, filled,
  logs/fill_archive.jsonl           average price; ids LE<entry_t><nonce><M|N><E|S|T>): a filled stop or target is the exit price
  logs/learning/costs.json          the learned commission a micro (engine/live_learning.py), when it has learned one

Checks, per trade on a NinjaTrader account (Sim or real; a paper fill is the model price and is not checked):
  size        NinjaTrader filled another number of micros than the bot sent, the stop covers fewer micros than are filled, or
              the bot sent more micros than the account's cap (Zlarior 40, ATLAS / BLITZ 20)
  stop        filled but no stop at NinjaTrader (the bracket was not delivered, was rejected, or the leg is UNPROTECTED), or
              the plan had no stop
  slip_entry  the entry filled more than 2 ticks worse than the plan's price
  slip_exit   a stop filled more than 2 ticks past its price
  stop_off / target_off   the bracket's stop / target more than 2 ticks away from the plan's
  costs       slippage + commission a micro more than 2 ticks ($1.00) above what the sizer prices in (1 tick + $1.90), when no
              single fill was already flagged
  refused     the entry never filled (NinjaTrader refused it or it was cancelled): no position

  reviews(root, now) -> [review] newest first. review = {"acct", "name", "entry_t", "side", "dir", "kind" LIVE|SIM, "strategy",
        "plan" {entry, stop, target, qty, t}, "real" {filled, fill, stop, target, covered, status, exit, exit_kind, exit_t},
        "slip" {entry_ticks, exit_ticks}, "costs" {plan_micro, real_micro, comm, exec_usd}, "flags" [{code, level, text, fix}],
        "ok", "settled", "line"}
  summary(reviews, now) -> the dashboard's small block; push_text(review, flag) -> (title, body) for one phone push.
Tests: tests/test_launch_kit.py (fake state files, never the network).
"""
from __future__ import annotations

import datetime as dt
import json
import os
import time

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
TICK, PV = 0.25, 2.0                     # MNQ: 0.25 point a tick, $2 a point a micro
COMM = 1.90                              # engine/sizing.LIVE_COMM: what the bot books a micro round trip
PLAN_SLIP_TICKS = 1.0                    # the sizer prices one tick of slippage (engine/sizing cost reserve, nothing learned)
SLIP_TICKS = 2.0                         # owner 2026-11-14: slippage above 2 ticks is flagged
OFF_TICKS = 2.0                          # a bracket price more than 2 ticks away from the plan's
COST_TICKS = 2.0                         # costs a micro more than 2 ticks above the plan's
SETTLE_S = 300                           # an entry not filled 5 minutes after it was sent is settled (size / refused checks)
KEEP_S = 36 * 3600                       # trades of the last 36 hours (today and last night)
MAX_MICROS = {"lit": 40, "atlas": 20, "blitz": 20}
NAMES = {"lit": "Zlarior", "atlas": "ATLAS", "blitz": "BLITZ"}
PLANS = {"lit": "50K", "atlas": "25K", "blitz": "25K"}
ACCOUNTS = (("lit", "live_state.json", "ninjatrader_state.json"),
            ("atlas", "live_state_acctb.json", "ninjatrader_state_acctb.json"),
            ("blitz", "live_state_acctc.json", "ninjatrader_state_acctc.json"))
OPEN_STATUS = ("entry_sent", "pending", "cancel_pending")
STOP_OK = ("WORKING", "ACCEPTED", "TRIGGERPENDING", "FILLED", "PARTFILLED", "CHANGEPENDING", "SUBMITTED", "PENDINGSUBMIT")
LEVEL_RANK = {"bad": 3, "warn": 2, "info": 1}
FIX = {
    "size": "Open NinjaTrader > Positions: the position must be the micros the bot sent. If it is not, flatten it there by hand "
            "(right-click > Flatten); the bot keeps managing what it sent.",
    "stop": "Open NinjaTrader now: if this position has no stop order, flatten it there (Positions > right-click > Flatten). "
            "The bot re-sends the stop every poll.",
    "slip_entry": "Nothing to do now. If it repeats, tell Claude: the cost reserve learns from the real fills.",
    "slip_exit": "Nothing to do now. If it repeats, tell Claude: the cost reserve learns from the real fills.",
    "stop_off": "Open NinjaTrader > Orders and check the stop order's price against the plan's.",
    "target_off": "Open NinjaTrader > Orders and check the target order's price against the plan's.",
    "costs": "Nothing to do now; Claude looks at it in the Sunday review.",
    "refused": "Check NinjaTrader is connected (Control Center > Connections) and the MNQ chart has LE_BarFeed; the bot "
               "takes the next setup by itself.",
}
TITLE = {"size": "wrong size", "stop": "NO STOP at NinjaTrader", "slip_entry": "entry slippage", "slip_exit": "stop slippage",
         "stop_off": "stop price off", "target_off": "target price off", "costs": "costs above plan", "refused": "entry not filled"}


# ------------------------------------------------------------------------------------------------ small helpers
def _f(x):
    try:
        v = float(x)
        return v if v == v else None
    except (TypeError, ValueError):
        return None


def _i(x):
    v = _f(x)
    return None if v is None else int(v)


def _d(x) -> dict:
    return x if isinstance(x, dict) else {}


def _l(x) -> list:
    return x if isinstance(x, list) else []


def _read_json(path, default=None):
    try:
        with open(path, "r", encoding="utf-8") as fh:
            return json.load(fh)
    except Exception:
        return default


def _jl_read(path) -> list:
    out = []
    try:
        with open(path, "r", encoding="utf-8") as fh:
            for ln in fh:
                ln = ln.strip()
                if not ln:
                    continue
                try:
                    r = json.loads(ln)
                except ValueError:
                    continue
                if isinstance(r, dict):
                    out.append(r)
    except OSError:
        pass
    return out


def px(v) -> str:
    x = _f(v)
    return "-" if x is None else f"{x:,.2f}"


def usd(v, sign=False) -> str:
    x = _f(v)
    if x is None:
        return "-"
    s = "${:,.0f}".format(abs(x)) if abs(x) >= 10 else "${:,.2f}".format(abs(x))
    return ("-" + s) if x < 0 else (("+" + s) if sign else s)


def ticks_text(t) -> str:
    x = _f(t)
    if x is None:
        return "?"
    x = round(x, 1)
    n = int(x) if float(x).is_integer() else x
    return f"{n} tick" + ("" if abs(x) == 1 else "s")


def et_hm(t) -> str:
    v = _f(t)
    if v is None:
        return "-"
    try:
        from zoneinfo import ZoneInfo
        return dt.datetime.fromtimestamp(v, ZoneInfo("America/New_York")).strftime("%a %H:%M ET")
    except Exception:
        return dt.datetime.fromtimestamp(v, dt.timezone.utc).strftime("%a %H:%M UTC")


def _mult(inst) -> int:
    """micros per contract of a leg's instrument: NQ (the mini) = 10 MNQ, MNQ = 1."""
    s = str(inst or "").strip().upper()
    return 10 if (s.startswith("NQ ") or s == "NQ") else 1


def _is_sim(name) -> bool:
    try:
        from engine.ninjatrader import is_sim
        return bool(is_sim(name))
    except Exception:
        return str(name or "").lower().startswith(("sim", "playback"))


def _rkey(r) -> str:
    return json.dumps([r.get("t"), r.get("side"), r.get("entry_t"), r.get("stop"), r.get("reason")], default=str)


def _merge_rows(*lists) -> list:
    seen, out = set(), []
    for rows in lists:
        for r in rows or []:
            if not isinstance(r, dict) or r.get("t") is None:
                continue
            k = _rkey(r)
            if k in seen:
                continue
            seen.add(k)
            out.append(r)
    return sorted(out, key=lambda r: _f(r.get("t")) or 0)


# ------------------------------------------------------------------------------------------------ the sources
def orders_archive(root: str = ROOT) -> dict:
    """order id -> its newest known state from NinjaTrader's outgoing\\ folder, as the bot archived it (a FILLED state is never
    replaced by a later non-FILLED one, as tools/fill_audit.load_archive)."""
    rows = {}
    for p in (os.path.join(root, "logs", "fill_archive.jsonl"), os.path.join(root, "logs", "exec_audit", "orders.jsonl")):
        for r in _jl_read(p):
            oid = r.get("id")
            if not oid:
                continue
            old = rows.get(oid)
            if old and old.get("state") == "FILLED" and r.get("state") != "FILLED":
                continue
            rows[oid] = r
    return rows


def parse_oid(oid):
    """'LE1792405860ABCDME' -> {"entry_t", "tag", "contract" M|N, "leg" entry|stop|target}; None if not one of ours."""
    try:
        from tools.fill_audit import parse_oid as _p
        return _p(str(oid))
    except Exception:
        return None


def load(root: str = ROOT) -> dict:
    """What the PC's files say right now: {"accounts": {key: {"ledger", "legs"}}, "orders": {(entry_t): {nonce: {leg: [states]}}},
    "comm": {key: learned $ a micro or None}}. Never raises (a missing or broken file is empty)."""
    data = os.path.join(root, "data")
    out = {"accounts": {}, "orders": {}, "comm": {}}
    for key, state_f, nt_f in ACCOUNTS:
        try:
            st = _read_json(os.path.join(data, state_f), {}) or {}
            nt = _read_json(os.path.join(data, nt_f), {}) or {}
            led = [r for r in _l(st.get("ledger")) if isinstance(r, dict)]
            legs = [lg for lg in _l(nt.get("legs")) if isinstance(lg, dict)]
            if key == "lit":
                led = _merge_rows(_jl_read(os.path.join(root, "logs", "exec_audit", "ledger.jsonl")), led)
                arch = _read_json(os.path.join(root, "logs", "exec_audit", "legs.json"), {}) or {}
                have = {lg.get("entry_id") for lg in legs if lg.get("entry_id")}
                legs += [lg for lg in arch.values() if isinstance(lg, dict) and lg.get("entry_id") not in have]
            adapter = st.get("adapter") if key == "lit" else ("ninjatrader" if nt else None)
            out["accounts"][key] = {"ledger": led, "legs": legs, "account": nt.get("account") or st.get("account"), "adapter": adapter}
        except Exception:
            out["accounts"][key] = {"ledger": [], "legs": []}
    try:
        for oid, stt in orders_archive(root).items():
            p = parse_oid(oid)
            if p:
                out["orders"].setdefault(int(p["entry_t"]), {}).setdefault(p["tag"], {}).setdefault(p["leg"], []).append(
                    {**stt, "id": oid, "contract": p["contract"]})
    except Exception:
        pass
    for key in ("lit", "atlas"):
        try:
            from engine import live_learning
            C = live_learning.load_costs(key, path=os.path.join(root, "logs", "learning", "costs.json")) or {}
            out["comm"][key] = _f(C.get("comm")) if C.get("comm_obs") else None
        except Exception:
            out["comm"][key] = None
    return out


# ------------------------------------------------------------------------------------------------ one trade
def _vwap(pairs):
    q = sum(n for _, n in pairs)
    return (sum(p * n for p, n in pairs) / q) if q else None


def _flag(code, level, text) -> dict:
    return {"code": code, "level": level, "text": " ".join(str(text).split()), "fix": FIX.get(code, "")}


def _archive_group(orders: dict, et_: int, legs: list, plan_qty: int):
    """The archived order states of this entry: {leg: [states]} of the right nonce. With two nonces on the same minute (two
    accounts entered on the same bar) the legs' own ids pick it, else the one whose entry fill matches the plan; else none."""
    groups = orders.get(int(et_)) or {}
    if not groups:
        return {}
    ids = {str(lg.get(k)) for lg in legs for k in ("entry_id", "stop_id", "target_id") if lg.get(k)}
    for tag, g in groups.items():
        if any(s.get("id") in ids for ss in g.values() for s in ss):
            return g
    if len(groups) == 1:
        return next(iter(groups.values()))
    for g in groups.values():
        q = sum(int(_f(s.get("filled")) or 0) * (10 if s.get("contract") == "N" else 1) for s in g.get("entry") or [])
        if q == plan_qty:
            return g
    return {}


def review(key: str, e: dict, rows: list, legs: list, orders: dict, now: int, comm=None, acct: dict | None = None) -> dict | None:
    """One routed entry of one account against NinjaTrader. None for a paper / non-NinjaTrader route (nothing to compare) and
    for the bot's own hedging refusal (by design, logged by the bot). acct = {"adapter", "account"} of the account's files."""
    res = _d(e.get("result"))
    A = _d(acct)
    adapter = res.get("adapter") or e.get("adapter") or A.get("adapter")
    if adapter != "ninjatrader":
        return None
    if res.get("ok") is False and "hedg" in str(res.get("error") or "").lower():
        return None
    et_ = int(e["entry_t"])
    d = 1 if e.get("side") == "buy" else -1
    t_route = _i(e.get("t")) or et_
    plan = {"entry": _f(e.get("entry")), "stop": _f(e.get("stop")), "target": _f(e.get("target")), "qty": int(_f(e.get("qty")) or 0),
            "t": t_route}
    nm = res.get("account") or A.get("account")
    kind = "SIM" if (res.get("env") == "demo" or (nm and _is_sim(nm))) else "LIVE"
    rl = [lg for lg in _l(res.get("legs")) if isinstance(lg, dict)]
    al = [lg for lg in legs if _i(lg.get("entry_t")) == et_]
    grp = _archive_group(orders, et_, al, plan["qty"])
    # ---- the entry fill: the route answer, then the adapter's legs (late fills), then the archived entry order
    pairs_r = [(float(lg["fill_px"]), int(_f(lg.get("filled")) or 0) * _mult(lg.get("instrument"))) for lg in rl
               if _f(lg.get("fill_px")) is not None and int(_f(lg.get("filled")) or 0) > 0]
    pairs_a = [(float(lg["fill_px"]), int(_f(lg.get("filled")) or 0) * _mult(lg.get("instrument"))) for lg in al
               if _f(lg.get("fill_px")) is not None and int(_f(lg.get("filled")) or 0) > 0]
    pairs_o = [(float(s["avg"]), int(_f(s.get("filled")) or 0) * (10 if s.get("contract") == "N" else 1)) for s in grp.get("entry") or []
               if _f(s.get("avg")) and int(_f(s.get("filled")) or 0) > 0]
    best = max((pairs_r, pairs_a, pairs_o), key=lambda p: sum(n for _, n in p))
    filled = sum(n for _, n in best)
    fill = _vwap(best)
    status = [str(lg.get("status")) for lg in al if lg.get("status")]
    covered = sum(int(_f(lg.get("bracket_qty")) or 0) * _mult(lg.get("instrument")) for lg in al) if al else None
    if covered is None and rl and all(lg.get("ok") for lg in rl if int(_f(lg.get("filled")) or 0) > 0) and filled:
        covered = filled
    # the bracket's stop / target as NinjaTrader got them (route answer, else the leg)
    b_stop = next((_f(lg.get("stop")) for lg in rl if _f(lg.get("stop")) is not None and lg.get("ok")), None)
    if b_stop is None:
        b_stop = next((_f(lg.get("stop0") or lg.get("stop")) for lg in al if _f(lg.get("stop0") or lg.get("stop")) is not None), None)
    b_tgt = next((_f(lg.get("target")) for lg in rl if _f(lg.get("target")) is not None and lg.get("ok")), None)
    if b_tgt is None:
        b_tgt = next((_f(lg.get("target")) for lg in al if _f(lg.get("target")) is not None), None)
    stop_states = [str(lg.get("stop_state")).upper() for lg in rl if lg.get("stop_state")] + \
                  [str(s.get("state")).upper() for s in grp.get("stop") or [] if s.get("state")]
    # ---- breakeven moves and the exit
    mods = [r for r in rows if r.get("side") == "modify" and _i(r.get("entry_t")) == et_ and _d(r.get("result")).get("ok") is not False]
    exits = [r for r in rows if r.get("side") == "exit" and _i(r.get("entry_t")) == et_]
    stop_level = _f(mods[-1].get("stop")) if mods else (b_stop if b_stop is not None else plan["stop"])
    ex_px = ex_kind = ex_t = None
    for leg, kind_x in (("stop", "STOP"), ("target", "TARGET")):
        for s in grp.get(leg) or []:
            if str(s.get("state")).upper() == "FILLED" and _f(s.get("avg")):
                ex_px, ex_kind, ex_t = float(s["avg"]), ("BE" if kind_x == "STOP" and mods else kind_x), _i(s.get("mtime"))
    model_exit = exits[-1] if exits else None
    if ex_kind is None and model_exit:
        ex_kind = str(model_exit.get("reason") or "EXIT").upper()
        ex_t = _i(model_exit.get("exit_t")) or _i(model_exit.get("t"))
    closed = bool(ex_px is not None or model_exit is not None or any(lg.get("closed") for lg in al))
    waited = now - t_route >= SETTLE_S        # a market order fills at once; a partial fill is resized by the next ticks
    settled = waited or closed or (bool(filled) and bool(status) and not any(s in OPEN_STATUS for s in status))
    # ---- slippage (+ = worse for us)
    slip_e = round((fill - plan["entry"]) * d / TICK, 2) if fill is not None and plan["entry"] is not None else None
    slip_x = None
    if ex_px is not None and ex_kind in ("STOP", "BE") and stop_level is not None:
        slip_x = round((stop_level - ex_px) * d / TICK, 2)
    elif ex_px is not None and ex_kind == "TARGET" and (b_tgt or plan["target"]) is not None:
        slip_x = round(((b_tgt or plan["target"]) - ex_px) * d / TICK, 2)
    cm = _f(comm) if _f(comm) else COMM
    plan_micro = round(COMM + PLAN_SLIP_TICKS * TICK * PV, 2)
    real_micro = round(cm + max(0.0, slip_e or 0.0) * TICK * PV + (max(0.0, slip_x or 0.0) * TICK * PV if slip_x is not None else 0.0), 2)
    exec_usd = None
    if ex_px is not None and fill is not None and filled:
        real_pnl = filled * ((ex_px - fill) * d * PV - cm)
        booked = _f(model_exit.get("pnl")) if model_exit else None
        exec_usd = round(real_pnl - booked, 2) if booked is not None else None
    # ---- the flags
    flags = []
    name = NAMES.get(key, key.upper())
    side = "LONG" if d == 1 else "SHORT"
    if plan["stop"] is None:
        flags.append(_flag("stop", "bad", f"The plan of this {side} had no stop price."))
    if filled:
        unprot = any(s == "unprotected" for s in status)
        not_deliv = any(("bracket not delivered" in str(lg.get("error") or "").lower() or "unprotected" in str(lg.get("error") or "").lower())
                        for lg in rl)
        protected_later = any(s in ("protected", "closing") for s in status) or any(s in STOP_OK for s in stop_states)
        rejected = any(s == "REJECTED" for s in stop_states)
        if unprot or rejected or (not_deliv and not protected_later):
            why = ("NinjaTrader rejected the stop order" if rejected else
                   "the stop and target could not be delivered" if not_deliv and not protected_later else "the leg is UNPROTECTED")
            flags.append(_flag("stop", "bad", f"{side} {filled} filled at {px(fill)} but {why}: no stop at NinjaTrader"
                                              + (" (the trade is closed now)" if closed else "") + "."))
    if (waited or closed) and filled and plan["qty"] and filled != plan["qty"]:
        flags.append(_flag("size", "bad", f"NinjaTrader filled {filled} micros, the bot sent {plan['qty']}."))
    if waited and filled and covered is not None and covered < filled and not closed and not any(s in OPEN_STATUS for s in status):
        flags.append(_flag("size", "bad", f"The stop covers {covered} of the {filled} filled micros."))
    cap = MAX_MICROS.get(key)
    if cap and plan["qty"] > cap:
        flags.append(_flag("size", "bad", f"The bot sent {plan['qty']} micros, above {name}'s cap of {cap}."))
    if slip_e is not None and slip_e > SLIP_TICKS:
        flags.append(_flag("slip_entry", "warn", f"Entry filled {ticks_text(slip_e)} worse than the plan ({px(fill)} vs {px(plan['entry'])}): "
                                                 f"{usd(slip_e * TICK * PV * filled)} on {filled} micros."))
    if slip_x is not None and slip_x > SLIP_TICKS and ex_kind in ("STOP", "BE"):
        flags.append(_flag("slip_exit", "warn", f"The stop filled {ticks_text(slip_x)} past its price ({px(ex_px)} vs {px(stop_level)}): "
                                                f"{usd(slip_x * TICK * PV * filled)} on {filled} micros."))
    if b_stop is not None and plan["stop"] is not None and abs(b_stop - plan["stop"]) / TICK > OFF_TICKS:
        flags.append(_flag("stop_off", "bad", f"The stop at NinjaTrader is {px(b_stop)}, the plan said {px(plan['stop'])} "
                                              f"({ticks_text(abs(b_stop - plan['stop']) / TICK)} apart)."))
    if b_tgt is not None and plan["target"] is not None and abs(b_tgt - plan["target"]) / TICK > OFF_TICKS:
        flags.append(_flag("target_off", "warn", f"The target at NinjaTrader is {px(b_tgt)}, the plan said {px(plan['target'])} "
                                                 f"({ticks_text(abs(b_tgt - plan['target']) / TICK)} apart)."))
    if filled and real_micro - plan_micro > COST_TICKS * TICK * PV + 1e-9 and not any(f["code"].startswith("slip") for f in flags):
        flags.append(_flag("costs", "warn", f"Costs {usd(real_micro)} a micro (slippage + commission), the plan prices {usd(plan_micro)}."))
    if waited and not filled and not any(s in OPEN_STATUS for s in status):
        err = str(res.get("error") or res.get("note") or "").strip()
        if "fill not reported yet" in err.lower():
            err = "sent, but NinjaTrader never reported a fill"
        flags.append(_flag("refused", "warn", f"The {side} {plan['qty']} entry never filled at NinjaTrader"
                                              + (f" ({err[:140]})" if err else "") + ": no position."))
    out = {"acct": key, "name": name, "label": f"{name} {PLANS.get(key, '')}".strip(), "entry_t": et_, "side": side, "dir": d,
           "kind": kind, "strategy": e.get("strategy") or e.get("src") or ("LIT" if key == "lit" else None), "plan": plan,
           "real": {"filled": filled, "fill": None if fill is None else round(fill, 2), "stop": b_stop, "target": b_tgt, "covered": covered,
                    "status": status[-1] if status else None, "exit": ex_px, "exit_kind": ex_kind, "exit_t": ex_t, "closed": closed},
           "slip": {"entry_ticks": slip_e, "exit_ticks": slip_x},
           "costs": {"plan_micro": plan_micro, "real_micro": real_micro if filled else None, "comm": cm, "exec_usd": exec_usd},
           "flags": flags, "ok": not flags, "settled": settled,
           "level": max((f["level"] for f in flags), key=lambda x: LEVEL_RANK.get(x, 0)) if flags else "ok"}
    out["line"] = line(out)
    return out


def line(r: dict) -> str:
    """One plain sentence for the dashboard."""
    P, R = _d(r.get("plan")), _d(r.get("real"))
    head = f"{r.get('label')} {r.get('side')} {et_hm(r.get('entry_t'))}"
    if not R.get("filled"):
        body = "not filled" if r.get("settled") else "entry sent, waiting for the fill"
    else:
        se = _d(r.get("slip")).get("entry_ticks")
        body = (f"filled {R['filled']} of {P.get('qty')} at {px(R.get('fill'))}"
                + (f" (plan {px(P.get('entry'))}, {ticks_text(se)} {'worse' if se > 0 else 'better' if se < 0 else 'same'})" if se is not None else "")
                + (f", stop {px(R.get('stop') if R.get('stop') is not None else P.get('stop'))}" if (R.get("stop") or P.get("stop")) is not None else ", NO STOP"))
        if R.get("exit") is not None:
            sx = _d(r.get("slip")).get("exit_ticks")
            body += f", out {str(R.get('exit_kind') or '').lower()} at {px(R['exit'])}" + (f" ({ticks_text(sx)} past)" if sx and sx > 0 else "")
        elif R.get("exit_kind"):
            body += f", out {str(R['exit_kind']).lower()} (no exit price from NinjaTrader)"
    fl = r.get("flags") or []
    tail = "fill check OK" if not fl else ("; ".join(TITLE.get(f["code"], f["code"]) for f in fl))
    return f"{head}: {body}. {tail[0].upper() + tail[1:]}."


def reviews(root: str = ROOT, now=None, src: dict | None = None, keep_s: int = KEEP_S) -> list:
    """Every trade NinjaTrader handled in the last keep_s seconds, newest first. src = load(root) (tests pass their own).
    Never raises (a broken trade is left out)."""
    now = int(now or time.time())
    S = src if isinstance(src, dict) else load(root)
    out = []
    for key, _a, _b in ACCOUNTS:
        A = _d(_d(S.get("accounts")).get(key))
        rows = [r for r in _l(A.get("ledger")) if isinstance(r, dict)]
        ents = {}
        for r in rows:
            if r.get("side") in ("buy", "sell") and _i(r.get("entry_t")) is not None:
                et_ = int(r["entry_t"])
                if now - et_ > keep_s or et_ > now + 3600:
                    continue
                prev = ents.get(et_)
                ok = _d(r.get("result")).get("ok") is not False
                if prev is None or ok or _d(prev.get("result")).get("ok") is False:
                    ents[et_] = r                  # the last accepted send of the entry (a re-send after a refusal wins)
        for et_, e in ents.items():
            try:
                rv = review(key, e, rows, _l(A.get("legs")), _d(S.get("orders")), now, comm=_d(S.get("comm")).get(key), acct=A)
            except Exception:
                rv = None
            if rv:
                out.append(rv)
    out.sort(key=lambda r: r["entry_t"], reverse=True)
    return out


def summary(revs: list, now=None, n: int = 6) -> dict:
    """The dashboard's block: today's checked trades and flags per account + the last rows."""
    now = int(now or time.time())
    try:
        from engine.live_board import trading_day
        today = trading_day(now)
        day = lambda t: trading_day(t)          # noqa: E731
    except Exception:
        today, day = None, (lambda t: None)
    rows = [r for r in revs or [] if isinstance(r, dict)]
    tod = [r for r in rows if today is None or day(r["entry_t"]) == today]
    by = {}
    for r in tod:
        b = by.setdefault(r["acct"], {"trades": 0, "flags": [], "last": None})
        b["trades"] += 1
        b["flags"] += [{**f, "entry_t": r["entry_t"]} for f in r.get("flags") or []]
        b["last"] = b["last"] or r["line"]
    return {"v": 1, "t": now, "day": today, "n": len(tod), "n_flags": sum(len(r.get("flags") or []) for r in tod), "by": by,
            "rows": [{k: r.get(k) for k in ("acct", "label", "entry_t", "side", "kind", "level", "line", "ok")} for r in rows[:n]]}


def push_text(r: dict, f: dict) -> tuple:
    """(title, body) of one flag's phone push (title ASCII, short; body: what, the numbers, the one action)."""
    kind = "real account" if r.get("kind") == "LIVE" else "Sim"
    title = f"{r.get('label')} fill check: {TITLE.get(f['code'], f['code'])}"
    P = _d(r.get("plan"))
    body = (f"{r.get('side')} {P.get('qty')} at {et_hm(r.get('entry_t'))} ({kind}): {f['text']} "
            f"Plan: entry {px(P.get('entry'))}, stop {px(P.get('stop'))}, target {px(P.get('target'))}, {P.get('qty')} micros. "
            + (f"Do: {f['fix']}" if f.get("fix") else ""))
    return title, " ".join(body.split())


def short(r: dict | None) -> str:
    """The fill check in a few words for a trade push ('Fill check OK: 6 of 6 filled, 1 tick from the plan, stop in place')."""
    if not isinstance(r, dict):
        return ""
    R, P = _d(r.get("real")), _d(r.get("plan"))
    if r.get("flags"):
        return "Fill check: " + "; ".join(TITLE.get(f["code"], f["code"]) for f in r["flags"]) + " (separate alert)."
    if not R.get("filled"):
        return ""
    se = _d(r.get("slip")).get("entry_ticks")
    return (f"Fill check OK: {R['filled']} of {P.get('qty')} filled"
            + (f", {ticks_text(abs(se))} {'worse' if se > 0 else 'better'} than the plan" if se else ", at the plan's price" if se == 0 else "")
            + (", the stop was in place." if R.get("closed") else ", stop in place."))


def main(argv=None) -> int:
    import argparse
    ap = argparse.ArgumentParser(description="Real fills vs the live loop's plan (read-only).")
    ap.add_argument("--hours", type=float, default=36.0)
    a = ap.parse_args(argv)
    revs = reviews(keep_s=int(a.hours * 3600))
    if not revs:
        print("  no NinjaTrader trade in the last", a.hours, "hours")
    for r in revs:
        print(("  [OK]  " if r["ok"] else "  [FIX] ") + r["line"])
        for f in r["flags"]:
            print(f"        {f['code']}: {f['text']}  Do: {f['fix']}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
