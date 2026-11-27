"""MISSED-MONEY AUDIT, every lane x account (day-moneyaudit 2026-11-27, owner/lead: "like today's ATLAS funded find, for EVERY lane x
account since Oct 19"). READ ONLY RESEARCH: never trades, routes, sizes live or edits live code / live_model*.json / a switch.

For each backtest twin signal (LIT = engine/lit.run_x with the live params; ATLAS = engine/second.run, its 3 members, its raw stream with
the one-position rule) and every lane that was meant to trade it that day:
  LIT     Zlarior 50K (from Oct 19), Zlarior 25K #2 (Nov 18), the Rapid EOD 25K's LIT lane (Nov 20)
  ATLAS   its own Builder 25K (account B: eval Nov 6-17, funded from Nov 18), the Rapid EOD 25K's ATLAS lane (Nov 20),
          the combo on Zlarior's 50K and on the 25K #2 (owner yes Nov 23; engine/combo50k / combo25)
did the account route it, at the size the lane's OWN rule gives (the real functions: livegap.eval_size = two_week for LIT;
account_b.qty / funded_qty for B; rapid.stack_qty + best_day_cap for the Rapid; combo50k.atlas_qty for the combos), and fill near
the model? Every difference gets one cause with its evidence: not armed / not switched on, stuck record, refused (Name), PC off,
guard / rule by design (size 0, one position, best-day), slippage, bug.

Live side: tools/web_public/trading/trades.json live rows, data/pc_days/<day>/ (trades / fills / gaps / thoughts) when pulled,
the PC's status post (tools/board.fetch_lite: today's rows, "at", "mf", Board events) saved by --feed <file>.

    python -X utf8 tools/money_audit.py [--feed scratch.json]     # -> research/moneyaudit/AUDIT.json + the table
"""
from __future__ import annotations

import argparse
import collections
import datetime as dt
import glob
import gzip
import json
import os
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)
OUT = os.path.join(ROOT, "research", "moneyaudit", "AUDIT.json")
PV, COMM = 2.0, 1.90
SINCE = "2026-10-19"

# lane -> account, from / to (CME days), the evidence it was meant to trade; "armed" windows where the lane existed but was not on
LANES = [
    {"lane": "LIT", "acct": "z50k", "name": "Zlarior 50K", "from": "2026-10-19", "src": "live_model eval_start; live since Oct 19"},
    {"lane": "LIT", "acct": "z25k2", "name": "Zlarior 25K #2", "from": "2026-11-18", "src": "accounts.json; mf sd 2026-11-18"},
    {"lane": "LIT", "acct": "rapid25k", "name": "Rapid EOD 25K", "from": "2026-11-20", "src": "mf sd 2026-11-20",
     "not_armed": [("2026-11-20", "2026-11-26", "added DISARMED Nov 19; armed the night of Nov 26 (STATE 'Rapid EOD 25K never armed until tonight')")]},
    {"lane": "ATLAS", "acct": "atlas25", "name": "ATLAS 25K (eval Nov 6-17, funded from Nov 18)", "from": "2026-11-06",
     "src": "first live ATLAS row Nov 6 (data/pc_days/2026-11-06 acctb.eval_...6017); the Nov 17 balance $26,946.10 fits trades from Nov 6 only",
     "early": ("2026-10-19", "2026-11-05", "no ATLAS live row in the cloud or the PC's day folders before Nov 6 (their trade files are empty "
                                          "before Nov 4); ATLAS was on only on Oct 27 for certain (its refused 03:30 MACD LONG 3, "
                                          "tests/test_acctb_not_placed): not counted, not verifiable")},
    {"lane": "ATLAS", "acct": "rapid25k", "name": "Rapid EOD 25K (ATLAS lane)", "from": "2026-11-20", "src": "atlas-on-rapid yes Nov 20",
     "not_armed": [("2026-11-20", "2026-11-26", "added DISARMED Nov 19; armed the night of Nov 26")]},
    {"lane": "ATLAS combo", "acct": "z50k", "name": "Zlarior 50K (ATLAS combo)", "from": "2026-11-24",
     "src": "card zlarior-atlas-50k yes 2026-11-23; first combo trade Nov 27 (Board combo_trade)"},
    {"lane": "ATLAS combo", "acct": "z25k2", "name": "Zlarior 25K #2 (ATLAS combo)", "from": "2026-11-24",
     "src": "owner 2026-11-23 'Yes do it' (the combo on BOTH Zlarior accounts, engine/combo25 docstring)"},
]
# known PC-wide gaps (tools/livegap.PC_GAPS) + this audit's own
EXTRA_GAPS = []
# a live row the cloud lacks but the evidence pins (today's feed)
REFUSED = {("atlas25", 1793086200): {"q": 3, "why": "order REFUSED: every MFFU order went to an account Name without the 'R' (bug, FIXED "
                                                   "Oct 27: engine/ninjatrader._nt_said_no_account); tests/test_acctb_not_placed '03:30 "
                                                   "MACD LONG 3 on the 25K was refused'"}}


