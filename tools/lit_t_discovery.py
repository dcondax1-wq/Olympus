"""LIT discovery: new LIT-only ideas nobody had tested yet, plus a walk-forward stability check (owner, 2026-10-18: "Remember
our strategy is LIT based nothing that goes outside, try every single one of these and go find more we haven't tested").

Wraps engine/lit.py (not edited) through tools/lit_tightstop.py (TS.tsim = the live LIT execution) on the live LIT settings
(live_model.json "lit" = lit_final + loss pack) with the live eval sizing ($800 up to a 25-pt stop, then 800x25/stop, weekly
stop, never more than 60% of the room to the MFFU max-loss floor = run lit_tight_eval_800_25_room60). Every idea defaults off,
and the defaults reproduce run lit_live trade for trade (120 trades in 2026) and the baseline eval numbers.

  1. trap      Smart-money trap ("a zone reacts, then fails", report 5.15/5.16): a LIT zone (a setup that passed the live
               filters) reacts by >= `react` ATR, then its sweep extreme breaks within `win` 5m bars. The trapped side's stops
               are gone, so trade the failure: a limit at the retest of the broken extreme (lvl "ext") or of the zone's CISD
               level (lvl "ref"), valid `wait` minutes, then the live 1m CISD confirmation; stop 1 tick beyond the reaction
               extreme; target the VIX band on the new side (>= 1.5R, banked at 8R). Only on days without a trade, or (flip)
               also as the 2nd trade when the day's LIT trade was that zone and it stopped out.
  2. deeper    Failed continuation into a deeper zone (report 7.2): after the day's LIT trade stopped out, one more LIT
               setup on the same side, only if its sweep extreme is beyond the first stop AND it swept a major level
               (`major`: "daily" = PDL/PWL/PML, "box" = also session boxes) - the deeper zone. size = multiplier.
  3. recross   ETM early recross of the operating candle (report 7.10, the missing part): the operating candle is the 5m
               candle that made the sweep extreme; "early" = a 1m close back above its body top (below for shorts) within
               `k` minutes of the extreme, seen by the trigger close. mode size: x hi early, x lo otherwise; mode skip: only
               early ones.
  4. cont      Multiple-inducement continuation into the HTF draw (report 6.8 + IET stacking): after a non-stop LIT trade,
               a 2nd same-side LIT setup with >= `idm` inducements, aimed at the nearest of the VIX band / PDH-PWH-PMH
               (lows for shorts) >= 1.5R. size = multiplier.
  5. tgt2      Second LIT trade only after a target hit: after the day's trade hit its target, one more LIT setup (side
               "any" / "same" / "opp"), live target rules. size = multiplier.
  6. mon_asia  Asia-box-only Mondays: on Monday a setup counts only when it swept an Asia box (set "asia") or an Asia box /
               Friday's high-low (set "asia_pd"); others skipped (the day stays free) or x size.
  7. lowvix    London-only on low-VIX days: when the prior VIX close < `vix`, entries after `end` (ET minute) are skipped
               (day stays free) or x size.
  WF           walk-forward: the 3 most sensitive lit_final parameters (lit_final critic neighbours: 1m confirmation bars,
               displacement, inducement distance) re-tuned every month on the prior 3 months (best net $ at the eval size),
               traded the next month; against the fixed lock.

  python tools/lit_t_discovery.py check   # defaults == run lit_live (120 trades 2026) and == the baseline eval numbers
  python tools/lit_t_discovery.py grid    # every variant -> research/lit/t_discovery_results.json
  python tools/lit_t_discovery.py wf      # walk-forward -> research/lit/t_discovery_wf.json
  python tools/lit_t_discovery.py save    # store the runs lit_u_discovery_* (rl.save, family other, tags lit, lit_untested, lit_discovery)
Pick on 2026 H1 (Jan 2 - Jun 30), check on 2026 H2 (Jul 1 - Oct 16); 2021-25 is a reference line (5m only, no 1m data).
1 CPU process. Paper research only.
"""
from __future__ import annotations

import collections
import copy
import itertools
import json
import os
import re
import sys

