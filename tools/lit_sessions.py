"""LIT research, dimension SESSIONS AND TIMING (owner order 2026-10-18: LIT is the strategy, tuned and judged on 2026 only).

Starts from lit_A (tools/research_lit.py CAND["A"]) and tests, one change at a time and then in combination:
  * session boxes: new Asia boxes that cross midnight (18-02, 19-03, 20-04, Reim 18:05-01:00), Reim's boxes as his published code
    draws them (+60 min on US summer dates from 2023-11), the 06:00-10:00 4H candle, 08:00-08:30; which box gets swept
  * trap close-back (a bar closes back inside the level within n bars of the breach)
  * entry windows (London, NY AM, NY PM, combos, lunch block)
  * the opens as PO3 reference (00:00, 06:00, 07:30, 08:30, 09:30, 10:00, 18:00) with an entry cap, as filters or size
  * IET 10:00 reversal of the 06:00-10:00 4H candle
  * the high/low-of-week window (size), how_direction, Mon-Wed range break on Thu/Fri, Friday size
  * one direction per day (first sweep, IET "opposite pool taken", TTrades PDH/PDL bias), max trades/day 1 vs 2, AM time stop

Nothing in engine/lit.py is edited: SessMarket subclasses lit.Market (extra boxes), annotate() adds per-level sweep data to the
candidates, run_s() is lit.run with per-day state (one direction, size multipliers, per-trade flat time).

Selection rule (overfitting guard): parameters are picked on 2026 H1 (Jan-Jun), checked on 2026 H2 (Jul-Oct 16); 2021-25 is a
reference line only.

  python tools/lit_sessions.py search      # every variant -> research/lit/sessions_results.json (+ a printed table)
  python tools/lit_sessions.py save        # store the best 5 with rl.save (ids lit_sessions_*, family other, tag lit)
"""
from __future__ import annotations

import bisect
import collections
import datetime as dt
import json
import os
import sys
from zoneinfo import ZoneInfo

import numpy as np

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)
from engine import lit  # noqa: E402
from engine.analytics import PLANS, simulate_eval  # noqa: E402
from tools import runlib as rl  # noqa: E402
from tools import research_lit as R  # noqa: E402

ET = ZoneInfo("America/New_York")
OUT = os.path.join(ROOT, "research", "lit", "sessions_results.json")

SESS_ALL = R.SESS
S26 = [d for d in SESS_ALL if d >= "2026-01-01"]
S_H1 = [d for d in S26 if d <= "2026-06-30"]
S_H2 = [d for d in S26 if d >= "2026-07-01"]
S_REF = [d for d in SESS_ALL if "2021-01-01" <= d <= "2025-12-31"]

# ------------------------------------------------------------------------------------------------ extra session boxes
# name: (start ET minute, end ET minute exclusive, class). start >= 1080 and end < 1080 = crosses midnight inside the 18:00 day.
SESS_EXTRA = {
    "asia18_02": (1080, 120, "x_asia"),     # P1: 8-hour Asia from the reopen, ends at the Frankfurt hour
    "asia19_03": (1140, 180, "x_asia"),     # P2: Tokyo 19:00 -> London open 03:00
    "asia20_04": (1200, 240, "x_asia"),     # P3: ICT Asia start, 8 hours
    "asia18_01": (1085, 60, "x_asia"),      # Reim "LIT - Timing" intended futures Asia 18:05-01:00
    "lon15": (60, 300, "x_lon"),            # ICT 2017 London killzone 01:00-05:00
    "ny8_830": (480, 510, "x_ny"),          # ICT NY open-range model 08:00-08:30
    "h4_610": (360, 600, "x_h4"),           # the 06:00-10:00 4H candle (IET 10:00 reversal)
}
# Reim's published code (summer tables end 2023-10-29): from then on, on US summer-time dates the boxes draw 1 hour later in ET.
REIM_CODED = {"rc_asia": (1085, 60), "rc_lon": (180, 240), "rc_ny": (480, 540)}
REIM_CLASS = {"rc_asia": "x_asia", "rc_lon": "x_lon", "rc_ny": "x_ny"}


def _us_summer(date):
    d = dt.datetime.fromisoformat(date).replace(hour=12, tzinfo=ET)
    return d.utcoffset() == dt.timedelta(hours=-4)


def _box_idx(md, a, z):
    if a >= 1080 and z < 1080:              # crosses midnight: evening part + the after-midnight part of the same trading day
        return np.flatnonzero((md >= a) | (md < z))
    if a >= 1080:
        return np.flatnonzero((md >= a) & (md < z))
    return np.flatnonzero((md >= a) & (md < z) & (md < 1080))


class SessMarket(lit.Market):
    """lit.Market plus the boxes above as extra levels (their own classes, so lit_A's target/class logic is unchanged)."""

    def _context(self):
        super()._context()
        h, l, mod = self.h, self.l, self.mod
        for x in self.ctx:
            s, e = x["s"], x["e"]
            md = mod[s:e]
            boxes = {nm: (a, z) for nm, (a, z, _c) in SESS_EXTRA.items()}
            shift = x["date"] >= "2023-10-30" and _us_summer(x["date"])
            for nm, (a, z) in REIM_CODED.items():
                if shift:
                    a2, z2 = (a + 60) % 1440, (z + 60) % 1440
                    boxes[nm] = (a2, z2)
                else:
                    boxes[nm] = (a, z)
            xb = {}
            for nm, (a, z) in boxes.items():
                ii = _box_idx(md, a, z)
                if len(ii) >= 2:
                    xb[nm] = (float(h[s + ii].max()), float(l[s + ii].min()), int(s + ii[-1]))
            x["xbox"] = xb

    def levels(self, k):
        L = super().levels(k)
        for nm, (hi, lo, ki) in self.ctx[k].get("xbox", {}).items():
            cls = SESS_EXTRA[nm][2] if nm in SESS_EXTRA else REIM_CLASS[nm]
            L.append(("high", hi, ki, nm + "_h", cls)); L.append(("low", lo, ki, nm + "_l", cls))
        return L