def atlas_twin(since=SINCE):
    """tools/livegap.atlas_twin + each trade's target and member key (the Rapid's best-day rule needs the target)."""
    import pandas as pd
    from engine import second
    from tools import livegap as G
    d5 = pd.read_csv(os.path.join(ROOT, "data", "NQ_5m.csv"))
    d1 = pd.read_csv(os.path.join(ROOT, "data", "NQ_1m.csv"))
    lo = int(dt.datetime.fromisoformat(since).replace(tzinfo=G.ET).timestamp())
    d5 = d5[d5.time >= lo - 86400 * 45].reset_index(drop=True)
    d1 = d1[d1.time >= lo - 86400 * 3].reset_index(drop=True)
    r = second.run(d5, one_min=d1, now=int(d5.time.max()) + 300, cfg=second.load_cfg(), lit=[])
    out = []
    for k, m in G.ATLAS_MEMBERS.items():
        for t in r["strategies"][k]["trades"]:
            if t["day"] >= since and t.get("exit_kind") and t["exit_kind"] != "OPEN":
                out.append({"bot": "ATLAS", "member": m, "key": k, "day": t["day"], "entry_t": int(t["entry_t"]), "exit_t": int(t["exit_t"]),
                            "dir": int(t["dir"]), "exit": t["exit_kind"], "entry": t["entry"], "stop": t["stop"], "target": t.get("target"),
                            "r": round(t["r"], 3), "risk": t["risk_pts"]})
    out.sort(key=lambda t: t["entry_t"])
    busy = 0
    for t in out:
        t["one_position_skip"] = t["entry_t"] < busy
        if not t["one_position_skip"]:
            busy = t["exit_t"]
    return out


def _et(ts):
    from zoneinfo import ZoneInfo
    return dt.datetime.fromtimestamp(int(ts), ZoneInfo("America/New_York"))


def _hm(ts):
    return _et(ts).strftime("%a %b %d %H:%M")


def usd_of(t, q):
    """The twin trade's $ at q micros: R x stop pts x $2 x q - $1.90 x q."""
    return round(float(t["r"]) * float(t["risk"]) * PV * q - COMM * q, 2) if q else 0.0


def tgt_pts(t):
    if t.get("target") is not None and t.get("entry") is not None:
        return abs(float(t["target"]) - float(t["entry"]))
    return 2.0 * float(t["risk"])