import numpy as np

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)
from engine import lit  # noqa: E402
from tools import lit_final as F  # noqa: E402
from tools import lit_tightstop as TS  # noqa: E402
from tools import lit_t_entries as TE  # noqa: E402  (TS.qty_of capped at 40 micros for size multipliers > 1; manage())
from tools import runlib as rl  # noqa: E402

OUT = os.path.join(ROOT, "research", "lit", "t_discovery_results.json")
OUT_WF = os.path.join(ROOT, "research", "lit", "t_discovery_wf.json")
SESS, SPAN = F.SESS, F.SPAN
PV, SLIP = lit.PV, lit.SLIP
LIVE = TS.LIVE
RULE, ROOM_K = TE.RULE, TE.ROOM_K

DDEF = {"trap": None, "deeper": None, "recross": None, "cont": None, "tgt2": None, "mon_asia": None, "lowvix": None,
        "ov": None}        # ov = {"YYYY-MM": {param overrides}} (walk-forward)


def P_of(P=None):
    return {**TS.P_of(), **DDEF, **(P or {})}


# ================================================================================================ helpers
def _tp(M, z, P, risk, classes=None):
    """Target distance from the planned limit (direction space) as the live run picks it (None = no trade)."""
    ep = min(float(z["ref_d"]), z["trig_c"])
    sh = z["entry_d"] - ep
    Pc = {**P, "classes": classes or P["classes"]}
    TT = {c: [x + sh for x in v] for c, v in lit.targets_x(M, z, Pc).items()}
    best = None
    for c in Pc["classes"]:
        for dist in TT.get(c, []):
            if dist >= P["min_rr"] * risk:
                if best is None or dist < best:
                    best = dist
                break
    if best is None:
        return None
    return min(best, P["max_rr"] * risk) if P["max_rr"] else best


def idm_count(z, P):
    dm, age, _ = P["idm_a"] or (1.0, 36, 1)
    return sum(1 for dd, aa in z["idm_a"] if dd <= dm and aa <= age)


def recross_min(M, B1, z):
    """Minutes from the sweep extreme to the first close back beyond the operating candle's body (the 5m candle that made the
    extreme), seen by the trigger close; None = not by then. 1m bars when the day has them, else 5m."""
    d = z["dir"]
    e5 = z["ext_i"]
    o5, c5 = (M.o, M.c) if d == 1 else (-M.o, -M.c)
    lvl = max(float(o5[e5]), float(c5[e5]))
    t_ext, t_trig = int(M.t[e5]), int(M.t[z["i"]]) + 300
    if B1 is not None and int(M.day_of[z["entry_i"]]) in B1.full:
        hi_d, lo_d, c_d, o_d = B1.dirs(d)
        a = int(np.searchsorted(B1.t, t_ext)); b = int(np.searchsorted(B1.t, t_trig))
        if b <= a:
            return None
        xe = a + int(np.argmin(lo_d[a:min(b, a + 5)]))          # the 1m bar of the extreme inside the operating candle
        for j in range(xe, b):
            if c_d[j] > lvl:
                return (int(B1.t[j]) + 60 - int(B1.t[xe])) / 60.0
        return None
    c_d = c5
    for j in range(e5, z["i"] + 1):
        if c_d[j] > lvl:
            return (int(M.t[j]) + 300 - t_ext) / 60.0
    return None


