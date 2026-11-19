"""ATLAS health (2026-11-18, night-atlasfix): is ATLAS's AMBER light (last 40 sessions to Oct 16: fixed-size R-PF 1.89, the
eval-sized $ PF 1.41 vs a 2026 H1 median 2.86) a broken strategy or normal noise, and does any PROTECTIVE rule keep more
of the money on the owner's FUNDED Builder 25K (ATLAS alone; balance $24,887 after -$113 today, $887 room)?

RESEARCH ONLY. Nothing here touches second_model.json, data/account_b.json, live_model*.json or any engine file.

  python -X utf8 tools/atlas_health.py diag       # members, regime, base rates, drawdowns, the weeks after Oct 16
  python -X utf8 tools/atlas_health.py rules      # the protective rules on the funded 25K -> research/second/atlas_health.json
  python -X utf8 tools/atlas_health.py control    # random-timing control for a timing rule that passes (only if one does)
  python -X utf8 tools/atlas_health.py register   # one ZEUS Lab experiment per rule family (kind atlas_funded)
  python -X utf8 tools/atlas_health.py all

Trades: the live ATLAS units (tools/atlas.account_units: never opposite LIT incl. its armed setups, HEDGE close), then ATLAS's
own one position + max 2 a day (tools/atlas_revive.one_pos), 2021-11 .. 2026-10-16. R per trade at a fixed risk, costs in
($1.90 a micro, slippage in the stored exits; tools/atlas_revive.r_net). Newest weeks (no member re-run on the PC's bars in
the cloud): CBOE's free daily VIX file (research/runs/_cache/edge/VIX_History.csv, gitignored; `tools/edge_health.py --fetch`
writes the same file) and the members' own PC paper ledgers to Nov 6 (heartbeat branch).

Funded 25K money: the MFFU Builder 25K funded rules of tools/uprisk.Funded (= engine/funded_life builder25k: $1,000 EOD
trailing floor locked at start + $100, payouts above the $1,100 buffer, $250-$1,000, 80% to the owner, 50% consistency, 2
traded days a cycle, 48 h first wait, 5 payouts), the funded preset size of engine/account_b.funded_qty (engine/sizing.funded_qty
UP25: risk 60% of the room, $50-$750, a winner <= $1,000, the $600 soft daily loss, 20 micros) on the Monte Carlo paths of
tools/money/funded25.py (600 paths x 126 sessions, 5-session blocks; H1 = 2026 Jan-Jun pick, H2 = Jul-Oct 16 check, REF =
2021-11..2025). One addition the older funded tools lack: the live bot's STUCK stop (engine/account_b MIN_ROOM: under $100 of
room = no new trade on the account, "buy a new eval"), so "dead" = floor touched OR stuck. The "ATLAS today" row also runs
without it and must reproduce research/second/atlas_revive.json (funded25.py) exactly.

PRE-DECLARED (2026-11-18, written before the first rule run). Families, each version scored on the same paths:
  M  member pause on the member's OWN paper ledger (all its signals, fixed R, costs in, trades closed before the entry):
     M1 last-10 PF < 1 -> paper only (x0) until it is back >= 1;  M2 the same on the last 20;  M3 last-20 PF < 1 -> x0.5.
     (Close to 2026-10-30 "member weights from the member's last 5-20 trades", 0/24 on the EVAL path: this is the funded
     money path and a full pause.)
  L  the ATLAS edge light as the owner sees it (tools/edge_health: the account's own last 40 sessions, R a week at a fixed
     size, GREEN > 2.14, RED <= 0.17; the 40 sessions BEFORE the trade's day):  L1 AMBER x0.75, RED x0.5;  L2 AMBER x0.5,
     RED x0.5;  L3 RED paper only (x0);  L4 AMBER x0.5, RED x0;  L5 the PF the owner reads: last-40-session R-PF < 1.5 -> x0.5.
  D  daily loss caps tied to the $1,100 buffer (today: the $600 soft daily loss, max 2 trades a day): D1 no new trade after a
     losing trade (day P&L <= -$25);  D2 day cap $275 (25% of the buffer: every trade's full stop-out fits what is left);
     D3 day cap $367 (a third of the buffer);  D4 day cap = a third of the room at the day's start.
  S  smaller risk while the account is under its start balance (in the hole):  S1 40% of the room (not 60%);  S2 30%;
     S3 40% always.
  K  skip conditions:  K1 skip days with the prior VIX close under 15 (RE-MEASURE: the post-hoc lead of atlas-revive);
     K2 skip the session after a losing day on the account (one cool-off day).
POST-HOC (added after the first run, shown, never eligible): K1 at VIX 14.5 / 15.5 / 16 (the knife edge under the dead-account
measure), S4 50% of the room always, S5 40% of the room while the balance is under its best end-of-day balance.
GATE (the family's Jan-Jun pick = its version with the most funded $ a month in Jan-Jun; that pick must hold ALL of):
  (a) money   funded $ a month to the owner >= today - $10 in H1 and H2 (seed noise), REF >= today - $5;
  (b) safety  dead accounts in 6 months (floor touched or stuck) <= today in H1, H2 and REF, lower by >= 1 point in one of them;
  (c) speed   median first payout <= today + 1 session and no payout in 6 months <= today + 0.5 point, H1 and H2;
  (d) trades  2.0-4.1 a week on the account (fixed view) in H1 and H2;
  (e) the same (a)-(c) from TODAY's account (balance -$113, room $887);
  (f) real day order (a funded start every 5 sessions, 126 sessions or to Oct 16): dead not higher in any span, $ a month not
      lower by more than $10 in H1 / H2;
  (g) a timing rule (M, L, K) beats >= 90% of 40 random-timing controls on (a) + (b) (`control`, run only for a passer);
  (h) made explicit after the first run (the project's own "checked on Jul-Oct" rule, not a new bar): the rule must ACT in
      Jul-Oct (change a trade or the funded numbers there); one that never acts there cannot be checked there.
Fixed view (the proof rule's table): every trade at $250 x the rule's weight, the real days in order, costs in: trades a week,
PF, net $, $ a month, max drawdown, for H1 / H2 / 2025 / 2021-24 (D1-D3 and K2 act there too; D4 / S change only funded sizes).
"""
from __future__ import annotations

import argparse
import collections
import datetime as dt
import json
import math
import os
import subprocess
import sys
import time
from zoneinfo import ZoneInfo

import numpy as np

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)
sys.path.insert(0, os.path.join(ROOT, "tools", "money"))
import logging  # noqa: E402
logging.getLogger("engine.sizing").setLevel(logging.ERROR)
from tools import atlas as A  # noqa: E402
from tools import atlas_revive as RV  # noqa: E402
from tools import second_mix as M  # noqa: E402

ET = ZoneInfo("America/New_York")
DATE = "2026-11-18"
OUT = os.path.join(ROOT, "research", "second", "atlas_health.json")
OUT_DIAG = os.path.join(ROOT, "research", "second", "atlas_health_diag.json")
EDGE = os.path.join(ROOT, "research", "lab", "edge_health.json")
CBOE = os.path.join(ROOT, "research", "runs", "_cache", "edge", "VIX_History.csv")
PV, COMM, SLIP = 2.0, 1.90, 0.25
MIN_ROOM = 100.0                       # engine/account_b.MIN_ROOM: the funded stage's stuck line
LOSS_DAY = -25.0                       # a "losing" trade / day: more than costs (a breakeven scratch is not a loss)
TODAY_BAL = -113.0                     # the owner's funded 25K: $24,887 after -$113 on its first day (2026-11-18)
FIX = {"H1": ("2026-01-01", "2026-06-30"), "H2": ("2026-07-01", "2026-10-16"), "2025": ("2025-01-01", "2025-12-31"),
       "2021-24": ("2021-11-01", "2024-12-31")}