# ------------------------------------------------------------------------------------------------ the live side
def live_rows(feed=None):
    """[{acct, bot, member, entry_t, dir, q, usd, src}] from trades.json, data/pc_days and the PC's post (today)."""
    out = []
    T = json.load(open(os.path.join(ROOT, "tools", "web_public", "trading", "trades.json"), encoding="utf-8"))
    AK = {"zlarior": "z50k", "atlas": "atlas25"}
    for t in T["trades"]:
        if t.get("src") == "live":
            out.append({"acct": AK.get(t["acct"], t["acct"]), "bot": t["bot"], "member": t.get("m"), "entry_t": int(t["t"]),
                        "dir": 1 if t["side"] == "LONG" else -1, "q": t["q"], "usd": t["usd"], "e": t.get("e"), "src": "trades.json"})
    for d in sorted(glob.glob(os.path.join(ROOT, "data", "pc_days", "????-??-??"))):
        p = os.path.join(d, "trades.jsonl.gz")
        if not os.path.exists(p):
            continue
        rows = [json.loads(x) for x in gzip.open(p, "rt", encoding="utf-8") if x.strip()]
        ent = {}
        for r in rows:
            if r.get("mode") != "live" or r.get("bot") == "blitz":
                continue
            if r.get("side") in ("buy", "sell", "BUY", "SELL", "LONG", "SHORT"):
                ent[(r.get("acct"), r.get("src"), int(r["entry_t"]))] = r
        for (acct, src, et_), r in ent.items():
            ex = next((x for x in rows if x.get("side") == "exit" and int(x.get("entry_t") or 0) == et_ and x.get("src") == src), {})
            a = "atlas25" if str(acct) in ("atlas", "acctb") else "rapid25k" if "acctr" in str(src) else \
                "z25k2" if "b25k" in str(src) or "x:" in str(acct) else "z50k"
            out.append({"acct": a, "bot": str(r.get("bot") or "").upper() or "LIT", "member": r.get("strategy"), "entry_t": et_,
                        "dir": 1 if str(r.get("side")).lower() in ("buy", "long") else -1, "q": r.get("qty"), "usd": ex.get("pnl"),
                        "src": f"pc_days {os.path.basename(d)} ({src})"})
    if feed:
        AF = {"mffu50k_eval": "z50k", "atlas": "atlas25", "rapid": "rapid25k", "b25k_2": "z25k2"}
        for a in ((feed.get("at") or {}).get("a") or []):
            for tr in a.get("tr") or []:
                out.append({"acct": AF.get(a.get("id"), a.get("id")), "bot": None, "member": None, "entry_t": int(tr[0]), "dir": int(tr[2]),
                            "q": tr[3], "usd": tr[8], "e": tr[4], "src": "PC post 'at'"})
        for e in ((feed.get("brd") or {}).get("ev") or []):
            if len(e) >= 4 and e[1] == "combo_trade" and "ATLAS on Zlarior 50K" in str(e[3]):
                out.append({"acct": "z50k", "bot": "ATLAS", "member": None, "entry_t": int(e[0]) - int(e[0]) % 300, "dir": 1 if "LONG" in e[3] else -1,
                            "q": None, "usd": None, "src": "PC Board combo_trade", "combo": True})
        for a in ((feed.get("mf") or {}).get("a") or []):        # the Rapid's +$304 today has no "at" row: mf's best day + last trade day
            if a.get("id") == "rapid" and a.get("lt") and a.get("bd") and a["bd"][0] == a["lt"]:
                out.append({"acct": "rapid25k", "bot": None, "member": None, "day": a["lt"], "entry_t": None, "dir": None, "q": None,
                            "usd": a["bd"][1], "src": "PC post 'mf' (best day = its only trade day)"})
    seen, uniq = set(), []
    for r in out:
        k = (r["acct"], r.get("entry_t"), r.get("day"), r.get("dir"))
        if k not in seen:
            seen.add(k)
            uniq.append(r)
    return uniq


def find(rows, acct, t, window=600):
    for r in rows:
        if r["acct"] != acct:
            continue
        if r.get("entry_t") is not None and abs(int(r["entry_t"]) - int(t["entry_t"])) <= window and (r.get("dir") in (None, t["dir"])):
            return r
        if r.get("entry_t") is None and r.get("day") == t["day"]:
            return r
    return None


