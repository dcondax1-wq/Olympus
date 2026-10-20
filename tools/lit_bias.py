"""LIT bias and discretion (2026-10-20, owner: "trading with bias and discretion - there's stuff you haven't tried").

Daily-bias methods, an A+ discretionary checklist and a small walk-forward meta-labeling model, all known BEFORE the entry
(features read only 5m bars <= the setup's trigger bar i, daily / weekly facts only from closed days), used on today's LIT as
  size     a size tilt with / against the bias (the trade list stays identical)
  target   a target / bank tilt (with: hold past the 8R bank; against: bank earlier), engine option ctx_day (after the fill only;
           the trade list stays identical, asserted)
  filter   skip setups against the bias (engine option skip_keys: the day stays free for a later setup, like the Monday rule);
           only worth it if trades/week stay >= 2.5 in both halves
Judged the LIT way: 2026 only, pick on H1 (Jan-Jun), check on H2 (Jul-Oct 16); 2021-25 is a reference line (LIT size rule,
5m entries). Two references: base = today's live LIT (run lit_live), all3 = the adopt-candidate combo t_check + scale_in +
be_off. Scored on the real eval path (engine/sizing.lit_qty: two_week for 10 sessions then safe_eval, no reset, $1.90 a micro,
true 1m; tools/lit_adv_manage.py + tools/lit_big_ideas.run_eval_x; the gates of tools/lit_context.py: strict + neighbours +
beats a flat multiplier of the same mean size).

    python -X utf8 tools/lit_bias.py feats      # bias features for every live-eligible setup -> research/runs/_cache
    python -X utf8 tools/lit_bias.py lookahead  # features recomputed on data cut at the trigger bar == full-data features
    python -X utf8 tools/lit_bias.py screen     # size / target / filter grid on base and all3 -> research/lit/bias.json
    python -X utf8 tools/lit_bias.py aplus      # the A+ checklist -> research/lit/bias_aplus.json
    python -X utf8 tools/lit_bias.py meta       # walk-forward meta-labeling + label-shuffle test -> research/lit/bias_meta.json
    python -X utf8 tools/lit_bias.py followup   # wider target with the bias: strengths, 8R bank kept, AND / OR -> bias_followup.json
    python -X utf8 tools/lit_bias.py random base amd wide 1.25   # random trade sets of the same size -> bias_random.json
    python -X utf8 tools/lit_bias.py engine     # engine/lit.py bias_with / bias_tgt == the research path (exit 1 if not)
    python -X utf8 tools/lit_bias.py save       # rl.save the runs lit_bias_* from the json files (save_one for one variant)
    python -X utf8 tools/lit_bias.py table base # markdown table per bias method; counts = variants up in both halves
Paper only. Changes nothing in live_model.json.
"""
from __future__ import annotations

import bisect
import collections
import json
import os
import pickle
import sys

import numpy as np
import pandas as pd

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)
from engine import lit  # noqa: E402
from tools import lit_adopt_combo as AC  # noqa: E402
from tools import lit_adv_manage as A  # noqa: E402
from tools import lit_big_ideas as BI  # noqa: E402  (installs run_eval_x: size multiplier t["m"] + adds)
from tools import lit_final as F  # noqa: E402
from tools import runlib as rl  # noqa: E402

CACHE = os.path.join(ROOT, "research", "runs", "_cache")
OUTD = os.path.join(ROOT, "research", "lit")
VER = "v1"
P_LIVE = {**lit.DEFAULTS, **AC.LIVE}
REFS = {"base": {}, "all3": {"t_check": AC.T15, "scale_in": AC.SCALE, "be_off": AC.BE_OFF}}


# ================================================================================================ features
def plan_of(M, z, P=P_LIVE):
    """The live plan (ep, risk, tp) of a setup, or None when the live filters refuse it (lit._run_core order)."""
    if not lit.setup_ok(z, P, None):
        return None
    if P.get("monday") and lit.monday_block(M, z):
        return None
    ep = min(float(z["ref_d"]), z["trig_c"])
    risk = ep - (z["ext_d"] - P["stop_buf"])
    if not (P["min_stop"] <= risk <= P["max_stop"]):
        return None
    sh = z["entry_d"] - ep
    TT = {c: [x + sh for x in v] for c, v in lit.targets_x(M, z, P).items()}
    best = None
    for c in P["classes"]:
        for dist in TT.get(c, []):
            if dist >= P["min_rr"] * risk:
                best = dist if best is None else min(best, dist)
                break
    if best is None:
        return None
    return {"ep": ep, "risk": risk, "tp": min(best, P["max_rr"] * risk) if P["max_rr"] else best}


def _sgn(x, eps=0.0):
    if x is None or not np.isfinite(x) or abs(x) <= eps:
        return 0
    return 1 if x > 0 else -1


def _w(v):
    """lit_htf 1/0/nan ('with the trade' flag) -> +1 with / -1 against / 0 unknown."""
    return 0 if v is None or not np.isfinite(v) else (1 if v >= 0.5 else -1)


