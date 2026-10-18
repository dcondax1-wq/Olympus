"""Fill audit: what the broker really filled vs what the backtest and the realistic fill model expected.

After a week of the PC bot on NinjaTrader (Sim101 first, then the MFFU account), this replaces the fill assumptions of
engine/lit_fills.py with measured numbers.

Inputs (all read-only; nothing is ever written to NinjaTrader's folders):
  * NinjaTrader's outgoing\\ order files  <ORDER ID>.txt = "STATE;FILLED;AVG PRICE" for the bot's orders
    (engine/ninjatrader.py ids: LE<entry_t><tag><M|N><E|S|T> = entry / stop / target). NinjaTrader WIPES outgoing\\ when it
    restarts, so run `archive` once a day (or more): it copies every LE* order state with its file time into
    logs/fill_archive.jsonl.
  * the bot's ledger  data/live_state.json "ledger": every routed entry (model price, stop, target, route time), stop move
    (breakeven) and exit (model reason, model P&L).
  * optional: NinjaTrader's Executions export (Control Center > Executions tab > right click > Export, CSV) - the only place
    that has the fill price and time of a CLOSEPOSITION (end-of-day / model exits) and the exact fill times.
  * optional: the 1m bars (Documents\\NinjaTrader 8\\le_feed\\MNQ_1m.csv) - for the price at the moment an order was sent
    (splits the entry cost into decision latency and execution slippage), the bar range of each stop fill, and whether a
    target limit was touched / traded through without filling.

  python tools/fill_audit.py archive                     # snapshot outgoing\\ order files (run daily, after 16:00 ET)
  python tools/fill_audit.py report [--executions X.csv] [--bars MNQ_1m.csv] [--since 2026-10-19] [--comm 1.90]
                                                          # -> logs/fill_audit_report.json + a printed summary
  python tools/fill_audit.py selftest                    # synthetic fills, every number checked
Slippage is in ticks (0.25 pt), positive = worse for us. "Suggested fills" in the report is a dict for engine/lit.py's
"fills" option (tools/lit_fills.py runs it as scenario "measured").
"""
from __future__ import annotations

import csv
import datetime as dt
import json
import os
import re
import sys
from zoneinfo import ZoneInfo

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)

ET = ZoneInfo("America/New_York")
TICK, PV = 0.25, 2.0
ARCHIVE = os.path.join(ROOT, "logs", "fill_archive.jsonl")
REPORT = os.path.join(ROOT, "logs", "fill_audit_report.json")
STATE = os.path.join(ROOT, "data", "live_state.json")
OID = re.compile(r"^(LE)(\d{9,11})([A-Z0-9]{4})([NM])([EST])$")
# what the realistic model assumes today (engine/lit_fills.py FILL_DEFAULTS), to print next to the measured numbers
ASSUMED = {"half_spread_ticks": {"asia": 1.0, "london": 0.75, "pre": 0.5, "rth": 0.5},
           "stop_base_ticks": {"asia": 2.0, "london": 1.5, "pre": 1.0, "rth": 1.0}, "stop_k": 0.025,
           "decision_latency_s": 95.3, "tgt_thr": 1}


def _et(t):
    return dt.datetime.fromtimestamp(float(t), ET)


def bucket(t):
    h = _et(t).hour
    return "rth" if 9 <= h < 16 else "pre" if h == 8 else "london" if 2 <= h < 8 else "asia"


def parse_oid(name):
    """'LE1792405860ABCDME' -> {"entry_t", "tag", "contract" (M micro / N mini), "leg" (E/S/T)}; None if not ours."""
    m = OID.match(os.path.splitext(os.path.basename(name))[0])
    if not m:
        return None
    return {"entry_t": int(m.group(2)), "tag": m.group(3), "contract": m.group(4), "leg": {"E": "entry", "S": "stop", "T": "target"}[m.group(5)]}


# ------------------------------------------------------------------------------------------------ archive
def read_outgoing(folder):
    from engine.ninjatrader import parse_order_state
    out = {}
    od = os.path.join(folder, "outgoing")
    try:
        names = os.listdir(od)
    except OSError:
        return out
    for n in names:
        if not n.lower().endswith(".txt") or parse_oid(n) is None:
            continue
        p = os.path.join(od, n)
        try:
            raw = open(p, encoding="utf-8", errors="replace").read()
            mt = os.path.getmtime(p)
        except OSError:
            continue
        st = parse_order_state(raw)
        if st:
            out[os.path.splitext(n)[0]] = {"state": st["state"], "filled": st["filled"], "avg": st["avg"], "mtime": mt}
    return out