VIXB = ((0, 15, "<15"), (15, 18, "15-18"), (18, 22, "18-22"), (22, 99, "22+"))
NOW_PF_R, NOW_PF_USD = 1.89, 1.41      # the AMBER reading on Oct 16 (fixed-size R-PF, eval-sized $ PF), research/lab/edge_health.json


# ================================================================================================ trades
_C = {}


def sessions():
    if "S" not in _C:
        import stack_one_account as SA
        _C["S"] = list(SA.data()["S"])
    return _C["S"]


def stream():
    """ATLAS's account trades (one position, max 2 a day), each with its fixed-risk net R."""
    if "T" not in _C:
        T = []
        for u in RV.one_pos(A.account_units(A.BASE)):
            T.append({"day": u["day"], "entry_t": int(u["entry_t"]), "exit_t": int(u["exit_t"]), "dir": int(u["dir"]),
                      "risk": float(u["risk"]), "tgt": float(u["tgt"] or 0) or None, "pts": float(u["pts"]),
                      "w1": float(min(0.0, u["w1"])), "src": u["src"], "exit": str(u.get("exit", "?")), "R": float(RV.r_net(u)),
                      "strat": "ATLAS"})
        _C["T"] = sorted(T, key=lambda t: t["entry_t"])
    return _C["T"]


def ledgers():
    """Each member's own paper ledger (every signal it took on its own, 2021-11 .. 2026-10-16), by exit time."""
    if "L" not in _C:
        U = M.units()
        _C["L"] = {nm: sorted([{"day": u["day"], "entry_t": int(u["entry_t"]), "exit_t": int(u["exit_t"]), "R": float(RV.r_net(u))}
                               for u in U[nm]], key=lambda u: u["exit_t"]) for nm in ("EMA", "MD", "SR")}
    return _C["L"]


def span_of(day, spans=FIX):
    for k, (a, z) in spans.items():
        if a <= day <= z:
            return k
    return None


def pf(rs):
    r = np.asarray(rs, float)
    gw, gl = r[r > 0].sum(), -r[r < 0].sum()
    return round(float(gw / gl), 2) if gl > 0 else (99.0 if gw > 0 else None)


def rstats(rs):
    r = np.asarray(rs, float)
    if not len(r):
        return {"n": 0}
    return {"n": int(len(r)), "sum_r": round(float(r.sum()), 2), "avg_r": round(float(r.mean()), 3),
            "win": round(100 * float((r > 0.05).mean()), 1), "pf": pf(r)}


def vix_cboe():
    """day -> CBOE VIX close (the cached free daily file), or {} when it is not there."""
    out = {}
    try:
        import csv
        with open(CBOE, encoding="utf-8") as fh:
            for r in csv.DictReader(fh):
                m, d, y = r["DATE"].split("/")
                out[f"{y}-{m}-{d}"] = float(r["CLOSE"])
    except (OSError, KeyError, ValueError):
        return {}
    return out


def vb(v):
    return next((n for a, b, n in VIXB if a <= v < b), "na")


def light_cuts():
    try:
        c = json.load(open(EDGE, encoding="utf-8"))["atlas"]["light"]["cuts"]
        return float(c["green_above_r_week"]), float(c["red_at_or_below_r_week"])
    except Exception:  # noqa: BLE001
        return 2.14, 0.17


# ================================================================================================ 1. windows / base rates
def windows(T, S, n=40):
    """For every end session e (index): the account's trades of sessions e-n+1..e: n trades, R sum, R-PF, R a week."""
    idx = {d: i for i, d in enumerate(S)}
    by = [[] for _ in S]
    for t in T:
        i = idx.get(t["day"])
        if i is not None:
            by[i].append(t["R"])
    W = {}
    for e in range(n - 1, len(S)):
        rs = [r for b in by[e - n + 1:e + 1] for r in b]
        W[e] = {"day": S[e], "n": len(rs), "sum_r": float(np.sum(rs)) if rs else 0.0, "pf_r": pf(rs) if rs else None,
                "r_week": (float(np.sum(rs)) if rs else 0.0) / (n / 5.0)}
    return W


def base_rates(T, S, n=40):
    """How often a 40-session window looked like Oct 16's (R-PF <= 1.89, and <= 1.41) per span, and what the NEXT 40 / 60
    sessions did after it (non-overlapping forward windows), vs after every window of the span."""
    W = windows(T, S, n)
    g_cut, r_cut = light_cuts()
    W60 = windows(T, S, 60)
    out = {}
    for sp in FIX:
        E = [e for e, w in W.items() if span_of(w["day"]) == sp]
        if not E:
            continue
        v = np.array([min(20.0, W[e]["pf_r"] if W[e]["pf_r"] is not None else 0.0) for e in E])
        rw = np.array([W[e]["r_week"] for e in E])
        row = {"windows": len(E), "pf_r": {"p10": round(float(np.percentile(v, 10)), 2), "p25": round(float(np.percentile(v, 25)), 2),
                                           "median": round(float(np.median(v)), 2), "p75": round(float(np.percentile(v, 75)), 2),
                                           "p90": round(float(np.percentile(v, 90)), 2)},
               "share_pf_le_1_89": round(100 * float((v <= NOW_PF_R).mean()), 1),
               "share_pf_le_1_41": round(100 * float((v <= NOW_PF_USD).mean()), 1),
               "light": {"GREEN": round(100 * float((rw > g_cut).mean()), 1), "RED": round(100 * float((rw <= r_cut).mean()), 1),
                         "AMBER": round(100 * float(((rw > r_cut) & (rw <= g_cut)).mean()), 1)}}
        fw = {}
        for tag, cond in (("after_weak", lambda e: W[e]["pf_r"] is not None and W[e]["pf_r"] <= NOW_PF_R),
                          ("after_any", lambda e: True)):
            nx = [W[e + n] for e in E if cond(e) and (e + n) in W]
            nx60 = [W60[e + 60] for e in E if cond(e) and (e + 60) in W60]
            if nx:
                p = np.array([min(20.0, x["pf_r"] or 0.0) for x in nx])
                fw[tag] = {"windows": len(nx), "next40_pf_r_median": round(float(np.median(p)), 2),
                           "next40_r_week_mean": round(float(np.mean([x["r_week"] for x in nx])), 2),
                           "next40_pf_ge_2": round(100 * float((p >= 2.0).mean()), 1),
                           "next40_positive": round(100 * float(np.mean([x["sum_r"] > 0 for x in nx])), 1),
                           "next60_r_week_mean": round(float(np.mean([x["r_week"] for x in nx60])), 2) if nx60 else None}
        row["forward"] = fw
        # dips: runs of consecutive weak windows (R-PF <= 1.89) and the sessions until R-PF is back >= 2.0
        runs, cur, back = [], 0, []
        Es = sorted(E)
        for e in Es:
            weak = W[e]["pf_r"] is not None and W[e]["pf_r"] <= NOW_PF_R
            if weak:
                cur += 1
            elif cur:
                runs.append((e - cur, cur))
                cur = 0
        if cur:
            runs.append((Es[-1] - cur + 1, cur))
        for s0, ln in runs:
            k = next((e for e in range(s0, len(S)) if e in W and (W[e]["pf_r"] or 0) >= 2.0), None)
            back.append(None if k is None else k - s0)
        bk = [b for b in back if b is not None]
        row["dips"] = {"count": len(runs), "median_len": float(np.median([ln for _, ln in runs])) if runs else 0,
                       "longest": max([ln for _, ln in runs]) if runs else 0,
                       "back_to_pf2_median_sessions": float(np.median(bk)) if bk else None,
                       "never_back_in_data": sum(1 for b in back if b is None)}
        out[sp] = row
    return out, W