BASE_NAMES = ({f"{s}_{x}" for s in lit.SESSIONS for x in "hl"} | {"pdh", "pdl", "pwh", "pwl", "pmh", "pml", "nwog", "ndog", "bu_l", "bu_h"})
NY_TRAP_BAD = {f"{s}_{x}" for s in ("ny830", "ny930", "ny9301030", "pre") for x in "hl"}
SESSION_NAMES = {f"{s}_{x}" for s in lit.SESSIONS for x in "hl"}
X = lambda *nms: {f"{n}_{x}" for n in nms for x in "hl"}

ANCHORS = {"00": 0, "06": 360, "0730": 450, "0830": 510, "0930": 570, "1000": 600}


def annotate(M, C):
    """Per candidate: every swept level with its price (direction space), breach bar and bars until a close back beyond it;
    the opens at the trigger bar; the day's raw-candidate order (for one-direction rules); bias and weekly context."""
    o, h, l, c, mod = M.o, M.h, M.l, M.c, M.mod
    di = M.day_of
    opens = {nm: lit._anchor(o, di, mod, a) for nm, a in ANCHORS.items()}
    opens["18"] = M.open_d
    opens["22"] = M.open_22
    by = collections.defaultdict(list)
    for z in C:
        by[(z["k"], z["dir"])].append(z)
    for (k, d), zs in by.items():
        s, e = M.days[k][1], M.days[k][2]
        L = M.levels(k)
        if d == 1:
            lo_d, c_d = l, c
        else:
            lo_d, c_d = -h, -c
        liq = [(px * d, ki, nm) for side, px, ki, nm, cls in L if (side == "low") == (d == 1)]
        fb = [lit._first_breach(lo_d, max(ki, s - 600), e, p) for p, ki, nm in liq]
        for z in zs:
            ee, i, ext = z["ext_i"], z["i"], z["ext_d"]
            sw = {}
            for q, (p, ki, nm) in enumerate(liq):
                if ki < ee and ee - 24 <= fb[q] <= ee and ext < p:
                    seg = c_d[fb[q]:i + 1] > p
                    nb = int(np.argmax(seg)) if seg.any() else 999
                    if nm not in sw or p > sw[nm][0]:
                        sw[nm] = (p, nb)
            z["sw"] = sw
            z["opens"] = {nm: (None if np.isnan(arr[i]) else float(arr[i]) * d) for nm, arr in opens.items()}
    # day-level context: raw-candidate order (base levels only = the base market's candidates), TT bias, Mon-Wed range
    first_dir, seen = {}, collections.defaultdict(list)
    for z in sorted(C, key=lambda z: (z["i"], -z["dir"])):
        if not (set(z["sw"]) & BASE_NAMES):
            continue
        z["prior_dirs"] = list(seen[z["day"]])
        seen[z["day"]].append(z["dir"])
    for z in C:
        z.setdefault("prior_dirs", None)
    # TTrades daily bias: previous day's close vs the day before's high/low (+ wick rule); neutral once PDH/PDL is hit
    tt = {}
    for k in range(2, len(M.days)):
        x1, x0 = M.ctx[k - 1], M.ctx[k]
        if "pdh" not in x1 or "pdh" not in x0:
            continue
        H2, L2 = x1["pdh"], x1["pdl"]
        s1, e1 = M.days[k - 1][1], M.days[k - 1][2]
        C1, H1, L1 = float(c[e1 - 1]), float(h[s1:e1].max()), float(l[s1:e1].min())
        b = 0
        if C1 > H2:
            b = 1
        elif C1 < L2:
            b = -1
        elif L1 < L2 and C1 > L2:
            b = 1
        elif H1 > H2 and C1 < H2:
            b = -1
        tt[k] = (b, H1, L1, (H1 + L1) / 2)
    # Mon-Wed range per week, first break on Thu/Fri
    wk_days = collections.defaultdict(list)
    for k, (d, s, e) in enumerate(M.days):
        wk_days[int(M.week_id[s])].append(k)
    mw = {}
    for w, ks in wk_days.items():
        mon_wed = [k for k in ks if M.ctx[k]["dow"] <= 2]
        late = [k for k in ks if M.ctx[k]["dow"] >= 3]
        if len(mon_wed) < 2 or not late:
            continue
        H = max(float(h[M.days[k][1]:M.days[k][2]].max()) for k in mon_wed)
        Lw = min(float(l[M.days[k][1]:M.days[k][2]].min()) for k in mon_wed)
        a = M.days[late[0]][1]; zend = M.days[late[-1]][2]
        up = np.flatnonzero(h[a:zend] > H); dn = np.flatnonzero(l[a:zend] < Lw)
        fu = a + int(up[0]) if len(up) else 10 ** 12
        fd = a + int(dn[0]) if len(dn) else 10 ** 12
        for k in late:
            mw[k] = (fu, fd)
    for z in C:
        k, i = z["k"], z["i"]
        s = M.days[k][1]
        if k in tt:
            b, H1, L1, mid = tt[k]
            hit_h = float(h[s:i + 1].max()) >= H1
            hit_l = float(l[s:i + 1].min()) <= L1
            if (b == 1 and hit_h) or (b == -1 and hit_l):
                b = 0
            z["tt_bias"] = b
            z["pd_mid"] = 1 if M.ctx[k]["open18"] > mid else -1
        else:
            z["tt_bias"], z["pd_mid"] = 0, 0
        if k in mw:
            fu, fd = mw[k]
            brk = 0
            if min(fu, fd) <= i:
                brk = 1 if fu < fd else -1
            z["mw_break"] = brk
        else:
            z["mw_break"] = None
        ee = z["ext_i"]
        z["wm_ext"] = int(M.ctx[M.day_of[ee]]["dow"]) * 1440 + int((M.mod[ee] - 1080) % 1440)
    return C