def load_archive(path=ARCHIVE):
    """order id -> its latest known state (a FILLED state is never replaced by a later non-FILLED one)."""
    rows = {}
    if not os.path.exists(path):
        return rows
    for ln in open(path, encoding="utf-8"):
        try:
            r = json.loads(ln)
        except Exception:
            continue
        old = rows.get(r["id"])
        if old and old["state"] == "FILLED" and r["state"] != "FILLED":
            continue
        rows[r["id"]] = r
    return rows


def archive(folder=None, path=ARCHIVE):
    from engine.ninjatrader import default_folder
    folder = folder or default_folder()
    have = load_archive(path)
    cur = read_outgoing(folder)
    new = 0
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with open(path, "a", encoding="utf-8") as fh:
        for oid, st in sorted(cur.items()):
            old = have.get(oid)
            if old and all(old.get(k) == st.get(k) for k in ("state", "filled", "avg")):
                continue
            fh.write(json.dumps({"id": oid, **st, "seen": int(dt.datetime.now().timestamp())}) + "\n")
            new += 1
    print(f"archive: {len(cur)} order files in {os.path.join(folder, 'outgoing')}, {new} new/changed states -> {path}")
    return new


# ------------------------------------------------------------------------------------------------ inputs
def load_ledger(path=STATE):
    try:
        return json.load(open(path, encoding="utf-8")).get("ledger") or []
    except Exception:
        return []


def load_executions(path):
    """NinjaTrader Executions export -> [{"t", "action" BUY/SELL, "qty", "price", "ex" entry/exit, "order", "name"}]."""
    if not path:
        return []
    out = []
    with open(path, encoding="utf-8-sig", newline="") as fh:
        rd = csv.DictReader(fh)
        for r in rd:
            g = {k.strip().lower(): (v or "").strip() for k, v in r.items() if k}
            try:
                px = float(g.get("price", "").replace(",", ""))
                qty = abs(int(float(g.get("quantity") or g.get("qty") or 0)))
            except ValueError:
                continue
            tt = g.get("time") or g.get("date/time") or ""
            t = None
            for fmt in ("%m/%d/%Y %I:%M:%S %p", "%m/%d/%Y %H:%M:%S", "%Y-%m-%d %H:%M:%S", "%d/%m/%Y %H:%M:%S", "%m/%d/%Y %I:%M:%S.%f %p"):
                try:
                    t = dt.datetime.strptime(tt, fmt).replace(tzinfo=ET).timestamp()     # NinjaTrader shows its display zone: set it to ET
                    break
                except ValueError:
                    continue
            if t is None:
                continue
            act = (g.get("action") or "").upper()
            out.append({"t": t, "action": "BUY" if act.startswith("BUY") else "SELL", "qty": qty, "price": px,
                        "ex": (g.get("e/x") or g.get("ex") or "").lower(), "order": g.get("order id") or g.get("order") or "",
                        "name": g.get("name") or "", "instrument": g.get("instrument") or ""})
    return sorted(out, key=lambda x: x["t"])


def load_bars(path):
    """1m bars (LE_BarFeed CSV: time = bar open, unix s) -> sorted list of (t, o, h, l, c)."""
    if not path:
        return []
    rows = []
    for ln in open(path, encoding="utf-8"):
        f = ln.strip().split(",")
        if len(f) < 5:
            continue
        try:
            rows.append((int(float(f[0])), float(f[1]), float(f[2]), float(f[3]), float(f[4])))
        except ValueError:
            continue
    return sorted(set(rows))


def _bar_at(bars, t):
    import bisect
    i = bisect.bisect_right([b[0] for b in bars], t) - 1
    return bars[i] if 0 <= i < len(bars) and bars[i][0] <= t < bars[i][0] + 60 else None


def mid_at(bars, t):
    """Expected price at time t (Brownian-bridge mean inside the 1m bar), as engine/lit_fills.py uses."""
    b = _bar_at(bars, t)
    if b is None:
        return None
    f = (t - b[0]) / 60.0
    return b[1] + f * (b[4] - b[1])


