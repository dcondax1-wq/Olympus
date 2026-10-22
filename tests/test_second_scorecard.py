"""Go / no-go scorecard of the second strategies and account B (engine/second_scorecard.py). Read-only, ~10 s.

    python -X utf8 -m tests.test_second_scorecard

 a. the bands (research/second/scorecard.json): built from the 2026 H2 / 2025 trades of research/second/*_best.json
    (pool sizes match), quantiles rise with p, a rebuild gives the same file (seeded);
 b. the math: percentile interpolation, cumulative R / win / PF of a ledger, open and duplicate trades ignored, the PC's
    finished trades merged without double counting;
 c. the verdicts on synthetic ledgers: none -> "collecting (0/20)", 3 trades -> collecting, 10 straight losers -> "below
    range: don't go live", 10 typical trades -> "on track (pXX)", 25 good trades -> "ready", 25 flat trades (p5-p10) ->
    still on track, a member strategy below its range blocks account B;
 d. the wiring: engine/second.dashboard_block carries the scorecard (data.json "second" / /api/next/second), the README
    section has it, secondcore.js (phone + PC copies byte-identical, node --check, rendered in node with a stub DOM).
"""
from __future__ import annotations

import json
import os
import shutil
import subprocess
import sys
import tempfile

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if ROOT not in sys.path:
    sys.path.insert(0, ROOT)

from engine import second  # noqa: E402
from engine import second_scorecard as SC  # noqa: E402

RESULTS = []


def check(name, ok, detail=None):
    RESULTS.append((name, bool(ok)))
    print(("PASS " if ok else "FAIL ") + name + ("" if ok or detail is None else f"\n     {str(detail)[:400]}"), flush=True)


def rows(rs, t0=1_790_000_000, usd=500.0):
    return [{"entry_t": t0 + 3600 * i, "exit_t": t0 + 3600 * i + 900, "exit_kind": "TARGET" if r > 0 else "STOP", "r": r,
             "usd": round(r * usd, 2), "day": "2026-11-02"} for i, r in enumerate(rs)]


def part_a():
    d = SC.load()
    check("a. research/second/scorecard.json exists with a band per strategy + account B",
          bool(d) and set(d["bands"]) == set(SC.KEYS) | {SC.ACCT_B}, None if not d else list(d["bands"]))
    for k, fn in SC.KEYS.items():
        T = json.load(open(os.path.join(ROOT, "research", "second", fn), encoding="utf-8"))["trades"]
        n2 = sum(1 for t in T if "2026-07-01" <= t["day"] <= "2026-12-31")
        n5 = sum(1 for t in T if "2025-01-01" <= t["day"] <= "2025-12-31")
        b = d["bands"][k]
        check(f"a. {k}: pools = its 2026 H2 ({n2}) and 2025 ({n5}) research trades",
              b["expected"]["n_pool"] == n2 and b["bad_year"]["n_pool"] == n5, (b["expected"]["n_pool"], b["bad_year"]["n_pool"]))
    nb = d["bands"][SC.ACCT_B]["expected"]["n_pool"]
    check("a. account B pools the three strategies", nb == sum(d["bands"][k]["expected"]["n_pool"] for k in SC.KEYS), nb)
    mono = all(all(q[i] <= q[i + 1] for i in range(len(q) - 1))
               for b in d["bands"].values() for sp in b.values() for x in sp["by_n"].values() for q in [x["cum_r_q"]])
    check("a. every stored quantile series rises with p", mono)
    tmp = tempfile.mkdtemp()
    try:
        p = os.path.join(tmp, "sc.json")
        SC.build(p)
        check("a. a rebuild gives the same bands (seeded bootstrap)", json.load(open(p))["bands"] == d["bands"])
    finally:
        shutil.rmtree(tmp, ignore_errors=True)


