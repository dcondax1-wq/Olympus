"""The combination grid: time x confluence x "while" states, each scored as a mini-backtest (one trade a day: the first
event of the day that matches), per year, 2026 vs 2021-25, with three honesty guards:

  1. Benjamini-Hochberg FDR (q = 0.10) over every combination with >= MIN_N trades (two-sided test of mean R after costs
     = 0: every trade at the same $ risk, since size follows the stop; normal approximation, n >= 30);
  2. a sign-flip placebo: the same grid with every trade's $ multiplied by a random +/-1 (no edge by construction), whose
     FDR survivors say how many "discoveries" pure noise would make;
  3. a holdout: combinations picked on 2021-24 alone (BH on 2021-24), then looked at in 2025-26, which they never saw.
"""
from __future__ import annotations

import math

import numpy as np

from . import features as F

MIN_N = 30
FDR_Q = 0.10
KEY = ("vwap", "ema", "atr", "vix", "lsa", "today", "gap", "smt")          # families crossed in pairs
YEARS = (2021, 2022, 2023, 2024, 2025, 2026)
SLOT_TRIGS = ("slot_long", "slot_short")
SEED = 20261103
# the newer families (2026-11-03) are crossed with a few partners only, not with every KEY family
NEW_PAIRS = {"orw": ("vwap", "today", "gap"), "orp": ("vwap", "today", "atr"), "gapt": ("vwap", "today", "atr"),
             "vts": ("atr", "today", "vwap"), "vtr": ("atr", "today", "vwap"), "esr": ("vwap", "today", "smt"),
             "cal": ("vwap", "today", "atr")}
TIME_FAMS = ("wd", "dst", "news", "vix", "mon", "cal", "vts", "vtr", "orw", "gapt")   # a session open x one state
# districts: a combination lives where its most specific state belongs (first match wins), else times / confluences / while
DISTRICT_OF_FAMILY = (("esnq", ("smt", "esr")), ("orange", ("orw", "orp")), ("gaps", ("gap", "gapt")),
                      ("volatility", ("vix", "vxn", "atr", "vts", "vtr")), ("week", ("wd",)), ("seasons", ("mon", "cal")))
DISTRICTS = ("times", "confluences", "week", "seasons", "volatility", "gaps", "orange", "esnq", "while")


def district_of(base, conds) -> str:
    """The district of a combination: base is "times" / "confluences" / "while" (how it was made), conds its states."""
    fams = {f for f, _ in conds}
    for d, fs in DISTRICT_OF_FAMILY:
        if fams & set(fs):
            return d
    return base


def p_values(tstat):
    """Two-sided p-values of t statistics, normal approximation (every tested combination has >= MIN_N trades)."""
    return np.array([math.erfc(abs(x) / math.sqrt(2.0)) if np.isfinite(x) else 1.0 for x in np.atleast_1d(tstat)])


def bh(p, q=FDR_Q):
    """Benjamini-Hochberg: boolean array of rejections at FDR q."""
    p = np.asarray(p, dtype=float)
    m = len(p)
    if not m:
        return np.zeros(0, bool)
    o = np.argsort(p)
    thr = q * np.arange(1, m + 1) / m
    ok = p[o] <= thr
    k = np.max(np.flatnonzero(ok)) + 1 if ok.any() else 0
    rej = np.zeros(m, bool)
    rej[o[:k]] = True
    return rej


