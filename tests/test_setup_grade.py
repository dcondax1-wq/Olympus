"""Setup grade (tools/setup_grade.py, night-human 2026-11-18): offline checks, no backtest, no network, no browser.

  * the grade itself: flag count vs the typical setup (A / B / C), the size multiplier of each use, the median cut
  * every check fires when it should and never on a missing fact (ES before 2025-04, no news, no VIX)
  * the key-level check: only levels toward the target, more than 1 tick away, within 0.5R; the next 100-point number
  * no look-ahead: the facts at a signal bar do not move when later bars change (a small fake market)
  * the Jan-Jun pick uses Jan-Jun trades only and keeps a check only when it fires enough and loses R
  * a calm human: the checklist never reads P&L, wins, losses or streaks; no live file written, no broker import
  * the stored verdict (research/lab/setup_grade.json) and the ZEUS Lab entries (kind setup_grade) when present

    python -X utf8 -m tests.test_setup_grade
"""
from __future__ import annotations

import inspect
import json
import os
import re
import sys
import types

import numpy as np

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)

from tools import setup_grade as SG  # noqa: E402

RES = []


def check(name, ok, info=""):
    RES.append(bool(ok))
    print(("  PASS " if ok else "  FAIL ") + name + ("" if ok else f"   -> {str(info)[:300]}"))


def t_grade():
    f0 = {c: False for c in SG.CHECKS}
    check("0 flags with m 1 -> A, 1 -> B, 2 -> C", SG.grade_of(f0, m=1) == "A" and SG.grade_of({**f0, "trend": True}, m=1) == "B"
          and SG.grade_of({**f0, "trend": True, "chop": True}, m=1) == "C")
    two = {**f0, "trend": True, "level": True}
    check("m 2: 1 flag -> A, 2 -> B, 3 -> C", SG.grade_of({**f0, "es": True}, m=2) == "A" and SG.grade_of(two, m=2) == "B"
          and SG.grade_of({**two, "vol": True}, m=2) == "C")
    check("only the counted checks count", SG.grade_of(two, use=["news", "vol"], m=1) == "A")
    check("m is at least 1 (a check set that rarely fires still has A = no warning)", SG.grade_of(f0, m=0) == "A" and SG.typical([0, 0, 0, 1]) == 1)
    check("typical = median flag count, rounded down", SG.typical([1, 2, 2, 3]) == 2 and SG.typical([1, 2, 3, 3]) == 2 and SG.typical([]) == 1)
    check("uses: skipC = C out, A/B full", SG.mult_of("C", "skipC") == 0 and SG.mult_of("B", "skipC") == 1 and SG.mult_of("A", "skipC") == 1)
    check("uses: size = A full, B half, C out", SG.mult_of("A", "size") == 1 and SG.mult_of("B", "size") == 0.5 and SG.mult_of("C", "size") == 0)
    sk, mu = SG.variant_maps({"a": "A", "b": "B", "c": "C"}, "size")
    check("variant maps: C skipped, B at x0.5 (size), nothing else", sk == {"c"} and mu == {"b": 0.5} and SG.variant_maps({"b": "B"}, "skipC") == (set(), {}))


def t_level():
    check("next round above a long / below a short", SG.next_round(25257.75, 1) == 25300.0 and SG.next_round(25257.75, -1) == 25200.0)
    check("a round number 1 tick away is not 'next' (25299.75 long -> 25400)", SG.next_round(25299.75, 1) == 25400.0)
    check("level toward the target within 0.5R fires (long)", SG.level_flag(1, 100.0, 20.0, [108.0]))
    check("level behind the entry never fires", not SG.level_flag(1, 100.0, 20.0, [95.0]) and not SG.level_flag(-1, 100.0, 20.0, [105.0]))
    check("level beyond 0.5R does not fire", not SG.level_flag(1, 100.0, 20.0, [111.0]))
    check("level exactly 1 tick away does not fire, 0.5R exactly does", not SG.level_flag(1, 100.0, 20.0, [100.25]) and SG.level_flag(1, 100.0, 20.0, [110.0]))
    check("short: level below within 0.5R fires", SG.level_flag(-1, 100.0, 20.0, [93.0]))
    check("missing levels / zero risk never fire", not SG.level_flag(1, 100.0, 20.0, [None, float("nan")]) and not SG.level_flag(1, 100.0, 0.0, [101.0]))