def part_b():
    q = list(range(0, 101, 5))
    check("b. percentile interpolation: at a stored quantile, between two, outside",
          SC._pct(q, 50) == 50 and abs(SC._pct(q, 52.5) - 52.5) < 1e-9 and SC._pct(q, -1) == 0 and SC._pct(q, 101) == 100)
    R = rows([1.5, -1.0, 2.0, -1.0, 0.5])
    R.append({**R[0]})                                                   # a duplicate
    R.append({"entry_t": 1, "exit_kind": "OPEN", "r": 3.0, "usd": 900})   # still open
    v = SC.verdict(SC.load()["bands"]["ema_lon_vix"], R)
    check("b. a ledger's n / cum R / win / PF / $ (open + duplicate ignored)",
          v["n"] == 5 and v["cum_r"] == 2.0 and v["win"] == 60.0 and v["pf"] == 2.0 and v["usd"] == 1000.0, v)
    led = rows([1.0, -1.0])
    pc = rows([1.0, -1.0, 2.0])                                           # same first two entry times + one new
    m = SC.merge_rows(led, pc)
    check("b. PC trades merged into the cloud ledger without double counting", len(SC.finished(m)) == 3, len(m))


def part_c():
    B = SC.load()["bands"]
    E = B["ema_lon_vix"]
    v = SC.verdict(E, [])
    check("c. no trades -> collecting (0/20)", v["kind"] == "collecting" and v["text"] == "collecting (0/20)", v["text"])
    v = SC.verdict(E, rows([2.0, -1.0, 1.0]))
    check("c. 3 trades -> collecting (3/20) (nothing judged under 5)", v["kind"] == "collecting" and v["text"] == "collecting (3/20)", v["text"])
    v = SC.verdict(E, rows([-1.0] * 10))
    check("c. 10 straight losers -> below range: don't go live", v["kind"] == "below" and v["text"] == "below range: don't go live", v)
    med10 = B["ema_lon_vix"]["expected"]["by_n"]["10"]["cum_r_q"][10]
    v = SC.verdict(E, rows([med10 / 10.0] * 10))
    check(f"c. 10 trades at the expected median ({med10:+.1f}R) -> on track (p~50)", v["kind"] == "on_track" and 40 <= v["pct"] <= 60
          and v["text"] == f"on track (p{v['pct']})", v)
    v = SC.verdict(E, rows([1.6, -1.0, 1.6, 1.2, -1.0] * 5))
    check("c. 25 good trades -> ready: 20+ trades inside the range", v["kind"] == "ready" and v["text"] == "ready: 20+ trades inside the range", v)
    q20 = B["ema_lon_vix"]["expected"]["by_n"]["20"]["cum_r_q"]
    mid = (q20[1] + q20[2]) / 2.0                                         # between p5 and p10 after 20 trades
    v = SC.verdict(E, rows([mid / 20.0] * 20))
    check("c. 20 trades between p5 and p10 -> still on track (not ready)", v["kind"] == "on_track", v)
    c = SC.card({"ema_lon_vix": rows([2.5, -1.0] * 12), "macd_sweep": rows([-1.0] * 8, t0=1_790_500_000), "sr_nyreclaim": []})
    check("c. MACD below its range blocks account B even when the pool looks fine",
          c["strategies"]["macd_sweep"]["kind"] == "below" and c["account_b"]["kind"] == "below"
          and "macd_sweep" in c["account_b"]["text"], c["account_b"]["text"])
    c = SC.card({"ema_lon_vix": rows([1.5, -1.0] * 12)}, bands={})
    check("c. no bands file -> collecting with a hint (never an error)", "no band" in c["strategies"]["ema_lon_vix"]["text"], c)


