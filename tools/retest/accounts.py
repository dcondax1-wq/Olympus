"""Stage 2: the walk-forward OOS stream of a stand-alone family put ON TOP of Zlarior + ATLAS in the repo's own one-account
simulator (tools/money/combo_account.py, unchanged: MFFU rules, engine sizing, one net position first-in, $1.90 + 1 tick,
6-month slots net of eval fees, day bootstrap). The candidate rides as bot "P" (lane: min($125 x plan, 30% room, day loss
left)). Spans: 2022-05..2025 (OOS starts 2022-05), 2026 H1, 2026 H2 (Jul-Oct 16).  PAPER ONLY.
    python -X utf8 tools/retest/accounts.py <family> [n_paths]      (family 'none' = the bases)
"""
import collections, json, os, sys, time
import numpy as np
HERE = os.path.dirname(os.path.abspath(__file__)); ROOT = os.path.dirname(os.path.dirname(HERE))
sys.path[:0] = [ROOT, os.path.join(ROOT, "tools"), os.path.join(ROOT, "tools", "money")]
import combo_account as CA
OUT = os.path.join(ROOT, "research", "retest")
CA.SPAN["REF"] = ("2022-05-02", "2025-12-31")
CA.ALL_SPANS["REF"] = CA.SPAN["REF"]


def oos_rows(fam):
    if fam.startswith("fixed="):                     # one pre-declared rule, every month (no selection at all)
        rid = fam.split("=", 1)[1]
        ms = sorted({d[:7] for d in CA.sessions()})
        pick = {m: rid for m in ms}
        fam = rid.rsplit(":", 1)[0] if ":" in rid else "stored"
    else:
        wf = json.load(open(os.path.join(OUT, "wf.json")))["families"][fam]
        pick = {m: k for (m, _), k in zip(wf["oos"], wf["picks"]) if k != "(no change)"}
    rows = []
    if ":" in fam:
        src = fam.split(":")[0]
        cells = json.load(open(os.path.join(OUT, f"cells_{src}.json")))
        for m, k in pick.items():
            for r in cells[k]:
                if r[0][:7] == m:
                    rows.append(r[:7])
    else:
        cache = {}
        for m, k in pick.items():
            if k not in cache:
                d = json.load(open(os.path.join(ROOT, "research", "runs", f"{k}.json")))
                tc = d["trade_cols"]; ix = {c: i for i, c in enumerate(tc)}
                cache[k] = []
                for t in d["trades"]:
                    q = t[ix["qty"]] if "qty" in ix else None
                    rp = t[ix["risk_pts"]] if "risk_pts" in ix else None
                    if not q or not rp or "entry_t" not in ix:
                        continue
                    pts = (t[ix["pnl"]] / q + CA.COMM) / CA.PV
                    mae = t[ix["mae"]] if "mae" in ix else None
                    w1 = -mae * rp if mae is not None else -rp          # unknown worst open: assume a full stop (harsher)
                    cache[k].append([t[0], t[ix["entry_t"]], t[ix["exit_t"]], t[ix["dir"]], rp, pts, min(0.0, w1, pts)])
            rows += [r for r in cache[k] if r[0][:7] == m]
    return rows


def write_trades(fam):
    d = json.load(open(CA.TRADES, encoding="utf-8"))
    cols = d["cols"]; ci = {c: i for i, c in enumerate(cols)}
    keep = [r for r in d["rows"] if r[ci["s"]] in ("Z", "A")]
    add = []
    if fam != "none":
        for day, et, xt, dr, risk, pts, w1 in oos_rows(fam):
            if not risk or risk <= 0:
                continue
            r = [None] * len(cols)
            for c, v in (("s", "P"), ("day", day), ("et", int(et)), ("xt", int(xt)), ("d", int(dr)), ("risk", float(risk)),
                         ("tgt", None), ("pts", float(pts)), ("w1", float(min(0.0, w1))), ("tf", 5), ("src", fam), ("lb", 1.0),
                         ("sm", 1.0), ("x", ""), ("n", None)):
                r[ci[c]] = v
            add.append(r)
    rows = sorted(keep + add, key=lambda r: (r[ci["day"]], r[ci["et"]], CA.PRIO[r[ci["s"]]]))
    p = os.path.join(OUT, f"_trades_{fam.replace(':', '_').replace('/', '_')}.json")
    json.dump({"cols": cols, "rows": rows}, open(p, "w"))
    return p, len(add)


ROWS_BASE = [("b50", "Z", "own"), ("b50", "Z+A", "own"), ("b25", "Z+A", "own"), ("r25", "Z+A", "lanes")]
ROWS_CAND = [("b50", "Z+P", "own"), ("b50", "Z+A+P", "own"), ("b25", "Z+A+P", "own"), ("r25", "Z+A+P", "lanes"),
             ("b25", "P", "own"), ("r25", "P", "own")]


def overlap(fam):
    """daily corr + same-day overlap of the OOS stream with Zlarior + ATLAS (fixed $250 a trade, real days)."""
    out = {}
    for sp in ("REF", "H1", "H2"):
        a, z = CA.span_ix(sp)
        D = CA.combo_days("Z+A+P")
        za, pp = [], []
        for si in range(a, z):
            za.append(sum(1 for t in D[si] if t["s"] in "ZA")); pp.append(sum(1 for t in D[si] if t["s"] == "P"))
        pz = CA.plain_stats("Z+A", sp); pq = CA.plain_stats("P", sp) if any(pp) else None
        both = sum(1 for x, y in zip(za, pp) if x and y)
        out[sp] = {"p_days": sum(1 for y in pp if y), "same_day_as_ZA": both, "P_plain": pq, "ZA_plain": pz}
    return out


def main(fam, n):
    p, k = write_trades(fam)
    CA.TRADES = p
    CA._D.clear()
    CA._patch_account_b()
    rows = ROWS_BASE if fam == "none" else ROWS_CAND
    res = {"family": fam, "p_trades": k, "n_paths": n, "rows": {}}
    t0 = time.time()
    for acct, combo, sz in rows:
        r = CA.R(acct, combo, sizing=sz)
        r["live"] = "live"
        o = CA.score_row(r, n=n)
        res["rows"][f"{acct}|{combo}|{sz}"] = {sp: {"slot": v["slot"], "funded": v["funded"], "net": v["_net"].round(1).tolist()}
                                              for sp, v in o.items()}
        print(acct, combo, sz, {sp: (v["slot"]["net_m"], v["slot"]["eval"]["pass_med"], v["slot"]["first_pay_med"]) for sp, v in o.items()},
              round(time.time() - t0), "s", flush=True)
    if fam != "none":
        res["overlap"] = overlap(fam)
    json.dump(res, open(os.path.join(OUT, f"acct_{fam.replace(':', '_').replace('/', '_')}.json"), "w"))


if __name__ == "__main__":
    main(sys.argv[1], int(sys.argv[2]) if len(sys.argv) > 2 else 600)