def base_facts(**kw):
    f = {"dir": 1, "entry": 100.0, "risk": 20.0, "trend": 1.0, "levels": [], "range_so_far": 50.0, "adr": 100.0, "hi_so_far": 120.0,
         "lo_so_far": 80.0, "pdh": 110.0, "pdl": 90.0, "news_in": None, "es_move": 1.0, "vix": 18.0, "vix2": 17.0}
    f.update(kw)
    return f


def t_checks():
    c0 = SG.checks_from(base_facts())
    check("a clean long fires nothing", not any(c0.values()), c0)
    check("trend: long under its 20-day average fires, flat trend never", SG.checks_from(base_facts(trend=-1.0))["trend"]
          and not SG.checks_from(base_facts(trend=0.0))["trend"] and SG.checks_from(base_facts(dir=-1))["trend"])
    check("extended: range so far >= the 14-day ADR fires", SG.checks_from(base_facts(range_so_far=100.0))["extended"]
          and not SG.checks_from(base_facts(range_so_far=99.0))["extended"] and not SG.checks_from(base_facts(adr=None))["extended"])
    check("chop: still inside yesterday's range fires", SG.checks_from(base_facts(hi_so_far=105.0, lo_so_far=95.0))["chop"]
          and not SG.checks_from(base_facts(pdh=None))["chop"])
    check("news: a release in the next 30 min fires, 31 min / none / past never",
          SG.checks_from(base_facts(news_in=30.0))["news"] and not SG.checks_from(base_facts(news_in=31.0))["news"]
          and not SG.checks_from(base_facts(news_in=None))["news"] and not SG.checks_from(base_facts(news_in=0.0))["news"])
    check("ES against the trade fires; no ES data (before 2025-04) never", SG.checks_from(base_facts(es_move=-0.25))["es"]
          and not SG.checks_from(base_facts(es_move=None))["es"] and SG.checks_from(base_facts(dir=-1, trend=-1.0))["es"])
    check("vol: VIX >= 25 or a +20% jump fires, missing VIX never", SG.checks_from(base_facts(vix=25.0))["vol"]
          and SG.checks_from(base_facts(vix=20.5, vix2=17.0))["vol"] and not SG.checks_from(base_facts(vix=20.3, vix2=17.0))["vol"]
          and not SG.checks_from(base_facts(vix=None, vix2=None))["vol"])
    check("level check is wired (a level 5 pts above a long with a 20-pt stop)", SG.checks_from(base_facts(levels=[105.0]))["level"])


def fake_market(n_days=26, per=12):
    """A small 5m market: per bars a day, 18:00 start, overnight then RTH minutes, rising closes."""
    mods = [1080, 1085, 1200, 0, 120, 300, 560, 565, 570, 575, 600, 900][:per]
    t0 = 1_700_000_000
    t, o, h, l, c, v, mod, days, ctx, day_of = [], [], [], [], [], [], [], [], [], []
    k = 0
    px = 1000.0
    for d in range(n_days):
        s = len(t)
        for j, md in enumerate(mods):
            px += 1.0
            t.append(t0 + 300 * len(t)); o.append(px - 0.5); h.append(px + 2.0); l.append(px - 2.0); c.append(px); v.append(100.0 + j)
            mod.append(md); day_of.append(d)
        e = len(t)
        days.append((f"2026-01-{d + 1:02d}" if d < 31 else f"2026-02-{d - 30:02d}", s, e))
        x = {"s": s, "e": e}
        if d:
            ps, pe = days[d - 1][1], days[d - 1][2]
            x["pdh"], x["pdl"] = max(h[ps:pe]), min(l[ps:pe])
        ctx.append(x)
        k += 1
    M = types.SimpleNamespace(t=np.array(t), o=np.array(o), h=np.array(h), l=np.array(l), c=np.array(c), v=np.array(v),
                              mod=np.array(mod), days=days, ctx=ctx, n=len(t), day_of=np.array(day_of))
    return M