# ------------------------------------------------------------------------------------------------ variant -> filter / run
WINS = {
    "day": [(120, 930)],
    "london": [(120, 300)],
    "ny_am": [(570, 690)],
    "ny_830_11": [(510, 660)],
    "ny_both": [(570, 690), (810, 930)],
    "lon_nyam": [(120, 300), (570, 690)],
    "lon_ny": [(120, 300), (570, 690), (810, 930)],
    "lon_ny830": [(120, 300), (510, 690), (810, 930)],
    "no_lunch": [(120, 720), (810, 930)],
    "no_lunch1130": [(120, 690), (810, 930)],
    "no_lon_lunch": [(120, 300), (420, 720), (810, 930)],
    "no_pm": [(120, 720)],
}
WM = lambda dow, hh, mm: dow * 1440 + ((hh * 60 + mm - 1080) % 1440)    # trading-day weekday (0 = Mon, starts Sun 18:00)
HOW_WIN = {
    "tue03_wed1130": (WM(1, 3, 0), WM(2, 11, 30)),      # lit.in_how_window
    "mon18_wed1130": (WM(1, 18, 0), WM(2, 11, 30)),
    "tue02_wed0930": (WM(1, 2, 0), WM(2, 9, 30)),
    "tue03_wed12": (WM(1, 3, 0), WM(2, 12, 0)),
    "mon18_wed12": (WM(1, 18, 0), WM(2, 12, 0)),
}

LIT_A = dict(names=None, win="day", disp=1.0, depth=0.5, classes=("pd", "pw", "pm"), min_rr=1.5, max_rr=5.0, stop_buf=2.0,
             min_stop=8.0, max_stop=80.0, be_r=1.0, entry="ref", wait=12, max_per_day=1)


def _po3_ok(z, anchor, cap, risk):
    """Long: the sweep extreme is below the open and the (limit) entry is at most cap*R above it. Mirror for shorts.
    An open that does not exist yet at the trigger (e.g. 09:30 for a London trade) passes."""
    ov = z["opens"].get(anchor)
    if ov is None:
        return None
    if not z["ext_d"] < ov:
        return False
    if cap is None:
        return True
    return z["ref_d"] - ov <= cap * risk


def qualifies(z, v, names):
    """lit_A's entry filter with a configurable sweep set (depth measured from the nearest swept level of that set)."""
    if not any(a <= z["mod"] < b for a, b in WINS[v["win"]]):
        return False
    sw = {nm: x for nm, x in z["sw"].items() if nm in names}
    if v.get("trap_n") is not None:
        sw = {nm: x for nm, x in sw.items() if x[1] <= v["trap_n"]}
    if not sw:
        return False
    if z["disp"] < v["disp"]:
        return False
    near = max(x[0] for x in sw.values())
    if (near - z["ext_d"]) / max(z["atr_ext"], 1e-9) < v["depth"]:
        return False
    return True


def h4_qualifies(z, v):
    a, b = v["h4rev"]
    if not (a <= z["mod"] < b):
        return False
    return any(nm.startswith("h4_610") for nm in z["sw"])


def build(v):
    """Variant dict -> (cfg for run_s). Keys on top of LIT_A:
      names / add_names / drop_names    sweep set (default: every base level, as lit_A)
      trap_n                            close back beyond the level within n bars of its breach
      win                               entry window set (WINS)
      po3 (anchor, cap R, mode)         mode "filter" or a size multiplier for trades that fail it
      h4rev (from, to)                  also take the IET 10:00 reversal (06:00-10:00 4H candle swept), target its other end
      how (window, mult_out)            size multiplier outside the high/low-of-week window
      how_dir                           a window sweep that makes a new weekly extreme sets the direction for the rest of the week
      mw (mode)                         Thu/Fri: continuation of the Mon-Wed range break only ("filter") or size 0.5 against it
      fri                               Friday size multiplier (0 = skip)
      bias (kind, mode)                 kind first_sweep | opp_off | tt | pd_mid; mode "filter" or a size multiplier against it
      max_per_day, one_dir              per-day limits
      flat_am                           AM entries (before 12:00) flat by this minute"""
    v = {**LIT_A, **v}
    names = set(v["names"]) if v.get("names") is not None else set(BASE_NAMES)
    names |= set(v.get("add_names") or ())
    names -= set(v.get("drop_names") or ())
    v["_names"] = names
    return v


def size_mult(z, v, wk_state):
    m = 1.0
    risk = z["ref_d"] - (z["ext_d"] - v["stop_buf"])
    if v.get("po3"):
        anchor, cap, mode = v["po3"]
        ok = _po3_ok(z, anchor, cap, risk)
        if ok is False and mode != "filter":
            m *= mode
    if v.get("how"):
        wn, mo = v["how"]
        a, b = HOW_WIN[wn]
        if not (a <= z["wm_ext"] < b):
            m *= mo
    if v.get("mw") and v["mw"] != "filter" and z.get("mw_break") and z["mw_break"] != z["dir"]:
        m *= v["mw"]
    if v.get("fri") is not None and z["dow"] == 4:
        m *= v["fri"]
    if v.get("bias"):
        kind, mode = v["bias"]
        if mode != "filter" and _bias_against(z, kind):
            m *= mode
    if v.get("tt_boost") and z["tt_bias"] == z["dir"]:
        m *= v["tt_boost"]
    return m


