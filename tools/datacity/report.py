"""What the data city says: plain-language labels, the leaderboard (with rising / decaying from the run history),
discoveries, confluence lift, sized strategies with MFFU eval speed, the setups that fired on the last day, and the
JSON the 3D page and Jarvis read. Pure functions of a scored grid; learn.py writes the files.
"""
from __future__ import annotations

import datetime as dt
import json
import os
from zoneinfo import ZoneInfo

import numpy as np

from . import bars as B
from . import features as F
from . import grid as G

RISK_USD = 500.0          # sized strategies: $ at risk a trade, size follows the stop, 1..40 micros (MFFU 50K max)
TOP_N = 60                # leaderboard length
N_DISCOVERIES = 12
N_STRATEGIES = 8
N_PORTFOLIO = 10
# full cards a district carries per class (all gold, the best greens / ambers, the biggest greys); every other tested
# combination is a compact skyline row (skyline.py), so the page still draws all of them
CITY_CAPS = {"times": {"gold": 999, "green": 999, "amber": 60, "grey": 40},
             "confluences": {"gold": 999, "green": 999, "amber": 999, "grey": 999}}
CAPS_DEFAULT = {"gold": 999, "green": 110, "amber": 30, "grey": 30}
THEME = "#05060f"
WIN_LABEL = {"asia": "Asia (18:00-02:00)", "london": "London (02:00-07:00)", "pre": "NY pre-open (07:00-09:30)",
             "nyam": "NY AM (09:30-11:30)", "lunch": "NY lunch (11:30-13:30)", "pm": "NY PM (13:30-16:00)", "all": "any time"}
MONTHS = ("January", "February", "March", "April", "May", "June", "July", "August", "September", "October", "November",
          "December")
SPAN_KEYS = ("n", "tpw", "wk2", "win", "pf", "net", "per_month", "dd", "p10", "f10", "dec10", "p15", "f15", "slow_pass",
             "pass_med")


def _rnd(x, k=2):
    return None if x is None else round(float(x), k)


# ------------------------------------------------------------------------------------------------ words
def _clock(minutes):
    return f"{(minutes // 60) % 24:02d}:{minutes % 60:02d}"


def label(c) -> str:
    """'NY AM (09:30-11:30) long after a prior-day low sweep while with VWAP and VIX < 15'."""
    _, what, side = F.TRIGS[F.TRIG_ID[c["trig"]]]
    side = "long" if side > 0 else "short"
    if c["slot"] >= 0:
        where = f"{_clock(c['slot'] * 15)}-{_clock(c['slot'] * 15 + 15)} ET"
    else:
        where = WIN_LABEL[F.WIN_NAMES[c["win"]] if c["win"] >= 0 else "all"]
    if c["trig"] in G.SLOT_TRIGS:
        head = f"{where}: plain {side} at the open of the {'slot' if c['slot'] >= 0 else 'session'}"
    else:
        head = f"{where} {side} after {'an' if what[0] in 'aeiouAEIOU' else 'a'} {what}"
    conds = [MONTHS[v] if fam == "mon" else F.STATES[fam][v] for fam, v in c["conds"]]
    return head + (" while " + " and ".join(conds) if conds else "")


def holds_text(s) -> str:
    if s["cls"] == "amber":
        return ("only in 2026" if s["r26"] > 0 and s["mu26"] > 0 else "only in 2021-25") + " (does not hold in both)"
    return {"gold": "holds in 2026, in 2021-25 and in every year with 8+ trades, and survives the FDR guard",
            "green": "positive in 2026 and in 2021-25 (not proven against chance)",
            "grey": "noise or a loser", "thin": "too few trades"}[s["cls"]]


def finding(c, s) -> str:
    """The plain-language discovery line."""
    return (f"{label(c)}: {round(100 * s['h2'])}% to 2R, {'+' if s['mu'] >= 0 else '-'}${abs(s['mu']):.0f}/trade/micro "
            f"({s['r']:+.2f}R), {holds_text(s)}, {s['tpw']:.1f} a week")


