"""LIVE vs BACKTEST reconciliation of every real trade so far (2026-11-21, day-atlasedge, lead's task).
READ ONLY: reads the PC's day folders and the stored research files, writes research/lab/reconcile.json. Never trades, sizes,
routes or changes a setting; never edits live code.

    python -X utf8 tools/reconcile_live.py            # -> research/lab/reconcile.json + the owner table
    python -X utf8 tools/reconcile_live.py --print    # no file

Sources, best first:
  data/pc_days/<day>/  (tools/data_pull.py --latest; on the PC itself: logs/datapipe/days/<day>/ is read too)
    trades.jsonl.gz    the ledger rows (model entry / stop / target, the broker legs' fill, the exit row: reason, qty, booked $)
    fills.jsonl.gz     every MARKET entry: sent / filled seconds after the bar open, NinjaTrader's fill price and filled qty
    twin.json.gz       engine/fill_audit's nightly rows (Zlarior): the backtest twin's entry / exit, the live exit priced from
                       NinjaTrader's order states, missed / extra trades
    decisions.jsonl.gz the entries the bot held back (feed stale, sizer, late, refused)
  research/second/atlas_fills_why.json   the stored real-fill study (2026-11-20), when no day folder has a trade
  data/board/  owner notes (typed): a trade the owner closed or moved by hand is "manual"
Per trade: bot, account (key + last 4 only), signal time, model entry vs real fill (ticks, $), model exit vs real exit, model R
vs real R, $ difference, cause (latency, slippage, missed, partial, manual, exit, none). Real exit = NinjaTrader's priced exit
when known, else the model's exit (flagged "exit not priced": the bot books its ledger at the model's prices).
Totals per bot: real $ a trade vs model, the measured entry ticks, the implied real-cost PF (tools/cost_alarm at the measured
cost) and whether the nightly cost alarm agrees (same measured cost, same flag).
"""
from __future__ import annotations

import argparse
import datetime as dt
import glob
import gzip
import json
import os
import re
import sys
from zoneinfo import ZoneInfo

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)
OUT = os.path.join(ROOT, "research", "lab", "reconcile.json")
ET = ZoneInfo("America/New_York")
TICK, PV, COMM = 0.25, 2.0, 1.90
SLIP_T = 2.0            # ticks past the model (which already has 1) before "slippage" is the cause
LATE_S = 3.0            # seconds from the bar open to the order before "latency" is named
EXIT_T = 2.0
DAY_DIRS = (os.path.join(ROOT, "data", "pc_days"), os.path.join(ROOT, "logs", "datapipe", "days"))
HIDDEN = re.compile(r"blitz|v2|fleet|shadow", re.I)


def _f(v):
    try:
        x = float(v)
    except (TypeError, ValueError):
        return None
    return x if x == x and abs(x) != float("inf") else None


def _jl(path):
    if not os.path.exists(path):
        return []
    out = []
    try:
        with gzip.open(path, "rt", encoding="utf-8") as fh:
            for ln in fh:
                ln = ln.strip()
                if ln:
                    try:
                        out.append(json.loads(ln))
                    except ValueError:
                        continue
    except (OSError, EOFError):
        return out
    return out


def _js(path):
    try:
        with gzip.open(path, "rt", encoding="utf-8") as fh:
            return json.load(fh)
    except Exception:  # noqa: BLE001
        return None


def _hm(t):
    return dt.datetime.fromtimestamp(int(t), ET).strftime("%a %b %-d %H:%M")


def _a4(x):
    d = re.findall(r"\d", str(x or ""))
    return "..." + "".join(d[-4:]) if len(d) >= 4 else (str(x)[:12] if str(x or "").lower().startswith("sim") else None)


def day_folders():
    seen = {}
    for base in DAY_DIRS:
        for p in sorted(glob.glob(os.path.join(base, "20??-??-??"))):
            seen.setdefault(os.path.basename(p), p)
    return [seen[d] for d in sorted(seen)]


def bot_of(r):
    b = str(r.get("bot") or "")
    if b == "atlas" or "acctb" in str(r.get("src") or "") or "acctb" in str(r.get("acct") or ""):
        return "ATLAS"
    return "Zlarior"


def owner_notes():
    """[(t, text)] of the owner's typed notes on the board (manual actions)."""
    out = []
    p = os.path.join(ROOT, "data", "board", "shared.jsonl")
    try:
        for ln in open(p, encoding="utf-8"):
            try:
                e = json.loads(ln)
            except ValueError:
                continue
            if "owner" in str(e.get("kind") or e.get("who") or "") and e.get("t"):
                out.append((int(e["t"]), str(e.get("text") or e.get("body") or "")))
    except OSError:
        pass
    return out