def _bias_against(z, kind):
    if kind == "first_sweep":
        p = z.get("prior_dirs")
        return bool(p) and p[0] != z["dir"]
    if kind == "opp_off":
        p = z.get("prior_dirs")
        return bool(p) and (-z["dir"]) in p
    if kind == "tt":
        return z["tt_bias"] == -z["dir"]
    if kind == "tt_strict":
        return z["tt_bias"] != z["dir"]
    if kind == "pd_mid":
        return z["pd_mid"] == -z["dir"]
    if kind == "pd_mid_rev":
        return z["pd_mid"] == z["dir"]
    raise KeyError(kind)


def hard_filter(z, v, wk_state):
    risk = z["ref_d"] - (z["ext_d"] - v["stop_buf"])
    if v.get("po3") and v["po3"][2] == "filter":
        if _po3_ok(z, v["po3"][0], v["po3"][1], risk) is False:
            return False
    if v.get("mw") == "filter" and z.get("mw_break") and z["mw_break"] != z["dir"]:
        return False
    if v.get("fri") == 0 and z["dow"] == 4:
        return False
    if v.get("bias") and v["bias"][1] == "filter" and _bias_against(z, v["bias"][0]):
        return False
    if v.get("how_dir"):
        w = wk_state.get(z["week"])
        if w is not None and w != z["dir"]:
            return False
    return True


def run_s(M, C, v, sessions):
    """lit.run with per-day / per-week state. Reproduces lit.run exactly for lit_A (checked in selftest())."""
    v = build(v)
    names = v["_names"]
    sset = set(sessions)
    out, busy, per_day, day_dir = [], -1, collections.Counter(), {}
    wk_state = {}
    hw = HOW_WIN["tue03_wed1130"]
    for z in C:
        if z["day"] not in sset:
            continue
        # how_direction: the first window sweep that makes a new weekly extreme sets the week's direction (any raw setup)
        if v.get("how_dir") and z["week"] not in wk_state and z["wk_ext"] and hw[0] <= z["wm_ext"] < hw[1] \
                and z["entry_i"] > busy and set(z["sw"]) & BASE_NAMES:
            wk_state[z["week"]] = z["dir"]
        if z["entry_i"] <= busy or per_day[z["day"]] >= v["max_per_day"]:
            continue
        if v.get("one_dir") and z["day"] in day_dir and z["dir"] != day_dir[z["day"]]:
            continue
        is_h4 = False
        if not qualifies(z, v, names):
            if v.get("h4rev") and h4_qualifies(z, v):
                is_h4 = True
            else:
                continue
        if not hard_filter(z, v, wk_state):
            continue
        buf = v["stop_buf"]
        ep = lit.entry_price(z, v["entry"], buf)
        risk = ep - (z["ext_d"] - buf)
        if not (v["min_stop"] <= risk <= v["max_stop"]):
            continue
        sh = z["entry_d"] - ep
        zz = {**z, "targets": {k: [x + sh for x in xs] for k, xs in z["targets"].items()}}
        classes = ("x_h4",) + tuple(v["classes"]) if is_h4 else v["classes"]
        tp = lit.pick_target(zz, risk, classes, v["min_rr"], v["max_rr"], None, None)
        if tp is None:
            continue
        flat = 955
        if v.get("flat_am") and z["mod"] < 720:
            flat = v["flat_am"]
        t = lit.simulate(M, z, tp, buf, v["be_r"], None, 0.0, flat_mod=flat, entry_mode=v["entry"], wait=v["wait"])
        if t is None:
            continue
        m = size_mult(z, v, wk_state)
        if m != 1.0:
            t = scale(t, m)
            if t is None:
                continue
        t["setup"] = "h4rev" if is_h4 else "lit"
        out.append(t); busy = t["exit_i"]; per_day[z["day"]] += 1; day_dir.setdefault(z["day"], z["dir"])
    return out


def scale(t, m):
    q0 = t["qty"]
    q = max(1, int(q0 * m + 1e-9)) if m < 1 else min(lit.MAX_MICROS, int(q0 * m + 1e-9))
    if m <= 0:
        return None
    f = q / q0
    per = (t["pnl"] + lit.COMM * q0) / q0
    x = dict(t)
    x.update(qty=q, pnl=round(per * q - lit.COMM * q, 2), risk_usd=round(t["risk_usd"] * f, 2), half=f < 1, mult=round(f, 3),
             low=round(t["low"] * f, 2))
    return x


# ------------------------------------------------------------------------------------------------ scoring
KEYS = ("n", "tpw", "wk2", "win", "pf", "net", "per_month", "dd", "p10", "f10", "p20", "f20", "dec10", "pass_med", "b2b")


def pass_rate(days, horizon=60):
    plan = PLANS["builder_50k"]
    pn = [d["pnl"] for d in days]; lo = [d["low"] for d in days]
    p = f = 0
    for i in range(len(days)):
        r = simulate_eval(pn[i:i + horizon], plan, lo[i:i + horizon])["result"]
        p += r == "PASS"; f += r == "FAIL"
    return round(100 * p / (p + f), 1) if p + f else None


def score_all(T):
    out = {}
    for nm, sess, span in (("h1", S_H1, "2026"), ("h2", S_H2, "2026"), ("y26", S26, "2026"), ("ref", S_REF, "2021-25")):
        ss = set(sess)
        TT = [t for t in T if t["day"] in ss]
        S = rl.score(TT, sess)
        s = S["spans"][span]
        o = {k: s.get(k) for k in KEYS}
        o["pass_rate"] = pass_rate(S["days"]) if s.get("n") else None
        out[nm] = o
    return out