# ------------------------------------------------------------------------------------------------ the lanes' own sizes
def size_atlas(lane, acct, t, ctx):
    """(micros, reasons) for an ATLAS twin trade on one lane, from the lane's real sizing function."""
    from engine import account_b as AB
    from engine import combo50k as CB
    from engine import rapid as RP
    tr = {"risk_pts": float(t["risk"]), "tgt_pts": tgt_pts(t), "entry_t": int(t["entry_t"])}
    st = ctx.get(acct) or {}
    if lane == "ATLAS" and acct == "atlas25" and (t["day"], t.get("member")) in B_KNOWN:
        return B_KNOWN[(t["day"], t.get("member"))]
    if lane == "ATLAS" and acct == "atlas25" and not ctx.get("atlas25"):
        return None, ["account B's own need / funded sizing needs its state on the PC: estimate = its live micros (2 on every "
                      "seen trade but the capped Nov 20)"]
    if lane == "ATLAS" and acct == "atlas25":
        funded = t["day"] >= "2026-11-18"
        blk = {"account": "acctb", "plan": "builder25k", "strategies": list(ATLAS_KEYS), "sizing": "need",
               **({"stage": "funded", "funded_start": "2026-11-17", "funded_balance": 25000} if funded else {"eval_start": "2026-11-06"})}
        spec = AB.normalize(blk)
        state = {"room": st.get("room", 1000.0), "cum": 0.0, "profit": st.get("profit", 0.0), "session": st.get("session", 1),
                 "n_today": 0, "days_traded": st.get("days", 0), "balance": 25000 + st.get("profit", 0.0), "loss_streak": 0}
        r = AB.qty(spec, tr, state, key=t.get("key"))
        return int(r["qty"]), r["reasons"][-2:]
    if lane == "ATLAS" and acct == "rapid25k":
        room = st.get("room", 1000.0)
        q, usd, loss1 = RP.stack_qty(float(t["risk"]), room, 0.0, 20, 500.0, 250.0, 2.5)
        q2, cap = RP.best_day_cap(q, tgt_pts(t), float(t["risk"]), 1500.0, 0.0)
        why = [f"${usd:,.0f} risk / ${loss1:,.0f} a micro -> {q}"] + ([f"best-day rule 30%: a winner pays <= ${cap:,.0f} -> {q2}"] if q2 < q else [])
        return int(q2), why
    if lane == "ATLAS combo":
        plan = "builder50k" if acct == "z50k" else "builder25k"
        combo = {**json.load(open(os.path.join(ROOT, "research", "lab", "combo_50k.json"), encoding="utf-8")), "plan": plan}
        start = 50000.0 if plan == "builder50k" else 25000.0
        state = {"profit": st.get("profit", 0.0), "cum": 0.0, "room": st.get("room", 1000.0), "session": st.get("session", 1),
                 "n_today": 0, "days_traded": st.get("days", 0), "balance": start + st.get("profit", 0.0)}
        r = CB.atlas_qty(combo, tr, state, "2026-10-19" if acct == "z50k" else "2026-11-18")
        return int(r["qty"]), r["reasons"][-2:]
    return 0, ["no sizing for this lane"]