class Bias:
    """Every bias component for a Market, computed once; feats(z) reads only bars <= z['i'] and closed days."""

    def __init__(self, M):
        from tools import lit_htf as HT
        self.M = M
        self.H = HT.HTF(M)
        n = M.n
        # daily bars (trading days)
        D = self.H.tf["d"]
        self.D = D
        rng = D["h"] - D["l"]
        self.d_rng20 = pd.Series(rng).rolling(20, min_periods=5).mean().shift(1).values   # mean range of the 20 days before
        self._daily_fvg()
        self._es()
        self.wk_start = {}
        for k, (d, s, e) in enumerate(M.days):
            self.wk_start.setdefault(int(M.week_id[s]), s)

    # ---- daily FVG / IFVG events: (known after day m closes, side +1 bull / -1 bear)
    def _daily_fvg(self):
        D = self.D
        H, L, C = D["h"], D["l"], D["c"]
        N = len(H)
        ev = [[] for _ in range(N)]                      # events that become known at the close of day m
        act = []                                         # active FVGs [side, bot, top, inverted]
        for m in range(N):
            for g in act:                                # inversion: a daily close through the whole gap flips its side
                if not g[3] and ((g[0] == 1 and C[m] < g[1]) or (g[0] == -1 and C[m] > g[2])):
                    g[3] = True
                    ev[m].append(-g[0])
            if m >= 2:
                if L[m] > H[m - 2]:
                    act.append([1, H[m - 2], L[m], False]); ev[m].append(1)
                elif H[m] < L[m - 2]:
                    act.append([-1, H[m], L[m - 2], False]); ev[m].append(-1)
            act = act[-20:]
        self.d_fvg_ev = ev

    def d_fvg_bias(self, k, look=10):
        """Side of the most recent daily FVG / IFVG event of the `look` closed days before day k (0 = none)."""
        for m in range(k - 1, max(-1, k - 1 - look), -1):
            if self.d_fvg_ev[m]:
                return int(self.d_fvg_ev[m][-1])
        return 0

    # ---- ES: daily bars (data/ES_1d.csv, by trading date) and 5m bars (2025-04 on) for the SMT reads
    def _es(self):
        import datetime as dt
        df = pd.read_csv(os.path.join(ROOT, "data", "ES_1d.csv"))
        self.es_d = {dt.datetime.fromtimestamp(int(t), dt.timezone.utc).strftime("%Y-%m-%d"): (float(h), float(l))
                     for t, h, l in zip(df["time"], df["high"], df["low"])}
        from engine.data import load
        b = load("ES", "5m")
        self.es_t = np.asarray(b.t, dtype=np.int64)
        self.es_h, self.es_l = np.asarray(b.h, float), np.asarray(b.l, float)
        ds = np.array(b.date_str)
        self.es_day = {}
        st = np.r_[0, np.flatnonzero(ds[1:] != ds[:-1]) + 1]
        en = np.r_[st[1:], len(ds)]
        for a, z in zip(st, en):
            self.es_day[str(ds[a])] = (int(a), int(z))
        self.es_days = sorted(self.es_day)

    def es_prev(self, day):
        """ES (pdh, pdl) for trading day `day` from the ES 5m file (None when ES 5m does not cover the day before)."""
        j = bisect.bisect_left(self.es_days, day) - 1
        if j < 0 or day not in self.es_day:
            return None
        a, z = self.es_day[self.es_days[j]]
        return float(self.es_h[a:z].max()), float(self.es_l[a:z].min())

    def feats(self, z, pl):
        M, H = self.M, self.H
        i, d, k = int(z["i"]), int(z["dir"]), int(z["k"])
        x = M.ctx[k]
        s = x["s"]
        h = H.feats(z, pl)
        px = float(M.c[i])
        f = {}
        # ---- 1 HTF draw on liquidity (nearest untaken level): lit_htf + PDH/PDL/PWH/PWL only
        f["draw_all"] = _w(h["dr_all"]); f["draw_pd"] = _w(h["dr_pd"]); f["draw_pw"] = _w(h["dr_pw"])
        L = []
        if "pdh" in x:
            L += [(1, x["pdh"], H.dhi[i] > x["pdh"]), (-1, x["pdl"], H.dlo[i] < x["pdl"])]
        if "pwh" in x:
            L += [(1, x["pwh"], H.whi[i] > x["pwh"]), (-1, x["pwl"], H.wlo[i] < x["pwl"])]
        up = [p - px for sd, p, tk in L if sd == 1 and not tk and p > px]
        dn = [px - p for sd, p, tk in L if sd == -1 and not tk and p < px]
        f["draw_pdpw"] = 0 if not up and not dn else (d if (min(up) if up else np.inf) < (min(dn) if dn else np.inf) else -d)
        # draw fixed at the 18:00 open (the bias a trader writes down before the session): nearest of PDH / PDL from the open
        if "pdh" in x:
            o18 = x["open18"]
            f["draw_open"] = d if (x["pdh"] - o18) < (o18 - x["pdl"]) else -d
        else:
            f["draw_open"] = 0
        # ---- 2 previous day's close position in its range
        f["pdc_half"] = _w(h["bi_pdc"])
        f["pdc_third"] = 0
        if k >= 1:
            ps, pe = M.days[k - 1][1], M.days[k - 1][2]
            ph, pl_, pc = float(M.h[ps:pe].max()), float(M.l[ps:pe].min()), float(M.c[pe - 1])
            cp = (pc - pl_) / max(ph - pl_, 1e-9)
            f["pdc_third"] = (d if cp >= 2 / 3 else -d) if (cp >= 2 / 3 or cp <= 1 / 3) else 0
            # ---- 8 previous day's displacement (body vs the 20-day mean range)
            body = pc - float(M.o[ps])
            r20 = self.d_rng20[k] if k < len(self.d_rng20) else np.nan
            for th in (0.25, 0.5):
                f[f"pdisp{int(th * 100)}"] = d * _sgn(body, th * r20) if np.isfinite(r20) else 0
            f["pcandle"] = d * _sgn(body)
        else:
            f["pdisp25"] = f["pdisp50"] = f["pcandle"] = 0
        # ---- 3 premium / discount (direction space: < 0.5 = entry in discount for a long = with)
        for nm in ("pd", "pw", "20d", "wk"):
            v = h[f"rg_{nm}_pos"]
            f[f"pdz_{nm}"] = 0 if not np.isfinite(v) else (1 if v < 0.5 else -1)
        # ---- 4 Power of 3 / AMD: Asia (18:00-00:00) accumulates, London manipulates one side, NY distributes the other way
        f["amd"] = f["amd_ny"] = 0
        a18 = x.get("asia18")
        if a18 and i > a18[2]:
            ahi, alo = a18[0], a18[1]
            seg_h, seg_l = M.h[a18[2] + 1:i + 1], M.l[a18[2] + 1:i + 1]
            took_hi = bool(len(seg_h) and seg_h.max() > ahi)
            took_lo = bool(len(seg_l) and seg_l.min() < alo)
            if took_hi != took_lo:
                f["amd"] = d if took_lo else -d          # Asia low taken (and not the high): bullish day
                if M.mod[i] >= 480:
                    f["amd_ny"] = f["amd"]
            # ---- 7 Asia range direction (close vs open of 18:00-00:00)
            f["asia_dir"] = d * _sgn(float(M.c[a18[2]]) - float(M.o[s]))
        else:
            f["asia_dir"] = 0
        # ---- 5 ICT weekly profile: on Wed-Fri, a week low made Mon-Wed with the high after it = bullish week (mirror)
        f["wkprof"] = 0
        if x["dow"] >= 2:
            ws = self.wk_start.get(int(M.week_id[s]))
            if ws is not None and ws < i:
                jl = ws + int(np.argmin(M.l[ws:i + 1])); jh = ws + int(np.argmax(M.h[ws:i + 1]))
                dl, dh = int(M.dow[jl]), int(M.dow[jh])
                if dl <= 2 and jh > jl:
                    f["wkprof"] = d
                elif dh <= 2 and jl > jh:
                    f["wkprof"] = -d
        # ---- 6 opens as a bias line: above the open = bullish (the 'buy below the open' PO3 reading is the other sign)
        for nm, arr in (("o00", M.open_00), ("o830", M.open_830), ("o930", M.open_930), ("o18", M.open_d), ("owk", M.open_wk)):
            ov = float(arr[i])
            f[nm] = 0 if not np.isfinite(ov) else d * _sgn(px - ov)
        # ---- 9 daily FVG / IFVG direction (last event of the 10 closed days before today)
        f["d_fvg"] = d * self.d_fvg_bias(k)
        # ---- 10 HTF market structure (last 1H / 4H / daily break of structure)
        f["ms_1h"], f["ms_4h"], f["ms_d"] = _w(h["ms_1h"]), _w(h["ms_4h"]), _w(h["ms_d"])
        # ---- 11 NQ-ES SMT: daily (yesterday vs the day before) and today-so-far at PDH / PDL (ES 5m from 2025-04)
        f["smt_d"] = 0
        if k >= 2:
            d1, d2 = str(M.days[k - 1][0]), str(M.days[k - 2][0])
            e1, e2 = self.es_d.get(d1), self.es_d.get(d2)
            if e1 and e2:
                n1 = (float(M.h[M.days[k - 1][1]:M.days[k - 1][2]].max()), float(M.l[M.days[k - 1][1]:M.days[k - 1][2]].min()))
                n2 = (float(M.h[M.days[k - 2][1]:M.days[k - 2][2]].max()), float(M.l[M.days[k - 2][1]:M.days[k - 2][2]].min()))
                bear = n1[0] > n2[0] and e1[0] <= e2[0]
                bull = n1[1] < n2[1] and e1[1] >= e2[1]
                if bear != bull:
                    f["smt_d"] = d if bull else -d
        f["smt_pd"] = 0
        ep_ = self.es_prev(str(x["date"]))
        if ep_ and "pdh" in x:
            a, _z = self.es_day[str(x["date"])]
            tcut = int(M.t[i])
            j = int(np.searchsorted(self.es_t, tcut, side="right"))
            if j > a:
                eh, el = float(self.es_h[a:j].max()), float(self.es_l[a:j].min())
                nh, nl = float(H.dhi[i]), float(H.dlo[i])
                bear = nh > x["pdh"] and eh <= ep_[0]
                bull = nl < x["pdl"] and el >= ep_[1]
                if bear != bull:
                    f["smt_pd"] = d if bull else -d
        # ---- composite: vote of draw (pd/pw), previous close, 4H structure, AMD, daily FVG
        v = f["draw_pdpw"] + f["pdc_half"] + f["ms_4h"] + f["amd"] + f["d_fvg"]
        f["vote"] = _sgn(v)
        f["vote2"] = 1 if v >= 2 else (-1 if v <= -2 else 0)
        # ---- discretion facts for the A+ checklist / meta-labeling (all known at the trigger bar)
        cls = set(z["swept_cls"])
        idm = z.get("idm_a") or []
        f["_major"] = int(bool(cls & {"pd", "pw", "pm", "gap"}))
        f["_n_swept"] = len(z["swept"])
        f["_disp"] = float(z["disp"])
        f["_depth"] = float(z["depth_atr"])
        f["_idm2"] = sum(1 for dd, aa in idm if dd <= 2.0 and aa <= 48)
        f["_idm_age"] = min((aa for dd, aa in idm), default=99)
        f["_mod"] = int(M.mod[z["entry_i"]])
        f["_kz"] = int(120 <= f["_mod"] < 300 or 510 <= f["_mod"] < 660)
        f["_risk"] = float(pl["risk"])
        f["_rr"] = float(pl["tp"] / pl["risk"])
        f["_vix"] = float(x.get("vix") or np.nan)
        f["_how"] = int(bool(z["how"]))
        f["_vec"] = int(bool(z["vec"]))
        f["_dow"] = int(x["dow"])
        f["_atr"] = float(z["atr"])
        f["_fvway1h"] = int(h["fv_way1h"]); f["_fvway4h"] = int(h["fv_way4h"])
        f["_sw4h"] = _w(h["pl_sw4h"])
        return f


BIAS = ["draw_all", "draw_pd", "draw_pw", "draw_pdpw", "draw_open", "pdc_half", "pdc_third", "pdisp25", "pdisp50", "pcandle",
        "pdz_pd", "pdz_pw", "pdz_20d", "pdz_wk", "amd", "amd_ny", "asia_dir", "wkprof", "o00", "o830", "o930", "o18", "owk",
        "d_fvg", "ms_1h", "ms_4h", "ms_d", "smt_d", "smt_pd", "vote", "vote2"]
LABEL = {"draw_all": "HTF draw: nearest untaken PDH/PDL/PWH/PWL/PMH/PML/gap on the target side",
         "draw_pd": "draw: nearest untaken PDH/PDL on the target side", "draw_pw": "draw: nearest untaken PWH/PWL on the target side",
         "draw_pdpw": "draw: nearest untaken of PDH/PDL/PWH/PWL on the target side",
         "draw_open": "draw at the 18:00 open: the nearer of PDH / PDL is on the target side",
         "pdc_half": "previous day closed in the half of its range on the trade's side",
         "pdc_third": "previous day closed in the third of its range on the trade's side (middle third = no bias)",
         "pdisp25": "previous day's body >= 0.25 x the 20-day range, the trade's way", "pdisp50": "previous day's body >= 0.5 x "
         "the 20-day range, the trade's way", "pcandle": "previous day's candle closed the trade's way",
         "pdz_pd": "entry in discount (long) / premium (short) of the previous day's range", "pdz_pw": "... of the previous week's range",
         "pdz_20d": "... of the 20-day range", "pdz_wk": "... of this week's range so far",
         "amd": "Power of 3 / AMD: after Asia, the session took the Asia low (long) / high (short) and not the other side",
         "amd_ny": "AMD, read only for NY entries (08:00+)", "asia_dir": "Asia session (18:00-00:00) closed the trade's way",
         "wkprof": "ICT weekly profile (Wed-Fri): the week's low (long) / high (short) was made Mon-Wed and the other extreme after it",
         "o00": "price above (long) / below (short) the midnight open", "o830": "... the 08:30 open", "o930": "... the 09:30 open",
         "o18": "... the 18:00 open", "owk": "... the weekly open",
         "d_fvg": "the last daily FVG / IFVG (10 days) points the trade's way",
         "ms_1h": "last 1H break of structure the trade's way", "ms_4h": "last 4H break of structure the trade's way",
         "ms_d": "last daily break of structure the trade's way",
         "smt_d": "NQ-ES daily SMT yesterday (NQ new low, ES not = bullish) the trade's way",
         "smt_pd": "NQ-ES SMT today at PDH/PDL (NQ took it, ES did not) the trade's way",
         "vote": "composite vote (draw, previous close, 4H structure, AMD, daily FVG) the trade's way",
         "vote2": "composite vote, 2+ net votes"}


