"""Win / loss anatomy (owner 2026-11-18: "See why our losses lose for strategies. And why they win. I expect all of our
strategies to be better."). research/writeups/win-loss-anatomy-2026-11-18.md, phone page tools/web_public/why/.

RESEARCH ONLY: it never trades, never routes, never edits a live file (live_model*.json, second_model.json,
data/account_b.json are hashed before and after `rules`). Nothing is re-implemented: the trades are the repo's own
backtests, costs in:
  Zlarior (LIT)  tools/lit_edge.ctx()["T"] = run lit_live (the live loop's backtest, 631 trades: 2026 on true 1m fills,
                 2021-25 on 5m), the LIT size rule ($800 up to a 20-pt stop), its 57 entry facts (research/lab/trade_intel.json).
  ATLAS          tools/atlas.account_units(BASE) = the EMA / MACD / S-R members after the account-B no-hedge rules (1,288
                 trades 2021-26), facts of tools/atlas_deep.feats, $ at a fixed $250 a trade (the funded 25K size).
  BLITZ          tools/scalp_na_lib.lines(prng >= 0.8) = the live BLITZ rule (2026 on 1m: na_best_trades.json, 329 of its 330
                 trades sit on a bar of the LIT 1m set; 2021-25 on 5m), $ at its research size ($150 a trade, at least 1
                 micro: scalp_na_lib.stats). Hidden + paper: diagnosis only.

Per trade (build): MAE / MFE in R and $ and the minutes to each, minutes in the trade, exit, ET time / session / weekday,
VIX band, range before the entry and the overnight range (in daily ATR), the 18:00 and 09:30 gaps with the trade, the place
in the prior day's range and the distance to the prior-day high / low on the target side (R), daily trend (close vs its
20-day SMA) and 1h trend (EMA 20 vs 50) with / against the trade, the prior 5 days' efficiency ratio (chop vs trend),
minutes to / since the nearest high-impact US release and a release inside the trade, ES's 1h trend with / against
(ES 5m from 2025-04), the strategy's own setup facts, and what came after the exit (best price later that session in R,
the target reached after a stop, the move 30 / 60 minutes after the exit, "a stop 50% wider would have reached the
target first"). Hindsight facts are marked and never used by a rule.

Why (explain): every loss gets ONE main cause ($-weighted shares): news hit / shaken out then it went our way / worked then
turned / never worked; context tags compared on losers AND winners; the "careful human" checklist (pre-declared, entry
facts only) splits losers into "good trades that lost" and "a careful human would have skipped it", and counts the
winners the same checklist would have skipped too; consistent buckets (worse than the strategy's average in Jan-Jun,
Jul-Oct AND 2021-25) against a shuffled-R control (how many such buckets chance alone makes).

Rules (rules): the strongest findings as pre-declared single versions (RULES below), judged by the repo's own gates:
Zlarior = tools/lit_edge.evaluate (LIT size + the live two_week eval path) + engine/learn_loop.judge_lit (picked on 2026
Jan-Jun, checked on Jul-Oct, eval fails not up, 2-4 trades a week, enough trades changed, the 200-draw size shuffle);
ATLAS = tools/atlas_deep.score (the real account-B rules) + tools/atlas_v2.verdict + learn_loop.judge_atlas (2021-25 a
gate). Then the ZEUS Lab's sign-flip placebo under its many-tests bar (tools/zeus_lab.proof).

    python -X utf8 tools/win_loss_anatomy.py build      # per-trade tables -> research/anatomy/trades_<bot>.json (~1 min)
    python -X utf8 tools/win_loss_anatomy.py explain    # causes, tags, checklist -> research/anatomy/explain.json
    python -X utf8 tools/win_loss_anatomy.py rules      # the RULES on the real backtests -> research/anatomy/rules.json
    python -X utf8 tools/win_loss_anatomy.py register   # RULES -> the ZEUS Lab registry (tools/zeus_lab.register)
    python -X utf8 tools/win_loss_anatomy.py page       # the phone page data -> tools/web_public/why/why.json
    python -X utf8 tools/win_loss_anatomy.py all        # build + explain + rules + page
Test: python -X utf8 -m tests.test_why_page (offline: the page data, the page, the pure helpers).
"""
from __future__ import annotations

import collections
import datetime as dt
import json
import math
import os
import sys
from zoneinfo import ZoneInfo

import numpy as np

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if ROOT not in sys.path:
    sys.path.insert(0, ROOT)

ET = ZoneInfo("America/New_York")
OUT_DIR = os.path.join(ROOT, "research", "anatomy")
PAGE = os.path.join(ROOT, "tools", "web_public", "why", "why.json")
WRITEUP = "research/writeups/win-loss-anatomy-2026-11-18.md"
VERSION = 1
SPANS = {"H1": ("2026-01-01", "2026-06-30"), "H2": ("2026-07-01", "2026-12-31"), "2021-25": ("2021-01-01", "2025-12-31")}
SPAN_WORD = {"H1": "Jan-Jun 2026", "H2": "Jul-Oct 2026", "2021-25": "2021-25"}
BOTS = ("lit", "atlas", "blitz")
NAME = {"lit": "Zlarior", "atlas": "ATLAS", "blitz": "BLITZ"}
ATLAS_RISK = 250.0             # $ a trade for ATLAS (the funded 25K size = the ZEUS Lab's atlas_risk_usd)
BLITZ_RISK = 150.0             # $ a trade for BLITZ (its research size)
FLAT = 955                     # 15:55 ET: every bot is flat by then
DAY0 = 1080                    # 18:00 ET: the CME day starts
WIDER = 0.5                    # the "a stop 50% wider" diagnostic (the live stop stays 1 tick beyond the sweep: hard rule)
CAUSES = ("news", "wick", "turned", "never")
CAUSE_WORD = {"news": "a high-impact news release hit it",
              "wick": "shaken out, then price went on to our target (BLITZ: to +1R)",
              "turned": "it worked (+0.5R or more), then turned and lost",
              "never": "it never worked (less than +0.5R in our favour)"}
# the careful-human checklist (written before the first run; entry facts only, classic discretionary rules, no data mining)
CHECKS = (("against_htf", "against the daily AND the 1h trend"),
          ("late", "late: the day had already moved 1 daily ATR or more before the entry"),
          ("news_soon", "a high-impact release within 30 minutes after the entry"),
          ("no_room", "the prior-day high / low sits less than 1R ahead on the target side"))


# ================================================================================================ small helpers (pure)
def _num(v):
    try:
        x = float(v)
        return x if x == x and abs(x) != float("inf") else None
    except (TypeError, ValueError):
        return None


def money(x) -> str:
    x = _num(x)
    if x is None:
        return "-"
    return ("-" if x < 0 else "+") + f"${abs(x):,.0f}"


def span_of(day: str):
    for s, (a, z) in SPANS.items():
        if a <= str(day) <= z:
            return s
    return None


def session_of(mod: int) -> str:
    m = int(mod)
    if m >= DAY0 or m < 120:
        return "Asia 18-02"
    if m < 300:
        return "London 02-05"
    if m < 480:
        return "London late 05-08"
    if m < 570:
        return "NY pre 08-09:30"
    if m < 690:
        return "NY AM 09:30-11:30"
    if m < 810:
        return "NY lunch 11:30-13:30"
    return "NY PM 13:30-16"


def vix_band(v) -> str | None:
    v = _num(v)
    if v is None:
        return None
    return "VIX <15" if v < 15 else "VIX 15-20" if v < 20 else "VIX 20-25" if v < 25 else "VIX 25+"


def side_word(x) -> str | None:
    x = _num(x)
    if x is None or x == 0:
        return None
    return "with" if x > 0 else "against"


def et(ts) -> dt.datetime:
    return dt.datetime.fromtimestamp(int(ts), ET)


def et_mod(ts) -> int:
    x = et(ts)
    return x.hour * 60 + x.minute


def since18(mod: int) -> int:
    """Minutes since 18:00 ET (the CME day's start) of an ET minute of the day."""
    return (int(mod) - DAY0) % 1440


def cause_of(r: dict) -> str | None:
    """The main cause of one losing trade (None for a trade that did not lose $). Order: news, wick, turned, never."""
    if (_num(r.get("usd")) or 0.0) >= 0:
        return None
    if r.get("news_in"):
        return "news"
    back = r.get("post_tgt_clean") if r.get("post_tgt_clean") is not None else r.get("post_1r_clean")
    if r.get("exit") in ("STOP", "CUT") and back:
        return "wick"
    if (_num(r.get("mfe_r")) or 0.0) >= 0.5:
        return "turned"
    return "never"


def checks_of(r: dict) -> list:
    """The careful-human checklist flags of one trade (entry facts only)."""
    out = []
    if r.get("d1") == "against" and r.get("h1") == "against":
        out.append("against_htf")
    x = _num(r.get("rng_atr"))
    if x is not None and x >= 1.0:
        out.append("late")
    x = _num(r.get("news_next"))
    if x is not None and 0 <= x <= 30:
        out.append("news_soon")
    x = _num(r.get("pd_tgt_r"))
    if x is not None and 0 < x < 1.0:
        out.append("no_room")
    return out


def agg(rows: list, usd="usd") -> dict:
    """n, win %, avg R, PF, $ of a list of rows."""
    if not rows:
        return {"n": 0, "win": None, "avg_r": None, "pf": None, "usd": 0}
    u = [float(r[usd]) for r in rows]
    R = [float(r["r"]) for r in rows]
    g, l = sum(x for x in u if x > 0), -sum(x for x in u if x < 0)
    return {"n": len(rows), "win": round(100.0 * sum(1 for x in u if x > 0) / len(u), 1), "avg_r": round(sum(R) / len(R), 3),
            "pf": round(g / l, 2) if l else None, "usd": round(sum(u))}