def usd_pf_rates():
    """The eval-sized $ PF of the stored run (the '1.41' the edge card shows): how often a 40-session $ PF <= 1.41 per span."""
    try:
        from tools import edge_health as EH
        T, sess = EH.atlas_trades()
    except Exception as ex:  # noqa: BLE001
        return {"error": str(ex)[:120]}
    W = EH.window_stats(T, sess, 40)
    out = {}
    for sp in FIX:
        v = np.array([min(20.0, w["pf"]) for d, w in W.items() if span_of(d) == sp and w["pf"] is not None])
        if len(v):
            out[sp] = {"windows": int(len(v)), "median": round(float(np.median(v)), 2), "p10": round(float(np.percentile(v, 10)), 2),
                       "share_le_1_41": round(100 * float((v <= NOW_PF_USD).mean()), 1)}
    return out


def drawdowns(T, S):
    """Fixed 1R a trade, costs in, real order: per span the deepest drawdown (R), the longest stretch under the last equity
    high (sessions), and the drawdown standing on the last day of data."""
    idx = {d: i for i, d in enumerate(S)}
    out = {}
    for sp, (a, z) in FIX.items():
        L = [t for t in T if a <= t["day"] <= z]
        if not L:
            continue
        eq, peak, peak_i, dd, under = 0.0, 0.0, idx.get(L[0]["day"], 0), 0.0, 0
        for t in L:
            eq += t["R"]
            i = idx.get(t["day"], 0)
            if eq >= peak - 1e-9:
                under = max(under, i - peak_i)
                peak, peak_i = eq, i
            dd = min(dd, eq - peak)
        end_i = idx.get(L[-1]["day"], 0)
        under = max(under, end_i - peak_i)
        out[sp] = {"trades": len(L), "sum_r": round(eq, 1), "max_dd_r": round(dd, 1), "longest_under_sessions": int(under),
                   "dd_at_end_r": round(eq - peak, 1), "sessions_since_high": int(end_i - peak_i)}
    return out


# ================================================================================================ 2. regime + members
def day_facts():
    """day -> RTH trend efficiency and RTH range (% of the open) from the 5m NQ1! bars (09:30-16:00 ET)."""
    if "df" not in _C:
        from tools import atlas_deep as D
        B = D.bars5()
        dd = [dt.datetime.fromtimestamp(int(t), ET) for t in B.t]
        mods = np.array([x.hour * 60 + x.minute for x in dd])
        days = np.array([x.date().isoformat() for x in dd])
        rth = (mods >= 570) & (mods < 960)
        out = {}
        for d in np.unique(days[rth]):
            k = np.where(rth & (days == d))[0]
            if len(k) < 30:
                continue
            path = float(np.abs(np.diff(np.r_[B.o[k[0]], B.c[k]])).sum())
            er = abs(float(B.c[k[-1]] - B.o[k[0]])) / path if path > 0 else 0.0
            out[str(d)] = {"er": er, "rng": 100.0 * float(B.h[k].max() - B.l[k].min()) / float(B.o[k[0]])}
        _C["df"] = out
    return _C["df"]


def regime(T, S):
    """Last 40 sessions (to Oct 16) vs Jan-Jun: the share of sessions per VIX bucket, R a trade per bucket, and the R the
    last 40 sessions would have made with Jan-Jun's R a trade in each bucket (mix effect) vs what they made."""
    vix = A.vix_prev()
    F = day_facts()
    last = S[-40:]
    h1 = [d for d in S if "2026-01-01" <= d <= "2026-06-30"]
    h2a = [d for d in S if "2026-07-01" <= d <= "2026-08-31"]
    out = {"last40": [last[0], last[-1]], "by_vix": {}, "by_member": {}, "by_daytype": {}}
    sets = {"H1": set(h1), "Jul-Aug": set(h2a), "last40": set(last)}
    for nm, ds in sets.items():
        ss = sorted(ds)
        vv = [vix.get(d, float("nan")) for d in ss]
        out.setdefault("days", {})[nm] = {"sessions": len(ss), "vix_mean": round(float(np.nanmean(vv)), 2),
                                          "rth_range_pct": round(float(np.mean([F[d]["rng"] for d in ss if d in F])), 2),
                                          "trend_eff": round(float(np.mean([F[d]["er"] for d in ss if d in F])), 3),
                                          "vix_share": {b: round(100 * float(np.mean([vb(v) == b for v in vv])), 1) for _, _, b in VIXB}}
    exp, act = 0.0, 0.0
    for _, _, b in VIXB:
        r1 = [t["R"] for t in T if t["day"] in sets["H1"] and vb(vix.get(t["day"], float("nan"))) == b]
        rl = [t["R"] for t in T if t["day"] in sets["last40"] and vb(vix.get(t["day"], float("nan"))) == b]
        out["by_vix"][b] = {"H1": rstats(r1), "last40": rstats(rl)}
        if r1 and rl:
            exp += len(rl) * float(np.mean(r1))
        act += float(np.sum(rl)) if rl else 0.0
    out["mix"] = {"last40_actual_r": round(act, 2), "last40_with_h1_r_per_bucket": round(exp, 2),
                  "h1_r_per_trade": round(float(np.mean([t["R"] for t in T if t["day"] in sets["H1"]])), 3),
                  "last40_trades": sum(1 for t in T if t["day"] in sets["last40"]),
                  "last40_at_h1_overall": round(sum(1 for t in T if t["day"] in sets["last40"]) *
                                                float(np.mean([t["R"] for t in T if t["day"] in sets["H1"]])), 2)}
    for nm in ("EMA", "MD", "SR"):
        out["by_member"][nm] = {k: rstats([t["R"] for t in T if t["day"] in ds and t["src"] == nm]) for k, ds in sets.items()}
    for ty, f in (("trend (eff >= 0.35)", lambda e: e >= 0.35), ("mixed", lambda e: 0.15 <= e < 0.35), ("chop (eff < 0.15)", lambda e: e < 0.15)):
        out["by_daytype"][ty] = {k: rstats([t["R"] for t in T if t["day"] in ds and t["day"] in F and f(F[t["day"]]["er"])])
                                 for k, ds in sets.items()}
    return out


def member_pf_now(extra=None):
    """Each member's last-10 / last-20 ledger PF on Oct 16 and (extra = the PC paper trades after Oct 16) on Nov 6."""
    L = ledgers()
    out = {}
    for nm, X in L.items():
        r = [x["R"] for x in X]
        row = {"oct16_last10_pf": pf(r[-10:]), "oct16_last20_pf": pf(r[-20:]), "oct16_last10_r": round(float(np.sum(r[-10:])), 2),
               "oct16_last20_r": round(float(np.sum(r[-20:])), 2)}
        if extra is not None:
            r2 = r + [t["r"] for t in extra if t["src"] == nm]
            row.update(nov6_last10_pf=pf(r2[-10:]), nov6_last20_pf=pf(r2[-20:]), nov6_added=len(r2) - len(r))
        out[nm] = row
    return out


# ================================================================================================ 3. the weeks after Oct 16
def pc_bars_days():
    """RTH range % and trend efficiency per day from the PC's NinjaTrader 5m bars (heartbeat branch) after Oct 16."""
    try:
        from tools import edge_health as EH
        hb = EH.heartbeat_bars(False)["5m"]
    except Exception as ex:  # noqa: BLE001
        return {"error": str(ex)[:120]}
    if not len(hb):
        return {}
    out = {}
    t = hb["time"].astype(int).values
    o, h, l, c = (hb[k].astype(float).values for k in ("open", "high", "low", "close"))
    dd = [dt.datetime.fromtimestamp(int(x), ET) for x in t]
    days = np.array([x.date().isoformat() for x in dd])
    mods = np.array([x.hour * 60 + x.minute for x in dd])
    rth = (mods >= 570) & (mods < 960)
    for d in np.unique(days[rth]):
        if d <= "2026-10-16":
            continue
        k = np.where(rth & (days == d))[0]
        if len(k) < 30:
            continue
        path = float(np.abs(np.diff(np.r_[o[k[0]], c[k]])).sum())
        out[str(d)] = {"er": abs(float(c[k[-1]] - o[k[0]])) / path if path > 0 else 0.0,
                       "rng": 100.0 * float(h[k].max() - l[k].min()) / float(o[k[0]])}
    return out