def fmt(s):
    if not s.get("n"):
        return "no trades"
    return (f"n={s['n']} tpw={s['tpw']} wk2={s['wk2']}% win={s['win']}% PF={s['pf']} net={s['net']:+,} (${s['per_month']:,}/mo) "
            f"DD={s['dd']:,} 2w {s['p10']}/{s['f10']} 1m {s['p20']}/{s['f20']} passrate {s['pass_rate']}% med {s['pass_med']}")


# ------------------------------------------------------------------------------------------------ data
def load_all():
    M = SessMarket()
    C = lit.candidates(M)
    for z in C:
        z["atr_ext"] = float(M.atr[z["ext_i"]])
        z["week"] = int(M.week_id[z["ext_i"]])
    annotate(M, C)
    return M, C


def selftest(M, C):
    """lit_A through run_s on the extended market must equal lit.run on the base market."""
    M0, C0 = R.market()
    T0 = lit.run(M0, C0, R.make(**R.CAND["A"]), SESS_ALL)
    T1 = run_s(M, C, {}, SESS_ALL)
    k0 = [(t["day"], t["entry_t"], t["pnl"]) for t in T0]
    k1 = [(t["day"], t["entry_t"], t["pnl"]) for t in T1]
    print("selftest lit_A:", len(k0), len(k1), "identical" if k0 == k1 else "DIFFERENT", flush=True)
    if k0 != k1:
        a, b = set(k0), set(k1)
        print("  only base:", sorted(a - b)[:5], " only new:", sorted(b - a)[:5])
    return k0 == k1


# ------------------------------------------------------------------------------------------------ the search
def stage1():
    """One change at a time on top of lit_A."""
    V = collections.OrderedDict()
    V["lit_A"] = ("lit_A as is (all levels, 02:00-15:30, 1 trade/day)", {})
    # -- which box gets swept / new box definitions
    V["sw_add_asia18_02"] = ("+ Asia box 18:00-02:00 (P1)", dict(add_names=X("asia18_02")))
    V["sw_add_asia19_03"] = ("+ Asia box 19:00-03:00 (P2)", dict(add_names=X("asia19_03")))
    V["sw_add_asia20_04"] = ("+ Asia box 20:00-04:00 (P3)", dict(add_names=X("asia20_04")))
    V["sw_add_asia18_01"] = ("+ Reim Asia 18:05-01:00", dict(add_names=X("asia18_01")))
    V["sw_add_all_asiaX"] = ("+ all 4 new Asia boxes", dict(add_names=X("asia18_02", "asia19_03", "asia20_04", "asia18_01")))
    V["sw_add_lon15"] = ("+ London 01:00-05:00", dict(add_names=X("lon15")))
    V["sw_add_ny8_830"] = ("+ NY 08:00-08:30", dict(add_names=X("ny8_830")))
    V["sw_add_h4"] = ("+ 06:00-10:00 4H candle high/low as a level", dict(add_names=X("h4_610")))
    V["sw_add_reim_coded"] = ("+ Reim boxes as coded (+60 min in summer from 2023-11)", dict(add_names=X("rc_asia", "rc_lon", "rc_ny")))
    V["sw_drop_nytrap"] = ("- NY 08:30/09:30/09:30-10:30 and premarket boxes", dict(drop_names=NY_TRAP_BAD))
    V["sw_drop_ny_all"] = ("- every NY box and premarket", dict(drop_names=NY_TRAP_BAD | X("ny89")))
    V["sw_only_sessions"] = ("only session boxes (no daily, gap, build-up sweeps)", dict(names=SESSION_NAMES))
    V["sw_only_asia_lon"] = ("only Asia + London boxes (all definitions)", dict(names=X("asia20", "asia18", "asia19", "lon25", "lon34", "lon23", "asia18_02", "asia19_03", "asia20_04", "asia18_01", "lon15")))
    V["sw_reim_intended"] = ("Reim intended boxes only (Asia 18:05-01, Lon 03-04, NY 08-09) + PDH/PWH/PMH", dict(names=X("asia18_01", "lon34", "ny89") | {"pdh", "pdl", "pwh", "pwl", "pmh", "pml"}))
    V["sw_reim_coded"] = ("Reim boxes as coded only + PDH/PWH/PMH", dict(names=X("rc_asia", "rc_lon", "rc_ny") | {"pdh", "pdl", "pwh", "pwl", "pmh", "pml"}))
    V["sw_no_session"] = ("no session boxes (daily, gap, build-ups only)", dict(names=BASE_NAMES - SESSION_NAMES))
    # -- trap close-back
    for n in (0, 1, 2, 3):
        V[f"trap{n}"] = (f"sweep counts only with a close back inside within {n} bars of the breach", dict(trap_n=n))
    # -- entry windows
    for w in ("london", "ny_am", "ny_both", "lon_nyam", "lon_ny", "lon_ny830", "no_lunch", "no_lunch1130", "no_lon_lunch", "no_pm"):
        V[f"win_{w}"] = (f"entry window {w}: {WINS[w]}", dict(win=w))
    # -- opens / PO3 (filter)
    for an, cap in (("00", None), ("00", 0.5), ("00", 0.0), ("06", None), ("0730", None), ("0830", None), ("0930", None),
                    ("1000", None), ("18", None), ("22", None), ("06", 0.5)):
        V[f"po3_{an}_{cap}"] = (f"PO3 filter: extreme beyond the {an} open, entry within {cap}R of it", dict(po3=(an, cap, "filter")))
    # -- IET 10:00 4H reversal (added to lit_A)
    for a, b in ((600, 660), (590, 690), (600, 630)):
        V[f"h4rev_{a}_{b}"] = (f"+ IET 06-10 4H candle swept {a // 60:02d}:{a % 60:02d}-{b // 60:02d}:{b % 60:02d}, target its other end", dict(h4rev=(a, b)))
    # -- high/low-of-week
    for wn in HOW_WIN:
        V[f"how_{wn}_05"] = (f"size 0.5 outside the HOW window {wn}", dict(how=(wn, 0.5)))
    V["how_dir"] = ("HOW direction: a window sweep making a new weekly extreme sets the week's side", dict(how_dir=True))
    V["mw_filter"] = ("Thu/Fri: only trades in the direction that broke the Mon-Wed range", dict(mw="filter"))
    V["mw_half"] = ("Thu/Fri: half size against the Mon-Wed range break", dict(mw=0.5))
    V["fri_half"] = ("Friday half size", dict(fri=0.5))
    V["fri_skip"] = ("no Friday trades", dict(fri=0))
    # -- one direction / bias
    for kind in ("first_sweep", "opp_off", "tt", "pd_mid"):
        V[f"bias_{kind}_f"] = (f"bias {kind} as a filter", dict(bias=(kind, "filter")))
        V[f"bias_{kind}_h"] = (f"bias {kind}: half size against it", dict(bias=(kind, 0.5)))
    # -- trades per day / AM time stop
    V["perday2"] = ("max 2 trades/day", dict(max_per_day=2))
    V["perday2_onedir"] = ("max 2 trades/day, same direction only", dict(max_per_day=2, one_dir=True))
    V["flat_am_1130"] = ("AM entries flat by 11:30", dict(flat_am=690))
    V["flat_am_1200"] = ("AM entries flat by 12:00", dict(flat_am=720))
    return V