_S = {}


def market():
    if "M" not in _S:
        M, C = F.market(AC.LIVE["ref"], AC.LIVE.get("extra_boxes") or [])
        _S.update(M=M, C=C)
    return _S["M"], _S["C"]


def feats(force=False):
    """{(day, i, dir): features} for every setup that passes the live filters (all years)."""
    if "F" in _S:
        return _S["F"]
    p = os.path.join(CACHE, f"litbias_{VER}_{rl._data_key().replace(':', '_')}.pkl")
    if os.path.exists(p) and not force:
        _S["F"] = pickle.load(open(p, "rb"))
        return _S["F"]
    M, C = market()
    B = Bias(M)
    out = {}
    for z in C:
        pl = plan_of(M, z)
        if pl is None:
            continue
        out[(z["day"], int(z["i"]), int(z["dir"]))] = B.feats(z, pl)
    pickle.dump(out, open(p, "wb"))
    _S["F"] = out
    print(f"features for {len(out)} live-eligible setups", flush=True)
    return out


def lookahead(n=12, seed=7):
    """Recompute the features of n 2026 trades on 5m data cut at their trigger bar + 1 (bars after i removed) == full data."""
    from engine.data import load
    M, C = market()
    Fx = feats()
    T = [t for t in run_ref("base") if t["day"] >= "2026-01-01"]
    rng = np.random.default_rng(seed)
    pick = [T[j] for j in rng.choice(len(T), size=min(n, len(T)), replace=False)]
    from engine.data import Bars
    b = load("NQ", "5m")
    ok = 0
    for t in pick:
        key = (t["day"], int(t["i"]), int(t["dir"]))
        x = b.slice(0, int(t["i"]) + 2)               # bars 0..i+1, bar i+1 (the entry bar) reduced to its open
        o_, h_, l_, c_, v_ = x.o.copy(), x.h.copy(), x.l.copy(), x.c.copy(), x.v.copy()
        h_[-1] = l_[-1] = c_[-1] = o_[-1]; v_[-1] = 0.0
        cut = Bars(x.sym, x.tf, x.t, o_, h_, l_, c_, v_, x.mod, x.tday, x.dow, x.date_str)
        Mc = lit.Market(extra_boxes=list(AC.LIVE.get("extra_boxes") or []), bars=cut)
        Cc = [z for z in lit.candidates(Mc, ref=AC.LIVE["ref"]) if (z["day"], int(z["i"]), int(z["dir"])) == key]
        if not Cc:
            print("  cut market has no such setup", key); continue
        Bc = Bias(Mc)
        pl = plan_of(Mc, Cc[0])
        fc = Bc.feats(Cc[0], pl)
        f0 = Fx[key]
        diff = [k_ for k_ in f0 if not (f0[k_] == fc[k_] or (isinstance(f0[k_], float) and np.isnan(f0[k_]) and np.isnan(fc[k_])))]
        diff = [k_ for k_ in diff if k_ not in ("_rr",)]      # the VIX band target uses the day's 18:00 open: same, but float
        ok += not diff
        print(f"  {key}: {'same' if not diff else 'DIFF ' + str({k_: (f0[k_], fc[k_]) for k_ in diff})}", flush=True)
    print(f"look-ahead: {ok}/{len(pick)} identical", flush=True)
    return ok, len(pick)


# ================================================================================================ references / scoring
_R = {}


def run_ref(ref, **extra):
    x = {**AC.LIVE, **REFS[ref], **extra}
    return F.run(x)


def key_of(t):
    return (t["day"], int(t["i"]), int(t["dir"]))


def trades_key(T):
    return [(t["day"], int(t["entry_t"])) for t in T]


def score_eval(U):
    A._MC.clear()
    return BI.short(BI.score(U))


def score_lit(T):
    return F.score(T, spans=("H1", "H2", "2021-25"), fast=True)


class Ref:
    def __init__(self, nm):
        self.nm = nm
        self.T = run_ref(nm)
        self.U = AC.units(self.T)
        self.key = trades_key(self.T)
        self.ev = score_eval(self.U)
        self.lr = score_lit(self.T)
        Fx = feats()
        self.f = [Fx.get(key_of(t)) for t in self.T]
        miss = sum(1 for v in self.f if v is None)
        assert miss == 0, f"{miss} trades without features"
        self.f26 = [f for t, f in zip(self.T, self.f) if t["day"] >= "2026-01-01"]
        M, _ = market()
        self.vm = {str(M.days[k][0]): M.ctx[k].get("vix_move") for k in range(len(M.days))}


def ref(nm):
    if nm not in _R:
        _R[nm] = Ref(nm)
    return _R[nm]


def apply_m(R, ms):
    """ms: a size multiplier per engine trade (same order as R.T) -> (LIT-rule trades, eval units)."""
    TT = [lit.scale_trade(t, m) if m != 1.0 else t for t, m in zip(R.T, ms)]
    m26 = [m for t, m in zip(R.T, ms) if t["day"] >= "2026-01-01"]
    UU = [{**u, "m": m} for u, m in zip(R.U, m26)]
    return TT, UU


def eval_ms(R, ms, info):
    TT, UU = apply_m(R, ms)
    h1 = [m for t, m in zip(R.T, ms) if "2026-01-01" <= t["day"] <= "2026-06-30"]
    h2 = [m for t, m in zip(R.T, ms) if t["day"] >= "2026-07-01"]
    m26 = h1 + h2
    info = {**info, "flag_h1": sum(1 for m in h1 if m != 1.0), "flag_h2": sum(1 for m in h2 if m != 1.0),
            "mean_m": round(float(np.mean(m26)), 4) if m26 else 1.0}
    return {"info": info, "eval": score_eval(UU), "lit": score_lit(TT)}


def gains(R, o):
    e, b = o["eval"], R.ev
    lr, lb = o["lit"], R.lr
    return {"d_net_h1": e["H1"]["net"] - b["H1"]["net"], "d_net_h2": e["H2"]["net"] - b["H2"]["net"],
            "d_p10_h1": round(e["H1"]["p10"] - b["H1"]["p10"], 1), "d_p10_h2": round(e["H2"]["p10"] - b["H2"]["p10"], 1),
            "d_f10_h1": round(e["H1"]["f10"] - b["H1"]["f10"], 1), "d_f10_h2": round(e["H2"]["f10"] - b["H2"]["f10"], 1),
            "d_mcf_h1": round(e["H1"]["mc_f10"] - b["H1"]["mc_f10"], 1), "d_mcf_h2": round(e["H2"]["mc_f10"] - b["H2"]["mc_f10"], 1),
            "d_lit_h1": (lr["H1"]["net"] or 0) - (lb["H1"]["net"] or 0), "d_lit_h2": (lr["H2"]["net"] or 0) - (lb["H2"]["net"] or 0),
            "d_lit_ref": (lr["2021-25"]["net"] or 0) - (lb["2021-25"]["net"] or 0),
            "tpw_h1": e["H1"]["tpw"], "tpw_h2": e["H2"]["tpw"]}


def strict(g, info):
    """Adopt test (both halves): eval net up, 2-week pass not down, 2-week fail (exact and Monte Carlo) not up, LIT-rule net not
    down, enough flagged trades (>= 10 in H1, >= 5 in H2); a filter also needs >= 2.5 trades a week in both halves."""
    ok = (g["d_net_h1"] > 0 and g["d_net_h2"] > 0 and g["d_p10_h1"] >= 0 and g["d_p10_h2"] >= 0 and g["d_f10_h1"] <= 0
          and g["d_f10_h2"] <= 0 and g["d_mcf_h1"] <= 0 and g["d_mcf_h2"] <= 0 and g["d_lit_h1"] >= 0 and g["d_lit_h2"] >= 0
          and info.get("flag_h1", 0) >= 10 and info.get("flag_h2", 0) >= 5)
    if info.get("chg_h1") is not None:
        ok = ok and info["chg_h1"] >= 5 and info["chg_h2"] >= 3 and (info["top_h1"] or 1) <= 0.5 and (info["top_h2"] or 1) <= 0.5
    if info.get("use") == "filter":
        ok = ok and g["tpw_h1"] >= 2.5 and g["tpw_h2"] >= 2.5
    return bool(ok)


def loose(g):
    return g["d_net_h1"] > 0 and g["d_net_h2"] > 0


# ================================================================================================ the grid
# size shapes: (family, strength) -> (with, neutral, against)
SIZE = {("tilt", 0.15): (1.15, 1.0, 0.85), ("tilt", 0.25): (1.25, 1.0, 0.75), ("tilt", 0.4): (1.4, 1.0, 0.6),
        ("up", 0.25): (1.25, 1.0, 1.0), ("up", 0.5): (1.5, 1.0, 1.0),
        ("cut", 0.25): (1.0, 1.0, 0.75), ("cut", 0.5): (1.0, 1.0, 0.5),
        ("rev", 0.25): (0.75, 1.0, 1.25), ("rev", 0.4): (0.6, 1.0, 1.4)}
# target / bank shapes: (family, strength) -> ctx_day spec for (with, against) trades (None = unchanged)
TGT = {("bank_ag", 3): (None, {"max_rr": 3.0}), ("bank_ag", 4): (None, {"max_rr": 4.0}), ("bank_ag", 5): (None, {"max_rr": 5.0}),
       ("near_ag", 0.6): (None, {"tgt_m": 0.6}), ("near_ag", 0.75): (None, {"tgt_m": 0.75}),
       ("hold_w", 12): ({"max_rr": 12.0}, None), ("hold_w", 99): ({"max_rr": None}, None),
       ("wide_w", 1.25): ({"tgt_m": 1.25, "max_rr": None}, None), ("wide_w", 1.5): ({"tgt_m": 1.5, "max_rr": None}, None),
       ("pair", 4): ({"max_rr": None}, {"max_rr": 4.0}), ("pair", 5): ({"max_rr": None}, {"max_rr": 5.0}),
       ("be_ag", 0.75): (None, {"be_r": 0.75}), ("be_ag", 0.5): (None, {"be_r": 0.5})}


