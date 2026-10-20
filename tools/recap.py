"""Learn from every live trade on the phone: recap cards, the daily LIT brief image and the weekly review (read-only).

Run by tools/cloud_monitor.py every run (cloud_hook); never places or changes an order, never changes a trading decision.
Everything lands in <out>/recaps/ on the `dashboard` branch (restored every run by the workflow) and is copied to the
phone app (tools/build_web_dashboard.py -> site/recaps/, data.json live.recaps / live.weekly):

  recap cards  one PNG per finished trade (the cloud paper ledger and the PC's routed trades from its heartbeat "acct"
               block): 5m + 1m around the trade with the swept level(s), inducement, displacement candle, 5m CISD, limit,
               1m CISD, entry, stop, breakeven stop line, target, the 15-minute check and the exit (tools/lit_trade_charts.py
               drawing), plus "why it entered / the plan / what happened / lessons" (tools/export_backtest.py _report_lit).
               The setup is rebuilt by the LIT engine on the cloud's own bars (the live loop's window and 1m bars); when it
               cannot be matched (a PC fill the cloud model did not take), the card shows the trade's own prices only.
               Kept: the newest 30 (KEEP). recaps/<key>.png, key = <src>_<date>_<HHMM>_<side>.
  brief image  recaps/brief.png from the morning brief (engine/lit_brief.py, first run after 01:30 ET, refreshed after
               07:30): today's LIT levels map (PDH/PDL, PWH/PWL, PMH/PML, session boxes, gaps, build-ups; taken / untaken),
               the VIX target band and its width, the day's news and the eval status.
  weekly       the review of the last Mon-Fri week, built on Sunday (or the first run after it): trades, $, R, best / worst,
               execution quality (PC fills vs the model, the PC's fill audit), and "what to watch next week" from the data.

Notifications (engine/push.py, the app's service worker): a "recap" notice per new card (same tag as the trade, so it
replaces the outcome notice; tap opens the card; the PNG rides along as the notification image where the phone shows one),
one "brief" notice a day and one "weekly" notice a week. Generation is cached (a card is drawn once) and capped per run.

    python tools/recap.py --state dash/state.json --out dash      # draw what is missing from a saved state (needs the bars)
"""
from __future__ import annotations

import datetime as dt
import hashlib
import json
import os
import sys
from zoneinfo import ZoneInfo

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if ROOT not in sys.path:
    sys.path.insert(0, ROOT)

ET = ZoneInfo("America/New_York")
DIR = "recaps"
KEEP = 30                   # cards kept on the dashboard branch / in the app
MAX_NEW = 6                 # cards drawn in one run at most (a restored state with many trades catches up over a few runs)
WAIT_TRIES = 2              # runs to wait for the bars before a PC trade gets a card with its own prices only
MAX_TRIES = 6               # runs without any bars around a trade before it is given up
MAX_AGE_D = 12              # a trade older than this gets no card (the cloud keeps 12 days of 1m bars)
DPI, SIZE = 100, (8.0, 4.6)  # 800 x 460 px
BRIEF_SIZE = (8.0, 5.2)
VERSION = 1


# ------------------------------------------------------------------------------------------------ small helpers
def _et(t):
    return dt.datetime.fromtimestamp(int(t), ET)


def tday(t) -> str:
    return (_et(t) + dt.timedelta(hours=6)).strftime("%Y-%m-%d")


def _usd(x) -> str:
    x = float(x or 0)
    return f"{'+' if x > 0 else '-' if x < 0 else ''}${abs(x):,.0f}"


def _px(x) -> str:
    return f"{float(x):,.2f}" if x is not None else "-"


def _f(x, nd=2):
    try:
        return round(float(x), nd)
    except (TypeError, ValueError):
        return None


def _paths(out):
    d = os.path.join(out, DIR)
    return d, os.path.join(d, "index.json")


def load_index(out) -> dict:
    try:
        with open(_paths(out)[1], encoding="utf-8") as fh:
            ix = json.load(fh)
        return ix if isinstance(ix, dict) else {}
    except Exception:
        return {}


def save_index(out, ix):
    d, p = _paths(out)
    os.makedirs(d, exist_ok=True)
    with open(p, "w", encoding="utf-8") as fh:
        json.dump(ix, fh, indent=1, default=str)


def _shrink(path, colors=96):
    """Palette PNG (about a third of the size; the chart has few colours). Never fails the card."""
    try:
        from PIL import Image
        im = Image.open(path).convert("RGB")
        im.quantize(colors=colors, method=Image.Quantize.MEDIANCUT).save(path, optimize=True)
    except Exception:
        pass


def _hash(path) -> str:
    try:
        with open(path, "rb") as fh:
            return hashlib.sha1(fh.read()).hexdigest()[:10]
    except OSError:
        return ""


# ------------------------------------------------------------------------------------------------ finished trades
def finished_trades(state: dict, now=None) -> list:
    """The finished live trades of a cloud state, newest exit first: the PC's routed trades (heartbeat "acct" block) and the
    cloud paper ledger. Same keys for both: src, account, day, entry_t, exit_t, side, d, qty, entry, stop, target, exit_px,
    exit, r, usd, risk_pts, swept."""
    out = []
    pc = state.get("pc") if isinstance(state.get("pc"), dict) else {}
    acct = pc.get("acct") if isinstance(pc.get("acct"), dict) else {}
    name = ((acct.get("account") or {}).get("name") if isinstance(acct.get("account"), dict) else None) or "PC"
    for t in acct.get("trades") or []:
        if not isinstance(t, dict) or not t.get("entry_t") or not t.get("exit_t") or t.get("pnl") is None:
            continue
        side = str(t.get("side") or "").upper()
        out.append({"src": "pc", "account": f"PC · {name}", "day": t.get("day") or tday(t["entry_t"]), "entry_t": int(t["entry_t"]),
                    "exit_t": int(t["exit_t"]), "side": side, "d": 1 if side == "LONG" else -1, "qty": int(t.get("qty") or 0),
                    "entry": _f(t.get("entry")), "stop": _f(t.get("stop")), "target": _f(t.get("target")), "exit_px": _f(t.get("exit_px")),
                    "exit": str(t.get("exit") or ""), "r": _f(t.get("r"), 3), "usd": _f(t.get("pnl")), "risk_pts": _f(t.get("risk_pts")),
                    "swept": list(t.get("swept") or [])})
    for k, v in (state.get("ledger") or {}).items():
        if not str(k).isdigit() or not isinstance(v, dict) or not v.get("exit_ts") or v.get("exit") in (None, "OPEN"):
            continue
        if v.get("taken") is False:
            continue
        side = str(v.get("side") or "").upper()
        out.append({"src": "paper", "account": "Cloud paper", "day": v.get("day") or tday(int(k)), "entry_t": int(k),
                    "exit_t": int(v["exit_ts"]), "side": side, "d": 1 if side == "LONG" else -1, "qty": int(v.get("qty") or 0),
                    "entry": _f(v.get("entry_px")), "stop": _f(v.get("stop_px")), "target": _f(v.get("target_px")),
                    "exit_px": _f(v.get("exit_px")), "exit": str(v.get("exit") or ""), "r": _f(v.get("R"), 3), "usd": _f(v.get("usd")),
                    "risk_pts": _f(v.get("risk_pts")), "swept": []})
    if now is not None:
        out = [t for t in out if t["exit_t"] <= int(now)]
    return sorted(out, key=lambda t: (-t["exit_t"], t["src"] != "pc"))