def evaluate(M, C, V, res=None):
    res = res if res is not None else {}
    for name, (desc, v) in V.items():
        if name in res:
            continue
        T = run_s(M, C, v, SESS_ALL)
        sc = score_all(T)
        res[name] = {"desc": desc, "params": _ser(v), **sc}
        print(f"{name:22s} H1[{short(sc['h1'])}] H2[{short(sc['h2'])}] 26[{short(sc['y26'])}] ref[{short(sc['ref'])}]", flush=True)
    return res


def short(s):
    if not s.get("n"):
        return "0"
    return f"n{s['n']} {s['tpw']}/wk PF{s['pf']} {s['net']:+,} DD{s['dd']:,}"


def _ser(v):
    return {k: (sorted(x) if isinstance(x, (set, frozenset)) else list(x) if isinstance(x, tuple) else x) for k, x in v.items()}


def main_search():
    M, C = load_all()
    assert selftest(M, C)
    res = {}
    if os.path.exists(OUT):
        res = json.load(open(OUT))
    V = stage1()
    evaluate(M, C, V, res)
    json.dump(res, open(OUT, "w"), indent=1)
    return M, C, res


if __name__ == "__main__":
    cmd = sys.argv[1] if len(sys.argv) > 1 else "search"
    if cmd == "search":
        main_search()
    elif cmd == "selftest":
        M, C = load_all(); selftest(M, C)


# ------------------------------------------------------------------------------------------------ stage 2: around the H1 winner
DAILY_NAMES = {"pdh", "pdl", "pwh", "pwl", "pmh", "pml"}
REIM = X("asia18_01", "lon34", "ny89") | DAILY_NAMES


def stage2():
    """Neighbours of the stage-1 H1 winner (Reim's intended boxes + previous day/week/month levels), then layering."""
    V = collections.OrderedDict()
    V["r_no_daily"] = ("Reim boxes only (no PDH/PWH/PMH sweeps)", dict(names=X("asia18_01", "lon34", "ny89")))
    V["r_plus_bu"] = ("Reim boxes + daily + build-ups", dict(names=REIM | {"bu_l", "bu_h"}))
    V["r_plus_gap"] = ("Reim boxes + daily + NWOG/NDOG", dict(names=REIM | {"nwog", "ndog"}))
    V["r_asia20"] = ("Reim set with Asia 20:00-00:00 instead of 18:05-01:00", dict(names=X("asia20", "lon34", "ny89") | DAILY_NAMES))
    V["r_asia18_02"] = ("Reim set with Asia 18:00-02:00 instead", dict(names=X("asia18_02", "lon34", "ny89") | DAILY_NAMES))
    V["r_no_ny"] = ("Reim set without the NY 08-09 box", dict(names=X("asia18_01", "lon34") | DAILY_NAMES))
    V["r_lon25"] = ("Reim set with London 02:00-05:00 instead of 03-04", dict(names=X("asia18_01", "lon25", "ny89") | DAILY_NAMES))
    V["r_plus_ny8_830"] = ("Reim set + NY 08:00-08:30", dict(names=REIM | X("ny8_830")))
    # layering (each alone on the Reim set)
    V["r_how05"] = ("Reim set + size 0.5 outside the HOW window", dict(names=REIM, how=("tue03_wed1130", 0.5)))
    V["r_fri05"] = ("Reim set + Friday half size", dict(names=REIM, fri=0.5))
    V["r_po3_18"] = ("Reim set + PO3 18:00 open filter", dict(names=REIM, po3=("18", None, "filter")))
    V["r_po3_00"] = ("Reim set + PO3 midnight open filter", dict(names=REIM, po3=("00", None, "filter")))
    V["r_po3_00_h"] = ("Reim set + half size when not beyond the midnight open", dict(names=REIM, po3=("00", None, 0.5)))
    V["r_tt_f"] = ("Reim set + TTrades PDH/PDL bias filter", dict(names=REIM, bias=("tt", "filter")))
    V["r_trap2"] = ("Reim set + close back within 2 bars", dict(names=REIM, trap_n=2))
    V["r_mw_f"] = ("Reim set + Mon-Wed break filter on Thu/Fri", dict(names=REIM, mw="filter"))
    V["r_perday2_od"] = ("Reim set + max 2/day same direction", dict(names=REIM, max_per_day=2, one_dir=True))
    V["r_win_lon_ny830"] = ("Reim set + entries only London + NY 08:30-11:30 + PM", dict(names=REIM, win="lon_ny830"))
    V["r_win_no_lunch"] = ("Reim set + no entries 12:00-13:30", dict(names=REIM, win="no_lunch"))
    return V