def exec_lim(M, B, e, s_day, t0, L, stop, tg_lvl, P, wait_min):
    """A limit at L (direction space of e) placed at t0, valid wait_min minutes; after the tap the live 1m CISD confirmation
    (cisd1m bars, 5m: //5) -> next open + 1 tick. Cancelled when the stop trades first or the target trades before the tap.
    Returns (fill bar, entry) or None."""
    hi_d, lo_d, c_d, o_d = B.dirs(e)
    k = int(np.searchsorted(B.t, t0))
    cis = P.get("cisd1m")
    if cis and B.secs == 300:
        cis = max(1, cis // 5)
    flat = P["flat_mod"]
    tapped = None
    while k < B.n:
        if B.day[k] != s_day or B.mod[k] >= flat or B.mod[k] >= 1080:
            return None
        if tapped is None and B.t[k] >= t0 + wait_min * 60:
            return None
        if lo_d[k] <= stop:
            return None
        if tapped is None and lo_d[k] <= L:
            tapped = k
        if tapped is None and hi_d[k] >= tg_lvl:
            return None
        if tapped is not None:
            if k - tapped > cis:
                return None
            lowk = tapped + int(np.argmin(lo_d[tapped:k + 1]))
            cz = lit._cisd_level(c_d, o_d, lowk)
            if cz is not None and k > lowk and c_d[k] > cz[0] and k + 1 < B.n and B.day[k + 1] == s_day:
                return k + 1, float(o_d[k + 1]) + SLIP
        k += 1
    return None


# ================================================================================================ idea 1: trap setups
def trap_setups(M, C, P, sset, B1, B5):
    X = P["trap"]
    names = set(P["sweep_names"]) if P.get("sweep_names") else None
    out, seen = [], set()
    for z in C:
        if z["day"] not in sset or not lit.setup_ok(z, P, names):
            continue
        key = (z["day"], z["dir"], z["ext_i"])
        if key in seen:
            continue
        seen.add(key)
        d, k = z["dir"], z["k"]
        x = M.ctx[k]
        if not x.get("vix_move"):
            continue
        s, e_ = x["s"], x["e"]
        hi_d = M.h if d == 1 else -M.l
        lo_d = M.l if d == 1 else -M.h
        ext = z["ext_d"]
        rh, f = ext, None
        for j in range(z["ext_i"], min(e_, z["i"] + 1 + X["win"])):
            if j > z["i"] and lo_d[j] < ext:
                f = j
                break
            rh = max(rh, float(hi_d[j]))
        if f is None or (rh - ext) < X["react"] * z["atr_ext"]:
            continue
        t0 = int(M.t[f]) + 300
        mod0 = int(M.mod[f]) + 5
        if not any(a <= mod0 < b for a, b in P["window"]):
            continue
        ee = -d                                           # the trade's direction
        L = -ext if X["lvl"] == "ext" else -float(z["ref_d"])
        stop = -rh - P["stop_buf"]
        if L - stop > P["max_stop"] or L - stop < P["min_stop"]:
            continue
        vt = x["open18"] * ee + P["vix_k"] * x["vix_move"]
        use1 = B1 is not None and k in B1.full
        out.append({"day": z["day"], "t": t0, "dir": ee, "k": k, "f": f, "L": L, "stop": stop, "vt": vt, "B": B1 if use1 else B5,
                    "zone_dir": d, "zone_ext": ext * d, "wait": X.get("wait", 30)})
    out.sort(key=lambda r: (r["t"], -r["dir"]))
    return out


# ================================================================================================ the run (live loop order)
def drun(P=None, sessions=SESS):
    P = P_of(P)
    sset = set(sessions)
    M, C = F.market(P["ref"], P["extra_boxes"])
    B5 = F.bars(M, "5m")
    B1 = F.bars(M, "1m") if P["tf"] == "1m" else None
    ev = [(int(M.t[z["entry_i"]]), 0, n, z) for n, z in enumerate(C) if z["day"] in sset]
    if P["trap"]:
        ev += [(s_["t"], 1, n, s_) for n, s_ in enumerate(trap_setups(M, C, P, sset, B1, B5))]
    ev.sort(key=lambda r: (r[0], r[1], r[2]))
    ov = P["ov"] or {}
    out, busy, per_day, first = [], -1, collections.Counter(), {}
    second_rules = [k for k in ("deeper", "cont", "tgt2") if P[k]]
    for _t, src, _n, z in ev:
        day = z["day"]
        Pz = {**P, **ov.get(day[:7], {})} if ov else P
        if src == 1:                                       # idea 1: trap setup
            ei5 = int(np.searchsorted(M.t, z["t"], side="right") - 1)
            if ei5 <= busy:
                continue
            if per_day[day] >= 1:
                t1 = first[day]
                if not (P["trap"].get("flip") and per_day[day] == 1 and t1["exit"] == "STOP" and t1["dir"] == z["zone_dir"]
                        and abs(t1["stop0_px"] - (z["zone_ext"] - P["stop_buf"] * z["zone_dir"])) < 0.01):
                    continue
            if Pz.get("monday") and lit.monday_block(M, {"k": z["k"], "i": z["f"], "dir": z["dir"]}):
                continue
            B = z["B"]
            s_day = z["k"]
            r = exec_lim(M, B, z["dir"], s_day, z["t"], z["L"], z["stop"], z["vt"], Pz, z["wait"])
            if r is None:
                continue
            fill, entry = r
            risk = entry - z["stop"]
            if not (Pz["min_stop"] <= risk <= Pz["max_stop"] + 8) or lit.qty_for(risk) < 1:
                continue
            tg = TE._target(entry, risk, z["vt"], False, Pz)
            if tg is None:
                continue
            t = TE.manage(M, B, z["dir"], s_day, fill, entry, z["stop"], tg, False, Pz)
            if t is None:
                continue
            t.update(day=day, how="trap", src="trap", x_m=float(P["trap"].get("size", 1.0)), stop0_px=t["stop_px"], swept=["trap"])
            busy = t["exit_i"]; per_day[day] += 1; first.setdefault(day, t)
            out.append(t)
            continue
        if z["entry_i"] <= busy:
            continue
        names = set(Pz["sweep_names"]) if Pz.get("sweep_names") else None
        rule2, classes, xm = None, None, 1.0
        if per_day[day] >= 1:
            if per_day[day] >= 2 or not second_rules:
                continue
            t1 = first[day]
            for rk in second_rules:
                X = P[rk]
                if rk == "deeper":
                    if t1["exit"] != "STOP" or t1["dir"] != z["dir"] or not (z["ext_d"] < t1["stop0_px"] * z["dir"]):
                        continue
                    maj = {"pd", "pw", "pm"} | ({"asia", "london", "pre", "ny", "x_ny"} if X["major"] == "box" else set())
                    if not (set(z["swept_cls"]) & maj):
                        continue
                elif rk == "cont":
                    if t1["exit"] == "STOP" or t1["dir"] != z["dir"] or idm_count(z, Pz) < X["idm"]:
                        continue
                elif rk == "tgt2":
                    if t1["exit"] != "TARGET":
                        continue
                    if X["side"] == "same" and t1["dir"] != z["dir"]:
                        continue
                    if X["side"] == "opp" and t1["dir"] == z["dir"]:
                        continue
                rule2 = rk; xm = float(X.get("size", 1.0))
                classes = ["vix", "pd", "pw", "pm"] if (rk == "cont" and X.get("htf", True)) else None
                break
            if rule2 is None:
                continue
        if not lit.setup_ok(z, Pz, names):
            continue
        if Pz.get("monday") and lit.monday_block(M, z):
            continue
        x = M.ctx[z["k"]]
        # idea 6: Asia-box-only Mondays
        if P["mon_asia"] and x["dow"] == 0:
            X = P["mon_asia"]
            ok = any(n_.startswith("asia") for n_ in z["swept"]) or (X["set"] == "asia_pd" and any(n_ in ("pdh", "pdl") for n_ in z["swept"]))
            if not ok:
                if X["mode"] == "skip":
                    continue
                xm *= X["x"]
        # idea 7: London-only on low-VIX days
        if P["lowvix"] and x.get("vix") is not None and x["vix"] < P["lowvix"]["vix"] and z["mod"] >= P["lowvix"]["end"]:
            if P["lowvix"]["mode"] == "skip":
                continue
            xm *= P["lowvix"]["x"]
        # idea 3: ETM early recross
        rc = None
        if P["recross"]:
            X = P["recross"]
            rc = recross_min(M, B1, z)
            early = rc is not None and rc <= X["k"]
            if X["mode"] == "skip" and not early:
                continue
            if X["mode"] == "size":
                xm *= X["hi"] if early else X["lo"]
        ep = min(float(z["ref_d"]), z["trig_c"])
        stop0 = z["ext_d"] - Pz["stop_buf"]
        risk = ep - stop0
        if not (Pz["min_stop"] <= risk <= Pz["max_stop"]):
            continue
        tp = _tp(M, z, Pz, risk, classes)
        if tp is None:
            continue
        use1 = Pz["tf"] == "1m" and B1 is not None and int(M.day_of[z["entry_i"]]) in B1.full
        B = B1 if use1 else B5
        t = TS.tsim(M, B, z, ep, ep + tp, False, stop0, Pz)
        if t is None:
            continue
        t.update(how=rule2 or "lit", src=rule2 or "lit", x_m=xm, recross=rc, ind=idm_count(z, Pz))
        busy = t["exit_i"]; per_day[day] += 1; first.setdefault(day, t)
        out.append(t)
    return out


_U = {}


def unit(P=None, sessions=SESS):
    key = json.dumps([P or {}, len(sessions), sessions[0], sessions[-1]], sort_keys=True, default=str)
    if key not in _U:
        U = drun(P, sessions)
        TS.wk_marks(U)
        for t in U:
            if t.get("x_m", 1.0) != 1.0:
                t["wk_m"] = t["wk_m"] * t["x_m"]
        _U[key] = U
    return _U[key]


score, row = TE.score, TE.row


# ================================================================================================ check
def check():
    U = unit()
    T = TS.sized(U, ("lit", 800, 20.0))
    L = F.run(LIVE)
    ka = [(t["day"], t["entry_t"], round(t["pnl"], 2), t["exit"], t["qty"]) for t in sorted(L, key=lambda t: t["entry_t"])]
    kb = [(t["day"], t["entry_t"], round(t["pnl"], 2), t["exit"], t["qty"]) for t in T]
    bad = [(x, y) for x, y in zip(ka, kb) if not (x[:2] == y[:2] and abs(x[2] - y[2]) < 0.03 and x[3:] == y[3:])]
    n26 = [t for t in T if t["day"] >= "2026"]
    print(f"engine lit_live {len(ka)} trades | wrapper {len(kb)} | mismatches {len(bad) + abs(len(ka) - len(kb))} | "
          f"2026 {len(n26)} trades net {sum(t['pnl'] for t in n26):+,.0f}")
    o = score(U, spans=("H1", "H2"))
    print(row("baseline (eval sizing)", o, spans=("H1", "H2")))
    ok = (not bad and len(ka) == len(kb) and len(n26) == 120 and o["H1"]["net"] == 33305 and o["H2"]["net"] == 10465)
    print("CHECK", "OK" if ok else "FAILED")
    return ok


# ================================================================================================ the grid
IDEAS = collections.OrderedDict([
    ("trap", "1. Smart-money trap (a LIT zone reacts, then fails)"),
    ("deeper", "2. Failed continuation into a deeper zone (re-entry after a stop, major level only)"),
    ("recross", "3. ETM early recross of the operating candle"),
    ("cont", "4. Multiple-inducement continuation into the HTF draw"),
    ("tgt2", "5. Second LIT trade only after a target hit"),
    ("mon_asia", "6. Asia-box-only Mondays"),
    ("lowvix", "7. London-only on low-VIX days"),
])


def variants():
    V = collections.OrderedDict()
    V["base"] = {}
    for rc in (0.5, 1.0, 1.5):
        V[f"trap ext react{rc}"] = {"trap": {"react": rc, "win": 24, "lvl": "ext", "wait": 30}}
    V["trap ref react1.0"] = {"trap": {"react": 1.0, "win": 24, "lvl": "ref", "wait": 30}}
    V["trap ext react1.0 win12"] = {"trap": {"react": 1.0, "win": 12, "lvl": "ext", "wait": 30}}
    V["trap ext react1.0 flip"] = {"trap": {"react": 1.0, "win": 24, "lvl": "ext", "wait": 30, "flip": True}}
    V["trap ext react1.0 half"] = {"trap": {"react": 1.0, "win": 24, "lvl": "ext", "wait": 30, "size": 0.5}}
    for mj in ("daily", "box"):
        for sz in (0.5, 1.0):
            V[f"deeper {mj} x{sz}"] = {"deeper": {"major": mj, "size": sz}}
    for kk in (3, 5, 8):
        V[f"recross size k{kk}"] = {"recross": {"k": kk, "mode": "size", "hi": 1.25, "lo": 0.75}}
        V[f"recross slow k{kk}"] = {"recross": {"k": kk, "mode": "size", "hi": 0.75, "lo": 1.25}}
    V["recross skip k5"] = {"recross": {"k": 5, "mode": "skip"}}
    V["recross skip k8"] = {"recross": {"k": 8, "mode": "skip"}}
    for ni in (1, 2, 3):
        V[f"cont idm{ni} htf"] = {"cont": {"idm": ni, "size": 1.0}}
    V["cont idm2 htf half"] = {"cont": {"idm": 2, "size": 0.5}}
    V["cont idm2 vix only"] = {"cont": {"idm": 2, "size": 1.0, "htf": False}}
    for sd in ("any", "same", "opp"):
        V[f"tgt2 {sd}"] = {"tgt2": {"side": sd, "size": 1.0}}
    V["tgt2 any half"] = {"tgt2": {"side": "any", "size": 0.5}}
    V["mon_asia asia skip"] = {"mon_asia": {"set": "asia", "mode": "skip"}}
    V["mon_asia asia_pd skip"] = {"mon_asia": {"set": "asia_pd", "mode": "skip"}}
    V["mon_asia asia half"] = {"mon_asia": {"set": "asia", "mode": "size", "x": 0.5}}
    for vx in (15.5, 16, 17):
        V[f"lowvix {vx} skip"] = {"lowvix": {"vix": vx, "end": 480, "mode": "skip"}}
    V["lowvix 16 half"] = {"lowvix": {"vix": 16, "end": 480, "mode": "size", "x": 0.5}}
    V["lowvix 16 skip after 09:30"] = {"lowvix": {"vix": 16, "end": 570, "mode": "skip"}}
    return V


def _load(p=OUT):
    return json.load(open(p)) if os.path.exists(p) else {}


def grid(only=None):
    res = _load()
    for nm, P in variants().items():
        if only and not any(o in nm for o in only):
            continue
        U = unit(P)
        o = score(U)
        res[nm] = {"params": P, "score": o,
                   "src26": dict(collections.Counter(t.get("src", "lit") for t in U if t["day"] >= "2026")),
                   "extra26": [{k: t.get(k) for k in ("day", "dir", "src", "exit", "risk_pts", "legs")} for t in U
                               if t["day"] >= "2026" and t.get("src") not in (None, "lit")][:60],
                   "mult26": dict(collections.Counter(str(t.get("x_m", 1.0)) for t in U if t["day"] >= "2026"))}
        print(row(nm, o), "| src26", res[nm]["src26"], flush=True)
        json.dump(res, open(OUT, "w"), indent=1, default=str)
    return res


# ================================================================================================ walk-forward
WF_GRID = {"cisd1m": (15, 20, 30), "disp": (0.7, 0.8, 0.9), "idm_d": (0.75, 1.0, 1.25)}
WF_FROM = "2025-10-01"


def _months(a, z):
    return sorted({d[:7] for d in SESS if a <= d <= z})


def wf():
    """Each month of 2026: pick the (cisd1m, disp, inducement distance) combo with the best net $ (eval size, $800 up to 25 pts,
    weekly stop, no room cap) over the 3 prior months, trade it that month. Prior months before 2026 run on 5m (no 1m data)."""
    ss = [d for d in SESS if d >= WF_FROM]
    combos = list(itertools.product(*WF_GRID.values()))
    mon = {}
    units = {}
    for cb in combos:
        P = {"cisd1m": cb[0], "disp": cb[1], "idm_a": [cb[2], 36, 1]}
        U = unit(P, ss)
        units[cb] = U
        T = TS.sized(U, RULE)
        m = collections.defaultdict(float)
        for t in T:
            m[t["day"][:7]] += t["pnl"]
        mon[cb] = dict(m)
        print("combo", cb, {k: round(v) for k, v in sorted(m.items())}, flush=True)
    live = (LIVE["cisd1m"], LIVE["disp"], LIVE["idm_a"][0])
    allm = _months(WF_FROM, "2026-12-31")
    pick = {}
    for i, mo in enumerate(allm):
        if mo < "2026-01" or i < 3:
            continue
        prior = allm[i - 3:i]
        sc = {cb: sum(mon[cb].get(p, 0.0) for p in prior) for cb in combos}
        best = max(sc.values())
        cands = [cb for cb in combos if sc[cb] == best]
        cb = live if live in cands else cands[0]
        pick[mo] = {"combo": list(cb), "prior": prior, "prior_net": round(best), "live_prior_net": round(sc[live])}
    # assemble: each month's trades from its picked combo (one trade a day; trades never cross days)
    W = []
    for mo, pk in pick.items():
        cb = tuple(pk["combo"])
        W += [copy.deepcopy(t) for t in units[cb] if t["day"][:7] == mo]
    W.sort(key=lambda t: t["entry_t"])
    TS.wk_marks(W)
    base = [copy.deepcopy(t) for t in units[live] if t["day"] >= "2026"]
    TS.wk_marks(base)
    ow = score(W, spans=("H1", "H2", "2026"))
    ob = score(base, spans=("H1", "H2", "2026"))
    # also: which fixed combo would have been best on H1 (the usual pick) and how it did on H2
    fx = {}
    for cb in combos:
        U = [copy.deepcopy(t) for t in units[cb] if t["day"] >= "2026"]
        TS.wk_marks(U)
        o = score(U, spans=("H1", "H2"))
        fx[str(cb)] = {s: {k: o[s].get(k) for k in ("n", "tpw", "pf", "net", "per_month", "dd", "p10", "f10", "pass_rate")} for s in ("H1", "H2")}
    res = {"grid": {k: list(v) for k, v in WF_GRID.items()}, "live": list(live), "picks": pick, "wf": ow, "fixed": ob,
           "monthly_net": {str(cb): {k: round(v) for k, v in mon[cb].items()} for cb in combos}, "fixed_combos": fx,
           "wf_trades": W, "fixed_trades": base}
    json.dump({k: v for k, v in res.items() if not k.endswith("_trades")}, open(OUT_WF, "w"), indent=1, default=str)
    print(row("walk-forward", ow, spans=("H1", "H2", "2026")))
    print(row("fixed lock", ob, spans=("H1", "H2", "2026")))
    for mo, pk in pick.items():
        print(mo, pk)
    return res


# ================================================================================================ store runs
def _slug(nm):
    return "lit_u_discovery_" + re.sub(r"[^a-z0-9]+", "_", nm.lower().replace(".", "p")).strip("_")


PICKS = {}            # filled after the grid: the H1 pick of each idea (ADOPT only when it also beats H2)


def verdict(o, b):
    d1, d2 = o["H1"]["net"] - b["H1"]["net"], o["H2"]["net"] - b["H2"]["net"]
    tpw = min(o["H1"]["tpw"], o["H2"]["tpw"]); tpx = max(o["H1"]["tpw"], o["H2"]["tpw"])
    if d1 > 0 and d2 > 0 and tpw >= 2 and tpx <= 4:
        return "ADOPT", d1, d2
    if abs(d1) < 500 and abs(d2) < 500:
        return "NEUTRAL", d1, d2
    return "REJECT", d1, d2


def _h(s):
    return (f"n={s['n']} {s['tpw']}/wk win {s['win']}% PF {s['pf']} net {s['net']:+,} (${s['per_month']:,}/mo) DD {s['dd']:,} "
            f"avg win ${s['avg_win']:,} avg loss ${s['avg_loss']:,}; eval 2wk {s['p10']}/{s['f10']} 1mo {s['p20']}/{s['f20']} "
            f"pass rate {s['pass_rate']}% median {s['pass_med']}") if s.get("n") else "no trades"


def _store(rid, title, P, U, o, st, why, tags=("lit", "lit_untested", "lit_discovery")):
    T = TS.evals(U, RULE, "2026", ROOM_K)[1] + TS.evals(U, RULE, "2021-25", ROOM_K)[1]
    T = [{k: v for k, v in t.items() if k not in ("legs", "B")} for t in T]
    S = rl.score(T, SESS)
    rl.save(rid, title, "other", "Owner 2026-10-18: find and test LIT-only ideas nobody had tested yet (discovery group).",
            params={**LIVE, **DDEF, **P, "size": list(RULE), "room_k": ROOM_K}, trades=T, scored=S, status=st,
            verdict=f"{why} 2026 H1 (pick) {_h(o['H1'])}; 2026 H2 (check) {_h(o['H2'])}; 2021-25 reference only "
                    f"{_h(o['2021-25']) if '2021-25' in o else 'n/a'}",
            notes="tools/lit_t_discovery.py (wraps engine/lit.py; defaults == run lit_live trade for trade and == run "
                  "lit_tight_eval_800_25_room60). Eval sizing: $800 up to a 25-pt stop, then 800x25/stop, weekly stop, 60% room cap.",
            writeup="lit-untested-discovery", tags=list(tags))


def save_all():
    res = _load()
    V = variants()
    b = res["base"]["score"]
    for nm, rec in res.items():
        o = rec["score"]
        if nm == "base":
            rid, title, st, why = (_slug("base"), "LIT live + eval sizing (reference of the discovery study, == lit_tight_eval_800_25_room60)",
                                   "info", "Reference: the live LIT with the live eval sizing.")
        else:
            v, d1, d2 = verdict(o, b)
            st = {"ADOPT": "adopt-candidate" if nm in PICKS else "promising", "NEUTRAL": "info", "REJECT": "rejected"}[v]
            idea = IDEAS[nm.split()[0]]
            rid, title, why = _slug(nm), f"LIT discovery - {idea}: {nm}", f"{v}: H1 {d1:+,} $ / H2 {d2:+,} $ vs the baseline (LIT live + eval sizing)."
        _store(rid, title, V[nm], unit(V[nm]), o, st, why)
        print("saved", rid, flush=True)
    if os.path.exists(OUT_WF + ".pkl"):
        pass


def save_wf():
    r = wf()
    W = r["wf_trades"]
    # the 2021-25 reference of the walk-forward is not defined (no 1m data, tuned on 2026): store 2026 only
    o = {**r["wf"]}
    d1, d2 = r["wf"]["H1"]["net"] - r["fixed"]["H1"]["net"], r["wf"]["H2"]["net"] - r["fixed"]["H2"]["net"]
    v = "ADOPT" if d1 > 0 and d2 > 0 else "REJECT"
    T = TS.evals(W, RULE, "2026", ROOM_K)[1]
    T = [{k: v_ for k, v_ in t.items() if k not in ("legs", "B")} for t in T]
    S = rl.score(T, SESS)
    rl.save("lit_u_discovery_walk_forward", "LIT discovery - walk-forward: 1m confirmation, displacement and inducement distance "
            "re-tuned every month on the prior 3 months", "other",
            "Stability check: does re-tuning the 3 most sensitive lit_final parameters month by month beat the fixed lock?",
            params={**LIVE, "wf_grid": r["grid"], "picks": r["picks"], "size": list(RULE), "room_k": ROOM_K}, trades=T, scored=S,
            status="rejected" if v == "REJECT" else "promising",
            verdict=f"{v}: walk-forward vs fixed H1 {d1:+,} $ / H2 {d2:+,} $. Walk-forward H1 {_h(o['H1'])}; H2 {_h(o['H2'])}. "
                    f"Fixed H1 {_h(r['fixed']['H1'])}; H2 {_h(r['fixed']['H2'])}.",
            notes="tools/lit_t_discovery.py wf. Prior months before 2026 run on 5m bars (no 1m data), as a live bot would have "
                  "seen them. Eval sizing as the baseline.", writeup="lit-untested-discovery", tags=["lit", "lit_untested", "lit_discovery"])
    print("saved lit_u_discovery_walk_forward", d1, d2)


if __name__ == "__main__":
    cmd = sys.argv[1] if len(sys.argv) > 1 else "check"
    if cmd == "check":
        sys.exit(0 if check() else 1)
    elif cmd == "grid":
        grid(sys.argv[2:] or None)
    elif cmd == "wf":
        wf()
    elif cmd == "save":
        save_all()
    elif cmd == "save_wf":
        save_wf()