ATLAS_KEYS = ("ema_lon_vix", "macd_sweep", "sr_nyreclaim")
# account B sizes the cloud CAN prove (the rule + the state at the time are known)
B_KNOWN = {("2026-11-20", "EMA"): (1, ["funded max_win $1,000: 2 micros x $516 > $1,000 -> 1 (by design, research/livegap)"])}
B_EST_Q = 2                     # account B's live micros on every seen trade but the capped Nov 20 (its own sizing is not replayed)
MEMBER_KEY = {"EMA": "ema_lon_vix", "MACD": "macd_sweep", "SR": "sr_nyreclaim", "S/R": "sr_nyreclaim"}
# the accounts' rooms / profit at the time (the PC's posts and the board; None = the plan start)
CTX = {
    "2026-11-20": {"rapid25k": {"room": 1000.0, "profit": 0.0, "session": 1}},
    "2026-11-27": {"rapid25k": {"room": 995.0, "profit": -5.0, "session": 6},
                   "z50k": {"room": 1009.0, "profit": -827.0, "session": 29, "days": 3},
                   "z25k2": {"room": 1019.24, "profit": 19.24, "session": 8, "days": 0},
                   "atlas25": {"room": 1000.0, "profit": 401.38, "session": 9, "days": 2}},
}


# ------------------------------------------------------------------------------------------------ the audit
def audit(feed=None, twins=None):
    from tools import livegap as G
    if twins is None:
        lit, sess = G.lit_twin(since=SINCE)
        atl = atlas_twin(since=SINCE)
    else:
        lit, sess, atl = twins["lit"], twins["sess"], twins["atlas"]
    for t in atl:
        t["key"] = MEMBER_KEY.get(t["member"], t["member"])
    if feed:                                                        # today's twin rows the bars do not reach yet (the PC's paper rows)
        last = max([t["day"] for t in atl] + [s for s in sess])
        for r in (feed.get("board") or {}).get("trades") or []:
            if r.get("src") == "paper" and r.get("acct") == "atlas" and r.get("day") > last and r.get("exit") not in (None, "OPEN"):
                q = int(r.get("qty") or 0) or 1
                risk = abs(float(r["usd"]) + COMM * q) / (abs(float(r["r"])) * PV * q) if r.get("r") else None
                atl.append({"bot": "ATLAS", "member": r.get("member"), "key": r.get("key"), "day": r["day"], "entry_t": int(r["entry_t"]),
                            "exit_t": int(r["exit_t"]), "dir": 1 if r["side"] == "LONG" else -1, "exit": r["exit"], "r": float(r["r"]),
                            "risk": round(risk, 2) if risk else None, "one_position_skip": False,
                            "src": "the PC's ATLAS paper (shadow) row: the bars end before this day"})
        for t in atl:
            if t.get("src") and t["entry_t"] == 1795792200 and t.get("exit") == "TARGET":   # today's S/R: the order's own levels (feed "at")
                t.update(entry=26289.5, stop=26210.75, target=26440.25, risk=78.75, r=round(150.75 / 78.75, 3))
    rows = live_rows(feed)
    gaps = G.PC_GAPS + EXTRA_GAPS
    out = []
    # ---- LIT: livegap's eval path sizes on the 50K (its two_week rule); the other LIT lanes had no twin signal while on
    A = G.ACCTS["z50k"]
    sz = G.eval_size(lit, A["acct"], A["start"], sess)
    for ln in [x for x in LANES if x["lane"] == "LIT"]:
        for t in [t for t in lit if t["day"] >= ln["from"]]:
            q = (sz.get(t["entry_t"]) or {}).get("qty") if ln["acct"] == "z50k" else None
            out.append(judge(ln, t, q, ["two_week (live_model lit_sizing)"] if q is not None else ["not sized here"], rows, gaps))
    # ---- ATLAS lanes
    for ln in [x for x in LANES if x["lane"] != "LIT"]:
        early = ln.get("early")
        for t in atl:
            if t.get("one_position_skip"):
                continue                                           # ATLAS's own one-position rule: never a gap on any lane
            if t["day"] < ln["from"] and not (early and early[0] <= t["day"] <= early[1] and (ln["acct"], t["entry_t"]) in REFUSED):
                if early and early[0] <= t["day"] <= early[1]:
                    out.append({**base(ln, t), "kind": "NOT LIVE", "cause": "lane not live yet (not counted)", "evidence": early[2],
                                "twin_usd": None, "gap_usd": 0.0})
                continue
            q, why = size_atlas(ln["lane"], ln["acct"], t, CTX.get(t["day"], {}))
            out.append(judge(ln, t, q, why, rows, gaps))
    return {"made": dt.datetime.now().strftime("%Y-%m-%d %H:%M"), "since": SINCE, "bars_to": sess[-1],
            "pc_days": sorted(os.path.basename(d) for d in glob.glob(os.path.join(ROOT, "data", "pc_days", "????-??-??"))),
            "lanes": LANES, "rows": out, "sum": summary(out)}