def neighbours(res, lab, o):
    """Same feature / use / family at the adjacent strength: all must keep eval net up in both halves (None = no neighbour)."""
    i = o["info"]
    if i.get("fam") is None:
        return None
    st = sorted({o2["info"]["st"] for o2 in res.values() if o2["info"].get("feat") == i["feat"]
                 and o2["info"].get("use") == i["use"] and o2["info"].get("fam") == i["fam"]})
    k = st.index(i["st"])
    nb = [st[j] for j in (k - 1, k + 1) if 0 <= j < len(st)]
    out = [o2["_g"]["d_net_h1"] > 0 and o2["_g"]["d_net_h2"] > 0 for lab2, o2 in res.items()
           if o2["info"].get("feat") == i["feat"] and o2["info"].get("use") == i["use"] and o2["info"].get("fam") == i["fam"]
           and o2["info"].get("st") in nb]
    return all(out) if out else None


def size_grid(R):
    res = {}
    for feat in BIAS:
        v = [f[feat] for f in R.f]
        for (fam, st), (mw, mn, ma) in SIZE.items():
            ms = [mw if x > 0 else ma if x < 0 else mn for x in v]
            res[f"{feat} size {fam} {st}"] = eval_ms(R, ms, {"feat": feat, "use": "size", "fam": fam, "st": st})
    return res


def changed(U0, U1):
    o = {}
    for sp, a, z in (("h1", "2026-01-01", "2026-06-30"), ("h2", "2026-07-01", "2026-12-31")):
        dR = []
        for u0, u1 in zip(U0, U1):
            if a <= u0["day"] <= z:
                r0 = (u0["pts"] + sum(x["pts"] for x in u0.get("adds") or [])) / u0["risk"]
                r1 = (u1["pts"] + sum(x["pts"] for x in u1.get("adds") or [])) / u1["risk"]
                if abs(r1 - r0) > 1e-3:
                    dR.append(r1 - r0)
        pos = sum(x for x in dR if x > 0)
        o["chg_" + sp] = len(dR)
        o["dR_" + sp] = round(sum(dR), 2)
        o["top_" + sp] = round(max(dR) / pos, 2) if pos > 0 else None
    return o


def ctx_of(R, feat, spec):
    sw, sa = spec
    cd = {}
    for t, f in zip(R.T, R.f):
        x = f[feat]
        s = sw if x > 0 else sa if x < 0 else None
        if s:
            cd[t["day"]] = dict(s)
    return cd


def target_grid(R):
    res = {}
    for feat in BIAS:
        for (fam, st), spec in TGT.items():
            cd = ctx_of(R, feat, spec)
            T = run_ref(R.nm, ctx_day=cd) if cd else R.T
            assert trades_key(T) == R.key, "a target variant changed the trade list"
            U = AC.units(T)
            info = {"feat": feat, "use": "target", "fam": fam, "st": st,
                    "flag_h1": sum(1 for d in cd if "2026-01-01" <= d <= "2026-06-30"),
                    "flag_h2": sum(1 for d in cd if d >= "2026-07-01"), **changed(R.U, U)}
            res[f"{feat} target {fam} {st}"] = {"info": info, "eval": score_eval(U), "lit": score_lit(T)}
    # the same change on every day (the bias must beat it)
    for (fam, st), spec in TGT.items():
        s = spec[0] or spec[1]
        cd = {t["day"]: dict(s) for t in R.T}
        T = run_ref(R.nm, ctx_day=cd)
        U = AC.units(T)
        res[f"ALL target {fam} {st}"] = {"info": {"feat": "ALL", "use": "target", "fam": fam, "st": st,
                                                  "flag_h1": 99, "flag_h2": 99, **changed(R.U, U)},
                                         "eval": score_eval(U), "lit": score_lit(T)}
    return res


def filter_grid(R):
    """Skip every live-eligible setup against the bias (strict) or only against a 2-vote composite."""
    Fx = feats()
    res = {}
    for feat in BIAS:
        sk = [list(k_) for k_, f in Fx.items() if f[feat] < 0]
        T = run_ref(R.nm, skip_keys=sk)
        U = AC.units(T)
        n6 = [t for t in T if t["day"] >= "2026-01-01"]
        info = {"feat": feat, "use": "filter", "fam": None, "st": None,
                "flag_h1": sum(1 for t, f in zip(R.T, R.f) if f[feat] < 0 and "2026-01-01" <= t["day"] <= "2026-06-30"),
                "flag_h2": sum(1 for t, f in zip(R.T, R.f) if f[feat] < 0 and t["day"] >= "2026-07-01"), "n_2026": len(n6)}
        res[f"{feat} filter"] = {"info": info, "eval": score_eval(U), "lit": score_lit(T)}
    return res


def leverage_control(R, mean_m):
    if abs(mean_m - 1.0) < 1e-3:
        return None
    TT, UU = apply_m(R, [mean_m] * len(R.T))
    return {"eval": score_eval(UU), "lit": score_lit(TT)}


def verdicts(R, res):
    for lab, o in res.items():
        o["_g"] = gains(R, o)
    for lab, o in res.items():
        o["nb_ok"] = neighbours(res, lab, o)
        o["strict"] = strict(o["_g"], o["info"])
        o["adopt"] = bool(o["strict"] and o["nb_ok"] is not False)
        i = o["info"]
        if i["use"] == "target" and i["feat"] != "ALL":
            al = res.get(f"ALL target {i['fam']} {i['st']}")
            if al is not None:
                o["vs_all"] = {s: o["eval"][s]["net"] - al["eval"][s]["net"] for s in ("H1", "H2")}
                o["adopt"] = bool(o["adopt"] and all(v > 0 for v in o["vs_all"].values()))
        if i["feat"] == "ALL":
            o["adopt"] = False
        if o["adopt"] and i["use"] == "size":
            lc = leverage_control(R, i["mean_m"])
            if lc is not None:
                o["lev_ctrl"] = {s: lc["eval"][s]["net"] for s in ("H1", "H2")}
                o["adopt"] = all(o["eval"][s]["net"] > lc["eval"][s]["net"] for s in ("H1", "H2"))
    return res


def show(R, grp, res, top=12):
    n_loose = sum(1 for o in res.values() if loose(o["_g"]))
    n_strict = sum(1 for o in res.values() if o["strict"])
    n_ad = sum(1 for o in res.values() if o["adopt"])
    print(f"   {R.nm} {grp}: {len(res)} variants, net up in both halves {n_loose}, strict {n_strict}, adopt {n_ad}", flush=True)
    for lab, o in sorted(res.items(), key=lambda kv: min(kv[1]["_g"]["d_net_h1"], kv[1]["_g"]["d_net_h2"]), reverse=True)[:top]:
        g, i = o["_g"], o["info"]
        print(f"     {lab[:40]:40s} dnet {g['d_net_h1']:+7,}/{g['d_net_h2']:+7,} 2w pass {g['d_p10_h1']:+5}/{g['d_p10_h2']:+5} "
              f"fail {g['d_f10_h1']:+5}/{g['d_f10_h2']:+5} mcf {g['d_mcf_h1']:+5}/{g['d_mcf_h2']:+5} LIT {g['d_lit_h1']:+7,}/"
              f"{g['d_lit_h2']:+7,} ref {g['d_lit_ref']:+7,} tpw {g['tpw_h1']}/{g['tpw_h2']} n {i['flag_h1']}/{i['flag_h2']} "
              f"chg {i.get('chg_h1')}/{i.get('chg_h2')} strict={o['strict']} nb={o['nb_ok']} adopt={o['adopt']}", flush=True)


def flag_stats(R):
    """How often each bias says with / against on the 2026 trades, and the R of each side per half (LIT rule)."""
    out = {}
    for feat in BIAS:
        row = {}
        for sp, a, z in (("H1", "2026-01-01", "2026-06-30"), ("H2", "2026-07-01", "2026-12-31"), ("ref", "2021-01-01", "2025-12-31")):
            w = [t["r"] for t, f in zip(R.T, R.f) if a <= t["day"] <= z and f[feat] > 0]
            g = [t["r"] for t, f in zip(R.T, R.f) if a <= t["day"] <= z and f[feat] < 0]
            n0 = sum(1 for t, f in zip(R.T, R.f) if a <= t["day"] <= z and f[feat] == 0)
            row[sp] = {"n_with": len(w), "n_against": len(g), "n_none": n0,
                       "r_with": round(float(np.mean(w)), 2) if w else None, "r_against": round(float(np.mean(g)), 2) if g else None}
        out[feat] = row
    return out


def screen():
    out = {"_note": "eval = live two_week eval path; lit = LIT size rule; d_* = vs the reference", "refs": {}}
    for nm in REFS:
        R = ref(nm)
        out["refs"][nm] = {"eval": R.ev, "lit": R.lr}
        print(f"== reference {nm}: " + " | ".join(f"{s} net {R.ev[s]['net']:+,} PF {R.ev[s]['pf']} DD {R.ev[s]['dd']:,} {R.ev[s]['tpw']}/wk "
                                                f"2w {R.ev[s]['p10']}/{R.ev[s]['f10']} mc {R.ev[s]['mc_p10']}/{R.ev[s]['mc_f10']}"
                                                for s in ("H1", "H2")), flush=True)
        if nm == "base":
            out["flags"] = flag_stats(R)
            for feat, row in out["flags"].items():
                print(f"   {feat:10s} " + " | ".join(f"{sp} with {r['n_with']:3d} ({r['r_with']}) against {r['n_against']:3d} "
                                                     f"({r['r_against']}) none {r['n_none']}" for sp, r in row.items()), flush=True)
        for grp, fn in (("size", size_grid), ("target", target_grid), ("filter", filter_grid)):
            res = verdicts(R, fn(R))
            show(R, grp, res)
            out.setdefault(nm, {})[grp] = res
            json.dump(out, open(os.path.join(OUTD, "bias.json"), "w"), indent=1, default=float)
    return out