# ------------------------------------------------------------------------------------------------ matching
def trades_from(ledger, orders, execs, since=None):
    """One record per routed entry: the ledger's plan + the broker's fills."""
    by_et = {}
    for r in ledger:
        et_ = r.get("entry_t")
        if et_ is None:
            continue
        x = by_et.setdefault(int(et_), {"entry_t": int(et_), "modifies": [], "exit": None, "entry": None})
        if r.get("side") in ("buy", "sell"):
            x["entry"] = r
        elif r.get("side") == "modify":
            x["modifies"].append(r)
        elif r.get("side") == "exit":
            x["exit"] = r
    legs = {}
    for oid, st in orders.items():
        p = parse_oid(oid)
        if p:
            legs.setdefault(p["entry_t"], {})[p["leg"] + ("_mini" if p["contract"] == "N" else "")] = {**st, "id": oid}
    out = []
    for et_, x in sorted(by_et.items()):
        e = x["entry"]
        if e is None:
            continue
        if since and dt.datetime.fromtimestamp(et_, ET).strftime("%Y-%m-%d") < since:
            continue
        d = 1 if e["side"] == "buy" else -1
        lg = legs.get(et_, {})
        ent = lg.get("entry")
        fill_px = ent["avg"] if ent and ent.get("filled") else None
        if fill_px is None:                              # the adapter's own record of the entry fill
            for leg in ((e.get("result") or {}).get("legs") or []):
                if leg.get("fill_px"):
                    fill_px = float(leg["fill_px"]); break
        rec = {"entry_t": et_, "dir": d, "qty": int(e.get("qty") or 0), "model_entry": e.get("entry"), "stop0": e.get("stop"),
               "target": e.get("target"), "t_route": e.get("t"), "fill_entry": fill_px,
               "t_fill_entry": ent.get("mtime") if ent else None, "stop_moves": [(m.get("t"), m.get("stop"), (m.get("result") or {}).get("ok"))
                                                                                   for m in x["modifies"]],
               "model_exit": (x["exit"] or {}).get("reason"), "model_pnl": (x["exit"] or {}).get("pnl"),
               "t_exit_route": (x["exit"] or {}).get("t"), "model_exit_t": (x["exit"] or {}).get("exit_t")}
        s, t = lg.get("stop"), lg.get("target")
        rec["stop_state"], rec["target_state"] = (s or {}).get("state"), (t or {}).get("state")
        be = [m for m in rec["stop_moves"] if m[2]]
        rec["stop_final"] = be[-1][1] if be else rec["stop0"]
        if s and s.get("state") == "FILLED":
            rec.update(exit_kind="BE" if be else "STOP", fill_exit=s["avg"], t_fill_exit=s.get("mtime"))
        elif t and t.get("state") == "FILLED":
            rec.update(exit_kind="TARGET", fill_exit=t["avg"], t_fill_exit=t.get("mtime"))
        else:
            rec.update(exit_kind="CLOSE", fill_exit=None, t_fill_exit=None)
        # executions: the exit fills of this trade (any order), and exact entry fill times
        if execs:
            t0 = (rec["t_route"] or et_) - 5
            t1 = (rec["t_exit_route"] or rec["t_fill_exit"] or t0 + 86400) + 120
            xs = [z for z in execs if t0 <= z["t"] <= t1]
            en = [z for z in xs if z["action"] == ("BUY" if d == 1 else "SELL")][:1]
            ex = [z for z in xs if z["action"] == ("SELL" if d == 1 else "BUY") and (not en or z["t"] >= en[0]["t"])]
            if en:
                rec["t_fill_entry"] = en[0]["t"]
                rec["fill_entry"] = rec["fill_entry"] or en[0]["price"]
            if ex:
                q = sum(z["qty"] for z in ex) or 1
                vw = sum(z["price"] * z["qty"] for z in ex) / q
                if rec["fill_exit"] is None:
                    rec["fill_exit"] = round(vw, 4)
                rec["t_fill_exit"] = ex[-1]["t"]
        out.append(rec)
    return out