# ------------------------------------------------------------------------------------------------ sized strategies
def sized(grid: G.Grid, rows, risk_usd=RISK_USD) -> list:
    """runlib trades of event rows sized like the bot: micros = $risk / (stop x $2), 1..40; costs already in the $."""
    ev = grid.ev
    out = []
    for i in rows:
        risk, R = float(ev["risk"][i]), float(ev["R"][i])
        q = int(max(1, min(40, risk_usd // (risk * F.PT_USD))))
        out.append({"day": str(grid.days[ev["day"][i]]), "entry_t": int(ev["t"][i]) + 300, "exit_t": None,
                    "dir": int(ev["dir"][i]), "r": round(R, 3), "pnl": round(float(ev["pnl"][i]) * q, 2), "risk_pts": risk,
                    "qty": q, "risk_usd": round(risk * F.PT_USD * q, 2), "half": False,
                    "exit": "target" if R >= F.TGT_R else "stop" if R <= -1 else "time",
                    "trigger": F.TRIGS[int(ev["trig"][i])][0], "mfe": None, "mae": 1.0 if R <= -1 else 0.0,
                    "bars_held": None, "regime": None, "mult": 1.0})
    return out


def strategy_score(grid: G.Grid, rows):
    """(trades, runlib score, the 2026 / 2021-25 headline incl. MFFU 50K eval speed)."""
    from tools import runlib as rl
    T = sized(grid, rows)
    S = rl.score(T, [str(d) for d in grid.days])
    return T, S, {k: {kk: S["spans"][k].get(kk) for kk in SPAN_KEYS} for k in ("2026", "2021-25")}


def first_of_day(grid: G.Grid, combos) -> np.ndarray:
    """One trade a day: the earliest event of the day among the combinations."""
    if not combos:
        return np.array([], dtype=np.int64)
    r = np.unique(np.concatenate([grid.rows(c) for c in combos]))
    r = r[np.lexsort((grid.ev["t"][r], grid.ev["day"][r]))]
    d = grid.ev["day"][r]
    return r[np.r_[True, d[1:] != d[:-1]]] if len(r) else r


def lit_tower(root=B.ROOT):
    """LIT's numbers for the central tower, from run lit_live (2026, the H2 check half, 2021-25)."""
    try:
        with open(os.path.join(root, "research", "runs", "lit_live.json"), encoding="utf-8") as fh:
            run = json.load(fh)
    except (OSError, ValueError):
        return None
    keep = ("n", "tpw", "win", "pf", "net", "per_month", "dd", "p10", "f10", "pass_med")
    spans = {k: {kk: run["spans"][k].get(kk) for kk in keep} for k in ("2026", "2021-25")}
    T = [dict(zip(run["trade_cols"], t, strict=True)) for t in run["trades"]]
    h2 = np.array([t["pnl"] for t in T if "2026-07-01" <= t["day"] <= "2026-12-31"])
    if len(h2):
        loss = -h2[h2 < 0].sum()
        days = [d for d in run["days"] if "2026-07-01" <= d[0] <= "2026-12-31"]
        spans["2026 H2"] = {"n": int(len(h2)), "win": round(100 * float((h2 > 0).mean()), 1),
                            "pf": round(float(h2[h2 > 0].sum() / loss), 2) if loss else None, "net": round(float(h2.sum())),
                            "per_month": round(float(h2.sum()) / max(len(days) / 21, 1e-9))}
    return {"title": "LIT (Zlarior), the live strategy", "spans": spans,
            "note": f"Run lit_live, costs in. {run.get('title', '')}. Quote the H2 (check) line."}


# ------------------------------------------------------------------------------------------------ the study
class Study:
    """One scored grid + the previous runs: everything the outputs need."""

    def __init__(self, grid: G.Grid, combos, rows, guard, history):
        self.grid, self.combos, self.rows, self.guard = grid, combos, rows, guard
        self.history = history
        prev = history["runs"][-1] if history["runs"] else {}
        self.prev_top = prev.get("top", {})
        self.has_prev = bool(prev)
        self.last_day = str(grid.days[-1])
        self.ranked = self._ranked()
        self.lead = self.ranked[:TOP_N]
        self.index = {c["id"]: i for i, c in enumerate(combos)}

    # -- ranking
    def _ranked(self):
        """Distinct combinations positive in both periods, FDR survivors first, then by the weaker period's t."""
        rows = self.rows
        ids = [i for i, s in enumerate(rows) if s.get("n", 0) >= G.MIN_N and "dup_of" not in s and s["cls"] in ("gold", "green")]
        ids.sort(key=lambda i: (bool(rows[i].get("fdr")), rows[i]["cls"] == "gold", min(rows[i]["t26"], rows[i]["told"])),
                 reverse=True)
        return ids

    def trend(self, i) -> str:
        """rising / decaying / steady: the last 26 weeks against the whole sample, and R against the previous run."""
        s, p = self.rows[i], self.prev_top.get(self.combos[i]["id"])
        tr = "steady"
        if s["nrec"] >= 4 and s["rrec"] < 0 < s["r"]:
            tr = "decaying"
        elif s["nrec"] >= 4 and s["rrec"] > max(s["r"], 0):
            tr = "rising"
        if p and s["r"] > p[0] + 0.02:
            tr = "rising"
        elif p and s["r"] < p[0] - 0.02 and tr != "rising":
            tr = "decaying"
        return tr

    def is_new(self, i) -> bool:
        return self.has_prev and self.combos[i]["id"] not in self.prev_top

    def _distinct_families(self, ids, k):
        """The first k ids with a distinct (trigger, window, slot): no wall of near-copies of one idea."""
        seen, out = set(), []
        for i in ids:
            c = self.combos[i]
            fam = (c["trig"], c["win"], c["slot"])
            if fam not in seen:
                seen.add(fam)
                out.append(i)
            if len(out) >= k:
                break
        return out

    # -- cards
    def card(self, i, full=False) -> dict:
        c, s = self.combos[i], self.rows[i]
        d = {"id": c["id"], "d": c["district"], "lab": label(c), "cls": s["cls"], "fdr": bool(s.get("fdr")),
             "e": _rnd(s["mu"], 1), "r": _rnd(s["r"], 3), "w": _rnd(100 * s["win"], 1), "h2": _rnd(100 * s["h2"], 1),
             "n": s["n"], "tpw": _rnd(s["tpw"], 2), "stop": _rnd(s["risk"], 1), "tr": self.trend(i),
             "e26": _rnd(s["mu26"], 1), "r26": _rnd(s["r26"], 3), "n26": s["n26"], "w26": _rnd(100 * (s["win26"] or 0), 1),
             "tpw26": _rnd(s["tpw26"], 2), "eo": _rnd(s["muold"], 1), "ro": _rnd(s["rold"], 3), "no": s["nold"],
             "wo": _rnd(100 * (s["winold"] or 0), 1), "tpwo": _rnd(s["tpwold"], 2),
             "yrs": {str(k): [v[0], round(v[1])] for k, v in s["years"].items()}}
        if full or s["cls"] in ("gold", "green"):
            d["sp"] = self.grid.spark(self.grid.rows(c))
        if full:
            d.update({"h1": _rnd(100 * s["h1"], 1), "h3": _rnd(100 * s["h3"], 1), "f15": _rnd(s["f15"], 2),
                      "f30": _rnd(s["f30"], 2), "f60": _rnd(s["f60"], 2), "p": _rnd(s.get("p"), 5),
                      "erec": _rnd(s["murec"], 1), "nrec": s["nrec"], "text": finding(c, s)})
        return d

    def leaderboard(self) -> list:
        out = []
        for rank, i in enumerate(self.lead, 1):
            cid = self.combos[i]["id"]
            out.append({**self.card(i, full=True), "rank": rank, "new": self.is_new(i),
                        "hist": [[r["t"], r["top"][cid][0]] for r in self.history["runs"][-30:] if cid in r.get("top", {})]})
        return out

    def discovery_ids(self):
        return self._distinct_families(self.lead, N_DISCOVERIES)

    def discoveries(self) -> list:
        return [{"id": self.combos[i]["id"], "text": finding(self.combos[i], self.rows[i]), "cls": self.rows[i]["cls"],
                 "new": self.is_new(i), "tr": self.trend(i)} for i in self.discovery_ids()]

    def buildings(self) -> list:
        """The city's buildings, district by district; the leaderboard is always in."""
        lead, out, ids = set(self.lead), [], set()
        for district in G.DISTRICTS:
            caps = CITY_CAPS.get(district, CAPS_DEFAULT)
            pool = [i for i, s in enumerate(self.rows)
                    if self.combos[i]["district"] == district and s.get("n", 0) >= G.MIN_N and "dup_of" not in s]
            for cls, cap in caps.items():
                k = [i for i in pool if self.rows[i]["cls"] == cls]
                k.sort(key=(lambda i: -self.rows[i]["n"]) if cls == "grey" else (lambda i: -self.rows[i]["t"]))
                for i in k[:cap]:
                    out.append(self.card(i, full=i in lead))
                    ids.add(i)
        out += [self.card(i, full=True) for i in self.lead if i not in ids]
        return out

    # -- strategies
    def strategies(self):
        """Each of the first discoveries sized like the bot, and the holdout portfolio: the 2021-24 FDR picks (BH on
        2021-24 only), one trade a day. Returns (strategies, portfolio trades, portfolio score)."""
        out = []
        for i in self.discovery_ids()[:N_STRATEGIES]:
            _, _, spans = strategy_score(self.grid, self.grid.rows(self.combos[i]))
            out.append({"id": "S:" + self.combos[i]["id"], "lab": label(self.combos[i]), "of": self.combos[i]["id"],
                        "cls": self.rows[i]["cls"], "spans": spans})
        picks = sorted((i for i, s in enumerate(self.rows) if s.get("hold_pick") and "dup_of" not in s),
                       key=lambda i: self.rows[i]["tis"], reverse=True)
        members = self._distinct_families(picks, N_PORTFOLIO)
        if not members:
            return out, None, None
        T, S, spans = strategy_score(self.grid, first_of_day(self.grid, [self.combos[i] for i in members]))
        oos = [t for t in T if t["day"] >= "2025-01-01"]
        out.append({"id": "S:holdout_portfolio", "lab": "Holdout portfolio: the 2021-24 FDR picks, one trade a day",
                    "spans": spans, "years": S["years"], "members": [self.combos[i]["id"] for i in members],
                    "member_text": [label(self.combos[i]) for i in members],
                    "oos_2025_26": {"n": len(oos), "r": _rnd(np.mean([t["pnl"] / t["risk_usd"] for t in oos]), 3) if oos else None,
                                    "net": round(sum(t["pnl"] for t in oos))}})
        return out, T, S

    # -- learning views
    def lift(self, k_top=12, k_bottom=6) -> list:
        """Confluence lift: what one state adds to the same trigger + window, in R after costs, across every base with
        30+ trades both ways; both_pct = share of bases where it helps in 2026 AND in 2021-25."""
        base = {(c["trig"], c["win"]): i for i, c in enumerate(self.combos) if not c["conds"] and c["slot"] < 0}
        acc = {}
        for i, c in enumerate(self.combos):
            if c["district"] != "while" or len(c["conds"]) != 1 or self.rows[i].get("n", 0) < G.MIN_N:
                continue
            b = base.get((c["trig"], c["win"]))
            if b is None or self.rows[b].get("n", 0) < G.MIN_N:
                continue
            s, sb = self.rows[i], self.rows[b]
            a = acc.setdefault(c["conds"][0], {"d": [], "both": 0})
            a["d"].append(s["r"] - sb["r"])
            a["both"] += (s["r26"] > sb["r26"]) and (s["rold"] > sb["rold"])
        out = sorted(({"key": f"{fam}={v}", "fam": fam, "lab": F.STATES[fam][v], "med_r": round(float(np.median(a["d"])), 3),
                       "bases": len(a["d"]), "both_pct": round(100 * a["both"] / len(a["d"]), 1)}
                      for (fam, v), a in acc.items() if len(a["d"]) >= 5), key=lambda x: -x["med_r"])
        return out[:k_top] + out[-k_bottom:]

    def today(self) -> list:
        """Leaderboard setups that fired on the last complete day (one line per trade) and how they did."""
        ev, out, seen = self.grid.ev, [], set()
        tz = ZoneInfo(F.ET)
        for i in self.lead:
            r = self.grid.rows(self.combos[i])
            if not len(r) or str(self.grid.days[ev["day"][r[-1]]]) != self.last_day or int(r[-1]) in seen:
                continue
            j = int(r[-1])
            seen.add(j)
            at = dt.datetime.fromtimestamp(int(ev["t"][j]) + 300, dt.timezone.utc).astimezone(tz)
            out.append({"id": self.combos[i]["id"], "lab": label(self.combos[i]), "pnl": _rnd(ev["pnl"][j], 1),
                        "R": _rnd(ev["R"][j], 2), "at": at.strftime("%H:%M")})
        return out

    def history_row(self, now) -> dict:
        return {"t": int(now), "last_day": self.last_day, "tested": self.guard["tested"], "fdr": self.guard["fdr_pos"],
                "top": {self.combos[i]["id"]: [round(self.rows[i]["r"], 3), round(self.rows[i]["mu"], 1), self.rows[i]["n"]]
                        for i in self.ranked[:100]}}


def jarvis_card(guard, leaderboard, last_day, built, now) -> dict:
    """The Jarvis live card (docs/JARVIS_APPS.md): plain text, the limits applied."""
    top = leaderboard[0] if leaderboard else None
    n = guard["fdr_pos"]
    return {"v": 1, "name": "Data City",
            "status": {"level": "ok" if n else "warn", "label": (f"{n} pass the noise guard" if n else "Nothing beats chance yet")[:48]},
            "kpis": [{"label": "Combos tested", "value": f"{guard['tested']:,}"},
                     {"label": "FDR survivors", "value": str(n), "delta": f"placebo {guard['placebo_fdr']}"[:16]},
                     {"label": "Top $/micro", "value": f"+${top['e']:.0f}" if top and top["e"] >= 0 else "-"}],
            "lines": [(top["text"] if top else "No discovery yet")[:120], f"Data to {last_day}, built {built}"[:120]],
            "t": int(now), "open": "#top", "theme": THEME}


def fixture(city, per=14) -> dict:
    """The page's demo city (tools/web_public/datacity/fixture.json): a small cut of a real city, marked demo."""
    keep = []
    for district in G.DISTRICTS:
        b = [x for x in city["buildings"] if x["d"] == district]
        keep += b[:per] + b[-3:]
    ids = {b["id"] for b in keep}
    sky = city.get("skyline") or {"cols": [], "rows": []}
    dcol = sky["cols"].index("d") if sky["rows"] else 0
    rows = []
    for k in range(len(G.DISTRICTS)):           # a slice of every district's skyline, so the demo city has every district
        rows += [r for r in sky["rows"] if r[dcol] == k][:70]
    harbor = city.get("harbor")
    return {**city, "demo": True, "buildings": keep, "discoveries": [d for d in city["discoveries"] if d["id"] in ids][:4],
            "top10": [t for t in city["top10"] if t["id"] in ids], "today": city["today"][:2], "strategies": city["strategies"][:3],
            "skyline": {"cols": sky["cols"], "rows": rows},
            "harbor": {**harbor, "rows": harbor["rows"][-60:]} if harbor else None}