B1 = X("asia20", "lon34", "ny89") | DAILY_NAMES          # stage-2 pick: ICT Asia 20-00 + Reim London/NY trap hours + PD/PW/PM
B2 = X("asia18_02", "lon34", "ny89") | DAILY_NAMES       # stage-2 H1-best Asia (18-02), weaker in H2 and 2021-25


def stage3():
    """Combinations on the two stage-2 bases (B1 = Asia 20-00, B2 = Asia 18-02, both with London 03-04, NY 08-09, PD/PW/PM)."""
    V = collections.OrderedDict()
    V["b1_asia19"] = ("B1 with Asia 19:00-00:00", dict(names=X("asia19", "lon34", "ny89") | DAILY_NAMES))
    V["b1_asia18"] = ("B1 with Asia 18:00-00:00", dict(names=X("asia18", "lon34", "ny89") | DAILY_NAMES))
    V["b1_two_asia"] = ("B1 + Asia 18:00-02:00 as well", dict(names=B1 | X("asia18_02")))
    V["b1_ny8_830"] = ("B1 + NY 08:00-08:30 box", dict(names=B1 | X("ny8_830")))
    V["b1_mw_f"] = ("B1 + Mon-Wed break filter Thu/Fri", dict(names=B1, mw="filter"))
    V["b1_fri05"] = ("B1 + Friday half size", dict(names=B1, fri=0.5))
    V["b1_how05"] = ("B1 + size 0.5 outside the HOW window", dict(names=B1, how=("tue03_wed1130", 0.5)))
    V["b1_perday2_od"] = ("B1 + max 2/day, same direction", dict(names=B1, max_per_day=2, one_dir=True))
    V["b1_ny8_830_mw_f"] = ("B1 + NY 08-08:30 + Mon-Wed break filter", dict(names=B1 | X("ny8_830"), mw="filter"))
    V["b1_ny8_830_od2"] = ("B1 + NY 08-08:30 + max 2/day same direction", dict(names=B1 | X("ny8_830"), max_per_day=2, one_dir=True))
    V["b1_ny8_830_mw_f_od2"] = ("B1 + NY 08-08:30 + Mon-Wed filter + max 2/day same dir",
                                 dict(names=B1 | X("ny8_830"), mw="filter", max_per_day=2, one_dir=True))
    V["b1_ny8_830_fri05"] = ("B1 + NY 08-08:30 + Friday half", dict(names=B1 | X("ny8_830"), fri=0.5))
    V["b2_ny8_830"] = ("B2 + NY 08-08:30", dict(names=B2 | X("ny8_830")))
    V["b2_mw_f"] = ("B2 + Mon-Wed break filter", dict(names=B2, mw="filter"))
    V["b2_ny8_830_mw_f_od2"] = ("B2 + NY 08-08:30 + Mon-Wed filter + max 2/day same dir",
                                 dict(names=B2 | X("ny8_830"), mw="filter", max_per_day=2, one_dir=True))
    return V


def run_stage(fn):
    M, C = load_all()
    res = json.load(open(OUT)) if os.path.exists(OUT) else {}
    evaluate(M, C, fn(), res)
    json.dump(res, open(OUT, "w"), indent=1)
    return M, C, res


if __name__ == "__main__" and len(sys.argv) > 1 and sys.argv[1] in ("stage2", "stage3"):
    run_stage({"stage2": stage2, "stage3": stage3}[sys.argv[1]])


B1N = B1 | X("ny8_830")      # stage-3 pick: + the NY 08:00-08:30 box


def stage4():
    V = collections.OrderedDict()
    V["b1n_mw_f_fri05"] = ("B1 + NY 08-08:30 + Mon-Wed filter + Friday half", dict(names=B1N, mw="filter", fri=0.5))
    V["b1n_how05"] = ("B1 + NY 08-08:30 + size 0.5 outside HOW window", dict(names=B1N, how=("tue03_wed1130", 0.5)))
    return V


ROBUST = {"disp0.8": dict(disp=0.8), "disp1.2": dict(disp=1.2), "depth0.3": dict(depth=0.3), "depth0.75": dict(depth=0.75),
          "maxstop60": dict(max_stop=60.0), "maxstop100": dict(max_stop=100.0), "wait6": dict(wait=6), "wait24": dict(wait=24),
          "minrr2": dict(min_rr=2.0), "bank4": dict(max_rr=4.0), "bank6": dict(max_rr=6.0), "be1.5": dict(be_r=1.5),
          "buf1": dict(stop_buf=1.0), "buf4": dict(stop_buf=4.0)}
PICKS = {
    "b1_ny8_830": dict(names=B1N),
    "b1_ny8_830_mw_f": dict(names=B1N, mw="filter"),
    "b1_ny8_830_mw_f_od2": dict(names=B1N, mw="filter", max_per_day=2, one_dir=True),
}