def base(ln, t):
    return {"lane": ln["lane"], "acct": ln["acct"], "account": ln["name"], "day": t["day"], "when": _hm(t["entry_t"]),
            "entry_t": int(t["entry_t"]), "member": t.get("member") or "LIT", "side": "LONG" if t["dir"] > 0 else "SHORT",
            "twin_exit": t.get("exit"), "twin_r": t.get("r")}


def judge(ln, t, q, why, rows, gaps):
    est = q is None and ln["lane"] == "ATLAS" and ln["acct"] == "atlas25"
    if est:
        q = B_EST_Q
    row = {**base(ln, t), "lane_qty": q, "lane_size_why": why, **({"size_estimate": True} if est else {})}
    tw = usd_of(t, q) if q else 0.0
    row["twin_usd"] = tw
    for a, b, w in ln.get("not_armed") or []:
        if a <= t["day"] <= b:
            if not q:
                return {**row, "kind": "BY DESIGN", "cause": "size 0 by the lane's own rule (and the lane was not armed)",
                        "evidence": "; ".join(why) + f" | {w}", "gap_usd": 0.0}
            return {**row, "kind": "MISSED", "cause": "not armed", "evidence": w, "live_usd": 0.0, "gap_usd": round(-tw, 2)}
    lv = find(rows, ln["acct"], t)
    if lv and ln["lane"] == "ATLAS combo" and not lv.get("combo") and lv.get("src") != "PC post 'at'":
        lv = None
    if lv:
        lu = lv.get("usd")
        row.update(live_qty=lv.get("q"), live_usd=lu, live_src=lv["src"])
        if lu is None:
            return {**row, "kind": "TRADED", "cause": "traded ($ not in the rows we have)", "gap_usd": 0.0}
        if est and lv.get("q"):                                   # account B: its own micros are the size (not replayed here)
            q = int(lv["q"])
            tw = usd_of(t, q)
            row.update(lane_qty=q, twin_usd=tw)
        g = round(float(lu) - tw, 2) if q else 0.0
        kind = "IDENTICAL" if abs(g) < 5 else "SIZE" if (lv.get("q") and q and int(lv["q"]) != int(q)) else "SLIPPED"
        return {**row, "kind": kind, "cause": {"IDENTICAL": "live = the lane's twin", "SIZE": "live micros != the lane's rule",
                                               "SLIPPED": "fill vs the model"}[kind], "gap_usd": g}
    if not q:
        return {**row, "kind": "BY DESIGN", "cause": "size 0 by the lane's own rule", "evidence": "; ".join(why), "gap_usd": 0.0}
    rf = REFUSED.get((ln["acct"], int(t["entry_t"])))
    if rf:
        tw = usd_of(t, rf["q"])
        return {**row, "lane_qty": rf["q"], "twin_usd": tw, "kind": "MISSED", "cause": "order refused (account Name bug, fixed Oct 27)",
                "evidence": rf["why"], "live_usd": 0.0, "gap_usd": round(-tw, 2)}
    g = None
    s = _et(t["entry_t"]).strftime("%Y-%m-%d %H:%M")
    for x in gaps:
        if x["from"] <= s <= (x["to"] if x["to"] != "now" else "9999"):
            g = x
    if g and "HELD BACK" not in g["what"]:
        cause = ("PC bot off" if "OFF" in g["what"] else "order refused (account Name bug, fixed Oct 27)" if "refused" in g["what"]
                 else "not armed (re-set up by hand)" if "re-armed" in g["what"] else "bot / feed gap")
        return {**row, "kind": "MISSED", "cause": cause, "evidence": g["what"], "live_usd": 0.0, "gap_usd": round(-tw, 2)}
    cause, ev = MISS_CAUSE.get((ln["acct"], ln["lane"], t["day"]), ("no live row (cause not in the data we have)", ""))
    return {**row, "kind": "MISSED", "cause": cause, "evidence": ev, "live_usd": 0.0, "gap_usd": round(-tw, 2)}