MANUAL = re.compile(r"\b(closed|flatten|flattened|moved (the|my) stop|by hand|manual|cut it|took it off)\b", re.I)


def trades_of_day(folder):
    rows = _jl(os.path.join(folder, "trades.jsonl.gz"))
    fills = {int(r["entry_t"]): r for r in _jl(os.path.join(folder, "fills.jsonl.gz")) if r.get("entry_t") is not None
             and r.get("leg", "entry") == "entry" and r.get("lane", "zlarior") in ("zlarior", None)}   # entries of the main account
    tw = _js(os.path.join(folder, "twin.json.gz")) or {}
    twin = {}
    for r in ((tw.get("nightly") or {}).get("rows") or []):
        if r.get("entry_t") is not None:
            twin[int(r["entry_t"])] = r
    held = [r for r in _jl(os.path.join(folder, "decisions.jsonl.gz")) if r.get("src") == "held_back"]
    ent, ex = {}, {}
    for r in rows:
        if r.get("mode") != "live" or r.get("entry_t") is None or HIDDEN.search(str(r.get("bot") or "")) \
                or str(r.get("src") or "").startswith("fleet"):
            continue
        k = (bot_of(r), str(r.get("acct") or ""), int(r["entry_t"]))
        if r.get("side") in ("buy", "sell"):
            ent[k] = r
        elif r.get("side") == "exit" and str(r.get("reason") or "").upper() != "NO TRADE":
            ex[k] = r
    return ent, ex, fills, twin, held, tw


def row_of(k, e, x, fl, tw, notes):
    bot, acct, et = k
    d = 1 if e.get("side") == "buy" else -1
    res = e.get("result") if isinstance(e.get("result"), dict) else {}
    legs = [lg for lg in (res.get("legs") or []) if isinstance(lg, dict) and lg.get("filled")]
    q_routed = int(e.get("qty") or 0) or None
    q_leg = sum(int(lg.get("filled") or 0) for lg in legs) or None
    fill = None
    if legs and q_leg:
        fill = sum(float(lg.get("fill_px") or 0) * int(lg.get("filled") or 0) for lg in legs) / q_leg
    if fl and _f(fl.get("fill_px")) is not None:
        fill = _f(fl.get("fill_px"))
    q_fill = int(_f((fl or {}).get("filled")) or 0) or q_leg
    m_entry, stop, tgt = _f(e.get("entry")), _f(e.get("stop")), _f(e.get("target"))
    q = int((x or {}).get("qty") or q_fill or q_routed or 1)
    risk = abs(m_entry - stop) if m_entry is not None and stop is not None else None
    m_exit = _f((x or {}).get("exit_px")) or _f((x or {}).get("price"))
    if m_exit is None and x and _f(x.get("pnl")) is not None and m_entry is not None:
        m_exit = round(m_entry + d * (float(x["pnl"]) + COMM * q) / (PV * q), 2)
    real_exit, exit_src = m_exit, "model (exit not priced)"
    if tw and _f(tw.get("live_exit")) is not None and tw.get("exit_src") not in (None, "model (broker close not priced)"):
        real_exit, exit_src = _f(tw["live_exit"]), str(tw.get("exit_src"))
    if tw and _f(tw.get("bt_exit")) is not None:
        m_exit = _f(tw["bt_exit"])
    fill = fill if fill is not None else m_entry
    out = {"bot": bot, "account": _a4(acct) or acct[:16], "day": (x or e).get("day") or dt.datetime.fromtimestamp(et, ET).date().isoformat(),
           "signal": _hm(et), "entry_t": et, "side": "LONG" if d == 1 else "SHORT", "member": e.get("strategy") or "",
           "qty_routed": q_routed, "qty_filled": q_fill, "model_entry": m_entry, "real_fill": round(fill, 2) if fill is not None else None,
           "stop": stop, "target": tgt, "model_exit": m_exit, "real_exit": real_exit, "exit_src": exit_src,
           "exit_kind": str((x or {}).get("reason") or "OPEN").upper()[:14],
           "sent_s": _f((fl or {}).get("sent_s_after_open")), "fill_s": _f((fl or {}).get("fill_s_after_sent"))}
    out["entry_ticks"] = round((fill - m_entry) * d / TICK, 1) if fill is not None and m_entry is not None else None
    out["entry_usd"] = round(-(out["entry_ticks"] or 0) * TICK * PV * q, 2)
    if real_exit is not None and m_exit is not None:
        out["exit_ticks"] = round((m_exit - real_exit) * d / TICK, 1)
        out["exit_usd"] = round(-out["exit_ticks"] * TICK * PV * q, 2)
    if m_exit is not None and m_entry is not None:
        out["model_usd"] = round((m_exit - m_entry) * d * PV * q - COMM * q, 2)
        out["model_r"] = round((m_exit - m_entry) * d / risk, 2) if risk else None
    if real_exit is not None and fill is not None:
        out["real_usd"] = round((real_exit - fill) * d * PV * q - COMM * q, 2)
        out["real_r"] = round((real_exit - fill) * d / risk, 2) if risk else None
    out["booked_usd"] = _f((x or {}).get("pnl"))
    if out.get("real_usd") is not None and out.get("model_usd") is not None:
        out["diff_usd"] = round(out["real_usd"] - out["model_usd"], 2)
    # cause (the biggest named one first)
    why = []
    xt = int((x or {}).get("exit_t") or (x or {}).get("t") or 0)
    if any(et - 600 <= t <= (xt or et + 86400) + 3600 and MANUAL.search(s) for t, s in notes) or "MANUAL" in out["exit_kind"] \
            or "FLAT" in out["exit_kind"] and "EOD" not in out["exit_kind"]:
        why.append("manual")
    if q_routed and q_fill and q_fill < q_routed:
        why.append(f"partial ({q_fill} of {q_routed})")
    if (out["entry_ticks"] or 0) > SLIP_T:
        why.append("latency + slippage" if (out["sent_s"] or 0) > LATE_S else "slippage")
    elif (out["sent_s"] or 0) > LATE_S:
        why.append("latency")
    if (out.get("exit_ticks") or 0) > EXIT_T:
        why.append("exit slippage")
    if tw and tw.get("bt_exit_reason") and tw.get("live_exit_kind") and str(tw["bt_exit_reason"]).upper() != str(tw["live_exit_kind"]).upper():
        why.append(f"outcome differs (model {tw['bt_exit_reason']}, real {tw['live_exit_kind']})")
    out["cause"] = ", ".join(why) or "none"
    out["status"] = "closed" if x else "open"
    return out