def part_d():
    led = {"ema_lon_vix": {"short": "EMA", "ledger": {str(t["entry_t"]): t for t in rows([1.5, -1.0, 2.0, -1.0, 1.0, 1.0])}}}
    b = second.dashboard_block({"first_run": 1_790_000_000, "t": 1_790_100_000, "strategies": led})
    e = next(s for s in b["strategies"] if s["key"] == "ema_lon_vix")
    check("d. dashboard_block: per strategy scorecard + the account B card + the rule",
          e["scorecard"]["n"] == 6 and b["scorecard"]["account_b"]["n"] == 6 and "Go live only after 20" in b["scorecard"]["rule"]
          and b["scorecard"]["source"].startswith("cloud paper ledger"), b.get("scorecard"))
    pc = {"t": 1_790_200_000, "strategies": {"macd_sweep": {"trades": rows([1.0, -1.0], t0=1_790_300_000)}}}
    b2 = second.dashboard_block({"first_run": 1_790_000_000, "t": 1_790_100_000, "strategies": led}, pc=pc)
    m = next(s for s in b2["strategies"] if s["key"] == "macd_sweep")
    check("d. the PC heartbeat's finished trades count when the cloud has not got them", m["scorecard"]["n"] == 2 and
          b2["scorecard"]["account_b"]["n"] == 8, (m["scorecard"]["n"], b2["scorecard"]["account_b"]["n"]))
    L = second.readme_lines({"first_run": 1_790_000_000, "t": 1_790_100_000, "strategies": led})
    txt = "\n".join(L)
    check("d. cloud README: 'Go / no-go scorecard' table with the verdicts", "### Go / no-go scorecard" in txt and "| EMA | 6 |" in txt
          and "Account B (EMA + MACD + S/R)" in txt, txt[-800:])
    a = os.path.join(ROOT, "tools", "web_public", "secondcore.js")
    p = os.path.join(ROOT, "web_next", "js", "next", "secondcore.js")
    check("d. secondcore.js: phone and PC copies byte-identical", open(a, "rb").read() == open(p, "rb").read())
    node = shutil.which("node")
    if not node:
        check("d. node available for the page checks", False, "node not found")
        return
    r = subprocess.run([node, "--check", a], capture_output=True, text=True)
    check("d. node --check secondcore.js", r.returncode == 0, r.stderr)
    for f in ("tools/web_public/second.js", "web_next/js/next/second.js"):
        fp = os.path.join(ROOT, f)
        if f.endswith("web_next/js/next/second.js"):
            tmp = tempfile.mkdtemp()
            try:
                g = os.path.join(tmp, "second.mjs")
                shutil.copy(fp, g)
                r = subprocess.run([node, "--check", g], capture_output=True, text=True)
            finally:
                shutil.rmtree(tmp, ignore_errors=True)
        else:
            r = subprocess.run([node, "--check", fp], capture_output=True, text=True)
        check(f"d. node --check {f}", r.returncode == 0, r.stderr)
    data = json.dumps(b2, default=str)
    js = ("const fs=require('fs');const window={};const document={head:{appendChild(){}},getElementById(){return null},"
          "createElement(){return {}}};global.window=window;global.document=document;"
          f"eval(fs.readFileSync({json.dumps(a)},'utf8'));const el={{innerHTML:''}};"
          f"window.SecondUI.render(el,{data},{{}});const h=el.innerHTML;"
          "const ok=h.includes('Scorecard: paper result vs the expected range')&&h.includes('Go / no-go')&&!h.includes('failed to draw');"
          "console.log(JSON.stringify({ok,v:window.SecondUI.version,len:h.length}));")
    r = subprocess.run([node, "-e", js], capture_output=True, text=True)
    try:
        o = json.loads(r.stdout.strip().splitlines()[-1])
    except Exception:
        o = {"ok": False, "err": r.stderr[-400:]}
    check("d. the page renders the scorecard (node, stub DOM; SecondUI v4)", o.get("ok") and o.get("v") == 4, o)
    idx = open(os.path.join(ROOT, "tools", "web_public", "index.html"), encoding="utf-8").read()
    sw = open(os.path.join(ROOT, "tools", "web_public", "sw.js"), encoding="utf-8").read()
    pcs = open(os.path.join(ROOT, "web_next", "js", "next", "second.js"), encoding="utf-8").read()
    check("d. phone loads secondcore.js?v=4, service worker cache bumped (le-public-v25), PC loads ?v=4",
          "secondcore.js?v=4" in idx and "le-public-v25" in sw and "secondcore.js?v=4" in pcs)


def main():
    part_a(); part_b(); part_c(); part_d()
    n = sum(1 for _, ok in RESULTS if ok)
    print(f"second scorecard: {n}/{len(RESULTS)} checks passed")
    sys.exit(0 if n == len(RESULTS) else 1)


if __name__ == "__main__":
    main()