MISS_CAUSE = {
    ("atlas25", "ATLAS", "2026-11-27"): (
        "BUG: account B skipped it silently (most likely a stuck position record of its Nov 20 trade)",
        "same signal routed on Zlarior 50K (combo) + Rapid EOD 25K; ATLAS funded: no row, no reason (held{} not in the feed), its last trade "
        "Nov 20, card trades_today 0, room $1,000, window open. Fix landed: day-atlasmiss-bot (dc363471f): every skip now has a reason + the "
        "stuck-record self-heal (17:02 ET update)"),
    ("z25k2", "ATLAS combo", "2026-11-27"): (
        "not switched on (most likely): the combo's ATLAS lane on the 25K #2 never traded",
        "owner yes 2026-11-23 for both Zlarior accounts; the switch is data/combo_50k.json 'accounts' on the PC (engine.combo50k --on "
        "--account <25K #2 Name>, the live phrase): the 50K is in it (traded today), the 25K #2 shows no ATLAS trade and no combo state "
        "in the feed. Proof on the PC: data/combo_50k.json; the feed now says it (day-moneyaudit-bot 'lanes')"),
}


def summary(rows):
    by = collections.defaultdict(lambda: {"n": 0, "usd": 0.0, "causes": collections.Counter()})
    for r in rows:
        if r["kind"] not in ("MISSED", "SIZE", "SLIPPED"):
            continue
        k = (r["lane"], r["account"])
        by[k]["n"] += 1
        by[k]["usd"] += float(r.get("gap_usd") or 0)
        by[k]["causes"][r["cause"]] += 1
    return [{"lane": k[0], "account": k[1], "misses": v["n"], "usd": round(v["usd"], 2), "causes": dict(v["causes"])} for k, v in sorted(by.items())]


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--feed", default=None, help="a saved PC status post (tools/board.fetch_lite) for today's rows")
    ap.add_argument("--twins", default=None, help="a saved {lit, sess, atlas} (skip the twin replays)")
    a = ap.parse_args()
    feed = json.load(open(a.feed, encoding="utf-8")) if a.feed else None
    tw = json.load(open(a.twins, encoding="utf-8")) if a.twins else None
    R = audit(feed, tw)
    os.makedirs(os.path.dirname(OUT), exist_ok=True)
    with open(OUT, "w", encoding="utf-8") as fh:
        json.dump(R, fh, indent=1, default=str)
    for r in R["rows"]:
        if r["kind"] == "NOT LIVE":
            continue
        print(f"{r['when']} {r['lane']:11s} {r['account'][:28]:28s} {r['member']:4s} {r['side']:5s} {r['twin_exit']:7s} {r['twin_r']:+.2f}R "
              f"q{r.get('lane_qty')} ${r.get('twin_usd')} | live q{r.get('live_qty')} ${r.get('live_usd')} | {r['kind']} {r.get('gap_usd'):+.2f} {r['cause']}")
    print("\nlane / account / misses / $ (live - lane twin) / causes")
    for s in R["sum"]:
        print(f"  {s['lane']:11s} {s['account'][:34]:34s} {s['misses']:2d} {s['usd']:+10.2f} {s['causes']}")
    print(f"-> {os.path.relpath(OUT, ROOT)}")


if __name__ == "__main__":
    main()