def from_folders():
    T, missed, notes = [], [], owner_notes()
    for f in day_folders():
        ent, ex, fills, twin, held, tw = trades_of_day(f)
        for k, e in sorted(ent.items(), key=lambda kv: kv[0][2]):
            if (e.get("result") or {}).get("ok") is False:
                missed.append({"bot": k[0], "day": os.path.basename(f), "signal": _hm(k[2]), "entry_t": k[2],
                               "cause": "missed (refused by the broker)", "reason": str((e.get("result") or {}).get("error") or "")[:120]})
                continue
            T.append(row_of(k, e, ex.get(k), fills.get(k[2]), twin.get(k[2]), notes))
        for r in ((tw.get("nightly") or {}).get("rows") or []):
            if r.get("status") == "missed":
                missed.append({"bot": "Zlarior", "day": r.get("day"), "signal": _hm(r["entry_t"]), "entry_t": int(r["entry_t"]),
                               "cause": "missed", "reason": r.get("reason"), "model_usd": _f(r.get("bt_pnl") or r.get("missed_usd"))})
        for h in held:
            if not any(m["entry_t"] == int(h.get("entry_t") or 0) for m in missed):
                missed.append({"bot": "ATLAS" if "acctb" in json.dumps(h) or "ATLAS" in json.dumps(h) else "Zlarior",
                               "day": os.path.basename(f), "signal": _hm(int(h.get("entry_t") or 0)), "entry_t": int(h.get("entry_t") or 0),
                               "cause": "held back", "reason": str(h.get("reason") or h.get("why") or "")[:120]})
    return T, missed