# ================================================================================================ follow-up: wider target with the bias
# The screen's best family: trades WITH the bias get a farther target (x tgt_m of the VIX-band distance, no 8R bank), trades
# against / without a bias keep today's target. Finer strengths, a version that keeps the 8R bank, AND / OR of two biases.
FU_FEATS = ["draw_pd", "draw_pdpw", "draw_all", "amd", "owk", "vote", "vote2", "ms_4h", "pdc_half", "and_dpd_amd", "or_dpd_amd"]
FU_ST = (1.1, 1.15, 1.2, 1.25, 1.3, 1.4)
FU_FAM = {"wide": lambda s: {"tgt_m": s, "max_rr": None}, "wide8": lambda s: {"tgt_m": s}}


def _derived(f):
    a, b = f["draw_pd"] > 0, f["amd"] > 0
    f["and_dpd_amd"] = 1 if (a and b) else 0
    f["or_dpd_amd"] = 1 if (a or b) else 0
    return f


def followup():
    out = {"refs": {}}
    for nm in REFS:
        R = ref(nm)
        R.f = [_derived(f) for f in R.f]
        out["refs"][nm] = {"eval": R.ev, "lit": R.lr}
        res = {}
        for fam, mk in FU_FAM.items():
            for s_ in FU_ST:
                cd_all = {t["day"]: mk(s_) for t in R.T}
                T = run_ref(nm, ctx_day=cd_all)
                U = AC.units(T)
                res[f"ALL {fam} {s_}"] = {"info": {"feat": "ALL", "use": "target", "fam": fam, "st": s_, "flag_h1": 99,
                                                   "flag_h2": 99, **changed(R.U, U)}, "eval": score_eval(U), "lit": score_lit(T)}
                for feat in FU_FEATS:
                    cd = {t["day"]: mk(s_) for t, f in zip(R.T, R.f) if f[feat] > 0}
                    T = run_ref(nm, ctx_day=cd)
                    assert trades_key(T) == R.key
                    U = AC.units(T)
                    info = {"feat": feat, "use": "target", "fam": fam, "st": s_,
                            "flag_h1": sum(1 for d in cd if "2026-01-01" <= d <= "2026-06-30"),
                            "flag_h2": sum(1 for d in cd if d >= "2026-07-01"), **changed(R.U, U)}
                    res[f"{feat} {fam} {s_}"] = {"info": info, "eval": score_eval(U), "lit": score_lit(T)}
        for lab, o in res.items():
            o["_g"] = gains(R, o)
        for lab, o in res.items():
            i = o["info"]
            o["nb_ok"] = neighbours(res, lab, o)
            o["strict"] = strict(o["_g"], i)
            al = res.get(f"ALL {i['fam']} {i['st']}")
            o["vs_all"] = {s: o["eval"][s]["net"] - al["eval"][s]["net"] for s in ("H1", "H2")} if i["feat"] != "ALL" else None
            o["adopt"] = bool(o["strict"] and o["nb_ok"] is not False and i["feat"] != "ALL"
                              and all(v > 0 for v in o["vs_all"].values()))
        show(R, "follow-up wide target", res, top=20)
        out[nm] = res
        json.dump(out, open(os.path.join(OUTD, "bias_followup.json"), "w"), indent=1, default=float)
    return out


def random_control(nm="base", feat="or_dpd_amd", fam="wide", st=1.25, n=100, seed=3):
    """Shuffle test for a bias-picked target change: the same change on random trade sets of the same size per half."""
    R = ref(nm)
    R.f = [_derived(f) for f in R.f]
    rng = np.random.default_rng(seed)
    mk = FU_FAM[fam]
    spans = {"H1": ("2026-01-01", "2026-06-30"), "H2": ("2026-07-01", "2026-12-31")}
    real = {sp: sum(1 for t, f in zip(R.T, R.f) if a <= t["day"] <= z and f[feat] > 0) for sp, (a, z) in spans.items()}
    days = {sp: [t["day"] for t in R.T if a <= t["day"] <= z] for sp, (a, z) in spans.items()}
    rows = []
    for _ in range(n):
        pick = set()
        for sp in spans:
            pick |= set(rng.choice(days[sp], size=real[sp], replace=False).tolist())
        T = run_ref(nm, ctx_day={d: mk(st) for d in pick})
        U = AC.units(T)
        e = score_eval(U)
        lr = score_lit(T)
        rows.append({s: {**{k: e[s][k] for k in ("net", "p10", "f10", "mc_f10")}, "lit": lr[s]["net"]} for s in ("H1", "H2")})
    o = json.load(open(os.path.join(OUTD, "bias_followup.json"), encoding="utf-8"))[nm][f"{feat} {fam} {st}"]
    b = R.ev
    dn1 = np.array([r["H1"]["net"] - b["H1"]["net"] for r in rows]); dn2 = np.array([r["H2"]["net"] - b["H2"]["net"] for r in rows])
    st_ok = [r["H1"]["net"] > b["H1"]["net"] and r["H2"]["net"] > b["H2"]["net"] and r["H1"]["p10"] >= b["H1"]["p10"]
             and r["H2"]["p10"] >= b["H2"]["p10"] and r["H1"]["f10"] <= b["H1"]["f10"] and r["H2"]["f10"] <= b["H2"]["f10"] for r in rows]
    g = o["_g"]
    res = {"n": n, "flagged": real, "real_d_net": [g["d_net_h1"], g["d_net_h2"]],
           "p_h1": round(float(np.mean(dn1 >= g["d_net_h1"])), 3), "p_h2": round(float(np.mean(dn2 >= g["d_net_h2"])), 3),
           "p_both": round(float(np.mean((dn1 >= g["d_net_h1"]) & (dn2 >= g["d_net_h2"]))), 3),
           "random_median_d_net": [round(float(np.median(dn1))), round(float(np.median(dn2)))],
           "real_d_lit": [g["d_lit_h1"], g["d_lit_h2"]],
           "p_lit_h1": round(float(np.mean(np.array([r["H1"]["lit"] - R.lr["H1"]["net"] for r in rows]) >= g["d_lit_h1"])), 3),
           "p_lit_h2": round(float(np.mean(np.array([r["H2"]["lit"] - R.lr["H2"]["net"] for r in rows]) >= g["d_lit_h2"])), 3),
           "random_median_d_lit": [round(float(np.median([r[s]["lit"] - R.lr[s]["net"] for r in rows]))) for s in ("H1", "H2")],
           "random_share_eval_test_passed": round(float(np.mean(st_ok)), 3)}
    print(f"random control {nm} {feat} {fam} {st}: {res}", flush=True)
    p = os.path.join(OUTD, "bias_random.json")
    allr = json.load(open(p, encoding="utf-8")) if os.path.exists(p) else {}
    allr[f"{nm} {feat} {fam} {st}"] = res
    json.dump(allr, open(p, "w"), indent=1)
    return res


def h1_pick(nm="base", top=5):
    """The honest pick: rank the follow-up variants on H1 only (eval net, H1 2-week fails not up), then read H2."""
    o = json.load(open(os.path.join(OUTD, "bias_followup.json"), encoding="utf-8"))[nm]
    rows = [(lab, v) for lab, v in o.items() if v["info"]["feat"] != "ALL" and v["_g"]["d_f10_h1"] <= 0 and v["_g"]["d_p10_h1"] >= 0]
    rows.sort(key=lambda kv: kv[1]["_g"]["d_net_h1"], reverse=True)
    out = []
    for lab, v in rows[:top]:
        g = v["_g"]
        out.append({"variant": lab, "d_net_h1": g["d_net_h1"], "d_net_h2": g["d_net_h2"], "d_p10": [g["d_p10_h1"], g["d_p10_h2"]],
                    "d_f10": [g["d_f10_h1"], g["d_f10_h2"]], "strict": v["strict"], "adopt": v["adopt"]})
        print(f"  H1 pick {nm}: {out[-1]}", flush=True)
    return out


# ================================================================================================ A+ checklist (discretion)
APLUS = [("major", "the sweep took a major level (PDH/PDL, PWH/PWL, PMH/PML or an opening-gap edge)", lambda f: f["_major"] == 1),
         ("disp", "strong displacement through structure (biggest body >= 1.2 ATR)", lambda f: f["_disp"] >= 1.2),
         ("idm", "inducement taken: 2+ inducement swings within 2 ATR / 48 bars", lambda f: f["_idm2"] >= 2),
         ("bias", "with the HTF bias (composite vote: draw, previous close, 4H structure, AMD, daily FVG)", lambda f: f["vote"] > 0),
         ("kz", "in a killzone (London 02:00-05:00 or NY 08:30-11:00 entry)", lambda f: f["_kz"] == 1),
         ("fresh", "fresh trap: the inducement swing was made <= 6 bars (30 min) before the sweep", lambda f: f["_idm_age"] <= 6),
         ("path", "clear path: no unfilled opposing 1H FVG between the entry and the target", lambda f: f["_fvway1h"] == 0)]


def aplus_score(f, items=None):
    return sum(1 for nm, _, fn in APLUS if (items is None or nm in items) and fn(f))


SPANS3 = (("H1", "2026-01-01", "2026-06-30"), ("H2", "2026-07-01", "2026-12-31"), ("ref", "2021-01-01", "2025-12-31"))