# ================================================================================================ market context (data)
class Mkt:
    """The LIT research market (tools/lit_edge.ctx: 5m market M + 1m / 5m bar containers) and the day facts built on it."""

    def __init__(self):
        from tools import lit_edge as E
        self.E = E
        c = E.ctx()
        self.c = c
        self.M = M = c["M"]
        self.B1, self.B5 = c[60].B, c[300].B
        self.dix = {str(d): k for k, (d, s, e) in enumerate(M.days)}
        n = len(M.days)
        O18, C, H, L = (np.zeros(n) for _ in range(4))
        RO, RC, RH, RL = (np.full(n, np.nan) for _ in range(4))
        ONH, ONL = np.full(n, np.nan), np.full(n, np.nan)
        for k, (d, s, e) in enumerate(M.days):
            O18[k], C[k] = M.o[s], M.c[e - 1]
            H[k], L[k] = M.h[s:e].max(), M.l[s:e].min()
            md = M.mod[s:e]
            rth = np.where((md >= 570) & (md < 960))[0]
            if len(rth):
                a, z = s + rth[0], s + rth[-1]
                RO[k], RC[k] = M.o[a], M.c[z]
                RH[k], RL[k] = M.h[a:z + 1].max(), M.l[a:z + 1].min()
            on = np.where((md >= DAY0) | (md < 570))[0]
            if len(on):
                ONH[k], ONL[k] = M.h[s + on].max(), M.l[s + on].min()
        self.O18, self.C, self.H, self.L = O18, C, H, L
        self.RO, self.RC, self.RH, self.RL, self.ONH, self.ONL = RO, RC, RH, RL, ONH, ONL
        pc = np.r_[C[0], C[:-1]]
        TR = np.maximum(H, pc) - np.minimum(L, pc)
        self.atr = np.full(n, np.nan)
        self.er5 = np.full(n, np.nan)
        self.d1 = np.zeros(n)
        for k in range(n):
            if k >= 14:
                self.atr[k] = TR[k - 14:k].mean()
            if k >= 6:
                path = np.abs(np.diff(C[k - 6:k])).sum()
                self.er5[k] = abs(C[k - 1] - C[k - 6]) / path if path > 0 else np.nan
            if k >= 21:
                self.d1[k] = np.sign(C[k - 1] - C[k - 21:k - 1].mean())
        self.h1_t, self.h1_s = self._h1(M.t, M.c)
        self.es = self._es()
        self.vix = self._vix()
        from tools import lit_lab_ideas as LI
        self.news = {k: v for k, v in LI.news_minutes().items() if not k.startswith("__")}

    @staticmethod
    def _h1(t, c):
        """1h trend: sign(EMA 20 - EMA 50) of the 1h closes, by the hour's end time (look up the last hour closed <= ts)."""
        b = (np.asarray(t, np.int64) // 3600)
        last = np.r_[np.nonzero(np.diff(b))[0], len(b) - 1]
        hc, hend = np.asarray(c, float)[last], (b[last] + 1) * 3600
        e20, e50 = np.empty(len(hc)), np.empty(len(hc))
        a20, a50 = 2.0 / 21, 2.0 / 51
        e20[0] = e50[0] = hc[0]
        for i in range(1, len(hc)):
            e20[i] = e20[i - 1] + a20 * (hc[i] - e20[i - 1])
            e50[i] = e50[i - 1] + a50 * (hc[i] - e50[i - 1])
        s = np.sign(e20 - e50)
        s[:50] = 0
        return hend, s

    def _es(self):
        import pandas as pd
        p = os.path.join(ROOT, "data", "ES_5m.csv")
        if not os.path.exists(p):
            return None
        d = pd.read_csv(p)
        t, c = d["time"].astype(np.int64).values, d["close"].astype(float).values
        return self._h1(t, c)

    def _vix(self):
        import pandas as pd
        v = pd.read_csv(os.path.join(ROOT, "data", "VIX_1d.csv"))
        return [str(x)[:10] for x in v["date"]], v["close"].astype(float).values

    def vix_prev(self, day):
        import bisect
        days, closes = self.vix
        k = bisect.bisect_left(days, str(day)) - 1
        return float(closes[k]) if k >= 0 else None

    @staticmethod
    def trend_at(T, ts):
        if T is None:
            return 0.0
        hend, s = T
        j = int(np.searchsorted(hend, int(ts), side="right")) - 1
        return float(s[j]) if j >= 0 else 0.0

    def news_facts(self, entry_t, exit_t):
        """(minutes to the next release after the entry that day, minutes since the last one, a release from 15 minutes before
        the entry to the exit). Calendar dates are ET dates (an evening Asia entry has none)."""
        a, z = et(entry_t), et(exit_t)
        ma = a.hour * 60 + a.minute
        mz = z.hour * 60 + z.minute if z.date() == a.date() else 1440
        L = self.news.get(a.date().isoformat(), [])
        nxt = [m - ma for m in L if m >= ma]
        prv = [ma - m for m in L if m < ma]
        inn = any(ma - 15 <= m <= mz for m in L)
        return (min(nxt) if nxt else 600), (min(prv) if prv else 600), bool(inn), bool(L)

    def day_facts(self, day, entry_t, d, entry, risk):
        """Facts of the day / market known at the entry (+ the day type, hindsight, marked h_)."""
        k = self.dix.get(str(day))
        M = self.M
        out = {"vix": self.vix_prev(day)}
        out["vix_band"] = vix_band(out["vix"])
        if k is None:
            return out
        s, e = M.days[k][1], M.days[k][2]
        atr = self.atr[k]
        x = M.ctx[k]
        j = int(np.searchsorted(M.t, int(entry_t) - 300, side="right"))          # 5m bars closed before the entry
        rng = float(M.h[s:j].max() - M.l[s:j].min()) if j > s else 0.0
        out.update({
            "atr_d": round(float(atr), 1) if atr == atr else None,
            "rng_atr": round(rng / atr, 3) if atr == atr and atr > 0 else None,
            "on_rng_atr": round(float(self.ONH[k] - self.ONL[k]) / atr, 3) if atr == atr and atr > 0 and self.ONH[k] == self.ONH[k] else None,
            "gap18": round(float(self.O18[k] - self.C[k - 1]) * d / atr, 3) if k > 0 and atr == atr and atr > 0 else None,
            "gap930": (round(float(self.RO[k] - self.RC[k - 1]) * d / atr, 3)
                       if k > 0 and atr == atr and atr > 0 and self.RO[k] == self.RO[k] and self.RC[k - 1] == self.RC[k - 1]
                       and et_mod(entry_t) >= 570 and et_mod(entry_t) < DAY0 else None),
            "d1": side_word(self.d1[k] * d),
            "h1": side_word(self.trend_at((self.h1_t, self.h1_s), entry_t) * d),
            "er5": round(float(self.er5[k]), 3) if self.er5[k] == self.er5[k] else None,
            "h_day_er": (round(abs(float(self.RC[k] - self.RO[k])) / float(self.RH[k] - self.RL[k]), 3)
                         if self.RH[k] == self.RH[k] and self.RH[k] > self.RL[k] else None),
            "h_day_with": side_word(np.sign(float(self.RC[k] - self.O18[k])) * d) if self.RC[k] == self.RC[k] else None,
        })
        if self.es is not None and int(entry_t) >= int(self.es[0][0]) + 50 * 3600:
            out["es_h1"] = side_word(self.trend_at(self.es, entry_t) * d)
        pdh, pdl = x.get("pdh"), x.get("pdl")
        if pdh is not None and pdl is not None and pdh > pdl and risk > 0:
            out["pd_pos"] = round((float(entry) - pdl) / (pdh - pdl), 3)
            lv = pdh if d == 1 else pdl
            out["pd_tgt_r"] = round((lv - float(entry)) * d / risk, 2)                # + = the level is still ahead
            lv2 = pdl if d == 1 else pdh
            out["pd_stop_r"] = round((float(entry) - lv2) * d / risk, 2)              # + = the level is behind the entry
        return out


# ================================================================================================ the trade path (data)
def path_facts(B, k0, kx, d, entry, stop, target, risk, exit_px, last_open=False, tick=0.25):
    """MFE / MAE (points, direction space) inside the trade and the minutes from the fill bar to each, + what came after the
    exit until 15:55 the same CME day. k0 = first bar in the trade, kx = the exit bar (last_open: the exit was at kx's open,
    so kx itself is not in the trade). Prices are real prices; d = +1 long / -1 short."""
    hi, lo, c, o = B.dirs(d)
    e, sp = entry * d, stop * d
    tg = target * d if target is not None else None
    xe = kx - 1 if last_open else kx
    xe = max(xe, k0)
    fav = hi[k0:xe + 1] - e
    adv = e - lo[k0:xe + 1]
    if tg is not None:
        fav = np.minimum(fav, tg - e)
    adv = np.minimum(adv, e - sp + tick)
    mfe, mae = max(0.0, float(fav.max())), max(0.0, float(adv.max()))
    i_f, i_a = int(np.argmax(fav)), int(np.argmax(adv))
    t_mfe = (int(B.t[k0 + i_f]) - int(B.t[k0])) / 60.0 + B.secs / 60.0
    t_mae = (int(B.t[k0 + i_a]) - int(B.t[k0])) / 60.0 + B.secs / 60.0
    out = {"mfe_pts": round(mfe, 2), "mae_pts": round(mae, 2), "t_mfe": round(t_mfe), "t_mae": round(t_mae)}
    # ---- after the exit (same CME day, before 15:55)
    day = B.day[kx]
    j0 = kx if last_open else kx + 1
    j1 = j0
    while j1 < B.n and B.day[j1] == day and since18(B.mod[j1]) < since18(FLAT):
        j1 += 1
    if j1 > j0 and risk > 0:
        H, Lo = hi[j0:j1], lo[j0:j1]
        out["post_best_r"] = round(float(H.max() - e) / risk, 2)
        out["post_worst_r"] = round(float(e - Lo.min()) / risk, 2)
        if tg is not None:
            hit = np.nonzero(H >= tg)[0]
            deep = np.nonzero(Lo <= sp - WIDER * risk)[0]
            out["post_tgt"] = bool(len(hit))
            out["post_tgt_clean"] = bool(len(hit) and (not len(deep) or hit[0] < deep[0]))
        h1r = np.nonzero(H >= e + risk)[0]                                     # +1R from the entry (BLITZ has no target)
        dp1 = np.nonzero(Lo <= sp - WIDER * risk)[0]
        out["post_1r_clean"] = bool(len(h1r) and (not len(dp1) or h1r[0] < dp1[0]))
        xd = float(exit_px) * d
        for mins in (30, 60):
            j = int(np.searchsorted(B.t, int(B.t[j0]) + mins * 60 - B.secs, side="right")) - 1
            j = min(max(j, j0), j1 - 1)
            out[f"after{mins}_r"] = round(float(c[j] - xd) / risk, 2)
    # ---- a stop 50% wider (diagnostic only): from the first bar, the target (+1R for BLITZ) before the wider stop?
    if risk > 0:
        aim = tg if tg is not None else e + risk
        j, wsp = k0, sp - WIDER * risk
        res = None
        while j < B.n and B.day[j] == day and since18(B.mod[j]) < since18(FLAT):
            if lo[j] <= wsp:
                res = False
                break
            if hi[j] >= aim:
                res = True
                break
            j += 1
        out["wider_win" if tg is not None else "wider_1r"] = res
    return out


# ================================================================================================ the three trade tables
def lit_rows(K: Mkt) -> list:
    """Zlarior (LIT): run lit_live's 631 trades + their entry facts + path / context."""
    c = K.c
    I = c["intel"]
    keep = ("lvl_type", "n_lvls", "major", "lvl_age_h", "lvl_touches", "depth_atr", "wick", "close_back", "idm_n", "idm_dist",
            "disp", "vec", "sweep_bars", "leg_bars", "wait_min", "fill", "stop_atr", "rr", "tgt_pts", "obst_r", "h4_draw",
            "es_swept", "prev_day", "prev_week", "pd18", "asia_rng", "lon_rng", "day_rng", "atr_regime", "gex_pos", "how",
            "monday", "wk_stops", "killzone", "macro", "t1r", "heat", "gave_back", "clean_win")
    rows = []
    for t in c["T"]:
        B = K.B1 if t["tf"] == 1 else K.B5
        d = int(t["dir"])
        k0 = int(np.searchsorted(B.t, int(t["entry_t"])))
        kx = int(np.searchsorted(B.t, int(t["exit_t"]) - B.secs))
        ex = {"CUT_T15": "CUT", "EOD": "EOD"}.get(t["exit"], t["exit"])
        risk = float(t["risk_pts"])
        q = int(t["qty"])
        pts = (float(t["pnl"]) + K.E.COMM * q) / (K.E.PV * q)
        exit_px = float(t["entry_px"]) + d * pts
        P = path_facts(B, k0, kx, d, float(t["entry_px"]), float(t["stop_px"]), float(t["target_px"]), risk, exit_px,
                       last_open=t["exit"] == "CUT_T15")
        r = {"bot": "lit", "day": t["day"], "span": span_of(t["day"]), "entry_t": int(t["entry_t"]), "exit_t": int(t["exit_t"]),
             "dir": d, "side": "long" if d == 1 else "short", "exit": ex, "r": round(float(t["r"]), 3), "usd": round(float(t["pnl"]), 2),
             "risk_pts": risk, "qty": q, "risk_usd": round(risk * K.E.PV * q, 2), "tf": int(t["tf"]),
             "mins": round((int(t["exit_t"]) - int(t["entry_t"])) / 60.0), "member": "LIT"}
        r.update(_time_facts(t["entry_t"], t["day"]))
        r.update(K.day_facts(t["day"], t["entry_t"], d, float(t["entry_px"]), risk))
        nn, npv, ni, nd = K.news_facts(t["entry_t"], t["exit_t"])
        r.update(news_next=nn, news_prev=npv, news_in=ni, news_day=nd)
        r.update(_path_r(P, risk, r["risk_usd"]))
        row = I.get(int(t["entry_t"]), {})
        r.update({f"s_{k}": row.get(k) for k in keep})
        r["mfe_r"] = round(float(t["mfe"]), 3)                                      # the engine's own MFE / MAE (R)
        r["mae_r"] = round(float(t["mae"]), 3)
        r["mfe_usd"] = round(r["mfe_r"] * r["risk_usd"])
        r["mae_usd"] = round(-r["mae_r"] * r["risk_usd"])
        rows.append(r)
    return rows


def _time_facts(entry_t, day):
    x = et(entry_t)
    m = x.hour * 60 + x.minute
    return {"hm": x.strftime("%H:%M"), "hour": x.hour, "mod": m, "session": session_of(m),
            "dow": ("Mon", "Tue", "Wed", "Thu", "Fri", "Sat", "Sun")[dt.date.fromisoformat(str(day)).weekday()]}


def _path_r(P, risk, risk_usd):
    o = dict(P)
    if risk > 0:
        o["mfe_r"] = round(P["mfe_pts"] / risk, 3)
        o["mae_r"] = round(P["mae_pts"] / risk, 3)
        o["mfe_usd"] = round(o["mfe_r"] * risk_usd)
        o["mae_usd"] = round(-o["mae_r"] * risk_usd)
    return o


def atlas_rows(K: Mkt) -> list:
    """ATLAS: the account's candidate trades (EMA / MACD / S-R after the no-hedge rules) + atlas_deep's facts + path / context."""
    from tools import atlas_deep as D
    D.V2.install()
    U = D.A.account_units(D.A.BASE)
    F = D.feats(U)
    src = {}
    for nm, fn in (("EMA", "ema_best.json"), ("MD", "md_best.json"), ("SR", "sr_best.json")):
        for t in json.load(open(os.path.join(ROOT, "research", "second", fn), encoding="utf-8"))["trades"]:
            src[(nm, int(t["entry_t"]))] = t
    rows = []
    for u, f in zip(U, F):
        t = src.get((u["src"], int(u["entry_t"])))
        if t is None:
            continue
        d = int(u["dir"])
        B = K.B1 if int(u["entry_t"]) >= int(K.B1.t[0]) + 86400 else K.B5
        k0 = int(np.searchsorted(B.t, int(u["entry_t"]), side="right"))
        kx = int(np.searchsorted(B.t, int(u["exit_t"]) - B.secs))
        kx = max(kx, k0)
        risk = float(u["risk"])
        R = float(f["R"])
        P = path_facts(B, k0, kx, d, float(t["entry"]), float(t["stop"]),
                       float(t["target"]) if t.get("target") is not None else None, risk, float(t["exit"]))
        ex = str(u["exit"]).upper()
        ex = {"TGT": "TARGET", "TIME": "EOD", "FLAT": "EOD"}.get(ex, ex)
        r = {"bot": "atlas", "day": u["day"], "span": span_of(u["day"]), "entry_t": int(u["entry_t"]), "exit_t": int(u["exit_t"]),
             "dir": d, "side": "long" if d == 1 else "short", "exit": ex, "r": round(R, 3), "usd": round(R * ATLAS_RISK, 2),
             "risk_pts": risk, "risk_usd": ATLAS_RISK, "mins": round((int(u["exit_t"]) - int(u["entry_t"])) / 60.0),
             "member": {"MD": "MACD", "SR": "S/R"}.get(u["src"], u["src"]), "src": u["src"]}
        r.update(_time_facts(u["entry_t"], u["day"]))
        r.update(K.day_facts(u["day"], u["entry_t"], d, float(t["entry"]), risk))
        nn, npv, ni, nd = K.news_facts(u["entry_t"], u["exit_t"])
        r.update(news_next=nn, news_prev=npv, news_in=ni, news_day=nd)
        r.update(_path_r(P, risk, ATLAS_RISK))
        r.update({"s_rr": round(f["rr"], 2) if f["rr"] == f["rr"] else None,
                  "s_stop_atr": round(f["stop_atr"], 3) if f["stop_atr"] == f["stop_atr"] else None,
                  "s_stop_med20": round(f["stop_med20"], 3) if f["stop_med20"] == f["stop_med20"] else None,
                  "s_trend": f["trend"], "s_k_today": f["k_today"], "s_lit_same_open": f["lit_same_open"],
                  "s_lit_won_other": f["lit_won_other"], "s_mem_same_lost": f["mem_same_lost"], "s_setup": t.get("setup")})
        rows.append(r)
    return rows


def blitz_rows(K: Mkt) -> list:
    """BLITZ: the live rule (prng >= 0.8) on 1m in 2026 and on 5m in 2021-25 (tools/scalp_na_lib.lines)."""
    from tools import scalp_na_lib as N
    _, TT = N.lines(None, lambda F: F["prng_ratio"] >= 0.8)
    rows = []
    for tf, B in ((1, K.B1), (5, K.B5)):
        for t in TT[tf]:
            sp = span_of(t["day"])
            if sp is None or (tf == 1) != (sp in ("H1", "H2")):
                continue
            d = int(t["dir"])
            k0 = int(np.searchsorted(B.t, int(t["entry_t"])))
            if k0 >= B.n or int(B.t[k0]) != int(t["entry_t"]):
                continue
            kx = int(np.searchsorted(B.t, int(t["exit_t"]) - B.secs))
            kx = max(kx, k0)
            q = max(1, min(20, int(BLITZ_RISK / t["risk_pm"])))                 # = scalp_na_lib.stats (min 1 micro)
            pnl = N.trade_pnl(t, q)[0]
            risk = float(t["risk_pts"])
            R = pnl / (q * t["risk_pm"])
            risk_usd = round(q * t["risk_pm"], 2)
            P = path_facts(B, k0, kx, d, float(t["entry"]), float(t["stop"]), None, risk, float(t["exit"]))
            ex = {"stop": "STOP", "time": "TIME", "flat": "EOD", "trail": "TRAIL", "be": "BE"}.get(t["exit_kind"], str(t["exit_kind"]).upper())
            r = {"bot": "blitz", "day": t["day"], "span": sp, "entry_t": int(t["entry_t"]), "exit_t": int(t["exit_t"]), "dir": d,
                 "side": "long" if d == 1 else "short", "exit": ex, "r": round(R, 3), "usd": round(pnl, 2),
                 "risk_pts": risk, "risk_usd": risk_usd, "mins": round((int(t["exit_t"]) - int(t["entry_t"])) / 60.0),
                 "member": "BLITZ", "tf": tf}
            r.update(_time_facts(t["entry_t"], t["day"]))
            r.update(K.day_facts(t["day"], t["entry_t"], d, float(t["entry"]), risk))
            nn, npv, ni, nd = K.news_facts(t["entry_t"], t["exit_t"])
            r.update(news_next=nn, news_prev=npv, news_in=ni, news_day=nd)
            r.update(_path_r(P, risk, risk_usd))
            r["mfe_r"] = round(float(t["mfe_pts"]) / risk, 3) if risk else None          # the executor's own (1 tick fills)
            r["mae_r"] = round(float(t["mae_pts"]) / risk, 3) if risk else None
            r["mfe_usd"] = round((r["mfe_r"] or 0) * risk_usd)
            r["mae_usd"] = round(-(r["mae_r"] or 0) * risk_usd)
            rows.append(r)
    return rows


def save_rows(bot: str, rows: list) -> str:
    """Columnar JSON (cols + rows): research/anatomy/trades_<bot>.json."""
    cols = []
    for r in rows:
        for k in r:
            if k not in cols:
                cols.append(k)
    os.makedirs(OUT_DIR, exist_ok=True)
    p = os.path.join(OUT_DIR, f"trades_{bot}.json")

    def cl(v):
        if isinstance(v, (np.floating,)):
            v = float(v)
        if isinstance(v, (np.integer,)):
            v = int(v)
        if isinstance(v, (np.bool_,)):
            v = bool(v)
        if isinstance(v, float):
            return None if v != v else round(v, 4)
        return v
    doc = {"v": VERSION, "bot": bot, "name": NAME[bot], "built": dt.datetime.now(ET).strftime("%Y-%m-%d %H:%M"),
           "cols": cols, "rows": [[cl(r.get(k)) for k in cols] for r in rows]}
    with open(p, "w", encoding="utf-8") as fh:
        json.dump(doc, fh, separators=(",", ":"))
    return p


def load_rows(bot: str) -> list:
    p = os.path.join(OUT_DIR, f"trades_{bot}.json")
    d = json.load(open(p, encoding="utf-8"))
    return [dict(zip(d["cols"], r)) for r in d["rows"]]


def build(bots=BOTS, say=print) -> dict:
    K = Mkt()
    out = {}
    for b in bots:
        rows = {"lit": lit_rows, "atlas": atlas_rows, "blitz": blitz_rows}[b](K)
        out[b] = save_rows(b, rows)
        say(f"{NAME[b]}: {len(rows)} trades -> {os.path.relpath(out[b], ROOT)}")
    return out


# ================================================================================================ why (explain)
def sessions():
    from tools import lit_final as F
    return {sp: [d for d in F.SESS if a <= d <= z] for sp, (a, z) in SPANS.items()}


def _med(v):
    v = [float(x) for x in v if _num(x) is not None]
    return round(float(np.median(v)), 3) if v else None


def _share(a, b):
    return round(100.0 * a / b, 1) if b else None


def bucket_fns(rows: list, bot: str) -> dict:
    """The entry-time facts cut into buckets (categories as they are; numbers in terciles picked on 2026 Jan-Jun only).
    Written before the first run; the same list feeds the chance control. Hindsight facts are never in here."""
    def terc(key):
        v = [_num(r.get(key)) for r in rows if r.get("span") == "H1"]
        v = [x for x in v if x is not None]
        if len(v) < 9:
            return None
        a, b = (float(x) for x in np.percentile(v, [100 / 3.0, 200 / 3.0]))
        return lambda r: None if _num(r.get(key)) is None else ("low" if r[key] < a else "mid" if r[key] < b else "high")

    def htf(r):
        if not r.get("d1") or not r.get("h1"):
            return None
        return {("with", "with"): "with both", ("with", "against"): "pullback in the daily trend",
                ("against", "with"): "against the daily, with the 1h", ("against", "against"): "against both"}[(r["d1"], r["h1"])]

    def news(r):
        nn, npv = _num(r.get("news_next")), _num(r.get("news_prev"))
        if nn is not None and 0 <= nn <= 30:
            return "release within 30 min after"
        if npv is not None and 0 < npv <= 30:
            return "release within 30 min before"
        return "no release near"

    def pd_place(r):
        x = _num(r.get("pd_pos"))
        if x is None:
            return None
        if (x < 0 and r["dir"] == 1) or (x > 1 and r["dir"] == -1):
            return "beyond the prior-day range, stop side"
        if (x > 1 and r["dir"] == 1) or (x < 0 and r["dir"] == -1):
            return "beyond the prior-day range, target side"
        return "inside the prior-day range"

    def room(r):
        x = _num(r.get("pd_tgt_r"))
        if x is None:
            return None
        return "PD level <1R ahead" if 0 < x < 1 else "PD level 1-3R ahead" if 1 <= x < 3 else \
            "PD level 3R+ ahead" if x >= 3 else "PD level already passed"

    def late(r):
        x = _num(r.get("rng_atr"))
        if x is None:
            return None
        return "day moved 1 ATR+ before" if x >= 1 else "day moved 0.6-1 ATR before" if x >= 0.6 else "day moved <0.6 ATR before"

    def gap(r):
        x = _num(r.get("gap18"))
        if x is None:
            return None
        return "18:00 gap with" if x > 0.05 else "18:00 gap against" if x < -0.05 else "no 18:00 gap"

    def chop(r):
        x = _num(r.get("er5"))
        if x is None:
            return None
        return "choppy week (ER < 0.2)" if x < 0.2 else "trending week (ER 0.5+)" if x >= 0.5 else "normal week"

    F = collections.OrderedDict([
        ("session", lambda r: r.get("session")), ("weekday", lambda r: r.get("dow")), ("VIX band", lambda r: r.get("vix_band")),
        ("side", lambda r: r.get("side")), ("daily trend", lambda r: r.get("d1")), ("1h trend", lambda r: r.get("h1")),
        ("daily x 1h trend", htf), ("ES 1h trend", lambda r: r.get("es_h1")), ("news", news), ("prior-day range", pd_place),
        ("room to the PD level", room), ("move before the entry", late), ("18:00 gap", gap), ("last 5 days", chop)])
    if bot in ("atlas", "blitz"):
        F["hour"] = lambda r: None if r.get("hour") is None else f"{int(r['hour']):02d}:00"
    if bot == "atlas":
        F["member"] = lambda r: r.get("member")
        F["member + side"] = lambda r: f"{r.get('member')} {r.get('side')}"
    keys = ["rng_atr", "er5", "pd_tgt_r", "risk_pts", "atr_d", "vix"]
    keys += {"lit": ["s_stop_atr", "s_rr", "s_disp", "s_depth_atr", "s_idm_n", "s_obst_r", "s_wait_min", "s_lvl_age_h"],
             "atlas": ["s_rr", "s_stop_atr", "s_stop_med20"], "blitz": []}[bot]
    for k in keys:
        f = terc(k)
        if f:
            F[f"{k} (tercile)"] = f
    return F


def _cells(rows, fns):
    """{(fact, bucket): {span: [rows]}}."""
    out = collections.defaultdict(lambda: collections.defaultdict(list))
    for name, fn in fns.items():
        for r in rows:
            b = fn(r)
            if b is None or r.get("span") is None:
                continue
            out[(name, str(b))][r["span"]].append(r)
    return out


def consistent(rows, fns, R=None, min_n: int = 8) -> list:
    """Buckets worse (or better) than the strategy's own average R in Jan-Jun, Jul-Oct AND 2021-25, min_n trades in each.
    R: an optional {id(row): R} (the shuffled control)."""
    rv = (lambda r: R[id(r)]) if R is not None else (lambda r: float(r["r"]))
    base = {sp: np.mean([rv(r) for r in rows if r["span"] == sp]) for sp in SPANS}
    out = []
    for (name, b), by in _cells(rows, fns).items():
        if any(len(by.get(sp, [])) < min_n for sp in SPANS):
            continue
        m = {sp: float(np.mean([rv(r) for r in by[sp]])) for sp in SPANS}
        if all(m[sp] < base[sp] for sp in SPANS):
            out.append((name, b, "worse"))
        elif all(m[sp] > base[sp] for sp in SPANS):
            out.append((name, b, "better"))
    return out


def chance(rows, fns, n: int = 200, seed: int = 5) -> dict:
    """The consistent-bucket count with the real R vs R shuffled across the trades of each span (the facts stay)."""
    real = consistent(rows, fns)
    rng = np.random.default_rng(seed)
    idx = {sp: [i for i, r in enumerate(rows) if r["span"] == sp] for sp in SPANS}
    cnt = []
    for _ in range(n):
        R = {}
        for sp, ix in idx.items():
            v = [float(rows[i]["r"]) for i in ix]
            rng.shuffle(v)
            for i, x in zip(ix, v):
                R[id(rows[i])] = x
        cnt.append(len(consistent(rows, fns, R)))
    cnt = np.array(cnt)
    return {"real": len(real), "worse": sum(1 for x in real if x[2] == "worse"), "better": sum(1 for x in real if x[2] == "better"),
            "shuffled_mean": round(float(cnt.mean()), 1), "shuffled_p95": int(np.percentile(cnt, 95)),
            "p": round(float((cnt >= len(real)).sum() + 1) / (n + 1), 3), "n_buckets": len(_cells(rows, fns)), "draws": n,
            "list": [{"fact": a, "bucket": b, "how": c} for a, b, c in real]}


def span_block(S: list, n_sess: int) -> dict:
    """Everything the page and the write-up say about one strategy in one span."""
    L = [r for r in S if r["usd"] < 0]
    G = [r for r in S if r["usd"] > 0]
    won, lost = sum(r["usd"] for r in G), -sum(r["usd"] for r in L)
    net = won - lost
    eq = np.cumsum([r["usd"] for r in sorted(S, key=lambda r: r["entry_t"])]) if S else np.zeros(1)
    dd = float((eq - np.maximum.accumulate(np.r_[0.0, eq])[1:]).min()) if S else 0.0
    o = {"n": len(S), "tpw": round(len(S) / (n_sess / 5.0), 2) if n_sess else None, "win": _share(len(G), len(S)),
         "pf": round(won / lost, 2) if lost else None, "net": round(net), "per_month": round(net / (n_sess / 21.0)) if n_sess else None,
         "dd": round(dd), "won": round(won), "lost": round(lost), "n_win": len(G), "n_loss": len(L)}
    ex = collections.defaultdict(list)
    for r in S:
        ex[r["exit"]].append(r["usd"])
    o["exits"] = {k: {"n": len(v), "usd": round(sum(v))} for k, v in sorted(ex.items(), key=lambda kv: sum(kv[1]))}
    cs = {c: [r for r in L if cause_of(r) == c] for c in CAUSES}
    o["causes"] = {c: {"n": len(v), "usd": round(sum(r["usd"] for r in v)), "share": _share(-sum(r["usd"] for r in v), lost)}
                   for c, v in cs.items()}
    st = [r for r in S if r["exit"] in ("STOP", "CUT")]
    o["stops"] = {"n": len(st), "usd": round(sum(r["usd"] for r in st)), "mfe_med": _med(r["mfe_r"] for r in st),
                  "mins_med": _med(r["mins"] for r in st),
                  "never_half": _share(sum(1 for r in st if (_num(r["mfe_r"]) or 0) < 0.5), len(st)),
                  "target_later": _share(sum(1 for r in st if r.get("post_tgt")), len(st)),
                  "back_clean": _share(sum(1 for r in st if cause_of(r) == "wick" or (r.get("post_tgt_clean") if r.get("post_tgt_clean") is not None else r.get("post_1r_clean"))), len(st)),
                  "wider_win": _share(sum(1 for r in st if (r.get("wider_win") if r.get("wider_win") is not None else r.get("wider_1r")) is True),
                                      sum(1 for r in st if (r.get("wider_win") if r.get("wider_win") is not None else r.get("wider_1r")) is not None)),
                  "after60_med": _med(r.get("after60_r") for r in st)}
    be = [r for r in S if r["exit"] == "BE"]
    o["be"] = {"n": len(be), "usd": round(sum(r["usd"] for r in be)), "mfe_med": _med(r["mfe_r"] for r in be),
               "target_later": _share(sum(1 for r in be if r.get("post_tgt")), len(be))}
    top = sorted(G, key=lambda r: -r["usd"])[:max(1, int(round(len(G) * 0.2)))] if G else []
    o["winners"] = {"n": len(G), "usd": round(won), "mae_med": _med(r["mae_r"] for r in G),
                    "mae_small": _share(sum(1 for r in G if (_num(r["mae_r"]) or 0) < 0.25), len(G)),
                    "t_mfe_med": _med(r["t_mfe"] for r in G), "mins_med": _med(r["mins"] for r in G),
                    "top20_usd": round(sum(r["usd"] for r in top)), "top20_share_of_net": _share(sum(r["usd"] for r in top), net) if net > 0 else None,
                    "day_with": _share(sum(1 for r in G if r.get("h_day_with") == "with"), sum(1 for r in G if r.get("h_day_with"))),
                    "beyond_target_r": _med((_num(r.get("post_best_r")) or 0) - float(r["r"]) for r in G
                                            if r["exit"] == "TARGET" and _num(r.get("post_best_r")) is not None)}
    o["losers"] = {"n": len(L), "usd": round(-lost), "mfe_med": _med(r["mfe_r"] for r in L), "t_mae_med": _med(r["t_mae"] for r in L),
                   "mins_med": _med(r["mins"] for r in L),
                   "day_with": _share(sum(1 for r in L if r.get("h_day_with") == "with"), sum(1 for r in L if r.get("h_day_with")))}
    dw = {w: [r for r in S if r.get("h_day_with") == w] for w in ("with", "against")}
    o["day_with"] = {w: {"n": len(v), "avg_r": _med([np.mean([r["r"] for r in v])]) if v else None, "usd": round(sum(r["usd"] for r in v))}
                     for w, v in dw.items()}
    # the careful-human checklist
    fl = [r for r in L if checks_of(r)]
    gf = [r for r in G if checks_of(r)]
    o["checklist"] = {"losers_flagged": {"n": len(fl), "usd": round(sum(r["usd"] for r in fl)), "share": _share(-sum(r["usd"] for r in fl), lost)},
                      "good_losers": {"n": len(L) - len(fl), "usd": round(-lost - sum(r["usd"] for r in fl)),
                                      "share": _share(lost + sum(r["usd"] for r in fl), lost)},
                      "winners_flagged": {"n": len(gf), "usd": round(sum(r["usd"] for r in gf)), "share": _share(sum(r["usd"] for r in gf), won)},
                      "net_if_skipped": round(-sum(r["usd"] for r in S if checks_of(r))),
                      "per_month_if_skipped": round(-sum(r["usd"] for r in S if checks_of(r)) / (n_sess / 21.0)) if n_sess else None,
                      "checks": {c: {"n": sum(1 for r in S if c in checks_of(r)),
                                     "losers_usd": round(sum(r["usd"] for r in S if c in checks_of(r) and r["usd"] < 0)),
                                     "winners_usd": round(sum(r["usd"] for r in S if c in checks_of(r) and r["usd"] > 0))} for c, _ in CHECKS}}
    big = sorted(L, key=lambda r: r["usd"])[:5]
    o["biggest_losers"] = [{"day": r["day"], "hm": r.get("hm"), "side": r["side"], "who": r.get("member"), "exit": r["exit"],
                            "usd": round(r["usd"]), "r": r["r"], "mfe_r": r["mfe_r"], "mins": r["mins"], "cause": cause_of(r),
                            "flags": checks_of(r)} for r in big]
    return o


def explain_bot(bot: str, rows: list, draws: int = 200) -> dict:
    SS = sessions()
    out = {"bot": bot, "name": NAME[bot], "spans": {}}
    for sp in SPANS:
        out["spans"][sp] = span_block([r for r in rows if r["span"] == sp], len(SS[sp]))
    out["spans"]["2026"] = span_block([r for r in rows if r["span"] in ("H1", "H2")], len(SS["H1"]) + len(SS["H2"]))
    fns = bucket_fns(rows, bot)
    out["chance"] = chance(rows, fns, n=draws)
    cells = _cells(rows, fns)
    tab = []
    for (name, b), by in cells.items():
        tab.append({"fact": name, "bucket": b, **{sp: agg(by.get(sp, [])) for sp in SPANS}})
    out["buckets"] = tab
    out["say"] = say_bot(out)
    return out


def say_bot(x: dict) -> list:
    """Plain-word lines from the numbers (2026 halves first; the 2021-25 line is the reference)."""
    nm = x["name"]
    H1, H2, R5 = (x["spans"][s] for s in ("H1", "H2", "2021-25"))
    L = []

    def cause_line(o, sp):
        c = o["causes"]
        return (f"{SPAN_WORD[sp]}: {o['n_loss']} losing trades cost {money(-o['lost'])}: never worked {c['never']['share']:.0f}%, "
                f"worked then turned {c['turned']['share']:.0f}%, shaken out then went our way {c['wick']['share']:.0f}%, "
                f"news {c['news']['share']:.0f}%.")
    for sp, o in (("H1", H1), ("H2", H2), ("2021-25", R5)):
        if o["n_loss"]:
            L.append(cause_line(o, sp))
    st = [o["stops"] for o in (H1, H2, R5)]
    if any(s["n"] for s in st):
        aim = "+1R" if x["bot"] == "blitz" else "the target"
        head = ("Stops are mostly real, not wicks" if max(s_["wider_win"] or 0 for s_ in st) < 15 else
                "Some stops are shake-outs (wider stops were tested before and lost: the other stop-outs get bigger)")
        L.append(f"{head}: a stop 50% wider would have reached {aim} first on "
                 f"{st[0]['wider_win'] if st[0]['wider_win'] is not None else '-'}% / {st[1]['wider_win'] if st[1]['wider_win'] is not None else '-'}% / "
                 f"{st[2]['wider_win'] if st[2]['wider_win'] is not None else '-'}% of stop-outs (Jan-Jun / Jul-Oct / 2021-25); "
                 f"the median stopped trade was only +{st[0]['mfe_med'] or 0:.2f}R our way at best and was out in {st[0]['mins_med'] or 0:.0f} min (Jan-Jun).")
    ck = [o["checklist"] for o in (H1, H2, R5)]
    L.append(f"A careful-human skip list (against both trends / late / news within 30 min / prior-day level under 1R ahead) "
             f"flags {ck[0]['losers_flagged']['share'] or 0:.0f}% of the losing $ but also {ck[0]['winners_flagged']['share'] or 0:.0f}% of the winning $ "
             f"(Jan-Jun): skipping them = {money(ck[0]['net_if_skipped'])} Jan-Jun, {money(ck[1]['net_if_skipped'])} Jul-Oct, "
             f"{money(ck[2]['net_if_skipped'])} in 2021-25.")
    w = H1["winners"]
    if w["n"]:
        L.append(f"Why winners win (Jan-Jun): the best 20% of winners made {money(w['top20_usd'])} "
                 f"({w['top20_share_of_net'] or 0:.0f}% of the net); the median winner went only {w['mae_med'] or 0:.2f}R against us first "
                 f"and took {w['mins_med'] or 0:.0f} min; {w['day_with'] or 0:.0f}% of winners came on days that closed our way "
                 f"(losers {H1['losers']['day_with'] or 0:.0f}%).")
    dw = [o["day_with"] for o in (H1, H2, R5)]
    L.append("Hindsight, not a rule: on days that closed our way the trades made "
             + " / ".join(money(d["with"]["usd"]) for d in dw) + ", on days that closed against us "
             + " / ".join(money(d["against"]["usd"]) for d in dw) + " (Jan-Jun / Jul-Oct / 2021-25). The day's direction is "
             "only known after the close.")
    c = x["chance"]
    L.append(f"Known at the entry, nothing separates losers from winners better than chance: {c['real']} of {c['n_buckets']} fact buckets "
             f"were worse (or better) in all three periods, vs {c['shuffled_mean']} on average with the results shuffled (p {c['p']}).")
    return L


def explain(bots=BOTS, draws: int = 200, say=print) -> dict:
    out = {"v": VERSION, "built": dt.datetime.now(ET).strftime("%Y-%m-%d %H:%M"), "bots": {}}
    for b in bots:
        rows = load_rows(b)
        out["bots"][b] = explain_bot(b, rows, draws)
        for ln in out["bots"][b]["say"]:
            say(f"{NAME[b]}: {ln}")
    os.makedirs(OUT_DIR, exist_ok=True)
    with open(os.path.join(OUT_DIR, "explain.json"), "w", encoding="utf-8") as fh:
        json.dump(out, fh, indent=1, default=float)
    return out


# ================================================================================================ rules (the real backtests)
REGISTERED = "2026-11-18"
RULE_FACTS = ("pullback", "checklist")
RULES = [
    {"id": "lit_anat_pullback_x1.25", "bot": "lit", "kind": "anatomy", "anatomy": {"fact": "pullback", "mult": 1.25},
     "title": "Zlarior: x1.25 size on a pullback in the daily trend (daily trend with the trade, 1h trend against)",
     "what_changes": "Zlarior trades 25% bigger when yesterday's close is on the trade's side of its 20-day average AND the 1h "
                     "trend (EMA 20 vs 50) points the other way: a dip in an uptrend or a rally in a downtrend (the classic "
                     "triple-screen pullback). Everything else as today.",
     "hypothesis": "Win/loss anatomy: these trades made +1.35R / +1.74R / +0.22R a trade (Jan-Jun / Jul-Oct / 2021-25) vs "
                   "+0.85R / +0.74R / +0.01R for all trades; the best of the 4 daily x 1h cells in Jan-Jun. Related family "
                   "already rejected: the 1h structure-trend SKIP (structure-management.md); this is a size-up, never a skip.",
     "registered": REGISTERED, "source": WRITEUP},
    {"id": "lit_anat_checklist_skip", "bot": "lit", "kind": "anatomy", "anatomy": {"fact": "checklist", "mult": 0.0},
     "title": "Zlarior: skip what a careful human would skip (against both trends, late, news within 30 min, no room)",
     "what_changes": "No Zlarior trade when any of the 4 checklist flags is on: against the daily AND the 1h trend; the day "
                     "already moved 1 daily ATR before the entry; a high-impact US release within 30 minutes after the entry; "
                     "the prior-day high / low less than 1R ahead on the target side.",
     "hypothesis": "The owner's question: would skipping the trades a careful human skips have helped? The checklist was "
                   "written before the first run (classic discretionary rules).",
     "registered": REGISTERED, "source": WRITEUP},
    {"id": "atlas_anat_london_open_x1.25", "bot": "atlas", "kind": "atlas_tilt",
     "rule": [{"feature": "hour", "op": "==", "value": 3, "mult": 1.25}],
     "title": "ATLAS: x1.25 size on London-open-hour entries (03:00-03:59 ET)",
     "what_changes": "ATLAS trades 25% bigger when the entry is in the 03:00 ET hour (08:00 London, the London open).",
     "hypothesis": "Win/loss anatomy: 03:00 entries made +1.99R / +1.61R / +0.32R a trade (Jan-Jun / Jul-Oct / 2021-25) vs "
                   "+0.92R / +0.65R / +0.05R for all ATLAS trades (atlas_deep autopsy: '03:00 makes most of the money'). "
                   "Window SKIPS were rejected (atlas-windows-entries-2026-10-30.md); this is a size-up of the best hour.",
     "registered": REGISTERED, "source": WRITEUP},
    {"id": "atlas_anat_checklist_skip", "bot": "atlas", "kind": "anatomy", "anatomy": {"fact": "checklist", "mult": 0.0},
     "title": "ATLAS: skip what a careful human would skip (against both trends, late, news within 30 min, no room)",
     "what_changes": "No ATLAS trade when any of the 4 checklist flags is on (the same checklist as for Zlarior); the slot "
                     "stays free for a later ATLAS signal that day.",
     "hypothesis": "The owner's question, on ATLAS: the checklist was written before the first run.",
     "registered": REGISTERED, "source": WRITEUP},
]


def rule_errors(e: dict) -> list:
    """Validation of a ZEUS Lab experiment of kind "anatomy" (tools/zeus_lab.load_registry calls it)."""
    a = e.get("anatomy")
    if not isinstance(a, dict) or a.get("fact") not in RULE_FACTS:
        return [f"anatomy must be a dict with fact in {RULE_FACTS}"]
    m = _num(a.get("mult"))
    if m is None or not (0.0 <= m <= 1.5):
        return ["anatomy mult must be 0..1.5"]
    if e.get("bot") not in ("lit", "atlas"):
        return ["anatomy is for bot lit or atlas"]
    return []


def fact_on(fact: str, r: dict) -> bool:
    """Is the rule's fact on for this trade (entry facts only)?"""
    if fact == "pullback":
        return r.get("d1") == "with" and r.get("h1") == "against"
    if fact == "checklist":
        return bool(checks_of(r))
    raise ValueError(fact)


_FK = {}


def _facts_lit():
    """entry_t -> entry facts of every live LIT trade (d1, h1, rng_atr, news_next, pd_tgt_r ...), no path."""
    if "lit" not in _FK:
        K = _FK.get("K") or Mkt()
        _FK["K"] = K
        out = {}
        for t in K.c["T"]:
            d, risk = int(t["dir"]), float(t["risk_pts"])
            r = {"dir": d, **K.day_facts(t["day"], t["entry_t"], d, float(t["entry_px"]), risk)}
            r["news_next"], r["news_prev"], r["news_in"], _ = K.news_facts(t["entry_t"], t["exit_t"])
            out[int(t["entry_t"])] = r
        _FK["lit"] = out
    return _FK["lit"]


def _facts_atlas(U):
    """(src, entry_t) -> entry facts of every ATLAS account unit (entry price from the member's stored trade)."""
    if "atlas" not in _FK:
        K = _FK.get("K") or Mkt()
        _FK["K"] = K
        src = {}
        for nm, fn in (("EMA", "ema_best.json"), ("MD", "md_best.json"), ("SR", "sr_best.json")):
            for t in json.load(open(os.path.join(ROOT, "research", "second", fn), encoding="utf-8"))["trades"]:
                src[(nm, int(t["entry_t"]))] = t
        out = {}
        for u in U:
            t = src.get((u["src"], int(u["entry_t"])))
            if t is None:
                continue
            d = int(u["dir"])
            r = {"dir": d, **K.day_facts(u["day"], u["entry_t"], d, float(t["entry"]), float(u["risk"]))}
            r["news_next"], r["news_prev"], r["news_in"], _ = K.news_facts(u["entry_t"], u["exit_t"])
            out[(u["src"], int(u["entry_t"]))] = r
        _FK["atlas"] = out
    return _FK["atlas"]


def _lit_run(e: dict, C, rules: dict) -> dict:
    from engine import learn_loop as LL
    from tools import lit_edge as E
    from tools import zeus_lab as Z
    o0, U0, L0, s0 = C.lit_base()
    a = e["anatomy"]
    m = float(a["mult"])
    FX = _facts_lit()
    on = {k for k, r in FX.items() if fact_on(a["fact"], r)}
    hits = collections.Counter(LL._span_lit(t["day"]) for t in E.ctx()["T"] if int(t["entry_t"]) in on)
    if m > 0:                                                         # a size tilt: the Lab's tilt machinery
        o, U, L = E.evaluate(mfn=lambda t, row: m if int(t["entry_t"]) in on else 1.0)
    else:                                                             # a skip: the trade is gone (the day is NOT re-filled)
        o, U, L = E.evaluate(U=[u for u in U0 if int(u["entry_t"]) not in on])
    s = E.short(o, o0)
    D = Z._lit_deltas(L, L0)
    flip = {h: Z.signflip_p([d["usd"] for d in D if Z.span_of(d["day"], "lit") == h], rules["signflip_draws"]) for h in ("H1", "H2")}
    hits = dict(hits)
    pre = LL.judge_lit(s, s0, hits, None)
    plc = None
    if m > 0 and not pre["why"].startswith("too few") and E.gate(s):
        plc = E.placebo(U, L0, n=LL.PLACEBO_N)
    v = LL.judge_lit(s, s0, hits, plc if m > 0 else flip) if (plc is not None or m == 0) else pre
    return {"rule": a, "hits": hits, "shuffle": plc, "flip": flip, "head": LL._lit_head(s), "base": LL._lit_head(s0),
            "deltas": D, "proof_ok": v["status"] == "candidate", "why": v["why"], "usd_month_by": v["usd_month_by"],
            "eval_usd_month_by": v.get("eval_usd_month_by")}


def _atlas_run(e: dict, C, rules: dict) -> dict:
    from engine import learn_loop as LL
    from tools import atlas_deep as D
    from tools import zeus_lab as Z
    o0, U, F = C.atlas_base()
    a = e["anatomy"]
    m = float(a["mult"])
    FX = _facts_atlas(U)
    key = lambda u: (u["src"], int(u["entry_t"]))                                 # noqa: E731
    name = f"anat_{e['id']}"
    D._UM[name] = {key(u): m for u in U if key(u) in FX and fact_on(a["fact"], FX[key(u)])}
    hits = dict(collections.Counter(f.get("span") for u, f in zip(U, F) if key(u) in D._UM[name]))
    o = D.score(D.V_of({"um": name}))
    v = D.V2.verdict(o, o0, "tilt")
    j = LL.judge_atlas(v, o, o0, hits)
    risk = float(rules["atlas_risk_usd"])
    Dl = [{"day": f["day"], "t": f"{f.get('src')}:{f['day']}:{f.get('hour')}", "usd": round((m - 1.0) * float(f["R"]) * risk, 2)}
          for u, f in zip(U, F) if key(u) in D._UM[name] and _num(f.get("R")) is not None]
    flip = {h: Z.signflip_p([d["usd"] for d in Dl if Z.span_of(d["day"], "atlas") == h], rules["signflip_draws"]) for h in ("H1", "H2")}
    why = j["why"]
    extra = Z.atlas_why(LL._atlas_head(o), LL._atlas_head(o0))
    if j["status"] != "candidate" and extra:
        why = f"{why} ({extra})"
    return {"rule": a, "hits": hits, "flip": flip, "head": LL._atlas_head(o), "base": LL._atlas_head(o0), "deltas": Dl,
            "proof_ok": j["status"] == "candidate", "why": why, "usd_month_by": j["usd_month_by"], "verdict_v2": v}


def lab_run(e: dict, C, rules: dict) -> dict:
    """The ZEUS Lab runner of kind "anatomy" (tools/zeus_lab.run_one): the real backtests, the Lab's result shape."""
    return _lit_run(e, C, rules) if e["bot"] == "lit" else _atlas_run(e, C, rules)


def _head_line(h: dict, sp: str, bot: str) -> dict:
    x = (h or {}).get(sp) or {}
    o = {k: x.get(k) for k in ("n", "tpw", "pf", "net", "per_month", "dd")}
    if bot == "lit":
        ev = x.get("eval") or {}
        o.update(eval_per_month=ev.get("per_month"), p10=ev.get("p10"), f10=ev.get("f10"), pass_med=ev.get("pass_med"))
    else:
        o.update(p10=x.get("p10"), f10=x.get("f10"), dead10=x.get("dead10"), pass_med=x.get("pass_med"),
                 money=x.get("mp_net_less_fees"), sig_tpw=x.get("sig_tpw"))
    return o


def run_rules(say=print) -> dict:
    """Every RULES entry on the real backtests + the Lab's full proof (project gate + sign-flip under the many-tests bar)."""
    from engine import learn_loop as LL
    from tools import zeus_lab as Z
    h0 = LL.protected_hashes(ROOT)
    C = LL.Ctx()
    exps, forever, rules, errs = Z.load_registry()
    exps = exps + Z.cross_experiments(exps, forever)                    # the same count as tools/zeus_lab.run
    have = {x["id"] for x in exps}
    runnable = [x for x in exps if x["kind"] in Z.RUNNABLE and not Z.blocked_by(x, forever)]
    n_cells = Z.cells(runnable, len(LL.load_queue()[0])) + sum(1 for e in RULES if e["id"] not in have)
    thr = Z.p_needed(n_cells, rules["family_alpha"])
    out = {"v": VERSION, "built": dt.datetime.now(ET).strftime("%Y-%m-%d %H:%M"), "cells": n_cells, "p_needed": thr, "rules": []}
    for e in RULES:
        b = Z.blocked_by(e, forever)
        if b:
            out["rules"].append({"id": e["id"], "bot": e["bot"], "title": e["title"], "status": "blocked", "why": b["title"]})
            continue
        r = lab_run(e, C, rules) if e["kind"] == "anatomy" else Z.run_one(e, C, rules)
        pr = Z.proof(r, thr)
        spans = ("H1", "H2", "2021-25") if e["bot"] == "lit" else ("H1", "H2", "2025", "2021-24")
        row = {"id": e["id"], "bot": e["bot"], "who": NAME[e["bot"]], "title": e["title"], "what": e["what_changes"],
               "status": "passes" if pr["ok"] else "rejected", "why": pr["why"], "hits": r.get("hits"), "flip": r.get("flip"),
               "shuffle": r.get("shuffle"), "usd_month_by": r.get("usd_month_by"), "eval_usd_month_by": r.get("eval_usd_month_by"),
               "with": {sp: _head_line(r.get("head"), sp, e["bot"]) for sp in spans},
               "today": {sp: _head_line(r.get("base"), sp, e["bot"]) for sp in spans}}
        out["rules"].append(row)
        say(f"  {e['id']:32s} {row['status']:9s} $/mo {row['usd_month_by']}  {str(row['why'])[:150]}")
    out["protected_ok"] = LL.protected_hashes(ROOT) == h0
    with open(os.path.join(OUT_DIR, "rules.json"), "w", encoding="utf-8") as fh:
        json.dump(out, fh, indent=1, default=float)
    return out


def register(say=print) -> list:
    """RULES -> the ZEUS Lab registry (validated by tools/zeus_lab.register; re-tested nightly from then on)."""
    from tools import zeus_lab as Z
    errs = []
    for e in RULES:
        x = {k: v for k, v in e.items()}
        er = Z.register(x)
        errs += er
        say(f"  {e['id']}: {'registered' if not er else er}")
    return errs


# ================================================================================================ the phone page (pure + write)
SIZE_WORD = {"lit": "at the LIT size ($800 a trade up to a 20-point stop)", "atlas": "at $250 a trade (the funded 25K size)",
             "blitz": "at $150 a trade"}
SHORT_CAUSE = {"never": "Never worked", "turned": "Worked, then turned", "wick": "Shaken out, then went our way",
               "news": "News release hit it"}
STATUS_PAGE = {"passes": "Passes", "rejected": "Rejected", "blocked": "Already tested"}


def _pct(x):
    x = _num(x)
    return "-" if x is None else f"{x:.0f}%"


def _money_rows(x: dict) -> list:
    out = []
    for sp in ("H1", "H2", "2021-25"):
        o = x["spans"][sp]
        out.append({"span": SPAN_WORD[sp], "n": o["n"], "tpw": o["tpw"], "win": o["win"], "pf": o["pf"], "net": o["net"],
                    "per_month": o["per_month"], "dd": o["dd"]})
    return out


def _rule_card(r: dict) -> dict:
    """One tested rule for the page: $ a month today vs with it, per period, + the verdict in plain words."""
    u = r.get("usd_month_by") or {}
    if r["bot"] == "lit":
        spans = (("H1", "Jan-Jun"), ("H2", "Jul-Oct"), ("2021-25", "2021-25"))
    else:
        spans = (("H1", "Jan-Jun"), ("H2", "Jul-Oct"), ("2025", "2025"), ("2021-24", "2021-24"))
    months = [{"span": w, "now": ((r.get("today") or {}).get(sp) or {}).get("per_month"),
               "with": ((r.get("with") or {}).get(sp) or {}).get("per_month"), "diff": u.get(sp)} for sp, w in spans]
    why = str(r.get("why") or "")
    return {"id": r["id"], "title": r["title"].split(": ", 1)[-1], "status": r["status"],
            "word": STATUS_PAGE.get(r["status"], r["status"]), "why": why[:240], "months": months,
            "line": ("Passes the adopt bar: " if r["status"] == "passes" else "Rejected: ") + why[:160]}


def bot_card(x: dict, rules: list) -> dict:
    """Everything the phone shows for one bot, in plain words with $ (2026 first, 2021-25 as the reference)."""
    bot = x["bot"]
    S, H1, H2, R5 = (x["spans"][k] for k in ("2026", "H1", "H2", "2021-25"))
    lost = S["lost"]
    causes = sorted(({"key": c, "label": SHORT_CAUSE[c], "word": CAUSE_WORD[c], "n": S["causes"][c]["n"],
                      "usd": S["causes"][c]["usd"], "share": S["causes"][c]["share"] or 0.0} for c in CAUSES),
                    key=lambda c: c["usd"])
    ck = S["checklist"]
    st, be, w = S["stops"], S["be"], S["winners"]
    aim = "+1R" if bot == "blitz" else "the target"
    after = [f"Stops were real: with a stop 50% wider, {_pct(st['wider_win'])} of the {st['n']} stop-outs of 2026 would have "
             f"reached {aim} first (2021-25: {_pct(R5['stops']['wider_win'])}).",
             f"A stopped trade was at best +{st['mfe_med'] or 0:.2f}R our way (median) and was out after {st['mins_med'] or 0:.0f} min; "
             f"an hour after the stop, price was a median {abs(st['after60_med'] or 0):.2f}R "
             + ("further against us." if (st['after60_med'] or 0) < 0 else "back our way.")]
    if be["n"]:
        after.append(f"Breakeven exits: {be['n']} in 2026, {money(be['usd'])} in total; {_pct(H1['be']['target_later'])} of the Jan-Jun "
                     f"ones and {_pct(H2['be']['target_later'])} of the Jul-Oct ones later reached the target (other breakeven and exit "
                     "rules were tested many times and lost: see Tested and rejected).")
    win = [f"The best 20% of the {w['n']} winners made {money(w['top20_usd'])} of the {money(S['net'])} net: a few big "
           "winners pay for everything.",
           f"A winner went only {w['mae_med'] or 0:.2f}R against us first (median; {_pct(w['mae_small'])} never went 0.25R "
           f"against) and took {w['mins_med'] or 0:.0f} min (best point after {w['t_mfe_med'] or 0:.0f} min).",
           f"Hindsight: {_pct(w['day_with'])} of winners came on days that closed our way, {_pct(S['losers']['day_with'])} of losers. "
           f"Days that closed our way made {money(S['day_with']['with']['usd'])}, days against {money(S['day_with']['against']['usd'])}. "
           "Nobody knows the close at the entry."]
    c = x["chance"]
    careful_line = (f"{ck['good_losers']['n']} of {S['n_loss']} losers ({_pct(ck['good_losers']['share'])} of the lost $) passed every "
                    f"check: good trades that lost. The checklist would have skipped losers that lost ${abs(ck['losers_flagged']['usd']):,.0f} "
                    f"but also winners that made ${abs(ck['winners_flagged']['usd']):,.0f}.")
    return {"bot": bot, "name": x["name"], "size": SIZE_WORD[bot], "money": _money_rows(x),
            "headline": (f"2026: {S['n']} trades, {money(S['net'])} ({money(S['per_month'])} a month), {S['win']:.0f}% winners. "
                         f"The {S['n_loss']} losing trades cost ${lost:,.0f}."),
            "lose": causes, "lose_total": -lost, "lose_n": S["n_loss"],
            "lose_ref": (f"2021-25 (reference): never worked {_pct(R5['causes']['never']['share'])}, worked then turned "
                         f"{_pct(R5['causes']['turned']['share'])}, shaken out {_pct(R5['causes']['wick']['share'])}, "
                         f"news {_pct(R5['causes']['news']['share'])} of {money(-R5['lost'])} lost."),
            "careful": {"good": ck["good_losers"], "flagged": ck["losers_flagged"], "winners_flagged": ck["winners_flagged"],
                        "net": [{"span": SPAN_WORD[sp], "usd": x["spans"][sp]["checklist"]["net_if_skipped"],
                                 "per_month": x["spans"][sp]["checklist"]["per_month_if_skipped"]} for sp in ("H1", "H2", "2021-25")],
                        "line": careful_line},
            "win": win, "after": after,
            "chance": (f"Known at the entry, nothing tells a loser from a winner better than chance: {c['real']} of {c['n_buckets']} "
                       f"buckets (session, weekday, VIX, trends, news, prior-day levels, setup) were worse or better in all three "
                       f"periods; shuffled results give {c['shuffled_mean']}."),
            "biggest": [{"day": b["day"], "line": f"{b['day']} {b['hm']} {b['side']}{(' ' + b['who']) if bot == 'atlas' else ''}: "
                                                    f"{money(b['usd'])}, {SHORT_CAUSE.get(b['cause'], b['cause']).lower()}, "
                                                    + ("checklist: " + ", ".join(b["flags"]) if b["flags"] else "passed every check")}
                        for b in S["biggest_losers"][:3]],
            "rules": [_rule_card(r) for r in rules if r.get("bot") == bot]}


def page_doc(E: dict, R: dict, hide=("blitz",), data_to: str | None = None) -> dict:
    """why.json (pure): explain.json + rules.json -> the phone page. Hidden bots are left out (engine/hidden_bots)."""
    bots = [b for b in BOTS if b in (E.get("bots") or {})]
    rules = (R or {}).get("rules") or []
    cards = [bot_card(E["bots"][b], rules) for b in bots]
    shown = [c for c in cards if c["bot"] not in set(hide or ())]
    n_pass = sum(1 for r in rules if r.get("status") == "passes" and r.get("bot") not in set(hide or ()))
    n_rules = sum(1 for r in rules if r.get("bot") not in set(hide or ()))
    lines = []
    for c in shown:
        never = next(x for x in c["lose"] if x["key"] == "never")
        lines.append(f"{c['name']}: {never['share']:.0f}% of 2026's lost $ came from trades that never worked; skipping what a "
                     f"careful human would skip = {money(c['careful']['net'][0]['per_month'])} / "
                     f"{money(c['careful']['net'][1]['per_month'])} a month (Jan-Jun / Jul-Oct).")
    verdict = ("Our losers are mostly good trades that lost: at the entry they look like the winners, the stops are real, and "
               "the trades a careful human would skip carry as many winners as losers. The money is in a few big winners.")
    doc = {"v": VERSION, "kind": "olympus-why", "built": E.get("built"), "data_to": data_to, "source": WRITEUP,
           "note": "Research only (tools/win_loss_anatomy.py). Nothing here changes a live setting.",
           "title": "Why we win / why we lose",
           "intro": ("Every Zlarior and ATLAS trade of 2021-2026 taken apart, costs in: how far it went for and against us and "
                     "when, what the day and the trends did, news, the prior day's levels, and what came after the exit."),
           "verdict": verdict, "lines": lines,
           "tested": (f"{n_rules} rules from this study were tested on the real backtests (picked on Jan-Jun 2026, checked on "
                      f"Jul-Oct and 2021-25, costs in): {n_pass} passed. They stay in the ZEUS Lab and are re-tested every night."),
           "checklist": [w for _, w in CHECKS], "bots": shown,
           "hidden_note": (f"{len(cards) - len(shown)} more bot is hidden (paper); its anatomy is in the write-up."
                           if len(cards) > len(shown) else None)}
    return doc


def page(say=print) -> dict:
    """research/anatomy/explain.json + rules.json -> tools/web_public/why/why.json (hidden bots scrubbed, stamped)."""
    from engine import hidden_bots as HB
    from tools import zeus_lab as Z
    E = json.load(open(os.path.join(OUT_DIR, "explain.json"), encoding="utf-8"))
    R = json.load(open(os.path.join(OUT_DIR, "rules.json"), encoding="utf-8")) if os.path.exists(os.path.join(OUT_DIR, "rules.json")) else {}
    hide = HB.hidden()
    doc = HB.publish(page_doc(E, R, hide=hide, data_to=Z.data_last_day()), hide)
    os.makedirs(os.path.dirname(PAGE), exist_ok=True)
    with open(PAGE, "w", encoding="utf-8") as fh:
        json.dump(doc, fh, indent=1, ensure_ascii=False)
        fh.write("\n")
    tile = jarvis_tile(doc)
    with open(os.path.join(os.path.dirname(PAGE), "jarvis.json"), "w", encoding="utf-8") as fh:
        json.dump(tile, fh, ensure_ascii=False)
    say(f"why.json: {len(doc['bots'])} bots, {os.path.getsize(PAGE):,} bytes -> {os.path.relpath(PAGE, ROOT)} (+ jarvis.json tile)")
    return doc


def jarvis_tile(doc: dict) -> dict:
    """The launcher tile (jarvis.json): what the study says in three numbers."""
    b = {c["bot"]: c for c in doc.get("bots") or []}
    lit = b.get("lit") or {}
    never = next((x for x in lit.get("lose") or [] if x["key"] == "never"), {})
    rules = [r for c in doc.get("bots") or [] for r in c.get("rules") or []]
    skip = (lit.get("careful") or {}).get("net") or [{}, {}]
    kp = [{"label": "Zlarior losses: never worked", "value": f"{(never.get('share') or 0):.0f}%"},
          {"label": "Rules passed", "value": f"{sum(1 for r in rules if r.get('status') == 'passes')} of {len(rules)}"},
          {"label": "Careful skip, Jul-Oct", "value": money(skip[1].get("per_month")) + "/mo" if len(skip) > 1 else "-"}]
    try:
        t = int(dt.datetime.strptime(str(doc.get("built")), "%Y-%m-%d %H:%M").replace(tzinfo=ET).timestamp())
    except (TypeError, ValueError):
        t = 0
    return {"v": 1, "name": "Why", "status": {"level": "ok", "label": "Study done"}, "kpis": kp,
            "lines": ["Why our trades win and lose, in $: every Zlarior and ATLAS trade taken apart.",
                      "Losers mostly look like winners at the entry; the skip list costs more than it saves."],
            "t": t, "open": "#", "theme": "#14110e", "stale_after": 31536000}


# ================================================================================================ CLI
def _main(argv=None) -> int:
    import argparse
    ap = argparse.ArgumentParser(prog="tools/win_loss_anatomy.py")
    ap.add_argument("cmd", choices=("build", "explain", "rules", "register", "page", "all"))
    ap.add_argument("--bots", default=",".join(BOTS))
    a = ap.parse_args(argv)
    bots = tuple(b for b in a.bots.split(",") if b in BOTS)
    if a.cmd in ("build", "all"):
        build(bots)
    if a.cmd in ("explain", "all"):
        explain(bots)
    if a.cmd in ("rules", "all"):
        run_rules()
    if a.cmd == "register":
        register()
    if a.cmd in ("page", "all"):
        page()
    return 0


if __name__ == "__main__":
    raise SystemExit(_main())