def model_exit_of(bot, entry_t, day, entry, stop, d):
    """The model's exit of a real trade: ATLAS = the live-code replay (research/second/atlas_more_fresh.json, same entry
    time); Zlarior = the edge check's fresh LIT trade of that day (research/lab/edge_health.json, one trade a day)."""
    try:
        if bot == "ATLAS":
            o = json.load(open(os.path.join(ROOT, "research", "second", "atlas_more_fresh.json"), encoding="utf-8"))
            for L in o["trades"].values():
                for t in L:
                    if int(t["entry_t"]) == entry_t and abs(float(t["entry"]) - entry) < 0.01:
                        return float(t["exit"]), str(t["exit_kind"]), "the ATLAS live-code replay"
        else:
            e = json.load(open(os.path.join(ROOT, "research", "lab", "edge_health.json"), encoding="utf-8"))
            L = [t for t in e.get("fresh_trades") or [] if t.get("day") == day]
            if len(L) == 1 and stop is not None:
                t = L[0]
                k = str(t.get("exit") or "").upper()
                xpx = stop - d * TICK if k == "STOP" else entry + d * float(t["r"]) * float(t["risk_pts"])
                return round(xpx, 2), k, "the edge check's LIT replay"
    except Exception:  # noqa: BLE001
        return None
    return None


def from_study():
    """No day folder: the stored real-fill study (entries only; exits from the model)."""
    p = os.path.join(ROOT, "research", "second", "atlas_fills_why.json")
    if not os.path.exists(p):
        return []
    out = []
    for f in json.load(open(p, encoding="utf-8")).get("fills") or []:
        d = 1 if f["side"] == "BUY" else -1
        q = int(f.get("qty") or 1)
        risk = _f(f.get("risk_pts_model") or f.get("risk_pts"))
        tk = float(f["ticks_vs_model"])
        mx = model_exit_of(f["bot"], int(f["entry_t"]), f["day"], float(f["model"]), _f(f.get("stop")), d)
        extra = {}
        if mx:
            xpx, kind, src = mx
            m_usd = round((xpx - float(f["model"])) * d * PV * q - COMM * q, 2)
            r_usd = round((xpx - float(f["fill"])) * d * PV * q - COMM * q, 2)
            extra = {"model_exit": xpx, "real_exit": xpx, "exit_kind": kind, "exit_src": f"model exit from {src} (real exit not priced)",
                     "model_usd": m_usd, "real_usd": r_usd, "diff_usd": round(r_usd - m_usd, 2),
                     "model_r": round((xpx - float(f["model"])) * d / risk, 2) if risk else None,
                     "real_r": round((xpx - float(f["fill"])) * d / risk, 2) if risk else None}
        out.append({"bot": f["bot"], "account": None, "day": f["day"], "signal": _hm(f["entry_t"]), "entry_t": int(f["entry_t"]),
                    "side": "LONG" if d == 1 else "SHORT", "member": f.get("member") or "", "qty_routed": q, "qty_filled": q,
                    "model_entry": f["model"], "real_fill": f["fill"], "stop": _f(f.get("stop")), "entry_ticks": tk,
                    "entry_usd": round(-tk * TICK * PV * q, 2), "sent_s": _f(f.get("ledger_s_after_open")),
                    "exit_src": "not in the study (entries only)", "diff_usd": round(-tk * TICK * PV * q, 2),
                    "model_r": None, "real_r": None, "risk_pts": risk,
                    "real_r_minus_model": round(-tk * TICK / risk, 3) if risk else None,
                    "cause": ("latency + slippage" if (f.get("ledger_s_after_open") or 0) > LATE_S else "slippage") if tk > SLIP_T else "none",
                    "status": "closed", "src": "research/second/atlas_fills_why.json", **extra})
    return out