def aplus():
    out = {"items": [(nm, txt) for nm, txt, _ in APLUS], "refs": {}}
    for nm in REFS:
        R = ref(nm)
        sc = [aplus_score(f) for f in R.f]
        out["refs"][nm] = {"eval": R.ev, "lit": R.lr}
        tab = {}
        for sp, a, z in SPANS3:
            row = collections.defaultdict(list)
            for t, s_ in zip(R.T, sc):
                if a <= t["day"] <= z:
                    row[s_].append(t["r"])
            tab[sp] = {int(k_): {"n": len(v), "r": round(float(np.mean(v)), 2),
                                 "win": round(100 * float(np.mean([x > 0.5 for x in v])), 1)} for k_, v in sorted(row.items())}
        out.setdefault(nm, {})["by_score"] = tab
        if nm == "base":
            for sp, row in tab.items():
                print(f"   A+ score {sp}: " + "  ".join(f"{k_}:{v['n']}x{v['r']:+.2f}R" for k_, v in row.items()), flush=True)
            it = {}
            for inm, txt, fn in APLUS:
                r = {}
                for sp, a, z in SPANS3:
                    y = [t["r"] for t, f in zip(R.T, R.f) if a <= t["day"] <= z and fn(f)]
                    n_ = [t["r"] for t, f in zip(R.T, R.f) if a <= t["day"] <= z and not fn(f)]
                    r[sp] = {"n_yes": len(y), "r_yes": round(float(np.mean(y)), 2) if y else None, "n_no": len(n_),
                             "r_no": round(float(np.mean(n_)), 2) if n_ else None}
                it[inm] = r
                print(f"   item {inm:6s} " + " | ".join(f"{sp} yes {v['n_yes']} ({v['r_yes']}) no {v['n_no']} ({v['r_no']})"
                                                       for sp, v in r.items()), flush=True)
            out["items_r"] = it
        h1 = [s_ for t, s_ in zip(R.T, sc) if "2026-01-01" <= t["day"] <= "2026-06-30"]
        med = float(np.median(h1))
        res = {}
        for k_ in range(1, 7):
            for fam, (up, dn) in (("step", (1.25, 0.75)), ("step_strong", (1.5, 0.5)), ("cut", (1.0, 0.5)), ("up", (1.5, 1.0))):
                ms = [up if s_ >= k_ else dn for s_ in sc]
                res[f"A+ score >= {k_} {fam} {up}/{dn}"] = eval_ms(R, ms, {"feat": "aplus", "use": "size", "fam": "ap_" + fam, "st": k_})
        for a_ in (0.1, 0.2, 0.3):
            ms = [float(np.clip(1 + a_ * (s_ - med), 0.5, 1.5)) for s_ in sc]
            res[f"A+ linear {a_}/point around {med:g}"] = eval_ms(R, ms, {"feat": "aplus", "use": "size", "fam": "ap_lin", "st": a_})
        for inm, _, _ in APLUS:                 # leave one item out: is one item carrying the score?
            its = [x[0] for x in APLUS if x[0] != inm]
            sc2 = [aplus_score(f, its) for f in R.f]
            k2 = float(np.median([s_ for t, s_ in zip(R.T, sc2) if "2026-01-01" <= t["day"] <= "2026-06-30"]))
            ms = [1.25 if s_ > k2 else 0.75 if s_ < k2 else 1.0 for s_ in sc2]
            res[f"A+ without {inm}: above / below the H1 median {k2:g}"] = eval_ms(R, ms, {"feat": "aplus-" + inm, "use": "size",
                                                                                        "fam": None, "st": None})
        ms = [1.25 if s_ > med else 0.75 if s_ < med else 1.0 for s_ in sc]
        res[f"A+ above / below the H1 median {med:g} 1.25/0.75"] = eval_ms(R, ms, {"feat": "aplus", "use": "size", "fam": None, "st": None})
        res = verdicts(R, res)
        show(R, "A+", res, top=14)
        out[nm]["size"] = res
        json.dump(out, open(os.path.join(OUTD, "bias_aplus.json"), "w"), indent=1, default=float)
    return out


# ================================================================================================ meta-labeling
META_X = ["vote", "draw_pdpw", "pdc_half", "ms_4h", "amd", "ms_d", "_disp", "_depth", "_idm2", "_idm_age", "_risk", "_rr", "_vix",
          "_kz", "_major"]


def _X(fs):
    X = np.array([[float(f[c]) for c in META_X] for f in fs], float)
    X[:, META_X.index("_idm_age")] = np.minimum(X[:, META_X.index("_idm_age")], 48)
    X[~np.isfinite(X)] = 0.0
    return X


def logit_fit(X, y, lam=5.0, it=50):
    """L2 logistic regression (Newton) on standardised features."""
    mu, sd = X.mean(0), X.std(0) + 1e-9
    Z = np.c_[np.ones(len(X)), (X - mu) / sd]
    w = np.zeros(Z.shape[1])
    I = np.eye(Z.shape[1]); I[0, 0] = 0
    for _ in range(it):
        p = 1 / (1 + np.exp(-np.clip(Z @ w, -30, 30)))
        g = Z.T @ (p - y) + lam * I @ w
        Hs = (Z * (p * (1 - p))[:, None]).T @ Z + lam * I
        step = np.linalg.solve(Hs, g)
        w -= step
        if np.abs(step).max() < 1e-8:
            break
    return lambda Xn: 1 / (1 + np.exp(-np.clip(np.c_[np.ones(len(Xn)), (Xn - mu) / sd] @ w, -30, 30)))


def gbm_fit(X, y, rounds=60, lr=0.1):
    """Gradient boosting of depth-1 stumps on the log loss (thresholds at feature deciles, >= 10 trades a side)."""
    f0 = np.log((y.mean() + 1e-6) / (1 - y.mean() + 1e-6))
    F_ = np.full(len(y), f0)
    ths = [np.unique(np.quantile(X[:, j], np.linspace(0.1, 0.9, 9))) for j in range(X.shape[1])]
    stumps = []
    for _ in range(rounds):
        p = 1 / (1 + np.exp(-F_))
        g = y - p
        h = np.maximum(p * (1 - p), 1e-6)
        best = None
        for j in range(X.shape[1]):
            for th in ths[j]:
                L = X[:, j] <= th
                if L.sum() < 10 or (~L).sum() < 10:
                    continue
                gl, hl, gr, hr = g[L].sum(), h[L].sum(), g[~L].sum(), h[~L].sum()
                gain = gl * gl / (hl + 1) + gr * gr / (hr + 1)
                if best is None or gain > best[0]:
                    best = (gain, j, th, gl / (hl + 1), gr / (hr + 1))
        if best is None:
            break
        _, j, th, vl, vr = best
        F_ += lr * np.where(X[:, j] <= th, vl, vr)
        stumps.append((j, th, vl, vr))

    def pred(Xn):
        s_ = np.full(len(Xn), f0)
        for j, th, vl, vr in stumps:
            s_ += lr * np.where(Xn[:, j] <= th, vl, vr)
        return 1 / (1 + np.exp(-s_))
    return pred


def auc(y, p):
    y = np.asarray(y); p = np.asarray(p, float)
    pos, neg = p[y == 1], p[y == 0]
    if not len(pos) or not len(neg):
        return None
    r = pd.Series(np.r_[pos, neg]).rank().values
    return float((r[:len(pos)].sum() - len(pos) * (len(pos) + 1) / 2) / (len(pos) * len(neg)))


SCHEMES = {"A: train 2021-25, test 2026 H1+H2": (("2021-01-01", "2025-12-31"), ("2026-01-01", "2026-12-31")),
           "B: train 2021-25 + H1, test H2": (("2021-01-01", "2026-06-30"), ("2026-07-01", "2026-12-31")),
           "C: train H1, test H2": (("2026-01-01", "2026-06-30"), ("2026-07-01", "2026-12-31")),
           "D: monthly walk-forward 2026 (train on everything before the month)": None}


def _preds(R, fit, scheme, perm_rng=None):
    """Out-of-sample win probability for every engine trade of R in the scheme's test span (None outside it) and the training
    terciles of the predictions (the size lines)."""
    T, Fs = R.T, R.f
    X = _X(Fs)
    y = np.array([float(t["r"] > 0.5) for t in T], float)
    days = np.array([t["day"] for t in T])
    P, TH = [None] * len(T), [None] * len(T)
    if SCHEMES[scheme] is None:
        months = sorted({d[:7] for d in days if d >= "2026-01-01"})
        blocks = [(("2021-01-01", f"{m}-00"), (f"{m}-01", f"{m}-31")) for m in months]
    else:
        blocks = [SCHEMES[scheme]]
    for (a, z), (ta, tz) in blocks:
        tr = (days >= a) & (days <= z)
        te = (days >= ta) & (days <= tz)
        yt = y[tr].copy()
        if perm_rng is not None:
            perm_rng.shuffle(yt)
        mdl = fit(X[tr], yt)
        ptr = mdl(X[tr])
        lo, hi = np.quantile(ptr, 1 / 3), np.quantile(ptr, 2 / 3)
        pte = mdl(X[te])
        for q, j in enumerate(np.flatnonzero(te)):
            P[j] = float(pte[q]); TH[j] = (lo, hi)
    return P, TH, y


def _ms_of(P, TH, up, dn):
    return [1.0 if p is None else (up if p >= th[1] else dn if p <= th[0] else 1.0) for p, th in zip(P, TH)]


FITS = {"logistic": lambda X, y: logit_fit(X, y), "gbm": lambda X, y: gbm_fit(X, y)}