def t_lookahead():
    keep = dict(SG._C)
    try:
        SG._C.clear()
        M = fake_market()
        SG.prep(M)
        SG._C["news"] = np.array([], dtype=np.int64)
        SG._C["es"] = {}
        SG._C["vix"] = {d: (18.0, 17.0) for d, s, e in M.days}
        k = 24
        d, s, e = M.days[k]
        j = s + 7
        f1 = SG.facts_at(j, 1, float(M.c[j]), 10.0)
        check("trend + ADR from the prior days only (rising closes -> long is with the trend)", f1["trend"] == 1.0
              and abs(f1["adr"] - np.mean([M.h[a:b].max() - M.l[a:b].min() for _, a, b in M.days[k - 14:k]])) < 1e-9)
        on = [i for i in range(s, j + 1) if M.mod[i] >= 1080 or M.mod[i] < 570]
        check("overnight high = 18:00-09:30 bars so far", f1["onh"] == max(M.h[i] for i in on))
        vw = sum((M.h[i] + M.l[i] + M.c[i]) / 3.0 * M.v[i] for i in range(s, j + 1)) / sum(M.v[i] for i in range(s, j + 1))
        check("VWAP anchored at 18:00, closed bars only", abs(f1["vwap"] - vw) < 1e-9)
        M.h[j + 1:] += 500.0
        M.l[j + 1:] -= 500.0
        M.c[j + 1:] += 300.0
        M.v[j + 1:] *= 50.0
        SG.prep(M)
        f2 = SG.facts_at(j, 1, float(M.c[j]), 10.0)
        same = all((f1[x] == f2[x]) or (isinstance(f1[x], float) and abs(f1[x] - f2[x]) < 1e-9)
                   for x in ("trend", "adr", "range_so_far", "hi_so_far", "lo_so_far", "onh", "onl", "vwap", "pdh", "pdl"))
        check("no look-ahead: later bars changed, the facts at the signal bar did not", same, (f1, f2))
        SG._C["news"] = np.array([int(M.t[j]) + 300 + 20 * 60], dtype=np.int64)
        check("news 20 min after the signal bar close -> news flag", SG.checks_from(SG.facts_at(j, 1, float(M.c[j]), 10.0))["news"])
    finally:
        SG._C.clear()
        SG._C.update(keep)


def t_pick():
    rows = []
    for i in range(20):                      # Jan-Jun: trend fires on 10 losers, chop on 3 trades only, es on 10 winners
        f = {c: False for c in SG.CHECKS}
        if i < 10:
            f["trend"] = True
        if i < 3:
            f["chop"] = True
        if i >= 10:
            f["es"] = True
        rows.append(("2026-03-%02d" % (i + 1), f, -1.0 if i < 10 else 2.0))
    for i in range(30):                      # Jul-Oct: would say the opposite; must not matter
        f = {c: (c == "es") for c in SG.CHECKS}
        rows.append(("2026-08-%02d" % (i % 28 + 1), f, -5.0))
    P = SG.pick(rows)
    check("pick: a check that fires on 8+ Jan-Jun trades with less R is kept", "trend" in P["keep"], P)
    check("pick: a check that fires on fewer than 8 is not judged", "chop" not in P["keep"] and P["per_check"]["chop"]["fires"] == 3)
    check("pick: a check whose flagged trades did better is dropped", "es" not in P["keep"])
    check("pick: Jul-Oct trades never enter the pick", P["n_h1"] == 20)
    check("pick: the cut m comes from the Jan-Jun flag counts", P["m"]["all7"] == 1 and P["m"]["h1"] == 1)