def heartbeat_units():
    """The members' own PC paper trades after Oct 16 (heartbeat branch) with risk / pts, for the light and the ledger PF."""
    try:
        raw = subprocess.run(["git", "-C", ROOT, "show", "origin/heartbeat:heartbeat.json"], capture_output=True, timeout=60).stdout
        h = json.loads(raw)
    except Exception:  # noqa: BLE001
        return []
    out = []
    for k, v in ((h.get("second") or {}).get("strategies") or {}).items():
        src = RV.HB_KEYS.get(k, k)
        if src not in ("EMA", "MD", "SR"):
            continue
        for t in v.get("trades") or []:
            if t.get("day", "") > "2026-10-16" and t.get("r") is not None and t.get("exit_kind") != "OPEN":
                out.append({"src": src, "day": t["day"], "dir": int(t["dir"]), "r": float(t["r"]), "exit": t.get("exit_kind"),
                            "entry_t": int(t["entry_t"]), "exit_t": int(t.get("exit_t") or t["entry_t"]),
                            "risk": abs(float(t["entry"]) - float(t["stop"])) if t.get("stop") is not None else None})
    return sorted(out, key=lambda t: t["entry_t"])


def fresh(T, S):
    vx = vix_cboe()
    hb = heartbeat_units()
    pcd = pc_bars_days()
    F = day_facts()
    out = {"vix_source": "CBOE daily VIX (free file, cached)" if vx else "missing"}
    if vx:
        days = sorted(d for d in vx if "2026-10-19" <= d <= "2026-11-18")
        prev = {}
        allv = sorted(vx)
        for d in days:                                   # the PRIOR close (what ATLAS's rules see before the day)
            k = allv.index(d)
            prev[d] = vx[allv[k - 1]]
        out["after_oct16"] = {"sessions": len(days), "first": days[0] if days else None, "last": days[-1] if days else None,
                              "vix_close_min": min(vx[d] for d in days) if days else None,
                              "vix_close_max": max(vx[d] for d in days) if days else None,
                              "prior_close_share": {b: round(100 * float(np.mean([vb(prev[d]) == b for d in days])), 1) for _, _, b in VIXB},
                              "closes": {d: vx[d] for d in days}}
        sep = [d for d in S if "2026-09-01" <= d <= "2026-10-16"]
        vp = A.vix_prev()
        out["sep1_oct16_prior_close_share"] = {b: round(100 * float(np.mean([vb(vp.get(d, float("nan"))) == b for d in sep])), 1) for _, _, b in VIXB}
        h1 = [d for d in S if "2026-01-01" <= d <= "2026-06-30"]
        out["h1_prior_close_share"] = {b: round(100 * float(np.mean([vb(vp.get(d, float("nan"))) == b for d in h1])), 1) for _, _, b in VIXB}
    if hb:
        out["pc_paper"] = {"to": max(t["day"] for t in hb), "by_member": {m: rstats([t["r"] for t in hb if t["src"] == m]) for m in ("EMA", "MD", "SR")},
                           "all": rstats([t["r"] for t in hb]), "trades": [{k: t[k] for k in ("day", "src", "dir", "r", "exit")} for t in hb]}
        if vx:
            allv = sorted(vx)
            pvx = {}
            for t in hb:
                k = allv.index(t["day"]) if t["day"] in vx else None
                pvx[t["entry_t"]] = vx[allv[k - 1]] if k else float("nan")
            out["pc_paper"]["by_vix"] = {b: rstats([t["r"] for t in hb if vb(pvx[t["entry_t"]]) == b]) for _, _, b in VIXB}
        # the light on Nov 6 with the PC paper trades (members' own ledgers, then one position + max 2 a day) appended
        P = RV.one_pos([{**t, "R": t["r"]} for t in hb])
        S2 = S + sorted({t["day"] for t in hb} | (set(pcd) if isinstance(pcd, dict) and "error" not in pcd else set()))
        T2 = T + [{"day": t["day"], "R": t["R"]} for t in P]
        W = windows(T2, S2, 40)
        e = len(S2) - 1
        g_cut, r_cut = light_cuts()
        w = W.get(e) or {}
        out["light_nov6"] = {"sessions_to": S2[-1], "trades": w.get("n"), "pf_r": w.get("pf_r"), "r_week": round(w.get("r_week", 0), 2),
                             "light": "GREEN" if w.get("r_week", 0) > g_cut else ("RED" if w.get("r_week", 0) <= r_cut else "AMBER"),
                             "note": "PC paper ledgers (members' own, after one position + max 2 a day; LIT no-hedge not applied)"}
    if isinstance(pcd, dict) and pcd and "error" not in pcd:
        h1 = [d for d in S if "2026-01-01" <= d <= "2026-06-30" and d in F]
        h2 = [d for d in S if "2026-07-01" <= d <= "2026-10-16" and d in F]
        out["rth"] = {"oct19_nov6": {"sessions": len(pcd), "range_pct": round(float(np.mean([x["rng"] for x in pcd.values()])), 2),
                                     "trend_eff": round(float(np.mean([x["er"] for x in pcd.values()])), 3)},
                      "H1": {"range_pct": round(float(np.mean([F[d]["rng"] for d in h1])), 2), "trend_eff": round(float(np.mean([F[d]["er"] for d in h1])), 3)},
                      "Jul-Oct16": {"range_pct": round(float(np.mean([F[d]["rng"] for d in h2])), 2), "trend_eff": round(float(np.mean([F[d]["er"] for d in h2])), 3)}}
    out["missing"] = "No NQ bars or ATLAS trades for Nov 9 - Nov 17 anywhere in the cloud (PC silent, no data branch on the backup yet); " \
                     "Nov 18 = the funded account's first live trade day (-$113, owner's report)."
    return out


def cmd_diag(log=print):
    T, S = stream(), sessions()
    br, W = base_rates(T, S)
    out = {"date": DATE, "trades": len(T), "sessions": [S[0], S[-1]], "light_cuts": light_cuts(),
           "now": {k: W[len(S) - 1][k] for k in ("day", "n", "pf_r", "r_week", "sum_r")},
           "base_rates": br, "usd_pf": usd_pf_rates(), "drawdowns": drawdowns(T, S), "regime": regime(T, S)}
    hb = heartbeat_units()
    out["members_pf"] = member_pf_now(hb)
    out["fresh"] = fresh(T, S)
    with open(OUT_DIAG, "w", encoding="utf-8") as fh:
        json.dump(out, fh, indent=1, default=float)
    log(f"wrote {os.path.relpath(OUT_DIAG, ROOT)}")
    log(json.dumps({k: out[k] for k in ("now", "base_rates", "usd_pf", "drawdowns")}, default=float)[:6000])
    return out