def card_key(t) -> str:
    from tools.lit_chart_data import trade_id
    return f"{t['src']}_{trade_id(t['day'], t['entry_t'], t['side'])}"


# ------------------------------------------------------------------------------------------------ the setup, rebuilt
def live_core(df5, P, one_min=None, sym="NQ", now=None):
    """The live loop's market on the cloud's bars (engine/lit_live.run without the forming-bar / sizing extras): returns
    (M, C, B5, B1, R) with R = engine/lit.py run_live (its raw trades carry the candidate index "i")."""
    from engine import lit, lit_live
    from engine.data import Bars, from_frame
    df5 = lit_live._clean5(df5)
    if now is not None:
        df5 = df5[df5["time"] + 300 <= int(now)]
    if not len(df5):
        return None
    last_t = int(df5["time"].max())
    w = df5[df5["time"] >= lit_live.window_start(last_t)]
    src = tol = None
    if P.get("tf") == "1m" and one_min is not None:
        if isinstance(one_min, Bars):
            src = lit_live._slice_bars(one_min, int(w["time"].min()))
        else:
            o = one_min if now is None else one_min[one_min["time"] + 60 <= int(now)]
            src, tol = lit_live.feed_1m(o, int(w["time"].min())), lit_live.LIVE_TOL_1M
    M = lit.Market(bars=from_frame(sym, "5m", w), extra_boxes=P.get("extra_boxes") or [])
    M.n_closed = M.n
    C = lit.candidates(M, ref=P["ref"])
    B5 = lit.bars_5m(M)
    B1 = lit.bars_1m(M, src=src, tol=tol, tail=True) if src is not None and len(src) else None
    if P.get("tf") == "1m" and B1 is not None and B1.full and not isinstance(one_min, Bars):
        k1 = min(B1.full)
        C = [z for z in C if z["k"] >= k1]
    R = lit.run_live(M, C, P, B1=B1, B5=B5)
    return M, C, B5, B1, R


def _match(core, t):
    """The model trade (raw run_live row) and its candidate for live trade t: same day and side, entry within 15 minutes."""
    if not core:
        return None, None
    M, C, B5, B1, R = core
    best = None
    for x in R.get("trades") or []:
        if x.get("exit") == "OPEN" or x.get("day") != t["day"] or int(x["dir"]) != t["d"]:
            continue
        gap = abs(int(x["entry_t"]) - t["entry_t"])
        if gap <= 900 and (best is None or gap < best[0]):
            best = (gap, x)
    if best is None:
        return None, None
    cand = {(z["i"], z["dir"]): z for z in C}
    return best[1], cand.get((best[1]["i"], best[1]["dir"]))