def totals(T, missed):
    from tools import cost_alarm as CA
    out = {}
    for bot in ("Zlarior", "ATLAS"):
        L = [t for t in T if t["bot"] == bot]
        ticks = sorted(t["entry_ticks"] for t in L if t.get("entry_ticks") is not None)
        med = (ticks[len(ticks) // 2] if len(ticks) % 2 else (ticks[len(ticks) // 2 - 1] + ticks[len(ticks) // 2]) / 2) if ticks else None
        closed = [t for t in L if t.get("real_usd") is not None and t.get("model_usd") is not None]
        o = {"trades": len(L), "closed_priced": len(closed), "missed_or_held": sum(1 for m in missed if m["bot"] == bot),
             "entry_ticks_median": med, "entry_ticks": ticks,
             "entry_usd_total": round(sum(t.get("entry_usd") or 0 for t in L), 2),
             "exit_priced": sum(1 for t in L if str(t.get("exit_src", "")).startswith(("model", "not")) is False)}
        if closed:
            o["real_usd_per_trade"] = round(sum(t["real_usd"] for t in closed) / len(closed), 2)
            o["model_usd_per_trade"] = round(sum(t["model_usd"] for t in closed) / len(closed), 2)
            o["diff_usd_per_trade"] = round(o["real_usd_per_trade"] - o["model_usd_per_trade"], 2)
            o["real_usd"] = round(sum(t["real_usd"] for t in closed), 2)
            o["model_usd"] = round(sum(t["model_usd"] for t in closed), 2)
        o["causes"] = {}
        for t in L:
            for c in (t.get("cause") or "none").split(", "):
                c = c.split(" (")[0]
                o["causes"][c] = o["causes"].get(c, 0) + 1
        # the implied real-cost PF (cost_alarm's re-pricing at THIS measured cost) and the alarm's own reading
        key = bot.lower()
        M_here = {key: {"n": len(ticks), "med": med or 0.0, "src": "reconcile"}}
        try:
            mine = CA.check(key, M_here)
            alarm = CA.check(key, CA.measured())
            o["implied_pf40"], o["implied_pf_2026_h1"], o["flag_here"] = mine["pf40"], mine["pf_2026_h1"], mine["flag"]
            o["alarm"] = {"flag": alarm["flag"], "fills": alarm["fills"], "pf40": alarm["pf40"]}
            same_cost = abs(float(alarm["fills"]["med"]) - float(med or 0)) < 0.51 and int(alarm["fills"]["n"]) == len(ticks)
            o["alarm_agrees"] = bool(same_cost and alarm["flag"] == mine["flag"])
            o["alarm_note"] = ("same measured cost and flag" if o["alarm_agrees"] else
                               f"alarm reads {alarm['fills']['n']} fills at {alarm['fills']['med']:+.0f} ticks ({alarm['fills']['src']}); "
                               f"reconcile {len(ticks)} at {(med or 0):+.0f}: flags {alarm['flag']} / {mine['flag']}")
        except Exception as e:  # noqa: BLE001
            o["alarm_note"] = f"cost alarm not run: {e.__class__.__name__}: {e}"
        out[bot] = o
    return out


def build():
    T, missed = from_folders()
    src = "data/pc_days day folders" if T or missed else None
    if not T:
        T = from_study()
        src = "research/second/atlas_fills_why.json (no day folder pulled: entries only)" if T else "none"
    T.sort(key=lambda t: t["entry_t"])
    return {"v": 1, "built": dt.datetime.now(dt.timezone.utc).isoformat(timespec="seconds"), "source": src,
            "what": "Every real trade vs its model (backtest) price: read-only, changes no bot.",
            "days": [os.path.basename(f) for f in day_folders()], "trades": T, "missed": missed, "totals": totals(T, missed)}


def table(o):
    L = ["| Bot | Trades | Entry fill vs model (median) | Real $ a trade vs model | $ lost to fills | Implied PF at real cost (last 40) | Cost alarm agrees |",
         "|---|---:|---|---|---:|---|---|"]
    for bot, t in o["totals"].items():
        med = "" if t["entry_ticks_median"] is None else f"{t['entry_ticks_median']:+.0f} ticks"
        L.append(f"| {bot} | {t['trades']} | {med} | "
                 f"{('$%+.0f vs $%+.0f' % (t['real_usd_per_trade'], t['model_usd_per_trade'])) if 'real_usd_per_trade' in t else 'exits not priced'} | "
                 f"${-t['entry_usd_total']:,.0f} | {t.get('implied_pf40')} | {'yes' if t.get('alarm_agrees') else 'no: ' + str(t.get('alarm_note'))} |")
    return "\n".join(L)


def main(argv=None):
    ap = argparse.ArgumentParser()
    ap.add_argument("--print", action="store_true", dest="show")
    a = ap.parse_args(argv)
    o = build()
    print(f"source: {o['source']}; days {len(o['days'])}; trades {len(o['trades'])}; missed / held {len(o['missed'])}")
    for t in o["trades"]:
        print(f"  {t['bot']:7s} {t['signal']} {t['side']:5s} {t.get('member') or '':12s} q {t.get('qty_filled')} model {t.get('model_entry')} "
              f"fill {t.get('real_fill')} ({t.get('entry_ticks'):+.0f}t, ${t.get('entry_usd'):+.2f}) exit {t.get('model_exit')} -> {t.get('real_exit')} "
              f"R {t.get('model_r')} -> {t.get('real_r')}  diff ${t.get('diff_usd')}  cause: {t['cause']}")
    print(table(o))
    if not a.show:
        os.makedirs(os.path.dirname(OUT), exist_ok=True)
        json.dump(o, open(OUT, "w", encoding="utf-8"), indent=1, default=str)
        print("wrote", os.path.relpath(OUT, ROOT))
    return 0


if __name__ == "__main__":
    sys.exit(main())