# ================================================================================================ 4. the rules
IDEAS = {
    "today": {"fam": "base"},
    "M1 member last-10 PF<1 -> paper": {"fam": "M", "mem_n": 10, "mem_w": 0.0},
    "M2 member last-20 PF<1 -> paper": {"fam": "M", "mem_n": 20, "mem_w": 0.0},
    "M3 member last-20 PF<1 -> x0.5": {"fam": "M", "mem_n": 20, "mem_w": 0.5},
    "L1 AMBER x0.75, RED x0.5": {"fam": "L", "light": {"AMBER": 0.75, "RED": 0.5}},
    "L2 AMBER x0.5, RED x0.5": {"fam": "L", "light": {"AMBER": 0.5, "RED": 0.5}},
    "L3 RED -> paper": {"fam": "L", "light": {"RED": 0.0}},
    "L4 AMBER x0.5, RED -> paper": {"fam": "L", "light": {"AMBER": 0.5, "RED": 0.0}},
    "L5 last-40 R-PF<1.5 -> x0.5": {"fam": "L", "pf40": (1.5, 0.5)},
    "D1 stop the day after a loss": {"fam": "D", "after_loss": True},
    "D2 day cap $275 (25% of buffer)": {"fam": "D", "day_cap": 275.0},
    "D3 day cap $367 (1/3 of buffer)": {"fam": "D", "day_cap": 367.0},
    "D4 day cap 1/3 of the room": {"fam": "D", "day_cap_room": 1.0 / 3.0},
    "S1 40% of room while under start": {"fam": "S", "pct_hole": 0.4},
    "S2 30% of room while under start": {"fam": "S", "pct_hole": 0.3},
    "S3 40% of room always": {"fam": "S", "pct": 0.4},
    "K1 skip VIX<15 (re-measure)": {"fam": "K", "vix_skip": 15.0},
    "K2 skip the day after a losing day": {"fam": "K", "cool": True},
    # POST-HOC, added after the first run (never eligible to pass): the K1 knife edge under the dead-account measure, and
    # the S trade-off curve (S3 halved the 2026 dead accounts but slowed the first payout)
    "K1b skip VIX<14.5 (post-hoc)": {"fam": "K", "vix_skip": 14.5},
    "K1c skip VIX<15.5 (post-hoc)": {"fam": "K", "vix_skip": 15.5},
    "K1d skip VIX<16 (post-hoc)": {"fam": "K", "vix_skip": 16.0},
    "S4 50% of room always (post-hoc)": {"fam": "S", "pct": 0.5},
    "S5 40% of room below the peak (post-hoc)": {"fam": "S", "pct_dd": 0.4},
}
FAMILY = {"M": "member pause on its own record", "L": "size down by the edge light", "D": "daily loss cap tied to the buffer",
          "S": "smaller risk while under the start balance", "K": "skip conditions"}
RE_MEASURE = {"K1 skip VIX<15 (re-measure)"}
POST_HOC = {"K1b skip VIX<14.5 (post-hoc)", "K1c skip VIX<15.5 (post-hoc)", "K1d skip VIX<16 (post-hoc)",
            "S4 50% of room always (post-hoc)", "S5 40% of room below the peak (post-hoc)"}


def weights(I, T, S):
    """entry_t -> size multiplier of a timing rule (M, L, K1), from what was known before the trade."""
    w = {t["entry_t"]: 1.0 for t in T}
    if I.get("mem_n"):
        n = int(I["mem_n"])
        L = ledgers()
        ex = {nm: np.array([x["exit_t"] for x in X]) for nm, X in L.items()}
        R = {nm: np.array([x["R"] for x in X]) for nm, X in L.items()}
        for t in T:
            k = int(np.searchsorted(ex[t["src"]], t["entry_t"], side="right"))
            if k < n:
                continue
            p = pf(R[t["src"]][k - n:k])
            if p is not None and p < 1.0:
                w[t["entry_t"]] = float(I["mem_w"])
    if I.get("light") or I.get("pf40"):
        g_cut, r_cut = light_cuts()
        W = windows(T, S, 40)
        idx = {d: i for i, d in enumerate(S)}
        for t in T:
            i = idx.get(t["day"])
            x = W.get(i - 1) if i is not None else None
            if x is None:
                continue
            if I.get("light"):
                lg = "GREEN" if x["r_week"] > g_cut else ("RED" if x["r_week"] <= r_cut else "AMBER")
                w[t["entry_t"]] *= float(I["light"].get(lg, 1.0))
            if I.get("pf40"):
                cut, m = I["pf40"]
                if x["pf_r"] is not None and x["pf_r"] < cut:
                    w[t["entry_t"]] *= float(m)
    if I.get("vix_skip"):
        vix = A.vix_prev()
        for t in T:
            if vix.get(t["day"], 99.0) < float(I["vix_skip"]):
                w[t["entry_t"]] = 0.0
    return w


def with_w(T, w):
    return [{**t, "w": float(w.get(t["entry_t"], 1.0))} for t in T]