def measure(recs, bars, comm=1.90):
    """Per-trade slippage numbers (ticks, positive = worse) and the $ difference against the model's P&L."""
    for r in recs:
        d = r["dir"]
        r["m"] = m = {}
        if r["fill_entry"] is not None and r["model_entry"] is not None:
            m["entry_vs_model_ticks"] = round((r["fill_entry"] - r["model_entry"]) * d / TICK, 2)
        if r["t_route"] is not None:
            m["decision_latency_s"] = round(r["t_route"] - r["entry_t"], 1)      # entry_t = the bar open the backtest buys at
        if r["t_fill_entry"] and r["t_route"]:
            m["fill_latency_s"] = round(r["t_fill_entry"] - r["t_route"], 2)
        if bars and r["t_route"] is not None and r["fill_entry"] is not None:
            mid = mid_at(bars, r["t_route"])
            if mid is not None:
                m["entry_vs_send_ticks"] = round((r["fill_entry"] - mid) * d / TICK, 2)     # execution only (spread + impact)
                if r["model_entry"] is not None:
                    m["latency_cost_ticks"] = round((mid - (r["model_entry"] - d * TICK)) * d / TICK, 2)   # price moved while deciding
        if r["exit_kind"] in ("STOP", "BE") and r["fill_exit"] is not None:
            lvl = r["stop_final"] if r["exit_kind"] == "BE" else r["stop0"]
            m["stop_slip_ticks"] = round((lvl - r["fill_exit"]) * d / TICK, 2)
            b = _bar_at(bars, r["t_fill_exit"]) if bars and r.get("t_fill_exit") else None
            if b:
                m["stop_bar_range"] = round(b[2] - b[3], 2)
        if r["exit_kind"] == "TARGET" and r["fill_exit"] is not None and r["target"] is not None:
            m["target_improve_ticks"] = round((r["fill_exit"] - r["target"]) * d / TICK, 2)
        if bars and r["target"] is not None and r["t_fill_entry"]:
            t_end = r["t_fill_exit"] or r["t_exit_route"] or r["t_fill_entry"] + 8 * 3600
            seg = [b for b in bars if r["t_fill_entry"] <= b[0] + 59 and b[0] <= t_end]
            if seg:
                best = max(b[2] for b in seg) if d == 1 else min(b[3] for b in seg)
                m["target_reach_ticks"] = round((best - r["target"]) * d / TICK, 2)   # >= 0 touched, >= 1 traded through
        if r["model_exit"] == "TARGET" and r["exit_kind"] != "TARGET":
            m["missed_target"] = True
        if r["fill_entry"] is not None and r["fill_exit"] is not None:
            real = (r["fill_exit"] - r["fill_entry"]) * d * PV * r["qty"] - comm * r["qty"]
            m["pnl_real"] = round(real, 2)
            if r["model_pnl"] is not None:
                m["pnl_diff"] = round(real - float(r["model_pnl"]), 2)
    return recs