def enumerate_combos():
    """Every combination: {"id", "district", "trig", "win", "slot", "conds"}. win: window index or -1 (any)."""
    out, ids = [], set()

    def mk(district, trig, win=-1, slot=-1, conds=()):
        w = "all" if win < 0 else F.WIN_NAMES[win]
        key = f"{trig}|{f's{slot:02d}' if slot >= 0 else w}"
        if conds:
            key += "|" + "&".join(f"{f}={v}" for f, v in conds)
        if key in ids:                             # a session open x weekday / DST / news / VIX lives in Times only
            return
        ids.add(key)
        out.append({"id": key, "district": district_of(district, conds), "trig": trig, "win": win, "slot": slot,
                    "conds": tuple(conds)})
    # Times: every 15-minute slot (18:00-16:00 ET) both ways; every session open both ways x weekday / month / DST / news / VIX
    for trig in SLOT_TRIGS:
        for s in range(96):
            if 64 <= s < 72:                       # 16:00-18:00 ET: no entries
                continue
            mk("times", trig, slot=s)
            for v in range(5):                     # the week: weekday x 15-minute slot
                mk("times", trig, slot=s, conds=(("wd", v),))
        for w in range(len(F.WINDOWS)):
            mk("times", trig, w)
            for fam in TIME_FAMS:
                vals = range(12) if fam == "mon" else range(len(F.STATES[fam]))
                for v in vals:
                    mk("times", trig, w, conds=((fam, v),))
    trigs = [t[0] for t in F.TRIGS if t[0] not in SLOT_TRIGS]
    # Confluences: every trigger in every window (and all day)
    for trig in trigs:
        for w in [-1] + list(range(len(F.WINDOWS))):
            mk("confluences", trig, w)
    # While-states: trigger (and the plain session open) x window x one state, and x two states of different key families
    pairs = []
    for i, a in enumerate(KEY):
        for b in KEY[i + 1:]:
            for va in range(len(F.STATES[a])):
                for vb in range(len(F.STATES[b])):
                    pairs.append(((a, va), (b, vb)))
    for a, partners in NEW_PAIRS.items():
        for b in partners:
            for va in range(len(F.STATES[a])):
                for vb in range(len(F.STATES[b])):
                    pairs.append(((a, va), (b, vb)))
    singles = [((f, v),) for f in F.FAMILIES for v in range(len(F.STATES[f]))]
    for trig in trigs + list(SLOT_TRIGS):
        for w in [-1] + list(range(len(F.WINDOWS))):
            if trig in SLOT_TRIGS and w < 0:
                continue
            for cs in singles + pairs:
                mk("while", trig, w, conds=cs)
    return out