def _bars_window(df, a, z):
    if df is None or not len(df):
        return None
    w = df[(df["time"] >= a) & (df["time"] < z)].sort_values("time").drop_duplicates("time")
    if not len(w):
        return None
    p0 = int(float(w["low"].min()) * 4) - 1
    t0, s = int(w["time"].iloc[0]), int(w["time"].iloc[1] - w["time"].iloc[0]) if len(w) > 1 else 300
    s = 60 if s <= 60 else 300
    q = lambda col: [int(round(float(v) * 4)) - p0 for v in w[col]]
    return {"t0": t0, "s": s, "p0": p0, "dt": [int((int(x) - t0) // s) for x in w["time"]], "o": q("open"), "h": q("high"),
            "l": q("low"), "c": q("close")}


def plain_record(t, df5, df1=None):
    """A card record from the trade's own prices only (no setup markers): the PC filled a trade the cloud model did not
    rebuild, or the bars are missing."""
    b5 = _bars_window(df5, t["entry_t"] - 7200, t["exit_t"] + 3600)
    if b5 is None:
        return None
    b1 = _bars_window(df1, t["entry_t"] - 1200, max(t["entry_t"] + 1200, min(t["exit_t"] + 300, t["entry_t"] + 3600))) \
        if df1 is not None else None
    if b1 is not None and b1["s"] != 60:
        b1 = None
    off = int(_et(t["entry_t"]).utcoffset().total_seconds())
    risk = abs((t["entry"] or 0) - (t["stop"] or 0))
    return {"id": card_key(t), "day": t["day"], "side": t["side"], "d": t["d"], "tf": 1 if b1 else 5, "off": off, "qty": t["qty"],
            "risk_usd": round(t["qty"] * risk * 2.0, 2), "risk_pts": round(t.get("risk_pts") or risk, 2), "pnl": t["usd"] or 0.0,
            "r": t["r"] or 0.0, "exit_kind": _kind(t["exit"]), "entry_kind": "-", "size_why": [],
            "entry": {"t": t["entry_t"], "px": t["entry"]}, "stop": t["stop"], "target": t["target"] if t["target"] is not None else t["entry"],
            "plan_rr": round(abs((t["target"] or t["entry"]) - t["entry"]) / risk, 2) if risk else 0.0, "target_label": "VIX band",
            "be": None, "exit": {"t": t["exit_t"] - 60, "t_end": t["exit_t"], "px": t["exit_px"] if t["exit_px"] is not None else t["entry"],
                                 "kind": _kind(t["exit"])},
            "adds": [], "levels": [], "sweep": None, "idm": [], "cisd5": None, "limit": None, "cisd1": None, "boxes": [],
            "b5": b5, "b1": b1,
            "sub": "LIT · " + (("swept " + ", ".join(t["swept"][:3]) + " · ") if t.get("swept") else "")
                   + "setup markers unavailable: the cloud's bars did not rebuild this trade, the prices are the fills"}


def _kind(x):
    x = str(x or "").upper()
    return "EOD" if x in ("TIME", "EOD", "TIME SAFETY") else x or "EXIT"


def record_for(t, core, P, df5, df1=None):
    """(card record, matched model trade or None, candidate or None) for live trade t."""
    from tools.lit_chart_data import record_of
    raw, z = _match(core, t)
    rec = None
    if raw is not None and z is not None:
        M, C, B5, B1, R = core
        try:
            rec, _miss = record_of(M, B5, B1, z, raw, P)
        except Exception:
            rec = None
    if rec is None:
        return plain_record(t, df5, df1), None, None
    d = t["d"]
    rec = dict(rec)
    rec["id"] = card_key(t)
    # the live trade's own numbers (paper: the paper size; PC: the real fills)
    if t["qty"]:
        rec["qty"] = t["qty"]
    if t["usd"] is not None:
        rec["pnl"] = t["usd"]
    if t["r"] is not None:
        rec["r"] = t["r"]
    if t["src"] == "pc":
        for k in ("stop", "target"):
            if t[k] is not None:
                rec[k] = t[k]
        if t["entry"] is not None:
            rec["entry"] = {**rec["entry"], "px": t["entry"]}
        if t["exit_px"] is not None:
            rec["exit"] = {**rec["exit"], "px": t["exit_px"]}
        if abs(t["entry_t"] - rec["entry"]["t"]) > 90:
            rec["entry"] = {**rec["entry"], "t": t["entry_t"]}
        if abs(t["exit_t"] - rec["exit"]["t_end"]) > 90:
            rec["exit"] = {**rec["exit"], "t": t["exit_t"] - 60, "t_end": t["exit_t"]}
        if t["exit"]:
            rec["exit_kind"] = _kind(t["exit"]) if _kind(t["exit"]) != "EXIT" else rec["exit_kind"]
    ent = rec["entry"]["px"]
    rec["risk_pts"] = round(abs(ent - rec["stop"]), 2)
    rec["risk_usd"] = round(rec["qty"] * rec["risk_pts"] * 2.0, 2)
    rec["disp_mark"] = True
    if rec.get("be") and P.get("be_off") is not None:
        rec["be_px"] = round(ent + d * float(P.get("be_off") or 0.0), 2)
    tc = P.get("t_check")
    if tc and rec.get("tf") == 1:
        ct = int(rec["entry"]["t"]) + int(tc.get("at", 15)) * 60
        cut = rec["exit_kind"] == "CUT_T15"
        if cut or rec["exit"]["t_end"] >= ct:
            rec["tcheck"] = {"t": ct, "cut": cut}
    return rec, raw, z


# ------------------------------------------------------------------------------------------------ the words
def recap_text(t, raw, z, P, label="LIT", rec=None) -> dict:
    """why it entered / the plan / what happened / lessons (tools/export_backtest.py _report_lit on the matched model trade,
    with the live trade's own size, prices and result)."""
    if raw is not None and z is not None:
        from tools import export_backtest as E
        x = E.lit_row(raw, z, P, label)
        model_entry = x["entry"]
        if t["qty"]:
            x["qty"] = t["qty"]
        if t["usd"] is not None:
            x["pnl"] = t["usd"]
        if t["r"] is not None:
            x["r"] = t["r"]
        if t["src"] == "pc":
            for a, b in (("entry", "entry"), ("stop", "stop"), ("target", "target"), ("exit_price", "exit_px")):
                if t[b] is not None:
                    x[a] = t[b]
            if t["exit"]:
                x["exit"] = t["exit"].upper()
            x["exit_t"] = t["exit_t"]
        x["risk_pts"] = round(abs(x["entry"] - x["stop"]), 2)
        x["risk_usd"] = round(x["qty"] * x["risk_pts"] * 2.0, 2)
        rep = E._report_lit(x, label)
        lessons = list(rep["lessons"])
        if t["src"] == "pc" and t["entry"] is not None:
            slip = (t["entry"] - model_entry) * t["d"]          # + = filled worse than the model
            ticks = round(slip / 0.25)
            lessons.append("filled at the model's price" if ticks == 0 else
                           f"filled {abs(ticks)} tick{'s' if abs(ticks) != 1 else ''} {'worse' if ticks > 0 else 'better'} than the model "
                           f"({'-' if slip > 0 else '+'}${abs(slip) * 2.0 * (t['qty'] or 0):,.2f} on {t['qty']} micro{'s' if t['qty'] != 1 else ''})")
        if not lessons:
            lessons.append("by the book: the rules did their job" if (t["r"] or 0) >= 0 else "a normal loss: the stop sat beyond the sweep")
        return {"why": rep["why"], "plan": rep["plan"], "result": rep["result"], "lessons": lessons, "matched": True}
    ex = _kind(t["exit"])
    why = [("Swept " + ", ".join(t["swept"])) if t.get("swept") else "The setup could not be rebuilt from the cloud's bars."]
    risk = abs((t["entry"] or 0) - (t["stop"] or 0))
    plan = (f"Entry {_px(t['entry'])}, stop {_px(t['stop'])} ({risk:.2f} pts) -> {t['qty']} micros, ${t['qty'] * risk * 2:,.0f} at risk; "
            f"target {_px(t['target'])}")
    res = f"{ex} at {_et(t['exit_t']):%H:%M} ET: {(t['r'] or 0):+.2f}R, {_usd(t['usd'])}"
    lessons = ["the cloud model did not take this trade: compare it with the paper ledger" if t["src"] == "pc" else
               "no setup markers: the bars around the trade were missing"]
    return {"why": why, "plan": plan, "result": res, "lessons": lessons, "matched": False}


# ------------------------------------------------------------------------------------------------ cards
def make_cards(state, out, df5, df1=None, P=None, now=None, label="LIT", max_new=MAX_NEW, keep=KEEP, core=None,
               wait_tries=WAIT_TRIES) -> list:
    """Draw the missing recap cards (newest first, at most max_new per call), keep the newest `keep`. Returns the cards made
    this call (index rows). The index (recaps/index.json "cards") is the app's list."""
    from engine import lit
    from tools import lit_trade_charts as LT
    import matplotlib.pyplot as plt
    P = {**lit.DEFAULTS, **(P or {})}
    now = int(now or 0) or None
    ix = load_index(out)
    cards = {c["key"]: c for c in ix.get("cards") or [] if isinstance(c, dict) and c.get("key")}
    d, _ = _paths(out)
    os.makedirs(d, exist_ok=True)
    trades = finished_trades(state, now)
    newest = trades[:keep]
    lim = (now or max([t["exit_t"] for t in trades] or [0])) - MAX_AGE_D * 86400
    made = []
    tries = {k: int(v) for k, v in (ix.get("tries") or {}).items() if k in {card_key(t) for t in newest}}
    for t in newest:
        key = card_key(t)
        c = cards.get(key)
        if c and c.get("v") == VERSION and os.path.exists(os.path.join(d, key + ".png")):
            continue
        if len(made) >= max_new or t["exit_t"] < lim or tries.get(key, 0) >= MAX_TRIES:
            continue
        if core is None and df5 is not None:
            try:
                core = live_core(df5, P, df1, now=now)
            except Exception as e:
                print("recap: setup rebuild failed:", e.__class__.__name__, e)
                core = False
        try:
            rec, raw, z = record_for(t, core or None, P, df5, df1)
            if rec is None or (raw is None and tries.get(key, 0) < wait_tries):
                # no bars around the trade yet, or the setup not rebuilt yet (the PC's bars may still be on their way):
                # try again next run; after WAIT_TRIES a card with the trade's own prices, after MAX_TRIES give up
                tries[key] = tries.get(key, 0) + 1
                print(f"recap: {key}: {'no bars around the trade' if rec is None else 'setup not rebuilt'} yet (try {tries[key]})")
                continue
            rec["src_label"] = t["account"]
            rec["footer"] = ("CME NQ futures · " + ("NinjaTrader fills" if t["src"] == "pc" else "cloud paper ledger")
                             + " · times ET · recap card")
            txt = recap_text(t, raw, z, P, label, rec)
            path = os.path.join(d, key + ".png")
            LT.render(rec, path, dpi=DPI, size=SIZE)
            plt.close("all")
            _shrink(path)
        except Exception as e:
            print(f"recap: card {key} failed:", e.__class__.__name__, e)
            continue
        row = {"key": key, "v": VERSION, "src": t["src"], "account": t["account"], "day": t["day"], "entry_t": t["entry_t"],
               "exit_t": t["exit_t"], "side": t["side"], "exit": rec["exit_kind"], "qty": rec["qty"], "r": _f(rec["r"], 2),
               "usd": _f(rec["pnl"]), "entry": rec["entry"]["px"], "stop": rec["stop"], "target": rec["target"],
               "exit_px": rec["exit"]["px"], "risk_pts": rec["risk_pts"], "risk_usd": rec["risk_usd"], "png": f"{DIR}/{key}.png",
               "h": _hash(path), "kb": round(os.path.getsize(path) / 1024, 1), "made_t": int(now or t["exit_t"]), **txt}
        cards[key] = row
        made.append(row)
    rows = sorted(cards.values(), key=lambda c: -int(c.get("exit_t") or 0))[:keep]
    ix["tries"] = {k: v for k, v in tries.items() if k not in cards}
    for n in os.listdir(d):
        if n.endswith(".png") and n != "brief.png" and n[:-4] not in {c["key"] for c in rows}:
            try:
                os.remove(os.path.join(d, n))
            except OSError:
                pass
    ix["cards"] = rows
    ix["v"] = VERSION
    save_index(out, ix)
    return made


def card_notices(made, base_url=None) -> list:
    """One "recap" notice per new card (engine/push.py shape): same tag as the trade's entry / outcome notice, so it
    replaces it on the phone; tap opens the card in the app; the PNG is the notification image where the phone shows one.
    A PC card and the paper card of the same trade make one notice (the PC's, processed first)."""
    from engine import push
    base = base_url or push.APP_URL
    out, seen = [], set()
    for c in sorted(made, key=lambda c: (c["src"] != "pc", -c["exit_t"])):
        k = f"recap:{c['day']}:{c['side']}"
        if k in seen:
            continue
        seen.add(k)
        lesson = (c.get("lessons") or [""])[0]
        out.append({"kind": "recap", "key": k, "t": int(c["exit_t"]), "src": c["account"], "account": c["account"],
                    "title": f"Recap · {c['side']} {_usd(c['usd'])} · {c['account']}",
                    "body": f"{(c.get('why') or [''])[0]}. {c.get('result') or ''}. Lesson: {lesson}"[:600],
                    "tag": push.trade_tag(c["entry_t"]), "url": f"#/recaps/{c['key']}",
                    "image": f"{base}{c['png']}?v={c.get('h') or ''}", "side": c["side"], "usd": c["usd"], "R": c["r"], "exit": c["exit"]})
    return out


# ------------------------------------------------------------------------------------------------ daily brief image
def brief_image(out, brief, df5, now=None, force=False):
    """recaps/brief.png from the morning brief (engine/lit_brief.py "morning"), drawn once per morning stage (built 01:30,
    refreshed 07:30). Returns the index row {"day", "built_t", "png", "h", ...} when drawn now, else None."""
    mo = (brief or {}).get("morning")
    if not mo or not mo.get("day"):
        return None
    ix = load_index(out)
    old = ix.get("brief") or {}
    d, _ = _paths(out)
    path = os.path.join(d, "brief.png")
    if not force and old.get("day") == mo["day"] and old.get("built_t") == mo.get("built_t") and os.path.exists(path):
        return None
    os.makedirs(d, exist_ok=True)
    try:
        _draw_brief(path, mo, df5, now or mo.get("built_t"))
        _shrink(path, 128)
    except Exception as e:
        print("recap: brief image failed:", e.__class__.__name__, e)
        return None
    vix = mo.get("vix") or {}
    width = (vix.get("high") - vix.get("low")) if vix.get("high") is not None and vix.get("low") is not None else None
    row = {"day": mo["day"], "built_t": mo.get("built_t"), "built": mo.get("built"), "stage": mo.get("stage"), "png": f"{DIR}/brief.png",
           "h": _hash(path), "kb": round(os.path.getsize(path) / 1024, 1), "plan": mo.get("plan"), "band_width": _f(width, 1),
           "vix": vix.get("vix"), "move": vix.get("move"), "news": mo.get("news_text"), "eval": (mo.get("eval") or {}).get("text"),
           "pushed": old.get("pushed") if old.get("day") == mo["day"] else None}
    ix["brief"] = row
    save_index(out, ix)
    return row


def brief_notice(out, base_url=None):
    """The day's "brief" notice, once a day (the first brief image of the day); marks it pushed in the index."""
    from engine import push
    ix = load_index(out)
    b = ix.get("brief") or {}
    if not b.get("day") or b.get("pushed"):
        return None
    b["pushed"] = True
    ix["brief"] = b
    save_index(out, ix)
    day = dt.date.fromisoformat(b["day"])
    body = (b.get("plan") or "") + (f" Target band {b['band_width']:.0f} pts wide." if b.get("band_width") else "")
    return {"kind": "brief", "key": f"brief:{b['day']}", "t": int(b.get("built_t") or 0), "src": "Cloud",
            "title": f"LIT brief · {day:%a %b %d}", "body": body[:600], "tag": "le-brief", "url": "#/brief",
            "image": f"{base_url or push.APP_URL}{b['png']}?v={b.get('h') or ''}"}


def _draw_brief(path, mo, df5, now):
    import matplotlib
    matplotlib.use("Agg")
    import matplotlib.pyplot as plt
    from matplotlib.patches import Rectangle
    from tools.lit_trade_charts import C, BOX_C, candles
    now = int(now)
    bars = []
    if df5 is not None and len(df5):
        w = df5[(df5["time"] + 300 <= now) & (df5["time"] >= now - 20 * 3600)].sort_values("time")
        bars = [(int(r.time), float(r.open), float(r.high), float(r.low), float(r.close)) for r in w.itertuples()]
    fig = plt.figure(figsize=BRIEF_SIZE, dpi=DPI, facecolor=C["page"])
    ax = fig.add_axes([0.055, 0.07, 0.57, 0.79])
    ax.set_facecolor(C["panel"])
    for s in ax.spines.values():
        s.set_color(C["grid"])
    price = float(mo.get("price") or (bars[-1][4] if bars else 0))
    levels = [r for r in mo.get("levels") or [] if r.get("kind") != "buildup" or not r.get("taken")]
    vix = mo.get("vix") or {}
    lo_b = [b[3] for b in bars] or [price]
    hi_b = [b[2] for b in bars] or [price]
    rng = max(hi_b) - min(lo_b) or 50
    # the levels map shows what sits within reach: the bars' range plus the target band (capped)
    span_lo, span_hi = min(lo_b) - 0.8 * rng, max(hi_b) + 0.8 * rng
    if vix.get("low") is not None:
        span_lo, span_hi = min(span_lo, vix["low"] - 10), max(span_hi, vix["high"] + 10)
    shown = [r for r in levels if span_lo <= r["price"] <= span_hi and (not r.get("taken") or r.get("kind") in ("pd", "pw", "pm", "gap"))]
    shown = sorted(shown, key=lambda r: abs(r["price"] - price))[:16]
    ys = [r["price"] for r in shown] + lo_b + hi_b + [x for x in (vix.get("low"), vix.get("high")) if x is not None]
    y0, y1 = min(ys), max(ys)
    pad = (y1 - y0) * 0.04 + 2
    ax.set_ylim(y0 - pad, y1 + pad)
    n = len(bars)
    ax.set_xlim(0, max(n, 10) * 1.6)
    ax.grid(axis="y", color=C["grid"], lw=0.5, zorder=0)
    ax.tick_params(axis="both", length=0, labelsize=6.5, pad=2)
    ax.yaxis.set_major_formatter(matplotlib.ticker.FuncFormatter(lambda v, _: f"{v:,.0f}"))
    if bars:
        off = int(_et(bars[-1][0]).utcoffset().total_seconds())
        ticks = [(i, b[0]) for i, b in enumerate(bars) if (b[0] + off) % 10800 == 0]
        ax.set_xticks([i for i, _ in ticks])
        ax.set_xticklabels([_et(t).strftime("%H:%M") for _, t in ticks])
        # session boxes from the brief (done ones: their high / low across the bars they cover)
        tt = [b[0] for b in bars]
        import bisect
        for bx in mo.get("boxes") or []:
            if bx.get("status") != "done" or bx.get("high") is None:
                continue
            a_, z_ = [int(x) for x in bx["window"].replace(":", "").split("-")]
            a_m, z_m = a_ // 100 * 60 + a_ % 100, z_ // 100 * 60 + z_ % 100
            idx = [i for i, t in enumerate(tt) if (lambda m: (m - a_m) % 1440 < (z_m - a_m) % 1440 or (z_m == a_m))(
                _et(t).hour * 60 + _et(t).minute)]
            if not idx:
                continue
            col = BOX_C.get(bx["label"].split()[0], C["accent"])
            ax.add_patch(Rectangle((idx[0], bx["low"]), idx[-1] + 1 - idx[0], bx["high"] - bx["low"], facecolor=col, alpha=0.07,
                                   edgecolor=col, lw=0.6, ls=(0, (2, 2)), zorder=1))
            ax.annotate(bx["label"], xy=(idx[0], bx["high"]), xytext=(2, 2), textcoords="offset points", fontsize=5.8, color=col)
        candles(ax, bars, w=0.6)
    # VIX target band
    if vix.get("low") is not None:
        for y, lab in ((vix["high"], "VIX band (long target)"), (vix["low"], "VIX band (short target)")):
            ax.axhline(y, color=C["gold"], lw=1.0, ls=(0, (6, 3)), zorder=4)
            ax.annotate(f"{lab} {y:,.2f}", xy=(0, y), xycoords=("axes fraction", "data"), xytext=(3, 2), textcoords="offset points",
                        ha="left", fontsize=6.0, color=C["gold"])
    # levels: untaken solid, taken faded dashed; labels on the right, nudged apart
    from tools.lit_trade_charts import spread
    yl = ax.get_ylim()
    gap = (yl[1] - yl[0]) * 0.035
    srt = sorted(shown, key=lambda r: r["price"])
    lab_y = spread([r["price"] for r in srt], gap)
    xr = max(n, 10) + 0.5
    for r, yy in zip(srt, lab_y):
        col = C["bsl"] if r["side"] == "H" else C["ssl"]
        alpha = 0.35 if r.get("taken") else 1.0
        ax.plot([0, xr], [r["price"], r["price"]], color=col, lw=0.8 if not r.get("taken") else 0.6,
                ls="-" if not r.get("taken") else (0, (2, 2)), alpha=alpha, zorder=5)
        txt = r["label"] + (" / " + (r.get("also") or [""])[0] if r.get("also") else "") + f" {r['price']:,.2f}" + (" (taken)" if r.get("taken") else "")
        ax.plot([xr, max(n, 10) * 1.6 * 0.995], [r["price"], yy], color=col, lw=0.4, alpha=0.5, zorder=5)
        ax.annotate(txt, xy=(0.995, yy), xycoords=("axes fraction", "data"), ha="right", va="bottom", fontsize=5.6, color=col,
                    alpha=max(alpha, 0.6), parse_math=False)
    if price:
        ax.axhline(price, color=C["accent"], lw=0.7, zorder=6)
    ax.set_title(f"5m, last 20 h · LIT map ({sum(1 for r in levels if not r.get('taken'))} untaken)", fontsize=7, color=C["ink2"], loc="left", pad=3)
    # text column
    day = dt.date.fromisoformat(mo["day"])
    fig.text(0.014, 0.955, f"LIT brief · {day:%a %Y-%m-%d}", fontsize=11, fontweight="bold", color=C["ink"], va="center")
    fig.text(0.985, 0.955, f"built {mo.get('built')} ET · NQ {price:,.2f}", fontsize=8, color=C["ink2"], va="center", ha="right")
    fig.text(0.014, 0.905, "orange = highs (buy stops), blue = lows (sell stops); solid untaken, faded dashed taken; gold = target band",
             fontsize=6, color=C["muted"], va="center")
    import textwrap
    x0, y = 0.645, 0.86
    ev = mo.get("eval") or {}
    width = (vix.get("high") - vix.get("low")) if vix.get("high") is not None else None
    blocks = [("Game plan", mo.get("plan") or "", C["ink"]),
              ("Target band", (f"{width:.0f} pts wide: VIX {vix.get('vix')} -> one-day move {vix.get('move'):.0f} pts from the "
                               f"18:00 open {vix.get('open18'):,.2f}") if width else (vix.get("text") or "no VIX close"), C["gold"]),
              ("Overnight", (mo.get("overnight") or {}).get("text") or "", C["ink2"]),
              ("News", mo.get("news_text") or "no high-impact USD news", C["warn"] if mo.get("news") else C["ink2"]),
              ("Eval", ev.get("text") or "", C["teal"])]
    if (mo.get("monday") or {}).get("text"):
        blocks.append(("Monday rule", mo["monday"]["text"], C["ink2"]))
    for h, body, col in blocks:
        if y < 0.08:
            break
        fig.text(x0, y, h.upper(), fontsize=6.2, fontweight="bold", color=C["muted"], va="top")
        y -= 0.035
        for ln in textwrap.wrap(body, 50)[:8 if h == "Game plan" else 5]:
            fig.text(x0, y, ln, fontsize=6.6, color=col, va="top", parse_math=False)
            y -= 0.033
        y -= 0.02
    fig.text(0.985, 0.022, "CME NQ futures · PC NinjaTrader bars · times ET · paper analysis, no trade advice", fontsize=5.6,
             color=C["muted"], ha="right")
    fig.savefig(path, dpi=DPI, facecolor=C["page"])
    plt.close(fig)


# ------------------------------------------------------------------------------------------------ weekly review
def week_bounds(now) -> tuple:
    """(monday, friday) of the last complete Mon-Fri week as of `now` (on a weekday: the previous week)."""
    e = _et(now)
    d = e.date()
    fri = d - dt.timedelta(days=(d.weekday() - 4) % 7)
    if fri == d and e.hour < 17:            # Friday before the session's end: that week is not complete yet
        fri -= dt.timedelta(days=7)
    return fri - dt.timedelta(days=4), fri


def weekly_due(prev: dict | None, now) -> bool:
    """Sunday (or the first run of the next week, a missed Sunday) and this week not reviewed yet."""
    e = _et(now)
    mon, fri = week_bounds(now)
    if (prev or {}).get("week") == str(mon):
        return False
    return e.weekday() == 6 or (e.weekday() == 0 and e.hour < 12) or e.weekday() == 5


def weekly(state: dict, now, df5=None, hub=None, cards=None) -> dict:
    """The weekly review of the last complete week (see the module doc)."""
    mon, fri = week_bounds(now)
    days = [str(mon + dt.timedelta(days=i)) for i in range(5)]
    tr = [t for t in finished_trades(state) if t["day"] in days]
    ck = {c["key"]: c for c in cards or []}
    by = {}
    for t in tr:
        by.setdefault(t["src"], []).append(t)
    srcs = {}
    for s, rows in by.items():
        rows = sorted(rows, key=lambda t: t["entry_t"])
        wins = [t for t in rows if (t["usd"] or 0) > 0]
        losses = [t for t in rows if (t["usd"] or 0) < 0]
        best = max(rows, key=lambda t: t["usd"] or 0)
        worst = min(rows, key=lambda t: t["usd"] or 0)
        srcs[s] = {"account": rows[0]["account"], "n": len(rows), "wins": len(wins), "losses": len(losses),
                   "net": round(sum(t["usd"] or 0 for t in rows), 2), "R": round(sum(t["r"] or 0 for t in rows), 2),
                   "win_rate": round(100.0 * len(wins) / len(rows), 1),
                   "best": {"day": best["day"], "side": best["side"], "usd": best["usd"], "r": best["r"], "exit": best["exit"], "key": card_key(best)},
                   "worst": {"day": worst["day"], "side": worst["side"], "usd": worst["usd"], "r": worst["r"], "exit": worst["exit"], "key": card_key(worst)},
                   "exits": {k: sum(1 for t in rows if _kind(t["exit"]) == k) for k in sorted({_kind(t["exit"]) for t in rows})}}
    main = "pc" if "pc" in srcs else "paper" if "paper" in srcs else None
    rows = [{"key": card_key(t), "src": t["src"], "account": t["account"], "day": t["day"], "time": f"{_et(t['entry_t']):%H:%M}",
             "side": t["side"], "exit": _kind(t["exit"]), "r": t["r"], "usd": t["usd"], "qty": t["qty"],
             "card": card_key(t) in ck, "lesson": ((ck.get(card_key(t)) or {}).get("lessons") or [None])[0]} for t in sorted(tr, key=lambda t: t["entry_t"])]
    # execution quality: the PC's fills against the cloud model on the same trades, and the PC's own fill audit
    ex = {"pairs": []}
    pt = {(t["day"], t["side"]): t for t in by.get("paper", [])}
    for t in by.get("pc", []):
        p = pt.get((t["day"], t["side"]))
        if p and t["entry"] is not None and p["entry"] is not None:
            slip = (t["entry"] - p["entry"]) * t["d"]
            ex["pairs"].append({"day": t["day"], "side": t["side"], "entry_slip_ticks": round(slip / 0.25),
                                "exit_pc": t["exit"], "exit_model": p["exit"], "same_exit": _kind(t["exit"]) == _kind(p["exit"])})
    missed = sorted({(t["day"], t["side"]) for t in by.get("paper", [])} - {(t["day"], t["side"]) for t in by.get("pc", [])})
    extra = sorted({(t["day"], t["side"]) for t in by.get("pc", [])} - {(t["day"], t["side"]) for t in by.get("paper", [])})
    ex["missed_by_pc"] = [f"{d} {s}" for d, s in missed] if "pc" in srcs or (state.get("pc") or {}).get("present") else []
    ex["extra_on_pc"] = [f"{d} {s}" for d, s in extra]
    au = (state.get("pc") or {}).get("exec") if isinstance(state.get("pc"), dict) else None
    if isinstance(au, dict):
        ex["audit"] = {k: au.get(k) for k in ("trades", "missed", "extra", "slip_usd", "slip_usd_per_trade", "entry_slip_ticks_med",
                                               "exit_slip_ticks_med", "latency_s_med", "be_delay_s_med", "text")}
    if ex["pairs"]:
        med = sorted(p["entry_slip_ticks"] for p in ex["pairs"])[len(ex["pairs"]) // 2]
        ex["text"] = (f"{len(ex['pairs'])} PC fill(s) next to the model: median entry {med:+d} ticks; "
                      f"{sum(1 for p in ex['pairs'] if p['same_exit'])} of {len(ex['pairs'])} exits the same as the model")
    elif "pc" in srcs:
        ex["text"] = "PC trades this week, but no cloud model trade to compare them with"
    else:
        ex["text"] = "no PC fills this week: execution quality is measured on the PC's routed trades" + (
            " (the cloud paper ledger traded)" if "paper" in srcs else "")
    if ex["missed_by_pc"]:
        ex["text"] += f"; the PC missed {len(ex['missed_by_pc'])} model trade(s): {', '.join(ex['missed_by_pc'])}"
    watch = _watch_next(state, now, mon, fri, df5, hub, by.get(main, []) if main else [], cards or [])
    parts = [f"{s['account']}: {s['n']} trade{'s' if s['n'] != 1 else ''}, {_usd(s['net'])}, {s['R']:+.2f}R"
             for k, s in sorted(srcs.items(), key=lambda kv: kv[0] != "pc")]
    head = "; ".join(parts) if parts else "no trades this week"
    if max([s["n"] for s in srcs.values()] or [0]) < 2:
        head += " - below the 2-4 a week the strategy aims for"
    return {"v": VERSION, "week": str(mon), "label": f"{mon:%b %d} - {fri:%b %d}", "built_t": int(now), "days": days,
            "main": main, "head": head, "sources": srcs, "trades": rows, "execution": ex, "watch": watch,
            "eval": {k: (state.get("eval_2wk") or {}).get(k) for k in ("session", "limit", "status", "to_target", "room", "text")}}


def _watch_next(state, now, mon, fri, df5, hub, trades, cards) -> list:
    """'What to watch next week': plain lines, each from the data (news, the new PWH/PWL, Friday's high/low for the Monday
    rule, the eval clock, this week's loss pattern, the trade count)."""
    out = []
    nmon = fri + dt.timedelta(days=3)
    nfri = nmon + dt.timedelta(days=4)
    ev = [e for e in ((hub or {}).get("events") or []) if isinstance(e, dict) and e.get("impact") == "high"
          and e.get("country", "USD") == "USD" and str(nmon) <= str(e.get("date") or "") <= str(nfri)]
    if ev:
        names = []
        for e in sorted(ev, key=lambda e: (e.get("date"), e.get("time_et") or "")):
            nm = f"{e.get('weekday') or ''} {e.get('time_et') or ''} {e.get('title') or e.get('kind_label') or ''}".strip()
            if nm not in names:
                names.append(nm)
        out.append({"kind": "news", "text": f"High-impact USD news next week: {'; '.join(names[:6])}"
                                            + (f" (+{len(names) - 6} more)" if len(names) > 6 else "") + "."})
    else:
        out.append({"kind": "news", "text": "No high-impact USD news listed for next week yet (the calendar fills in over the weekend)."})
    if df5 is not None and len(df5):
        a = int(dt.datetime.combine(mon - dt.timedelta(days=1), dt.time(18, 0), ET).timestamp())
        z = int(dt.datetime.combine(fri, dt.time(17, 0), ET).timestamp())
        w = df5[(df5["time"] >= a) & (df5["time"] < z)]
        if len(w):
            hi, lo = float(w["high"].max()), float(w["low"].min())
            out.append({"kind": "levels", "text": f"This week's high {hi:,.2f} and low {lo:,.2f} are next week's PWH / PWL: "
                                                  f"a sweep of either is a LIT level ({hi - lo:,.0f} pts apart)."})
            fa = int(dt.datetime.combine(fri - dt.timedelta(days=1), dt.time(18, 0), ET).timestamp())
            f = w[w["time"] >= fa]
            if len(f):
                out.append({"kind": "monday", "text": f"Monday rule: Friday's high {float(f['high'].max()):,.2f} / low "
                                                      f"{float(f['low'].min()):,.2f}. Once Monday takes the high only shorts, the low only longs."})
    ck = state.get("eval_2wk") or {}
    if ck.get("session"):
        rest = int(ck.get("limit") or 10) - int(ck["session"])
        out.append({"kind": "eval", "text": f"Eval: session {ck['session']} of {ck.get('limit', 10)}, ${float(ck.get('to_target') or 0):,.0f} to the "
                                            f"target, ${float(ck.get('room') or 0):,.0f} of room to the floor. "
                                            + (f"{rest} session(s) left in the two-week sizing." if rest > 0 else
                                               "Past session 10: the eval goes on in safe_eval sizing (smaller).")})
    elif (state.get("eval") or {}).get("balance") is not None:
        e = state["eval"]
        out.append({"kind": "eval", "text": f"Eval balance ${float(e['balance']):,.0f}, ${float(e.get('to_target') or 0):,.0f} to the target."})
    ck_ = {c["key"]: c for c in cards}
    los = [t for t in trades if (t["usd"] or 0) < 0]
    if los:
        les = [l for t in los for l in ((ck_.get(card_key(t)) or {}).get("lessons") or [])]
        cnt = {}
        for l in les:
            k = ("never moved" if "never moved" in l else "stopped at once" if "almost at once" in l else
                 "gave back" if "still lost" in l else "cut" if "15-minute" in l else None)
            if k:
                cnt[k] = cnt.get(k, 0) + 1
        if cnt:
            k, v = max(cnt.items(), key=lambda kv: kv[1])
            out.append({"kind": "losses", "text": f"{v} of {len(los)} loss(es) this week: {k} after the entry. "
                                                  "Watch the first 15 minutes after a fill (the 15-minute check cuts the ones that never get going)."})
        if sum(1 for t in los if _kind(t["exit"]) == "STOP") >= 2 and state.get("lit_sizing") not in ("two_week",):
            out.append({"kind": "weekly_stop", "text": "Two or more stop-outs this week: the weekly stop's half size resets on Monday."})
    if len(trades) < 2:
        out.append({"kind": "count", "text": f"Only {len(trades)} trade(s) this week (target 2-4): check the PC was up from ~01:55 ET "
                                             "(95 of 120 LIT trades in 2026 entered 02:00-08:00)."})
    return out


def weekly_notice(wk):
    if not wk or not wk.get("week"):
        return None
    return {"kind": "weekly", "key": f"weekly:{wk['week']}", "t": int(wk.get("built_t") or 0), "src": "Cloud",
            "title": f"Weekly review · {wk['label']}", "body": (wk["head"] + ". " + ((wk.get("watch") or [{}])[0].get("text") or ""))[:600],
            "tag": "le-weekly", "url": "#/weekly"}


def readme_lines(rc, wk=None) -> list:
    """The dashboard README's section: the latest recap card (image + lesson), the brief image, the weekly headline."""
    L = []
    cards = (rc or {}).get("cards") or []
    if cards:
        c = cards[0]
        L += ["## Latest trade recap", f"*{c['day']} {c['side']} · {c['account']} · {c['exit']} {_usd(c['usd'])} ({(c['r'] or 0):+.2f}R) · "
                                       f"{len(cards)} cards in the app (Trades -> Recaps)*", "", f"![recap]({c['png']})", "",
              f"- Why: {'; '.join(c.get('why') or [])}", f"- What happened: {c.get('result') or ''}",
              f"- Lesson: {'; '.join(c.get('lessons') or [])}", ""]
    b = (rc or {}).get("brief")
    if b:
        L += [f"**Brief image** ({b['day']}, built {b.get('built')} ET): [recaps/brief.png]({b['png']})", ""]
    if wk and wk.get("week"):
        L += [f"**Weekly review {wk['label']}:** {wk['head']}. " + " ".join(w["text"] for w in (wk.get("watch") or [])[:2]), ""]
    return L


# ------------------------------------------------------------------------------------------------ cloud hook
def cloud_hook(out, new_state, old_state, df5, df1, lm, now, hub=None) -> dict:
    """tools/cloud_monitor.py, after the state is built: recap cards, the brief image, the weekly review. Returns
    {"notices": [...], "cards": n made, ...}; new_state["recaps"] / ["weekly"] are set. Never raises."""
    res = {"notices": [], "made": 0}
    if (lm or {}).get("model") != "lit":
        return res
    P = lm.get("lit") or {}
    try:
        made = make_cards(new_state, out, df5, df1, P, now, label=lm.get("label") or "LIT")
        res["made"] = len(made)
        res["notices"] += card_notices(made)
    except Exception as e:
        print("recap: cards failed:", e.__class__.__name__, e)
    try:
        if brief_image(out, new_state.get("brief"), df5, now):
            n = brief_notice(out)
            if n:
                res["notices"].append(n)
    except Exception as e:
        print("recap: brief failed:", e.__class__.__name__, e)
    ix = load_index(out)
    prev_wk = (old_state or {}).get("weekly")
    try:
        if weekly_due(prev_wk, now):
            wk = weekly(new_state, now, df5, hub, ix.get("cards"))
            new_state["weekly"] = wk
            n = weekly_notice(wk)
            if n:
                res["notices"].append(n)
        else:
            new_state["weekly"] = prev_wk
    except Exception as e:
        print("recap: weekly failed:", e.__class__.__name__, e)
        new_state["weekly"] = prev_wk
    new_state["recaps"] = {"cards": ix.get("cards") or [], "brief": ix.get("brief")}
    try:
        from engine import lit_brief
        lit_brief._insert_readme(os.path.join(out, "README.md"), readme_lines(new_state["recaps"], new_state.get("weekly")))
    except Exception as e:
        print("recap: README section failed:", e.__class__.__name__, e)
    print(f"recap: {res['made']} new card(s), {len(ix.get('cards') or [])} kept"
          + (f", brief {ix['brief'].get('day')} {ix['brief'].get('built')}" if ix.get("brief") else "")
          + (f", weekly {new_state['weekly'].get('week')}" if new_state.get("weekly") else ""))
    return res


if __name__ == "__main__":
    import argparse
    import pandas as pd
    ap = argparse.ArgumentParser()
    ap.add_argument("--state", default="dash/state.json")
    ap.add_argument("--out", default="dash")
    a = ap.parse_args()
    st = json.load(open(a.state, encoding="utf-8"))
    lm = json.load(open(os.path.join(ROOT, "live_model.json"), encoding="utf-8"))
    df5 = pd.read_csv(os.path.join(ROOT, "data", "NQ_5m.csv"))
    p1 = os.path.join(a.out, "bars_1m.csv")
    df1 = pd.read_csv(p1) if os.path.exists(p1) else None
    print(make_cards(st, a.out, df5, df1, lm.get("lit"), st.get("last_run")))