def t_static():
    src = open(os.path.join(ROOT, "tools", "setup_grade.py"), encoding="utf-8").read()
    code = re.sub(r'"""[\s\S]*?"""', "", src)
    check("never opens a live file for writing", not re.search(r"open\([^)]*(live_model|second_model|account_b)", code))
    check("no broker / order import", not re.search(r"import .*(ninjatrader|botctl)|from engine import (live|ninjatrader|botctl|lit_live)", code))
    fx = "".join(inspect.getsource(fn) for fn in (SG.checks_from, SG.facts_at, SG.lit_facts, SG.atlas_facts, SG.grade_of, SG.level_flag))
    fx = re.sub(r'"""[\s\S]*?"""', "", fx)
    check("a calm human: the checklist never reads P&L, wins, losses or streaks",
          not re.search(r"pnl|\bwin|loss|streak|\[\"r\"\]|\[\"pts\"\]|exit", fx, re.I), re.findall(r"pnl|\bwin|loss|streak|exit", fx, re.I)[:5])
    ra = open(os.path.join(ROOT, "tests", "run_area.py"), encoding="utf-8").read()
    check("registered in tests/run_area.py (nq area)", '"setup_grade"' in ra)


def t_stored():
    p = SG.OUT
    if not os.path.exists(p):
        check("stored verdict not built here (python -X utf8 tools/setup_grade.py run) - skipped", True)
        return
    o = json.load(open(p, encoding="utf-8"))
    check("stored: both strategies, 4 pre-declared variants each", all(set(o[b]["variants"]) == {"h1:skipC", "h1:size", "all7:skipC", "all7:size"}
                                                                    for b in ("lit", "atlas")), [list(o.get(b, {}).get("variants", {})) for b in ("lit", "atlas")])
    check("stored: the pick and the cut were made on Jan-Jun", all(o[b]["pick"]["n_h1"] > 30 and o[b]["pick"]["m"]["all7"] >= 1 for b in ("lit", "atlas")))
    check("stored: per-grade stats for every span", set(o["lit"]["grades"]["all7"]) == {"H1", "H2", "2021-25"}
          and set(o["atlas"]["grades"]["all7"]) == {"H1", "H2", "2025", "2021-24"})
    check("stored: a passer needs the gate AND the random-grade luck test", all(
        (not r["pass"]) or (r["gate"] and r["placebo_ok"]) for b in o["verdict"].values() for r in b["rows"].values()))
    for bot in ("lit", "atlas"):
        e = {"id": f"setup_grade_{bot}", "bot": bot, "kind": "setup_grade", "variant": SG.LAB_VARIANT[bot]}
        r = SG.lab_result(e)
        check(f"Lab runner ({bot}): stored verdict with head / base / flip / why / deltas", {"proof_ok", "why", "flip", "head", "base", "deltas"} <= set(r)
              and r["head"]["H1"].get("per_month") is not None and r["base"]["H2"].get("per_month") is not None, r.get("why"))
    try:
        from tools import zeus_lab as Z
        E, F, R, errs = Z.load_registry()
        mine = [e for e in E if e.get("kind") == "setup_grade"]
        check("ZEUS Lab: setup_grade entries load (Zlarior + ATLAS), registry clean", {e["bot"] for e in mine} == {"lit", "atlas"}
              and not [x for x in errs if "setup_grade" in x], (mine, errs))
        check("ZEUS Lab: a setup_grade entry counts its variants in the many-tests bar", Z.cells(mine) == sum(int(e["cells"]) for e in mine))
    except Exception as ex:  # noqa: BLE001
        check("ZEUS Lab registry readable", False, ex)


def main() -> int:
    t_grade()
    t_level()
    t_checks()
    t_lookahead()
    t_pick()
    t_static()
    t_stored()
    n, ok = len(RES), sum(RES)
    print(f"\nsetup_grade: {ok}/{n} " + ("ALL PASS" if ok == n else "FAILED"))
    return 0 if ok == n else 1


if __name__ == "__main__":
    raise SystemExit(main())