def robust():
    """Neighbours, +2 ticks slippage, long/short and month by month for the picks (not used for selection)."""
    M, C = load_all()
    rep = {}
    for nm, v in PICKS.items():
        T = run_s(M, C, v, SESS_ALL)
        r = {"nb": {}}
        for k, tw in ROBUST.items():
            sc = score_all(run_s(M, C, {**v, **tw}, SESS_ALL))
            r["nb"][k] = {p: {q: sc[p][q] for q in ("n", "tpw", "pf", "net", "dd")} for p in sc}
            print(f"{nm:20s} {k:10s} H1[{short(sc['h1'])}] H2[{short(sc['h2'])}] ref[{short(sc['ref'])}]", flush=True)
        slip = [dict(t, pnl=round(t["pnl"] - 2 * lit.TICK * lit.PV * t["qty"], 2)) for t in T]
        sc = score_all(slip)
        r["slip2"] = {p: {q: sc[p][q] for q in ("n", "pf", "net", "dd")} for p in sc}
        print(f"{nm:20s} +2 ticks   H1[{short(sc['h1'])}] H2[{short(sc['h2'])}] ref[{short(sc['ref'])}]")
        for d, lab in ((1, "long"), (-1, "short")):
            sc = score_all([t for t in T if t["dir"] == d])
            r[lab] = {p: {q: sc[p][q] for q in ("n", "pf", "net")} for p in sc}
            print(f"{nm:20s} {lab:9s} H1[{short(sc['h1'])}] H2[{short(sc['h2'])}] ref[{short(sc['ref'])}]")
        mo = collections.defaultdict(float)
        for t in T:
            if t["day"] >= "2026":
                mo[t["day"][:7]] += t["pnl"]
        r["months_2026"] = {k: round(x) for k, x in sorted(mo.items())}
        yrs = collections.defaultdict(float)
        for t in T:
            yrs[t["day"][:4]] += t["pnl"]
        r["years"] = {k: round(x) for k, x in sorted(yrs.items())}
        r["setups"] = collections.Counter(t["exit"] for t in T if t["day"] >= "2026")
        print(nm, "2026 months", r["months_2026"], "years", r["years"], "exits26", dict(r["setups"]))
        rep[nm] = r
    json.dump(rep, open(OUT.replace(".json", "_robust.json"), "w"), indent=1, default=dict)


if __name__ == "__main__" and len(sys.argv) > 1 and sys.argv[1] in ("stage4", "robust"):
    run_stage(stage4) if sys.argv[1] == "stage4" else robust()


SAVE = {
    "lit_sessions_A": ("b1_ny8_830", "LIT sessions A: Asia 20-00 + London 03-04 + NY 08-09 + NY 08-08:30 + PD/PW/PM sweeps", "promising",
                       "Only these boxes and the previous day/week/month levels count as swept liquidity (lit_A otherwise unchanged). "
                       "Better than lit_A in both halves of 2026 and every neighbour holds; 2021-25 reference PF 1.17 (2025 loses)."),
    "lit_sessions_B": ("b1_ny8_830_mw_f", "LIT sessions B: A + Thu/Fri only in the direction that broke the Mon-Wed range", "promising",
                       "A plus the ICT Mon-Wed range rule on Thursday/Friday. Better than A in both 2026 halves; 1.99 trades/week."),
    "lit_sessions_B2": ("b1_ny8_830_mw_f_od2", "LIT sessions B2: B + a 2nd trade a day in the same direction", "info",
                        "B with max 2 trades/day, same direction only: keeps 2.18/week but H1 is weaker than B."),
    "lit_sessions_C": ("b1n_mw_f_fri05", "LIT sessions C: B + Friday half size", "info",
                       "Best 2026 H1 of the B1 family, but a calendar rule; 1.99/week."),
    "lit_sessions_D": ("b2_ny8_830_mw_f_od2", "LIT sessions D: Asia 18-02 version of B2 (the strict H1 winner)", "rejected",
                       "Highest 2026 H1 of every variant, but H2 is worse than A/B and 2021-25 loses (PF 0.95): picked by H1 noise."),
}


def save_best():
    M, C = load_all()
    res = json.load(open(OUT))
    for rid, (vn, title, status, verdict) in SAVE.items():
        v = res[vn]["params"]
        vv = dict(v)
        if "names" in vv and vv["names"] is not None:
            vv["names"] = set(vv["names"])
        T = run_s(M, C, vv, SESS_ALL)
        S = R.score(T, mc=True)
        params = {**_ser(build(vv)), "variant": vn}
        params.pop("_names", None)
        params["sweep_names"] = sorted(build(vv)["_names"])
        rl.save(rid, title, "other", "LIT sessions and timing: which boxes, windows, opens and day rules make LIT pay in 2026?",
                params=params, trades=[{k: x for k, x in t.items() if k != "setup"} for t in T], scored=S, status=status,
                verdict=verdict, writeup=None, tags=["lit", "lit_sessions"],
                notes="tools/lit_sessions.py; picked on 2026 Jan-Jun, checked on Jul-Oct; 2021-25 reference only; size $800 up to a "
                      "20-pt stop then 800x20/stop, MNQ, max 40 micros, $1.40/micro + 1 tick slippage")
        print(rid, rl.line(S, "2026"))


def table():
    res = json.load(open(OUT))
    rows = []
    for nm, r in res.items():
        f = lambda s: f"{s['n']} / {s['tpw']} / {s['pf']} / {s['net']:+,}" if s.get("n") else "0"
        rows.append(f"| `{nm}` | {r['desc']} | {f(r['h1'])} | {f(r['h2'])} | {f(r['y26'])} | {r['y26']['dd']:,} | {f(r['ref'])} |")
    print("\n".join(rows))


if __name__ == "__main__" and len(sys.argv) > 1 and sys.argv[1] in ("save", "table", "full"):
    if sys.argv[1] == "save":
        save_best()
    elif sys.argv[1] == "table":
        table()
    else:
        res = json.load(open(OUT))
        for nm in sys.argv[2:]:
            print(nm)
            for p in ("h1", "h2", "y26", "ref"):
                print("  ", p, fmt(res[nm][p]), "dec10", res[nm][p].get("dec10"), "b2b", res[nm][p].get("b2b"))