class Grid:
    """Scores every combination on one event table."""

    def __init__(self, feat, recent_weeks=26):
        ev = feat["ev"]
        self.ev, self.days = ev, feat["days"]
        dyear = self.days.astype("datetime64[Y]").astype(int) + 1970
        dmon = self.days.astype("datetime64[M]").astype(int) % 12
        self.year = dyear[ev["day"]]
        self.mon = dmon[ev["day"]].astype(np.int8)
        self.q = ((self.days.astype("datetime64[M]").astype(int)) // 3)[ev["day"]]
        self.q0 = int(self.q.min()) if len(self.q) else 0
        rng = np.random.default_rng(SEED)
        self.flip = rng.choice(np.array([-1.0, 1.0], dtype=np.float32), size=len(ev["pnl"]))
        last_day = self.days[-1] if len(self.days) else np.datetime64("2026-01-01")
        self.recent = self.days[ev["day"]] > last_day - np.timedelta64(7 * recent_weeks, "D")
        first_day = self.days[0] if len(self.days) else last_day
        self.weeks = {"all": max(1.0, (last_day - first_day).astype(int) / 7.0)}
        y26 = self.days[self.days >= np.datetime64("2026-01-01")]
        old = self.days[self.days < np.datetime64("2026-01-01")]
        self.weeks["2026"] = max(1.0, (y26[-1] - y26[0]).astype(int) / 7.0) if len(y26) else 1.0
        self.weeks["old"] = max(1.0, (old[-1] - old[0]).astype(int) / 7.0) if len(old) else 1.0
        self.by_trig = {tr[0]: np.flatnonzero(ev["trig"] == i) for i, tr in enumerate(F.TRIGS)}

    def rows(self, c):
        """Event rows of a combination: the first matching event of each day."""
        ev = self.ev
        r = self.by_trig[c["trig"]]
        if c["slot"] >= 0:
            r = r[ev["slot"][r] == c["slot"]]
        elif c["win"] >= 0:
            r = r[ev["win"][r] == c["win"]]
        for fam, val in c["conds"]:
            col = self.mon[r] if fam == "mon" else ev["s_" + fam][r]
            r = r[col == val]
            if not len(r):
                return r
        d = ev["day"][r]
        keep = np.r_[True, d[1:] != d[:-1]] if len(r) else np.zeros(0, bool)
        return r[keep]

    def stats(self, r):
        ev = self.ev
        n = len(r)
        if n == 0:
            return {"n": 0}
        p = ev["pnl"][r].astype(float)                     # $ per micro after costs
        q = p / (ev["risk"][r].astype(float) * F.PT_USD)   # R after costs (equal risk a trade: size follows the stop)
        y = self.year[r]
        is26 = y >= 2026

        def mstat(x):
            k = len(x)
            if k == 0:
                return 0, 0.0, 0.0
            mu = float(x.mean())
            sd = float(x.std(ddof=1)) if k > 1 else 0.0
            return k, mu, (mu / (sd / math.sqrt(k)) if sd > 0 else 0.0)

        out = {}
        for tag, m in (("", slice(None)), ("26", is26), ("old", ~is26), ("is", y <= 2024), ("oos", y >= 2025),
                       ("rec", self.recent[r])):
            k, mr, tr = mstat(q[m])
            out["n" + tag], out["r" + tag], out["t" + tag] = k, mr, tr
            out["mu" + tag] = float(p[m].mean()) if k else 0.0
        out["tpl"] = mstat(q * self.flip[r])[2]
        yrs = {}
        for yy in YEARS:
            m = y == yy
            if m.any():
                yrs[yy] = (int(m.sum()), round(float(p[m].mean()), 1), round(float(q[m].mean()), 3))
        out["ld"] = int(self.ev["day"][r[-1]])            # the last day it traded (the Today layer)
        f = lambda a: float(np.nanmean(a)) if np.isfinite(a).any() else None  # noqa: E731
        out.update({"win": float((p > 0).mean()), "h1": float(ev["h1"][r].mean()), "h2": float(ev["h2"][r].mean()),
                    "h3": float(ev["h3"][r].mean()), "risk": float(np.median(ev["risk"][r])),
                    "f15": f(ev["f15"][r]), "f30": f(ev["f30"][r]), "f60": f(ev["f60"][r]),
                    "tpw": n / self.weeks["all"], "tpw26": out["n26"] / self.weeks["2026"], "tpwold": out["nold"] / self.weeks["old"],
                    "years": yrs, "win26": float((p[is26] > 0).mean()) if out["n26"] else None,
                    "winold": float((p[~is26] > 0).mean()) if out["nold"] else None})
        return out

    def spark(self, r):
        """Cumulative $ per micro at the end of each quarter (the sparkline)."""
        nq = int(self.q.max() - self.q0 + 1) if len(self.q) else 0
        s = np.bincount(self.q[r] - self.q0, weights=self.ev["pnl"][r].astype(float), minlength=nq)
        return [int(round(x)) for x in np.cumsum(s)]

    def score_all(self, combos):
        """Stats of every combination. A combination that picks exactly the same trades as an earlier one (e.g. "VWAP loss"
        + "against VWAP" = "VWAP loss") is marked dup_of and not counted again by the guard."""
        rows, seen = [], {}
        for i, c in enumerate(combos):
            r = self.rows(c)
            if len(r) < MIN_N:
                rows.append({"n": len(r)})
                continue
            key = r.tobytes()
            if key in seen:
                rows.append({**rows[seen[key]], "dup_of": seen[key], "fdr": False})
                continue
            seen[key] = i
            rows.append(self.stats(r))
        return rows


def classify(s, fdr_ok):
    """gold: FDR survivor, positive in 2026 AND 2021-25 AND every year with 8+ trades; green: positive in both periods;
    amber: positive in one period only; grey: noise or loses."""
    if s.get("n", 0) < MIN_N:
        return "thin"
    up26 = s["mu26"] > 0 and s["r26"] > 0 and s["n26"] >= 10
    upold = s["muold"] > 0 and s["rold"] > 0 and s["nold"] >= 20
    yrs_ok = all(mu > 0 and r > 0 for k, mu, r in s["years"].values() if k >= 8)
    # 2021-25 must mean several years: SMT combinations (ES bars from 2025-04 only) never count as holding there
    upold = upold and sum(1 for y, v in s["years"].items() if y <= 2025 and v[0] >= 5) >= 3
    if up26 and upold and yrs_ok and fdr_ok:
        return "gold"
    if up26 and upold:
        return "green"
    if up26 != upold:
        return "amber"
    return "grey"


def guard(combos, rows):
    """FDR, placebo and holdout over the scored rows (in place: row["fdr"], row["cls"]). Returns the guard summary."""
    idx = [i for i, s in enumerate(rows) if s.get("n", 0) >= MIN_N and "dup_of" not in s]
    p = p_values(np.array([rows[i]["t"] for i in idx]))
    rej = bh(p)
    for k, i in enumerate(idx):
        rows[i]["p"] = float(p[k])
        rows[i]["fdr"] = bool(rej[k] and rows[i]["r"] > 0 and rows[i]["mu"] > 0)
    rej_pl = bh(p_values(np.array([rows[i]["tpl"] for i in idx])))
    # holdout: picked on 2021-24 (BH on 2021-24 only), looked at in 2025-26
    hi = [i for i in idx if rows[i]["nis"] >= MIN_N]
    rej_is = bh(p_values(np.array([rows[i]["tis"] for i in hi])))
    picked = [i for i, rj in zip(hi, rej_is, strict=True) if rj and rows[i]["ris"] > 0]
    kept = [i for i in picked if rows[i]["noos"] >= 5 and rows[i]["roos"] > 0]
    for i in picked:
        rows[i]["hold_pick"] = True
    for s in rows:
        if "dup_of" in s:
            s["fdr"] = rows[s["dup_of"]].get("fdr", False)
            s["p"] = rows[s["dup_of"]].get("p")
        s["cls"] = classify(s, s.get("fdr", False))
        if s.get("n", 0) < MIN_N:
            s.setdefault("fdr", False)
    pos = [i for i in idx if rows[i]["fdr"]]
    neg = int(rej.sum()) - len(pos)
    cls_count = {}
    for s in rows:
        cls_count[s["cls"]] = cls_count.get(s["cls"], 0) + 1
    by_d = {}
    for c, s in zip(combos, rows, strict=True):
        d = by_d.setdefault(c["district"], {"tried": 0, "tested": 0, "fdr": 0, "gold": 0})
        distinct = s.get("n", 0) >= MIN_N and "dup_of" not in s
        d["tried"] += 1
        d["tested"] += distinct
        d["fdr"] += distinct and bool(s.get("fdr"))
        d["gold"] += distinct and s["cls"] == "gold"
    oos = [rows[i]["muoos"] for i in picked if rows[i]["noos"] >= 5]
    oos_r = [rows[i]["roos"] for i in picked if rows[i]["noos"] >= 5]
    dups = sum(1 for s in rows if "dup_of" in s)
    return {"tried": len(combos), "tested": len(idx), "duplicates": dups, "thin": sum(1 for s in rows if s.get("n", 0) < MIN_N),
            "min_n": MIN_N, "q": FDR_Q,
            "fdr_pos": len(pos), "fdr_neg": neg, "placebo_fdr": int(rej_pl.sum()),
            "expected_false": round(FDR_Q * len(pos), 1),
            "holdout": {"picked_2021_24": len(picked), "positive_2025_26": len(kept),
                        "pct_positive": round(100 * len(kept) / len(picked), 1) if picked else None,
                        "mean_oos_usd": round(float(np.mean(oos)), 2) if oos else None,
                        "mean_oos_r": round(float(np.mean(oos_r)), 3) if oos_r else None},
            "classes": cls_count, "districts": by_d}