def meta(n_perm=200, seed=11):
    """Meta-labeling on the base trades (label: a winner, r > 0.5), predictions mapped to each reference's trades by setup."""
    out = {"features": META_X, "refs": {}}
    R0 = ref("base")
    rng = np.random.default_rng(seed)
    PR = {}
    for sch in SCHEMES:
        for fn_nm, fit in FITS.items():
            PR[(sch, fn_nm)] = _preds(R0, fit, sch)
    for nm in REFS:
        R = ref(nm)
        out["refs"][nm] = {"eval": R.ev, "lit": R.lr}
        yy = np.array([float(t["r"] > 0.5) for t in R.T])
        res = {}
        for (sch, fn_nm), (P, TH, _y) in PR.items():
            pmap = {key_of(t): (p, th) for t, p, th in zip(R0.T, P, TH)}
            PP = [pmap.get(key_of(t), (None, None)) for t in R.T]
            P2, TH2 = [p for p, _ in PP], [th for _, th in PP]
            info_auc = {}
            for sp, a, z, in SPANS3[:2]:
                jj = [j for j, t in enumerate(R.T) if a <= t["day"] <= z and P2[j] is not None]
                v = auc(yy[jj], [P2[j] for j in jj]) if len(jj) > 10 else None
                info_auc[sp] = round(v, 3) if v is not None else None
            for up, dn in ((1.25, 0.75), (1.5, 0.5)):
                ms = _ms_of(P2, TH2, up, dn)
                lab = f"{sch[:1]} {fn_nm} {up}/{dn}"
                o = eval_ms(R, ms, {"feat": "meta", "use": "size", "fam": None, "st": None, "scheme": sch, "model": fn_nm,
                                    "auc": info_auc})
                o["_g"] = gains(R, o)
                if nm == "base" and up == 1.25 and (fn_nm == "logistic" or sch[0] in "AB"):
                    npm = n_perm if fn_nm == "logistic" else 30
                    d1, d2, a2 = [], [], []
                    for _ in range(npm):
                        Pp, THp, _y2 = _preds(R0, FITS[fn_nm], sch, perm_rng=rng)
                        op = eval_ms(R, _ms_of(Pp, THp, up, dn), {})
                        d1.append(op["eval"]["H1"]["net"] - R.ev["H1"]["net"])
                        d2.append(op["eval"]["H2"]["net"] - R.ev["H2"]["net"])
                        jj = [j for j, t in enumerate(R.T) if t["day"] >= "2026-07-01" and Pp[j] is not None]
                        a2.append(auc(yy[jj], [Pp[j] for j in jj]))
                    g = o["_g"]
                    o["perm"] = {"n": npm, "p_net_h2": round(float(np.mean(np.array(d2) >= g["d_net_h2"])), 3),
                                 "p_net_h1": round(float(np.mean(np.array(d1) >= g["d_net_h1"])), 3) if sch[0] in "AD" else None,
                                 "p_auc_h2": round(float(np.mean(np.array(a2) >= (info_auc["H2"] or 0))), 3),
                                 "shuffle_net_h2_median": round(float(np.median(d2))), "shuffle_auc_h2_median": round(float(np.median(a2)), 3)}
                res[lab] = o
                g = o["_g"]
                print(f"   {nm} {lab:22s} AUC H1 {info_auc['H1']} H2 {info_auc['H2']} dnet {g['d_net_h1']:+7,}/{g['d_net_h2']:+7,} "
                      f"2w pass {g['d_p10_h1']:+5}/{g['d_p10_h2']:+5} fail {g['d_f10_h1']:+5}/{g['d_f10_h2']:+5} mcf "
                      f"{g['d_mcf_h1']:+5}/{g['d_mcf_h2']:+5} LIT {g['d_lit_h1']:+7,}/{g['d_lit_h2']:+7,} perm {o.get('perm')}", flush=True)
        for lab, o in res.items():
            o["strict"] = strict(o["_g"], o["info"])
            o["oos_halves"] = "H1+H2" if lab[0] in "AD" else "H2"
            pm = o.get("perm") or {}
            o["adopt"] = bool(o["strict"] and lab[0] in "AD" and (pm.get("p_net_h2", 0) <= 0.05 if pm else True))
            o["nb_ok"] = None
        out[nm] = res
        json.dump(out, open(os.path.join(OUTD, "bias_meta.json"), "w"), indent=1, default=float)
    return out


def engine_check(tgt_m=1.25):
    """engine/lit.py bias_with == the research features on every live-eligible setup, and the engine option bias_tgt ==
    the research ctx_day run trade for trade (both references, all years)."""
    M, C = market()
    Fx = feats()
    bad = 0
    n = 0
    for z in C:
        k_ = (z["day"], int(z["i"]), int(z["dir"]))
        if k_ not in Fx:
            continue
        f = _derived(dict(Fx[k_]))
        n += 1
        for feat, ref_v in (("draw_pd", f["draw_pd"]), ("amd", f["amd"])):
            bad += lit.bias_with(M, z, feat) != ref_v
        bad += (lit.bias_with(M, z, "or_dpd_amd") > 0) != (f["or_dpd_amd"] > 0)
    print(f"bias_with == research features: {n * 3 - bad}/{n * 3}", flush=True)
    ok = bad == 0
    for nm in REFS:
        R = ref(nm)
        R.f = [_derived(f) for f in R.f]
        cd = {t["day"]: {"tgt_m": tgt_m, "max_rr": None} for t, f in zip(R.T, R.f) if f["or_dpd_amd"] > 0}
        Ta = run_ref(nm, ctx_day=cd)
        Tb = run_ref(nm, bias_tgt={"feat": "or_dpd_amd", "tgt_m": tgt_m, "max_rr": None})
        same = len(Ta) == len(Tb) and all(a["day"] == b["day"] and a["entry_t"] == b["entry_t"] and a["exit"] == b["exit"]
                                          and abs(a["pnl"] - b["pnl"]) < 1e-6 and a["target_px"] == b["target_px"]
                                          for a, b in zip(Ta, Tb))
        print(f"{nm}: engine bias_tgt == research ctx_day: {same} ({len(Tb)} trades)", flush=True)
        ok = ok and same
    return ok


# ================================================================================================ write-up tables
def _row(lab, o):
    g = o["_g"]
    v = "ADOPT-CAND" if o.get("adopt") else ("strict only" if o.get("strict") else ("both halves $ up" if loose(g) else "reject"))
    return (f"| {lab} | {g['d_net_h1']:+,} | {g['d_net_h2']:+,} | {g['d_p10_h1']:+.1f} / {g['d_p10_h2']:+.1f} | "
            f"{g['d_f10_h1']:+.1f} / {g['d_f10_h2']:+.1f} | {g['d_lit_h1']:+,} / {g['d_lit_h2']:+,} | {g['d_lit_ref']:+,} | "
            f"{g['tpw_h1']} / {g['tpw_h2']} | {v} |")


HDR = ("| Variant | Eval net H1 vs ref | Eval net H2 vs ref | 2-wk pass H1 / H2 (pts) | 2-wk fail H1 / H2 (pts) | "
       "LIT size rule H1 / H2 $ | 2021-25 $ | Trades/wk H1 / H2 | Verdict |\n|---|---:|---:|---:|---:|---:|---:|---:|---|")


def table(nm="base"):
    """Per bias method: the best size tilt, the best target change and the filter (by the worse half), markdown."""
    S_ = json.load(open(os.path.join(OUTD, "bias.json"), encoding="utf-8"))
    lines = [HDR]
    for feat in BIAS:
        for grp in ("size", "target", "filter"):
            res = {k_: v for k_, v in S_[nm][grp].items() if v["info"]["feat"] == feat}
            if not res:
                continue
            lab, o = max(res.items(), key=lambda kv: min(kv[1]["_g"]["d_net_h1"], kv[1]["_g"]["d_net_h2"]))
            lines.append(_row(lab, o))
    print("\n".join(lines))
    return "\n".join(lines)


def counts():
    out = {}
    for fn, grp_of in (("bias.json", ("size", "target", "filter")), ("bias_followup.json", None), ("bias_aplus.json", ("size",)),
                       ("bias_meta.json", None)):
        p = os.path.join(OUTD, fn)
        if not os.path.exists(p):
            continue
        S_ = json.load(open(p, encoding="utf-8"))
        for nm in REFS:
            for grp in (grp_of or (None,)):
                res = S_[nm][grp] if grp else S_[nm]
                res = {k_: v for k_, v in res.items() if isinstance(v, dict) and "_g" in v}
                k_ = f"{fn[:-5]} {nm} {grp or ''}".strip()
                out[k_] = {"n": len(res), "both_up": sum(1 for v in res.values() if loose(v["_g"])),
                           "strict": sum(1 for v in res.values() if v.get("strict")), "adopt": sum(1 for v in res.values() if v.get("adopt"))}
                print(k_, out[k_])
    return out


# ================================================================================================ store (rl.save)
def _he(e, s):
    x = e[s]
    return (f"n={x['n']} {x['tpw']}/wk PF {x['pf']} net {x['net']:+,} (${x['per_month']:,}/mo) DD {x['dd']:,}; 2-week pass/fail "
            f"{x['p10']}/{x['f10']} (Monte Carlo {x['mc_p10']}/{x['mc_f10']}), 1 month {x['p20']}/{x['f20']}")


def _slug(s):
    import re
    return re.sub(r"[^a-z0-9]+", "_", s.lower()).strip("_")[:56]