def fixed_view(T, S, I, usd=250.0):
    """Every trade at $usd x its weight (int micros of a full stop-out + 1 tick, costs in), the real days in order, with the
    day rules (D1-D3, K2). -> per span stats + per-trade $ (for the Lab's sign-flip)."""
    by = collections.defaultdict(list)
    for t in T:
        by[t["day"]].append(t)
    cap = I.get("day_cap")
    pnl_of, cool = {}, False
    for d in S:
        ts = sorted(by.get(d, []), key=lambda t: t["entry_t"])
        if I.get("cool") and cool:
            cool = False
            continue
        cum = 0.0
        for t in ts:
            loss1 = (t["risk"] + SLIP) * PV + COMM
            q = int(usd * t.get("w", 1.0) // loss1)
            if I.get("after_loss") and cum <= LOSS_DAY:
                q = 0
            if cap:
                full = (t["risk"] + 2 * SLIP) * PV + COMM
                q = min(q, int(max(0.0, cap + cum) // full))
            if q <= 0:
                continue
            p = q * (t["pts"] * PV - COMM)
            cum += p
            pnl_of[t["entry_t"]] = p
        if I.get("cool"):
            cool = cum <= LOSS_DAY
    out = {}
    for sp, (a, z) in FIX.items():
        days = [d for d in S if a <= d <= z]
        L = [(t, pnl_of[t["entry_t"]]) for t in T if a <= t["day"] <= z and t["entry_t"] in pnl_of]
        p = np.array([x for _, x in L], float)
        eq = np.cumsum(p) if len(p) else np.zeros(1)
        gw, gl = p[p > 0].sum(), -p[p < 0].sum()
        out[sp] = {"n": len(L), "tpw": round(len(L) / (len(days) / 5), 2), "pf": round(float(gw / gl), 2) if gl > 0 else None,
                   "net": round(float(p.sum())), "per_month": round(float(p.sum()) / (len(days) / 21)),
                   "max_dd": round(float((eq - np.maximum.accumulate(np.r_[0.0, eq])[1:]).min())) if len(p) else 0}
    return out, pnl_of


def _pgf():
    import builder_levers as BL
    from engine import sizing as SZ
    from tools import uprisk as U

    class PGF(BL.GF):
        """The funded 25K (tools/uprisk.Funded + engine/sizing.funded_qty UP25 = engine/account_b.funded_qty) with the
        live stuck stop (room under $100 = no new trade, the account is done) and one protective rule I."""

        def __init__(self, I, stuck=True):
            super().__init__("builder25k", U.UP25, {"ATLAS": ("fq", None)})
            self.I, self.use_stuck = I, stuck
            self.dead, self.cool_next, self.min_room = None, False, float(self.A["mll"])

        def qty(self, t, st):
            I = self.I
            if self.dead:
                return 0
            if self.use_stuck and st["room"] < MIN_ROOM:
                self.dead = "stuck"
                return 0
            w = float(t.get("w", 1.0))
            if w <= 0:
                return 0
            if I.get("after_loss") and st["cum"] <= LOSS_DAY:
                return 0
            c = self.cfg
            if I.get("pct") is not None:
                c = {**c, "pct": float(I["pct"])}
            if I.get("pct_hole") is not None and st["bal"] + st["cum"] < 0:
                c = {**c, "pct": float(I["pct_hole"])}
            if I.get("pct_dd") is not None and st["bal"] + st["cum"] < self.peak - 1e-9:
                c = {**c, "pct": float(I["pct_dd"])}
            tt = t if t.get("tgt") else {**t, "tgt": 2.0 * t["risk"]}
            q = SZ.funded_qty({**tt, "tgt_pts": tt["tgt"], "risk_pts": tt["risk"]}, st, c, acct=self.A)
            if q > 0 and w != 1.0:
                q = min(q, max(1, int(q * w + 1e-9)))
            cap = I.get("day_cap")
            if I.get("day_cap_room"):
                cap = float(I["day_cap_room"]) * max(0.0, st["room"] - st["cum"])
            if q > 0 and cap:
                loss1 = (t["risk"] + SZ.TW_DLL_SLIP) * SZ.TW_PV + SZ.TW_COMM
                q = min(q, int(max(0.0, cap + st["cum"]) / loss1 + 1e-9))
            return max(0, int(q))

        def step(self, ts, keep=None):
            skip = bool(self.I.get("cool")) and self.cool_next
            a = self.trade_pnl
            ev, x = super().step([] if skip else ts, keep)
            d = self.trade_pnl - a
            self.cool_next = (not skip) and d <= LOSS_DAY
            if self.state == "on":
                st0, _ = self._fast_state()
                self.min_room = min(self.min_room, st0["balance"] - st0["floor"])
            return ev, x
    return PGF


def at_today(f):
    """The owner's funded 25K now: one traded day at -$113 (balance $24,887, floor $24,000, room $887)."""
    from engine import funded_life as FL
    from tools import uprisk as U
    d0 = U.cal(0)
    f.days[d0] = TODAY_BAL
    f.trade_pnl = TODAY_BAL
    f.bal = TODAY_BAL
    f.cyc = [TODAY_BAL]
    f.first_trade = d0
    f.elig_from = FL._next_weekday(FL._add_days(d0, int(math.ceil(f.P["first_wait_h"] / 24.0))))
    f.k = 1
    f.min_room = 1000.0 + TODAY_BAL
    return f


def run_paths(BY, paths, mk, real=False):
    from tools import uprisk as U
    LEN = U.LEN
    rows = []
    for seq in paths:
        f = mk()
        owner, first, npay, end = 0.0, None, 0, "on"
        seq = list(seq[:LEN])
        for k, si in enumerate(seq):
            ev, x = f.step(BY[si])
            if ev in ("paid", "grad"):
                owner += x
                npay += 1
                first = first or k + 1
            if ev == "lost":
                end = "lost"
                break
            if ev == "grad":
                end = "grad"
                break
            if f.dead:
                end = "stuck"
                break
        months = (len(seq) if real else LEN) / 21.0
        rows.append((owner / months, first, npay, end, f.min_room))
    n = len(rows)
    fr = [r[1] for r in rows if r[1]]
    return {"per_month": round(float(np.mean([r[0] for r in rows]))), "first_med": float(np.median(fr)) if fr else None,
            "first_p75": float(np.percentile(fr, 75)) if fr else None, "no_pay_6m": round(100.0 * (n - len(fr)) / n, 1),
            "lost_6m": round(100.0 * sum(r[3] == "lost" for r in rows) / n, 1),
            "stuck_6m": round(100.0 * sum(r[3] == "stuck" for r in rows) / n, 1),
            "dead_6m": round(100.0 * sum(r[3] in ("lost", "stuck") for r in rows) / n, 1),
            "min_room_p10": round(float(np.percentile([r[4] for r in rows], 10))), "payouts": round(float(np.mean([r[2] for r in rows])), 2),
            "paths": n}


def real_starts(S, step=5):
    from tools import uprisk as U
    out = {}
    for sp, (a, z) in U.SPAN.items():
        ix = [i for i, d in enumerate(S) if a <= d <= z]
        out[sp] = [list(range(s, min(s + U.LEN, len(S)))) for s in range(ix[0], ix[-1] + 1, step)]
    return out


def score(I, T, S, PF, RS, w=None):
    import builder_levers as BL
    PGF = _pgf()
    w = w if w is not None else weights(I, T, S)
    TW = with_w(T, w)
    BY = RV.by_session(TW, S)
    row = {"fixed": fixed_view(TW, S, I)[0]}
    row["funded"] = {sp: run_paths(BY, PF[sp], lambda: PGF(I)) for sp in BL.SPANS}
    row["today_state"] = {sp: run_paths(BY, PF[sp], lambda: at_today(PGF(I))) for sp in BL.SPANS}
    row["real"] = {sp: run_paths(BY, RS[sp], lambda: PGF(I), real=True) for sp in BL.SPANS}
    if I.get("fam") == "base":
        row["no_stuck"] = {sp: run_paths(BY, PF[sp], lambda: PGF(I, stuck=False)) for sp in BL.SPANS}
    hit = {}
    for t in TW:
        if t["w"] != 1.0:
            hit[span_of(t["day"]) or "?"] = hit.get(span_of(t["day"]) or "?", 0) + 1
    row["trades_resized"] = hit
    return row


def gate(r, b, fam):
    """The pre-declared gate (module doc) without (g). -> (ok, [reasons it fails])."""
    why = []
    f, fb = r["funded"], b["funded"]
    for sp in ("H1", "H2"):
        if f[sp]["per_month"] < fb[sp]["per_month"] - 10:
            why.append(f"{sp} ${fb[sp]['per_month']} -> ${f[sp]['per_month']}/mo")
    if f["REF"]["per_month"] < fb["REF"]["per_month"] - 5:
        why.append(f"2021-25 ${fb['REF']['per_month']} -> ${f['REF']['per_month']}/mo")
    if any(f[sp]["dead_6m"] > fb[sp]["dead_6m"] for sp in ("H1", "H2", "REF")):
        why.append("more dead accounts " + ", ".join(f"{sp} {fb[sp]['dead_6m']} -> {f[sp]['dead_6m']}%" for sp in ("H1", "H2", "REF")
                                                     if f[sp]["dead_6m"] > fb[sp]["dead_6m"]))
    if not any(f[sp]["dead_6m"] <= fb[sp]["dead_6m"] - 1.0 for sp in ("H1", "H2", "REF")):
        why.append("no fewer dead accounts (needs -1 point in one span)")
    for sp in ("H1", "H2"):
        if (f[sp]["first_med"] or 999) > (fb[sp]["first_med"] or 999) + 1:
            why.append(f"{sp} 1st payout {fb[sp]['first_med']:g} -> {f[sp]['first_med']:g} sessions" if f[sp]["first_med"] else f"{sp} no payout")
        if f[sp]["no_pay_6m"] > fb[sp]["no_pay_6m"] + 0.5:
            why.append(f"{sp} no payout {fb[sp]['no_pay_6m']} -> {f[sp]['no_pay_6m']}%")
    for sp in ("H1", "H2"):
        tp = r["fixed"][sp]["tpw"]
        if not 2.0 <= tp <= 4.1:
            why.append(f"{sp} {tp} trades a week")
    t, tb = r["today_state"], b["today_state"]
    for sp in ("H1", "H2"):
        bad = []
        if t[sp]["per_month"] < tb[sp]["per_month"] - 10:
            bad.append(f"${tb[sp]['per_month']} -> ${t[sp]['per_month']}/mo")
        if t[sp]["dead_6m"] > tb[sp]["dead_6m"]:
            bad.append(f"dead {tb[sp]['dead_6m']} -> {t[sp]['dead_6m']}%")
        if (t[sp]["first_med"] or 999) > (tb[sp]["first_med"] or 999) + 1:
            bad.append(f"1st payout {tb[sp]['first_med']} -> {t[sp]['first_med']} sessions")
        if t[sp]["no_pay_6m"] > tb[sp]["no_pay_6m"] + 0.5:
            bad.append(f"no payout {tb[sp]['no_pay_6m']} -> {t[sp]['no_pay_6m']}%")
        if bad:
            why.append(f"from today's account {sp}: " + ", ".join(bad))
    bad = []
    if t["REF"]["per_month"] < tb["REF"]["per_month"] - 5:
        bad.append(f"${tb['REF']['per_month']} -> ${t['REF']['per_month']}/mo")
    if t["REF"]["dead_6m"] > tb["REF"]["dead_6m"]:
        bad.append(f"dead {tb['REF']['dead_6m']} -> {t['REF']['dead_6m']}%")
    if bad:
        why.append("from today's account 2021-25: " + ", ".join(bad))
    q, qb = r["real"], b["real"]
    for sp in ("H1", "H2", "REF"):
        if q[sp]["dead_6m"] > qb[sp]["dead_6m"]:
            why.append(f"real order {sp} dead {qb[sp]['dead_6m']} -> {q[sp]['dead_6m']}%")
    for sp in ("H1", "H2"):
        if q[sp]["per_month"] < qb[sp]["per_month"] - 10:
            why.append(f"real order {sp} ${qb[sp]['per_month']} -> ${q[sp]['per_month']}/mo")
    return (not why), why


def cmd_rules(n=600, log=print):
    import builder_levers as BL
    from tools import uprisk as U
    t0 = time.time()
    T, S = stream(), sessions()
    PF = {sp: U.mc_paths(S, sp, n, length=BL.LEN, seed=BL.A4.SEED_LIFE) for sp in BL.SPANS}
    RS = real_starts(S)
    out = {"date": DATE, "n": n, "spans": U.SPAN, "fixed_spans": FIX, "rows": {}, "doc": __doc__.split("PRE-DECLARED")[1].strip(),
           "today_balance": TODAY_BAL}
    base = None
    for nm, I in IDEAS.items():
        r = score(I, T, S, PF, RS)
        r["idea"], r["fam"] = I, I["fam"]
        if base is None:
            base = r
            ok, why = None, []
        else:
            ok, why = gate(r, base, I["fam"])
        r["gate_ok"], r["gate_why"] = ok, why
        out["rows"][nm] = r
        f, x = r["funded"], r["fixed"]
        log(f"{nm:36s} " + " | ".join(f"{sp} ${f[sp]['per_month']}/mo 1st {f[sp]['first_med']} nopay {f[sp]['no_pay_6m']}% dead {f[sp]['dead_6m']}%"
                                      for sp in BL.SPANS) + f"  [{time.time() - t0:.0f}s]")
        log(f"{'':36s} " + " | ".join(f"{sp} {x[sp]['tpw']}/wk PF {x[sp]['pf']} ${x[sp]['per_month']}/mo dd {x[sp]['max_dd']}" for sp in FIX))
        log(f"{'':36s} today's acct " + " | ".join(f"{sp} ${r['today_state'][sp]['per_month']} dead {r['today_state'][sp]['dead_6m']}%"
                                                   for sp in BL.SPANS) + " | real " +
            " | ".join(f"{sp} ${r['real'][sp]['per_month']} dead {r['real'][sp]['dead_6m']}%" for sp in BL.SPANS) +
            ("" if ok is None else ("  PASS" if ok else "  - " + "; ".join(why)[:160])))
    # the project rule on top of the gate: the rule must ACT in Jul-Oct (the check half), else Jul-Oct cannot confirm it;
    # per-trade fixed-$250 changes in 2026 for the ZEUS Lab's sign-flip / shadow ledger
    from tools import zeus_lab as Z
    TW0 = with_w(T, {})
    _, p0 = fixed_view(TW0, S, IDEAS["today"])
    b = out["rows"]["today"]
    for nm, r in out["rows"].items():
        r["acts_h2"] = bool(r["trades_resized"].get("H2", 0) > 0 or r["funded"]["H2"] != b["funded"]["H2"])
        if nm == "today":
            r["deltas_2026"], r["flip"] = [], {"H1": 1.0, "H2": 1.0}
            continue
        I = IDEAS[nm]
        _, p1 = fixed_view(with_w(T, weights(I, T, S)), S, I)
        D = []
        for t in T:
            if t["day"] < "2026-01-01":
                continue
            dlt = p1.get(t["entry_t"], 0.0) - p0.get(t["entry_t"], 0.0)
            if abs(dlt) > 0.5:
                D.append({"day": t["day"], "t": f"{t['src']}:{t['entry_t']}", "usd": round(dlt, 2)})
        r["deltas_2026"] = D
        r["flip"] = {sp: Z.signflip_p([d["usd"] for d in D if Z.span_of(d["day"], "atlas") == sp]) for sp in ("H1", "H2")}
    # the H1 pick of each family (most funded $ a month in Jan-Jun), judged by the gate
    picks = {}
    for fam in FAMILY:
        cand = [nm for nm, r in out["rows"].items() if r["fam"] == fam and nm not in RE_MEASURE | POST_HOC]
        if not cand:
            continue
        pk = max(cand, key=lambda nm: (out["rows"][nm]["funded"]["H1"]["per_month"], -out["rows"][nm]["funded"]["H1"]["dead_6m"]))
        pr = out["rows"][pk]
        picks[fam] = {"pick": pk, "versions": sum(1 for nm, r in out["rows"].items() if r["fam"] == fam),
                      "gate_ok": pr["gate_ok"], "acts_h2": pr["acts_h2"], "proof_ok": bool(pr["gate_ok"] and pr["acts_h2"]),
                      "why": pr["gate_why"] + ([] if pr["acts_h2"] else ["never acts in Jul-Oct (0 trades changed): Jul-Oct cannot check it"])}
    out["picks"] = picks
    for nm, r in out["rows"].items():
        r["kind"] = "base" if nm == "today" else ("re-measure" if nm in RE_MEASURE else ("post-hoc" if nm in POST_HOC else "pre-declared"))
    out["passers"] = [nm for nm, r in out["rows"].items() if r.get("gate_ok")]
    out["took_s"] = round(time.time() - t0)
    with open(OUT, "w", encoding="utf-8") as fh:
        json.dump(out, fh, indent=1, default=float)
    log(f"picks: {json.dumps(picks)[:1200]}")
    log(f"passers (any version): {out['passers']}")
    log(f"wrote {os.path.relpath(OUT, ROOT)} in {out['took_s']}s")
    return out


def cmd_control(draws=40, n=300, log=print):
    """For each TIMING rule that passed the gate: the same number of trades resized per span, at random trades (seeded),
    40 draws. Hit = a draw as good on (a) money H1 + H2 and (b) dead accounts. Needs <= 10% hits to count."""
    import builder_levers as BL
    import random
    from tools import uprisk as U
    o = json.load(open(OUT, encoding="utf-8"))
    todo = [nm for nm in o["passers"] if o["rows"][nm]["fam"] in ("M", "L", "K")]
    if not todo:
        log("no timing rule passed the gate: no control to run")
        o["control"] = {"ran": False, "why": "no timing rule passed the gate"}
        with open(OUT, "w", encoding="utf-8") as fh:
            json.dump(o, fh, indent=1, default=float)
        return o
    T, S = stream(), sessions()
    PF = {sp: U.mc_paths(S, sp, n, length=BL.LEN, seed=BL.A4.SEED_LIFE) for sp in BL.SPANS}
    RS = real_starts(S)
    PGF = _pgf()
    res = {}
    base = {sp: run_paths(RV.by_session(with_w(T, {}), S), PF[sp], lambda: PGF({"fam": "base"})) for sp in BL.SPANS}
    for nm in todo:
        I = IDEAS[nm]
        w = weights(I, T, S)
        mine = {sp: run_paths(RV.by_session(with_w(T, w), S), PF[sp], lambda: PGF(I)) for sp in BL.SPANS}
        rng = random.Random(20261118)
        hits, D = 0, []
        for _ in range(draws):
            w2 = {t["entry_t"]: 1.0 for t in T}
            for sp, (a, z) in U.SPAN.items():
                ks = [t["entry_t"] for t in T if a <= t["day"] <= z]
                vals = [w[k] for k in ks]
                rng.shuffle(vals)
                w2.update(dict(zip(ks, vals)))
            g = {sp: run_paths(RV.by_session(with_w(T, w2), S), PF[sp], lambda: PGF(I)) for sp in BL.SPANS}
            good = all(g[sp]["per_month"] >= mine[sp]["per_month"] for sp in ("H1", "H2")) and \
                all(g[sp]["dead_6m"] <= mine[sp]["dead_6m"] for sp in BL.SPANS)
            hits += int(good)
            D.append({sp: {"per_month": g[sp]["per_month"], "dead_6m": g[sp]["dead_6m"]} for sp in BL.SPANS})
        per = {}
        for sp in BL.SPANS:
            for k, better in (("per_month", lambda a, b: a >= b), ("dead_6m", lambda a, b: a <= b)):
                v = [d[sp][k] for d in D]
                per[f"{sp} {k}"] = {"rule": mine[sp][k], "today": base[sp][k], "draws_median": float(np.median(v)),
                                    "draws_p10": float(np.percentile(v, 10)), "draws_p90": float(np.percentile(v, 90)),
                                    "share_as_good": round(float(np.mean([better(x, mine[sp][k]) for x in v])), 3)}
        res[nm] = {"hits": hits, "draws": draws, "rule": mine, "today": base, "ok": hits / draws <= 0.1, "per_metric": per}
        log(f"{nm}: random-timing draws as good {hits}/{draws}; " +
            "; ".join(f"{k} rule {v['rule']} today {v['today']} random p50 {v['draws_median']:g} as-good {v['share_as_good']:.0%}"
                      for k, v in per.items() if not k.startswith("H2")))
    o["control"] = {"ran": True, "rows": res, "n_paths": n}
    with open(OUT, "w", encoding="utf-8") as fh:
        json.dump(o, fh, indent=1, default=float)
    return o


# ================================================================================================ 5. ZEUS Lab
LAB = {
    "M": ("atlas_funded_member_pause", "ATLAS funded 25K: pause a member while its own last 10 / 20 trades lose (PF under 1)",
          "A member whose own last 10 or 20 paper trades have a profit factor under 1 trades 0 micros (or half) on the funded "
          "25K until its record is back at PF 1; it keeps trading on paper meanwhile.",
          "A member that has gone cold stays cold for a while, so pausing it keeps funded money."),
    "L": ("atlas_funded_light_size", "ATLAS funded 25K: smaller size while ATLAS's edge light is AMBER / RED",
          "The funded 25K trades x0.75 / x0.5 / paper while ATLAS's own last-40-session light (tools/edge_health) is AMBER or "
          "RED, or its last-40 R-PF is under 1.5.",
          "A weak last 40 sessions means weaker next weeks, so trading smaller then protects the account."),
    "D": ("atlas_funded_day_cap", "ATLAS funded 25K: a daily loss cap tied to the $1,100 buffer",
          "On the funded 25K ATLAS stops for the day after a losing trade, or caps the day's loss at $275 / $367 / a third of "
          "the room (today: $600 soft daily loss, max 2 trades).",
          "A second loss on a bad day is what drains a small funded account; capping the day keeps the room for the next good trade."),
    "S": ("atlas_funded_hole_size", "ATLAS funded 25K: risk 30-50% of the room instead of 60% (in a hole, or always)",
          "ATLAS risks 40% / 30% of the room to the floor instead of 60% while the funded 25K is under its start balance, "
          "or 40% always (post-hoc: 50% always, 40% while under its best day-end balance).",
          "Smaller bets make a string of losses less likely to strand the account under $100 of room (the bot then stops)."),
    "K": ("atlas_funded_skip", "ATLAS funded 25K: skip calm days (VIX under 15) or the day after a losing day",
          "ATLAS takes no trade on the funded 25K on days whose prior VIX close is under 15 (re-measure), or on the session "
          "after a losing day.",
          "Calm days shrink the VIX-band targets; a losing day is often followed by another."),
}


def lab_head(r):
    """ZEUS Lab page format (tools/zeus_lab.page_row, ATLAS): H1 / H2 funded $ a month + the fixed-$250 detail; 2025 /
    2021-24 carry the funded REF $ a month (2021-11..2025) and their own fixed detail."""
    h = {}
    for sp in ("H1", "H2"):
        x, f = r["fixed"][sp], r["funded"][sp]
        h[sp] = {"per_month": f["per_month"], "n": x["n"], "tpw": x["tpw"], "pf": x["pf"], "net": x["net"], "dd": x["max_dd"],
                 "first_med": f["first_med"], "no_pay_6m": f["no_pay_6m"], "dead_6m": f["dead_6m"]}
    for sp in ("2025", "2021-24"):
        x = r["fixed"][sp]
        h[sp] = {"per_month": r["funded"]["REF"]["per_month"], "n": x["n"], "tpw": x["tpw"], "pf": x["pf"], "net": x["net"],
                 "dd": x["max_dd"], "dead_6m": r["funded"]["REF"]["dead_6m"]}
    return h


def lab_result(e: dict, path: str = OUT) -> dict:
    """ZEUS Lab runner for kind atlas_funded: the stored verdict of this tool (research/second/atlas_health.json; rerun the
    tool for new bars). The family is judged by its Jan-Jun pick (e['family'] = M / L / D / S / K)."""
    o = json.load(open(path, encoding="utf-8"))
    rows = o["rows"]
    base = rows["today"]
    head0 = lab_head(base)
    pk = (o.get("picks") or {}).get(e.get("family")) or {}
    nm = pk.get("pick")
    if not nm or nm not in rows:
        return {"proof_ok": False, "why": f"family {e.get('family')!r} not scored: python -X utf8 tools/atlas_health.py rules",
                "flip": {}, "head": head0, "base": head0, "deltas": [], "usd_month_by": None}
    r = rows[nm]
    h = lab_head(r)
    by = {sp: round(h[sp]["per_month"] - head0[sp]["per_month"]) for sp in ("H1", "H2")}
    ok = bool(pk.get("proof_ok"))
    why = f"Jan-Jun pick '{nm}' of {pk.get('versions')} versions: " + (
        "passes the funded gate and acts in Jul-Oct" if ok else "; ".join(pk.get("why") or r.get("gate_why") or [])[:300])
    return {"proof_ok": ok, "why": why, "flip": r.get("flip") or {"H1": 1.0, "H2": 1.0}, "head": h, "base": head0,
            "deltas": r.get("deltas_2026") or [], "usd_month_by": by}


def cmd_register(log=print):
    from tools import zeus_lab as Z
    o = json.load(open(OUT, encoding="utf-8"))
    for fam, (eid, title, what, hyp) in LAB.items():
        pk = (o.get("picks") or {}).get(fam) or {}
        e = {"id": eid, "bot": "atlas", "kind": "atlas_funded", "family": fam, "cells": int(pk.get("versions") or 1),
             "registered": DATE, "origin": "claude", "source": "research/writeups/atlas-health-2026-11-18.md (tools/atlas_health.py)",
             "title": title, "what_changes": what, "hypothesis": hyp, "judged_by": "atlas_funded", "pick": pk.get("pick")}
        # replace=False: re-registering would rewrite the whole hand-kept registry file (zeus_lab.register's replace path);
        # the Lab reads the family's current pick from research/second/atlas_health.json anyway
        err = Z.register(e, replace=False)
        log(f"{eid}: {'saved' if not err else ('kept (already registered)' if 'already registered' in str(err) else err)}")
    return 0


def main(argv=None):
    ap = argparse.ArgumentParser()
    ap.add_argument("cmd", choices=("diag", "rules", "control", "register", "all"))
    ap.add_argument("--n", type=int, default=600)
    a = ap.parse_args(argv)
    t0 = time.time()
    if a.cmd in ("diag", "all"):
        cmd_diag()
    if a.cmd in ("rules", "all"):
        cmd_rules(a.n)
    if a.cmd in ("control", "all"):
        cmd_control()
    if a.cmd in ("register", "all"):
        cmd_register()
    print(f"{time.time() - t0:.0f}s")
    return 0


if __name__ == "__main__":
    sys.exit(main())