def _stats(xs):
    xs = sorted(x for x in xs if x is not None)
    if not xs:
        return None
    n = len(xs)
    return {"n": n, "mean": round(sum(xs) / n, 2), "median": xs[n // 2] if n % 2 else round((xs[n // 2 - 1] + xs[n // 2]) / 2, 2),
            "p90": xs[min(n - 1, int(0.9 * n))], "worst": xs[-1]}


def summarize(recs):
    S = {"trades": len(recs), "by_type": {}, "by_hour": {}, "targets": {}, "money": {}}
    for key, field in (("entry_vs_model", "entry_vs_model_ticks"), ("entry_vs_send", "entry_vs_send_ticks"),
                       ("latency_cost", "latency_cost_ticks"), ("stop", "stop_slip_ticks"), ("target", "target_improve_ticks"),
                       ("decision_latency_s", "decision_latency_s"), ("fill_latency_s", "fill_latency_s")):
        S["by_type"][key] = _stats([r["m"].get(field) for r in recs])
    for b in ("asia", "london", "pre", "rth"):
        R = [r for r in recs if r["t_route"] and bucket(r["t_route"]) == b]
        Rs = [r for r in recs if r.get("t_fill_exit") and r["exit_kind"] in ("STOP", "BE") and bucket(r["t_fill_exit"]) == b]
        S["by_hour"][b] = {"entry_vs_send": _stats([r["m"].get("entry_vs_send_ticks") for r in R]),
                           "entry_vs_model": _stats([r["m"].get("entry_vs_model_ticks") for r in R]),
                           "stop": _stats([r["m"].get("stop_slip_ticks") for r in Rs])}
    reach = [(r["m"]["target_reach_ticks"], r["exit_kind"] == "TARGET") for r in recs if "target_reach_ticks" in r["m"]]
    S["targets"] = {"touched_only": sum(1 for x, f in reach if 0 <= x < 1), "touched_only_filled": sum(1 for x, f in reach if 0 <= x < 1 and f),
                    "through_1": sum(1 for x, f in reach if 1 <= x < 2), "through_1_filled": sum(1 for x, f in reach if 1 <= x < 2 and f),
                    "through_2plus": sum(1 for x, f in reach if x >= 2), "through_2plus_filled": sum(1 for x, f in reach if x >= 2 and f),
                    "missed_model_targets": sum(1 for r in recs if r["m"].get("missed_target"))}
    dif = [r["m"]["pnl_diff"] for r in recs if "pnl_diff" in r["m"]]
    S["money"] = {"trades_priced": len(dif), "pnl_real": round(sum(r["m"]["pnl_real"] for r in recs if "pnl_real" in r["m"]), 2),
                  "pnl_model": round(sum(float(r["model_pnl"]) for r in recs if "pnl_diff" in r["m"]), 2),
                  "diff_total": round(sum(dif), 2), "diff_per_trade": round(sum(dif) / len(dif), 2) if dif else None,
                  "unpriced_exits": sum(1 for r in recs if r["fill_exit"] is None)}
    S["suggested_fills"] = suggest(S, recs)
    S["assumed"] = ASSUMED
    return S


def suggest(S, recs):
    """A fills dict for engine/lit.py from the measured numbers (only the parts with >= 3 observations)."""
    sug = {}
    sp = {}
    for b, k in (("asia", 0), ("london", 1), ("pre", 2), ("rth", 3)):
        e = S["by_hour"][b]["entry_vs_send"]
        if e and e["n"] >= 3:
            sp[b] = round(max(0.0, 2 * e["mean"]), 2)          # a market order pays half the spread over the mid
    if sp:
        d = ASSUMED["half_spread_ticks"]
        sug["spread_ticks"] = [sp.get(b, 2 * d[b]) for b in ("asia", "london", "pre", "rth")]
    st = {}
    for b in ("asia", "london", "pre", "rth"):
        e = S["by_hour"][b]["stop"]
        if e and e["n"] >= 3:
            st[b] = max(0.0, e["median"])
    if st:
        d = ASSUMED["stop_base_ticks"]
        sug["stop_base_ticks"] = [st.get(b, d[b]) for b in ("asia", "london", "pre", "rth")]
    ks = [r["m"]["stop_slip_ticks"] * TICK / r["m"]["stop_bar_range"] for r in recs
          if r["m"].get("stop_bar_range") and r["m"].get("stop_slip_ticks") is not None and r["m"]["stop_slip_ticks"] > 1]
    if len(ks) >= 3:
        ks.sort()
        sug["stop_k"] = round(ks[len(ks) // 2], 4)
    lat = S["by_type"]["decision_latency_s"]
    if lat and lat["n"] >= 3:
        # engine/lit_fills.py: latency = 60 (next bar must close, detect next_close) + poll x phase + compute + route + feed
        sug["_measured_decision_latency_s"] = lat["median"]
        sug["detect"] = "next_close" if lat["median"] >= 60 else "bar_close"
        rest = lat["median"] - (60 if sug["detect"] == "next_close" else 0)
        sug["poll_s"], sug["phase"], sug["compute_s"], sug["route_s"], sug["feed_s"] = round(max(0.0, rest), 1), 1.0, 0.0, 0.0, 0.0
    T = S["targets"]
    if T["touched_only"] + T["through_1"] >= 3:
        sug["tgt_thr"] = 0 if T["touched_only"] and T["touched_only_filled"] == T["touched_only"] else (
            1 if T["through_1"] == 0 or T["through_1_filled"] == T["through_1"] else 2)
    return sug


def report(folder=None, state=STATE, executions=None, bars=None, since=None, comm=1.90, out=REPORT, verbose=True):
    from engine.ninjatrader import default_folder
    orders = load_archive()
    orders.update({k: v for k, v in read_outgoing(folder or default_folder()).items()
                   if not (orders.get(k, {}).get("state") == "FILLED" and v["state"] != "FILLED")})
    recs = measure(trades_from(load_ledger(state), orders, load_executions(executions), since), load_bars(bars), comm)
    S = summarize(recs)
    S["trades_detail"] = [{k: v for k, v in r.items() if k != "stop_moves"} for r in recs]
    os.makedirs(os.path.dirname(out), exist_ok=True)
    with open(out, "w", encoding="utf-8") as fh:
        json.dump(S, fh, indent=1, default=str)
    if verbose:
        print_summary(S)
        print("report ->", out)
    return S


def print_summary(S):
    def f(x):
        return "-" if not x else f"n={x['n']} mean {x['mean']:+} median {x['median']:+} p90 {x['p90']:+} worst {x['worst']:+}"
    print(f"trades routed: {S['trades']}")
    for k, v in S["by_type"].items():
        print(f"  {k:20s} {f(v)}")
    for b, v in S["by_hour"].items():
        print(f"  {b:7s} entry vs send {f(v['entry_vs_send'])} | stop {f(v['stop'])}")
    print("  targets:", S["targets"])
    print("  money:", S["money"])
    print("  suggested fills:", json.dumps(S["suggested_fills"]))


# ------------------------------------------------------------------------------------------------ self-test
def selftest():
    import tempfile
    ok_all = True

    def check(name, cond, detail=""):
        nonlocal ok_all
        ok_all &= bool(cond)
        print(("OK   " if cond else "FAIL ") + name + (f"  [{detail}]" if detail and not cond else ""))

    base = int(dt.datetime(2026, 10, 20, 3, 0, tzinfo=ET).timestamp())        # 03:00 ET, London
    with tempfile.TemporaryDirectory() as tmp:
        nt = os.path.join(tmp, "NinjaTrader 8"); od = os.path.join(nt, "outgoing"); os.makedirs(od)
        bars_p = os.path.join(tmp, "MNQ_1m.csv")
        # 1m bars: flat 25000 for 3 hours, except the scripted moves below
        rows = []
        for i in range(180):
            t = base + 60 * i
            o = h = l = c = 25000.0
            if i == 2:                       # trade 1 entry bar after the model's fill bar: drifts up 2 pts
                o, h, l, c = 25000.0, 25002.0, 25000.0, 25002.0
            if i == 30:                      # trade 1 stop bar: a 20-pt bar through 24980
                o, h, l, c = 24995.0, 24996.0, 24976.0, 24978.0
            if i == 60:                      # trade 2 target only touched (limit 25040, high 25040.00)
                o, h, l, c = 25030.0, 25040.0, 25029.0, 25035.0
            if i == 90:                      # trade 3 target traded 3 ticks through (limit 25040, high 25040.75)
                o, h, l, c = 25030.0, 25040.75, 25029.0, 25038.0
            rows.append(f"{t},{o},{h},{l},{c},100")
        open(bars_p, "w").write("time,open,high,low,close,volume\n" + "\n".join(rows) + "\n")
        # trade 1: long, model entry 25000.25 at bar 1 open (base+60), routed 95 s later, filled 25002.25; stop 24980 fills 24978.5
        E1 = base + 60
        # trade 2: long, model TARGET, target limit only touched -> not filled, CLOSEPOSITION at 25034.0 (executions)
        E2 = base + 40 * 60
        # trade 3: long, target filled at 25040.00
        E3 = base + 80 * 60
        legs = {f"LE{E1}AB2CME": "FILLED;2;25002.25", f"LE{E1}AB2CMS": "FILLED;2;24978.50", f"LE{E1}AB2CMT": "CANCELLED;0;0",
                f"LE{E2}XY3ZME": "FILLED;3;25010.25", f"LE{E2}XY3ZMS": "CANCELLED;0;0", f"LE{E2}XY3ZMT": "CANCELLED;0;0",
                f"LE{E3}QR4SME": "FILLED;1;25010.50", f"LE{E3}QR4SMS": "CANCELLED;0;0", f"LE{E3}QR4SMT": "FILLED;1;25040.00",
                "SomethingElse": "FILLED;1;1"}
        mt = {f"LE{E1}AB2CME": E1 + 96, f"LE{E1}AB2CMS": base + 30 * 60 + 20, f"LE{E3}QR4SMT": base + 90 * 60 + 30}
        for k, v in legs.items():
            p = os.path.join(od, k + ".txt"); open(p, "w").write(v)
            if k in mt:
                os.utime(p, (mt[k], mt[k]))
        open(os.path.join(od, "MNQ 12-26 Globex_Sim101_Position.txt"), "w").write("FLAT;0;0")
        ledger = [
            {"t": E1 + 95, "side": "buy", "qty": 2, "stop": 24980.0, "target": 25100.0, "entry": 25000.25, "entry_t": E1, "result": {"ok": True}},
            {"t": base + 31 * 60 + 35, "side": "exit", "qty": 2, "reason": "STOP", "pnl": round((24979.75 - 25000.25) * 2 * 2 - 1.4 * 2, 2), "entry_t": E1, "exit_t": base + 31 * 60},
            {"t": E2 + 95, "side": "buy", "qty": 3, "stop": 24990.0, "target": 25040.0, "entry": 25010.25, "entry_t": E2, "result": {"ok": True}},
            {"t": base + 61 * 60 + 35, "side": "exit", "qty": 3, "reason": "TARGET", "pnl": round((25040.0 - 25010.25) * 2 * 3 - 1.4 * 3, 2), "entry_t": E2, "exit_t": base + 61 * 60},
            {"t": E3 + 95, "side": "buy", "qty": 1, "stop": 24990.0, "target": 25040.0, "entry": 25010.25, "entry_t": E3, "result": {"ok": True}},
            {"t": base + 85 * 60 + 35, "side": "modify", "qty": 1, "stop": 25010.25, "reason": "BE", "entry_t": E3, "result": {"ok": True}},
            {"t": base + 91 * 60 + 35, "side": "exit", "qty": 1, "reason": "TARGET", "pnl": round((25040.0 - 25010.25) * 2 - 1.4, 2), "entry_t": E3, "exit_t": base + 91 * 60},
        ]
        st_p = os.path.join(tmp, "live_state.json"); json.dump({"ledger": ledger}, open(st_p, "w"))
        ex_p = os.path.join(tmp, "executions.csv")
        fmt = lambda t: _et(t).strftime("%m/%d/%Y %I:%M:%S %p")
        with open(ex_p, "w", newline="") as fh:
            w = csv.writer(fh)
            w.writerow(["Instrument", "Action", "Quantity", "Price", "Time", "ID", "E/X", "Position", "Order ID", "Name", "Commission", "Account"])
            w.writerow(["MNQ 12-26", "Buy", 3, "25010.25", fmt(E2 + 96), "1", "Entry", "3 L", f"LE{E2}XY3ZME", "", "", "Sim101"])
            w.writerow(["MNQ 12-26", "Sell", 3, "25034.00", fmt(base + 61 * 60 + 36), "2", "Exit", "-", "abc", "Close", "", "Sim101"])
        arch = os.path.join(tmp, "arch.jsonl")
        n = archive(folder=nt, path=arch)
        check("archive: 9 bot order files kept, a foreign file ignored", n == 9, str(n))
        n2 = archive(folder=nt, path=arch)
        check("archive: unchanged states are not written twice", n2 == 0, str(n2))
        global ARCHIVE
        old = ARCHIVE; ARCHIVE = arch
        try:
            for f in os.listdir(od):                      # NinjaTrader restarted: outgoing wiped -> the archive still has them
                os.remove(os.path.join(od, f))
            S = report(folder=nt, state=st_p, executions=ex_p, bars=bars_p, comm=1.90, out=os.path.join(tmp, "rep.json"), verbose=False)
        finally:
            ARCHIVE = old
        R = {r["entry_t"]: r for r in S["trades_detail"]}
        check("matched 3 trades from the ledger + archived order files", S["trades"] == 3 and set(R) == {E1, E2, E3})
        m1 = R[E1]["m"]
        check("trade 1 entry: +8 ticks vs the model (25002.25 vs 25000.25)", m1.get("entry_vs_model_ticks") == 8.0, str(m1))
        # mid at the send time E1+95 = bar 2 (base+120) at 35 s: 25000 + 35/60 x 2 = 25001.1667 -> fill 25002.25 = +4.33 ticks
        check("trade 1 entry vs the price at send time: +4.33 ticks", abs(m1.get("entry_vs_send_ticks", 0) - 4.33) < 0.01, str(m1))
        check("trade 1 decision latency 95 s, fill latency 1 s", m1.get("decision_latency_s") == 95.0 and abs(m1.get("fill_latency_s", 0) - 1.0) < 0.01, str(m1))
        check("trade 1 stop slippage 6 ticks (24980 -> 24978.50) on a 20-pt bar", m1.get("stop_slip_ticks") == 6.0 and m1.get("stop_bar_range") == 20.0, str(m1))
        real1 = (24978.5 - 25002.25) * 2 * 2 - 1.9 * 2
        check("trade 1 real P&L and $ difference vs the model", abs(m1["pnl_real"] - real1) < 0.01
              and abs(m1["pnl_diff"] - (real1 - ledger[1]["pnl"])) < 0.01, str(m1))
        m2 = R[E2]["m"]
        check("trade 2: model TARGET, limit only touched (reach 0 ticks) -> missed, CLOSE priced from the executions",
              m2.get("missed_target") and m2.get("target_reach_ticks") == 0.0 and R[E2]["exit_kind"] == "CLOSE" and R[E2]["fill_exit"] == 25034.0, str(R[E2]))
        m3 = R[E3]["m"]
        check("trade 3: target filled at the limit (0 ticks better), reached 3 ticks through", m3.get("target_improve_ticks") == 0.0
              and m3.get("target_reach_ticks") == 3.0 and R[E3]["exit_kind"] == "TARGET", str(m3))
        T = S["targets"]
        check("targets: 1 touch-only (not filled), 1 traded through 2+ (filled), 1 missed model target",
              T["touched_only"] == 1 and T["touched_only_filled"] == 0 and T["through_2plus"] == 1 and T["through_2plus_filled"] == 1
              and T["missed_model_targets"] == 1, json.dumps(T))
        mo = S["money"]
        check("money: 3 trades priced, totals add up", mo["trades_priced"] == 3
              and abs(mo["diff_total"] - sum(R[e]["m"]["pnl_diff"] for e in R)) < 0.01, json.dumps(mo))
        check("by hour: all London (03:00-04:30 ET)", S["by_hour"]["london"]["entry_vs_model"]["n"] == 3)
        sg = S["suggested_fills"]
        check("suggested fills: London spread from the measured entry cost, latency 95 s -> next_close", sg.get("detect") == "next_close"
              and sg.get("spread_ticks") and abs(sg["spread_ticks"][1] - 2 * S["by_hour"]["london"]["entry_vs_send"]["mean"]) < 1e-6, json.dumps(sg))
        check("parse_oid: our ids only", parse_oid("LE1792405860AB2CME")["leg"] == "entry" and parse_oid("SomethingElse") is None
              and parse_oid("LE1792405860AB2CNT")["contract"] == "N")
    print("SELFTEST", "PASSED" if ok_all else "FAILED")
    return ok_all


def main(argv=None):
    import argparse
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("cmd", choices=["archive", "report", "selftest"])
    ap.add_argument("--folder", default=None, help="NinjaTrader 8 user folder (default: Documents\\NinjaTrader 8)")
    ap.add_argument("--state", default=STATE)
    ap.add_argument("--executions", default=None, help="NinjaTrader Executions tab export (CSV)")
    ap.add_argument("--bars", default=None, help="1m bars CSV (le_feed\\MNQ_1m.csv)")
    ap.add_argument("--since", default=None, help="first trading date (yyyy-mm-dd)")
    ap.add_argument("--comm", type=float, default=1.90, help="$ per micro round trip for the real P&L")
    a = ap.parse_args(argv)
    if a.cmd == "archive":
        archive(a.folder)
    elif a.cmd == "report":
        bars = a.bars
        if bars is None:
            from engine.ninjatrader import default_folder
            p = os.path.join(a.folder or default_folder(), "le_feed", "MNQ_1m.csv")
            bars = p if os.path.exists(p) else None
        report(a.folder, a.state, a.executions, bars, a.since, a.comm)
    else:
        sys.exit(0 if selftest() else 1)


if __name__ == "__main__":
    main()