def rebuild(nm, grp, lab, o):
    """(engine trades, eval units, extra params) of a stored variant."""
    R = ref(nm)
    i = o["info"]
    if grp == "size" and i["feat"] in BIAS:
        mw, mn, ma = SIZE[(i["fam"], i["st"])]
        ms = [mw if f[i["feat"]] > 0 else ma if f[i["feat"]] < 0 else mn for f in R.f]
        TT, UU = apply_m(R, ms)
        return TT, UU, {"bias_size": f"{i['feat']} with x{mw} / against x{ma}"}
    if grp == "target":
        cd = ctx_of(R, i["feat"], TGT[(i["fam"], i["st"])]) if i["feat"] != "ALL" else \
            {t["day"]: dict(TGT[(i["fam"], i["st"])][0] or TGT[(i["fam"], i["st"])][1]) for t in R.T}
        T = run_ref(nm, ctx_day=cd)
        return T, AC.units(T), {"ctx_day": f"{len(cd)} days ({lab})"}
    if grp == "followup":
        R.f = [_derived(f) for f in R.f]
        mk = FU_FAM[i["fam"]]
        cd = {t["day"]: mk(i["st"]) for t, f in zip(R.T, R.f) if i["feat"] == "ALL" or f[i["feat"]] > 0}
        T = run_ref(nm, ctx_day=cd)
        return T, AC.units(T), {"ctx_day": f"{len(cd)} days ({lab}: target x{i['st']}"
                                           f"{', no 8R bank' if i['fam'] == 'wide' else ''} on trades with the bias)"}
    if grp == "filter":
        sk = [list(k_) for k_, f in feats().items() if f[i["feat"]] < 0]
        T = run_ref(nm, skip_keys=sk)
        return T, AC.units(T), {"skip_keys": f"{len(sk)} setups against {i['feat']}"}
    if grp == "aplus":
        sc = [aplus_score(f) for f in R.f]
        if i.get("fam") and i["fam"].startswith("ap_") and i["fam"] != "ap_lin":
            up, dn = {"ap_step": (1.25, 0.75), "ap_step_strong": (1.5, 0.5), "ap_cut": (1.0, 0.5), "ap_up": (1.5, 1.0)}[i["fam"]]
            ms = [up if s_ >= i["st"] else dn for s_ in sc]
        else:
            med = float(np.median([s_ for t, s_ in zip(R.T, sc) if "2026-01-01" <= t["day"] <= "2026-06-30"]))
            ms = [float(np.clip(1 + i["st"] * (s_ - med), 0.5, 1.5)) for s_ in sc] if i.get("fam") == "ap_lin" else \
                [1.25 if s_ > med else 0.75 if s_ < med else 1.0 for s_ in sc]
        TT, UU = apply_m(R, ms)
        return TT, UU, {"bias_size": lab}
    if grp == "meta":
        R0 = ref("base")
        P, TH, _y = _preds(R0, FITS[i["model"]], i["scheme"])
        pmap = {key_of(t): (p, th) for t, p, th in zip(R0.T, P, TH)}
        PP = [pmap.get(key_of(t), (None, None)) for t in R.T]
        up, dn = (1.25, 0.75) if "1.25" in lab else (1.5, 0.5)
        ms = _ms_of([p for p, _ in PP], [th for _, th in PP], up, dn)
        TT, UU = apply_m(R, ms)
        return TT, UU, {"bias_size": lab}
    raise ValueError((grp, lab))


LEADS = ("amd wide 1.25", "or_dpd_amd wide 1.25")   # the study's leads (promising, not adopted)


def _store_one(Q, nm, grp, lab, o, refev):
    T, U, extra = rebuild(nm, grp, lab, o)
    A._MC.clear()
    Tp = []
    for sp in ("H1", "H2"):
        Tp += A.b2b(U, sp)[0]
    for t in Tp:
        t["risk_pts"] = t["risk"]; t["r"] = round(t["pnl"] / t["risk_usd"], 3) if t["risk_usd"] else 0.0
        t.update(half=False, trigger="LIT-1m", mfe=None, mae=None, bars_held=None, regime="", mult=None, tgt_pts=t["tgt"])
    e, b = o["eval"], refev
    g = o.get("_g") or {}
    st = "promising" if (o.get("adopt") or (grp == "followup" and lab in LEADS and loose(g))) else "rejected"   # not adopted (write-up)
    P = {**lit.DEFAULTS, **AC.LIVE, **REFS[nm], **extra}
    rid = "lit_bias_" + ("" if nm == "base" else "all3_") + grp + "_" + _slug(lab)
    rl.save(rid, f"LIT {'live' if nm == 'base' else '+ all3'} + bias {grp}: {lab}", "risk" if grp != "target" else "management", Q,
            params=P, sizing={"mode": "two_week", **A.CFG}, trades=Tp, scored=rl.score(Tp, A.S26), status=st,
            verdict=f"Eval path (two_week 10 sessions then safe_eval, no reset, $1.90, true 1m). H1 (pick) {_he(e, 'H1')}. "
                    f"H2 (check) {_he(e, 'H2')}. Reference {nm}: H1 net {b['H1']['net']:+,} 2-week {b['H1']['p10']}/{b['H1']['f10']}, "
                    f"H2 net {b['H2']['net']:+,} 2-week {b['H2']['p10']}/{b['H2']['f10']}. LIT size rule change H1 "
                    f"{g.get('d_lit_h1', 0):+,} H2 {g.get('d_lit_h2', 0):+,}, 2021-25 reference {g.get('d_lit_ref', 0):+,}. "
                    f"Strict test: {o.get('strict')}; neighbours hold: {o.get('nb_ok')}.",
            notes="tools/lit_bias.py (stored trades = the back-to-back eval path per half).", writeup="lit-bias-discretion",
            tags=["lit", "lit_bias"])
    print("saved", rid, st, flush=True)
    return rid


def save(top=3):
    Q = ("Owner 2026-10-20: trading with bias and discretion - daily-bias methods, an A+ checklist and meta-labeling as size, "
         "target or filter on today's LIT, on the real eval path, alone and on top of t_check + scale_in + be_off.")
    saved = []
    S_ = json.load(open(os.path.join(OUTD, "bias.json"), encoding="utf-8"))
    # the references on the eval path
    for nm in REFS:
        R = ref(nm)
        o = {"info": {"feat": "none"}, "eval": R.ev, "adopt": False, "strict": None, "nb_ok": None, "_g": {}}
        A._MC.clear()
        Tp = []
        for sp in ("H1", "H2"):
            Tp += A.b2b(R.U, sp)[0]
        for t in Tp:
            t["risk_pts"] = t["risk"]; t["r"] = round(t["pnl"] / t["risk_usd"], 3) if t["risk_usd"] else 0.0
            t.update(half=False, trigger="LIT-1m", mfe=None, mae=None, bars_held=None, regime="", mult=None, tgt_pts=t["tgt"])
        rid = "lit_bias_ref_" + nm
        rl.save(rid, f"LIT {'live' if nm == 'base' else '+ all3'} on the eval path (bias study reference)", "risk", Q,
                params={**lit.DEFAULTS, **AC.LIVE, **REFS[nm]}, sizing={"mode": "two_week", **A.CFG}, trades=Tp,
                scored=rl.score(Tp, A.S26), status="info", verdict=f"H1 {_he(R.ev, 'H1')}. H2 {_he(R.ev, 'H2')}.",
                notes="tools/lit_bias.py reference", writeup="lit-bias-discretion", tags=["lit", "lit_bias"])
        saved.append(rid)
        _ = o
    for nm in REFS:
        for grp in ("size", "target", "filter"):
            res = S_[nm][grp]
            pick = sorted(res.items(), key=lambda kv: min(kv[1]["_g"]["d_net_h1"], kv[1]["_g"]["d_net_h2"]), reverse=True)[:top]
            pick += [(lab, o) for lab, o in res.items() if o["adopt"] and (lab, o) not in pick]
            for lab, o in pick:
                saved.append(_store_one(Q, nm, grp, lab, o, S_["refs"][nm]["eval"]))
    for fn, grp in (("bias_aplus.json", "aplus"), ("bias_meta.json", "meta"), ("bias_followup.json", "followup")):
        p = os.path.join(OUTD, fn)
        if not os.path.exists(p):
            continue
        S2 = json.load(open(p, encoding="utf-8"))
        for nm in REFS:
            res = S2[nm]["size"] if grp == "aplus" else S2[nm]
            if grp == "followup":
                res = {k_: v for k_, v in res.items() if v["info"]["feat"] != "ALL"}
            pick = sorted(res.items(), key=lambda kv: min(kv[1]["_g"]["d_net_h1"], kv[1]["_g"]["d_net_h2"]), reverse=True)[:top]
            pick += [(lab, o) for lab, o in res.items() if (o.get("adopt") or lab in ("or_dpd_amd wide 1.25", "amd wide 1.25"))
                     and (lab, o) not in pick]
            for lab, o in pick:
                saved.append(_store_one(Q, nm, grp, lab, o, S2["refs"][nm]["eval"]))
    print(len(saved), "runs saved")
    return saved


if __name__ == "__main__":
    cmd = sys.argv[1] if len(sys.argv) > 1 else "screen"
    if cmd == "feats":
        feats(force=True)
    elif cmd == "lookahead":
        lookahead()
    elif cmd == "screen":
        screen()
    elif cmd == "aplus":
        aplus()
    elif cmd == "meta":
        meta()
    elif cmd == "followup":
        followup()
    elif cmd == "random":
        a_ = sys.argv[2:] + [None] * 4
        random_control(a_[0] or "base", a_[1] or "or_dpd_amd", a_[2] or "wide", float(a_[3] or 1.25))
    elif cmd == "engine":
        raise SystemExit(0 if engine_check() else 1)
    elif cmd == "table":
        table(sys.argv[2] if len(sys.argv) > 2 else "base")
    elif cmd == "counts":
        counts()
    elif cmd == "h1pick":
        for nm in REFS:
            h1_pick(nm)
    elif cmd == "save":
        save()
    elif cmd == "save_one":                    # e.g. save_one all3 followup "amd wide 1.25"
        nm_, grp_, lab_ = sys.argv[2], sys.argv[3], sys.argv[4]
        fn_ = {"followup": "bias_followup.json", "aplus": "bias_aplus.json", "meta": "bias_meta.json"}.get(grp_, "bias.json")
        S_ = json.load(open(os.path.join(OUTD, fn_), encoding="utf-8"))
        res_ = S_[nm_]["size"] if grp_ == "aplus" else S_[nm_] if grp_ in ("followup", "meta") else S_[nm_][grp_]
        _store_one("Owner 2026-10-20: trading with bias and discretion (see lit-bias-discretion).", nm_, grp_, lab_, res_[lab_],
                   S_["refs"][nm_]["eval"])
    else:
        raise SystemExit(__doc__)
