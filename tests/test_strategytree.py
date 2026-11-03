"""DAPHNE, the strategy-tree search (tools/strategytree): bound, search, look-ahead, determinism, JSON.

    python -X utf8 -m tests.test_strategytree          # ~30 s, real data for the look-ahead and JSON checks

 1. bound(S) equals the best score of any subset of S with min_n+ trades (brute force over every subset).
 2. With an unlimited budget the branch-and-bound finds the same best rule as trying every condition combination, and
    nothing it cut could have beaten that best.
 3. Determinism: the same search twice, and the whole quick build twice, give identical output.
 4. No look-ahead: scrambling every bar after the entry bar (NQ and ES) and every VIX close from the trade's day on
    changes neither the entry nor any condition of a trade.
 5. Root rules: fade stops sit 1 tick beyond the sweep extreme, costs are in, exits never come before the entry.
 6. The JSON: schema, a closed tree per featured root, size <= 1.5 MB, the Jarvis card contract; the module never
    touches the live configuration.
"""
from __future__ import annotations

import glob
import itertools
import json
import os
import sys
import tempfile

import numpy as np
import pandas as pd

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)
from engine import data as edata  # noqa: E402
from tools.strategytree import features as fx, report, roots as rx, search as sx, sessions  # noqa: E402

R = []
MAX_JSON_BYTES = 1_500_000


def check(name, ok, info=""):
    R.append(bool(ok))
    print(f"[{'PASS' if ok else 'FAIL'}] {name}{' - ' + str(info) if info else ''}")


def _score(vals, root_mean, k):
    return (np.mean(vals) - root_mean) * len(vals) / (len(vals) + k)


def test_bound_brute_force():
    rng = np.random.default_rng(7)
    worst = 0.0
    for _ in range(40):
        x = np.sort(rng.normal(0, 10, 11))[::-1]
        mask = rng.random(11) < 0.8
        root_mean, min_n, k = float(rng.normal()), 3, 4.0
        members = np.flatnonzero(mask)
        brute = max((_score(x[list(c)], root_mean, k) for m in range(min_n, len(members) + 1)
                     for c in itertools.combinations(members, m)), default=-np.inf)
        _, _, _, bound = sx.scores_and_bounds(x, mask[None, :], root_mean, min_n, k)
        worst = max(worst, abs(bound[0] - brute) if np.isfinite(brute) else 0.0)
    check("bound = best score of any min_n+ subset (40 random sets, brute force)", worst < 1e-9, f"max diff {worst:.2e}")


def _synthetic(n=90, seed=3):
    """Three features (ordered 4, plain 3, ordered 3) and values with a planted effect."""
    rng = np.random.default_rng(seed)
    feats = (fx.Feature("a", ("a0", "a1", "a2", "a3"), True, "a"), fx.Feature("b", ("b0", "b1", "b2"), False, "b"),
             fx.Feature("c", ("c0", "c1", "c2"), True, "c"))
    codes = np.column_stack([rng.integers(0, 4, n), rng.integers(0, 3, n), rng.integers(0, 3, n)])
    x = rng.normal(0, 20, n) + 15 * (codes[:, 0] >= 2) - 10 * (codes[:, 1] == 1)
    conds = fx.conditions(feats)
    return x, fx.condition_masks(codes, conds), np.array([c.feature for c in conds]), conds


def test_search_is_exact():
    x, masks, cfeat, conds = _synthetic()
    cfg = sx.SearchConfig(min_n=8, shrink_k=10.0, max_depth=3, max_expand=10**6)
    t = sx.search(x, masks, cfeat, cfg)
    best = 0.0
    for depth in (1, 2, 3):
        for combo in itertools.combinations(range(len(conds)), depth):
            if len({cfeat[c] for c in combo}) < depth:
                continue
            keep = np.logical_and.reduce([masks[c] for c in combo])
            if keep.sum() >= cfg.min_n:
                best = max(best, _score(x[keep], x.mean(), cfg.shrink_k))
    check("unlimited branch-and-bound = exhaustive best", abs(t.score[t.best] - best) < 1e-9,
          f"search {t.score[t.best]:.4f} vs brute {best:.4f}, {len(t) - 1} nodes")
    st = t.stats()
    cut_ok = all(t.bound[i] <= t.score[t.best] + 1e-9 for i, s in enumerate(t.status) if s == sx.CUT)
    check("every cut node's bound <= the final best; nothing left open", cut_ok and st["open"] == 0, st)
    keep = np.logical_and.reduce([masks[c] for c in t.conds_of(t.best)])
    check("the best node's stored n / mean match its conditions",
          keep.sum() == t.n[t.best] and abs(x[keep].mean() - t.mean[t.best]) < 1e-9)
    small = sx.search(x, masks, cfeat, sx.SearchConfig(min_n=8, shrink_k=10.0, max_depth=3, max_expand=5))
    check("a small budget leaves nodes OPEN and never beats the exact best",
          small.stats()["open"] > 0 and small.score[small.best] <= t.score[t.best] + 1e-9)


def test_search_deterministic():
    x, masks, cfeat, _ = _synthetic(seed=11)
    cfg = sx.SearchConfig(min_n=6, max_depth=4, max_expand=200)
    a, b = sx.search(x, masks, cfeat, cfg), sx.search(x, masks, cfeat, cfg)
    check("search twice -> identical trees", a.__dict__ == b.__dict__, f"{len(a)} nodes")


def _scrambled(m: sessions.Market, j: int, rng) -> sessions.Market:
    """A copy of the market with every NQ bar after bar j and every ES close after its time replaced by noise."""
    b = m.bars
    arr = {k: getattr(b, k).copy() for k in ("o", "h", "l", "c", "v")}
    tail = slice(j + 1, None)
    shift = rng.normal(0, 200, len(b) - j - 1)
    for k in ("o", "c"):
        arr[k][tail] += shift
    arr["h"][tail] = np.maximum(arr["o"][tail], arr["c"][tail]) + rng.random(len(b) - j - 1) * 50
    arr["l"][tail] = np.minimum(arr["o"][tail], arr["c"][tail]) - rng.random(len(b) - j - 1) * 50
    bars = edata.Bars(b.sym, b.tf, b.t, arr["o"], arr["h"], arr["l"], arr["c"], arr["v"], b.mod, b.tday, b.dow, b.date_str)
    t_j = int(b.t[j])
    es = {t: (c if t <= t_j else c + float(rng.normal(0, 80))) for t, c in m.es_close.items()}
    return sessions.Market(bars, m.days, es, m.es_open)


def test_no_lookahead():
    m = sessions.load_market()
    vix = pd.read_csv(os.path.join(edata.DATA_DIR, "VIX_1d.csv")).sort_values("date")
    edges = fx.train_edges(m.days)
    rng = np.random.default_rng(5)
    picks = [r for r in rx.all_roots() if r.target_r == 1.0 and r.horizon == 60][::3]
    bad, checked, with_es = [], 0, 0
    for root in picks:
        tr = rx.root_trades(m, root)
        if tr.empty:
            continue
        codes = fx.encode(m, tr, edges)
        late = np.flatnonzero(tr["date"].values >= "2025-04-15")        # ES data exists: the es condition is live
        early = np.flatnonzero(tr["date"].values < "2025-01-01")
        for k in (rng.choice(early), rng.choice(late)):
            t = tr.iloc[[k]]
            j, date = int(t["entry_i"].iloc[0]), t["date"].iloc[0]
            sm = _scrambled(m, j, rng)
            v2 = vix.copy()
            v2.loc[v2["date"] >= date, "close"] += rng.normal(0, 30, int((v2["date"] >= date).sum()))
            sm.days = sessions.build_days(sm.bars, v2)
            row = int(np.flatnonzero(sm.days["date"].values == date)[0])
            sig = rx.find_signal(sm, sm.days.iloc[row].to_dict(), root.level, root.mode)
            same_entry = sig is not None and sig[0] == j and abs(sig[1] - float(t["entry"].iloc[0])) < 1e-9 \
                and abs(sig[2] - float(t["stop"].iloc[0])) < 1e-9
            t2 = t.copy()
            t2["day_row"] = row
            same_codes = np.array_equal(fx.encode(sm, t2, edges)[0], codes[k])
            checked += 1
            with_es += int(codes[k][fx.F["es"]] >= 0)
            if not (same_entry and same_codes):
                bad.append(f"{root.id} {date}")
    check(f"no look-ahead: {checked} trades (half with ES data), the future scrambled (NQ, ES, VIX) -> same entry, "
          f"stop and conditions ({with_es} with an ES code)", checked >= 10 and with_es >= 3 and not bad, bad[:3])


def test_root_rules():
    m = sessions.load_market()
    b = m.bars
    ok_stop, ok_cost, ok_time, n = True, True, True, 0
    for root in (rx.Root("ORH", "fade", 1.0, 60), rx.Root("PDL", "fade", 2.0, 120)):
        tr = rx.root_trades(m, root)
        for t in tr.itertuples():
            n += 1
            row = m.days.iloc[t.day_row]
            mod = b.mod[int(row["a"]):int(row["z"])]
            i0 = int(row["a"] + np.flatnonzero((mod >= rx.FIRST_ENTRY_MOD) & (mod <= rx.LAST_ENTRY_MOD))[0])
            extreme = b.h[i0:t.entry_i + 1].max() if t.dir < 0 else b.l[i0:t.entry_i + 1].min()
            ok_stop &= abs(t.stop - (extreme - t.dir * rx.TICK)) < 1e-9
            ok_cost &= abs(t.pnl - ((t.exit - t.entry) * t.dir * rx.POINT_USD - rx.COST_RT)) < 1e-9
            ok_time &= t.exit_i > t.entry_i and b.mod[t.exit_i] <= rx.FLAT_MOD
    check(f"fade stops 1 tick beyond the sweep extreme ({n} trades)", ok_stop)
    check("P&L = points x $2 - $1.90 a micro", ok_cost)
    check("every exit comes after the entry and by the 15:55 flat", ok_time)


def _quick_doc(m):
    roots = [r for r in rx.all_roots() if r.level in ("ORH", "ORL")][:6]
    return report.build(m, sx.SearchConfig(min_n=50, max_expand=60), roots, placebos=1)


def test_build_and_json():
    m = sessions.load_market()
    a, b = _quick_doc(m), _quick_doc(m)
    strip = lambda d: json.dumps({k: v for k, v in d.items() if not k.startswith("_") and k != "meta"}, sort_keys=True)
    check("quick build twice -> identical JSON", strip(a) == strip(b))
    tmp = tempfile.mkdtemp(prefix="daphne_")
    try:
        path = report.write(a, tmp, page_json=None)
        doc = json.load(open(path, encoding="utf-8"))
    finally:
        for f in glob.glob(os.path.join(tmp, "*")):
            os.remove(f)
        os.rmdir(tmp)
    need = {"v", "meta", "features", "conds", "node_cols", "status_names", "roots", "trees", "top", "honesty"}
    check("schema: top-level keys", need <= set(doc), sorted(need - set(doc)))
    cols = doc["node_cols"]
    closed = True
    for rows in doc["trees"].values():
        ids = {r[0] for r in rows}
        closed &= all(len(r) == len(cols) for r in rows) and all(r[1] in ids or r[1] == -1 for r in rows)
        closed &= sum(r[cols.index("best")] for r in rows) >= 1
    check("every featured tree is closed (each node's parent is in the sample) and holds its best path",
          closed and len(doc["trees"]) >= 1)
    card = doc["top"][0]
    fields = {"key", "steps", "text", "train", "test", "y2026", "holds"}
    money_ok = all({"mean", "win", "tpw", "mo_1", "mo_bot"} <= set(card[p]) for p in ("train",) if card[p]["n"])
    check("top rule card: plain text, steps, train/test/2026 money", fields <= set(card) and money_ok, card["text"][:80])
    h = doc["honesty"]
    check("honesty: nodes searched, best rules, how many hold, a placebo",
          h["real"]["nodes"] > 0 and h["real"]["best_rules"] >= h["real"]["hold"] and len(h["placebo"]) == 1)
    card = report.jarvis_card(a, now=1793700000)
    text = json.dumps(card)
    fits = (card["v"] == 1 and len(card["name"]) <= 40 and card["status"]["level"] in ("ok", "warn", "bad", "off")
            and len(card["status"]["label"]) <= 48 and len(card["kpis"]) <= 3 and len(card["lines"]) <= 3
            and all(len(k["label"]) <= 20 and len(str(k["value"])) <= 24 for k in card["kpis"])
            and all(len(x) <= 120 and "<" not in x and "&" not in x for x in card["lines"])
            and card["theme"].startswith("#") and len(card["theme"]) == 7 and len(text.encode()) <= 8192)
    check("jarvis.json follows the contract (docs/JARVIS_APPS.md)", fits, card["status"]["label"])
    test_page_core(doc)
    real_json = os.path.join(report.OUT_DIR, "tree.json")
    if os.path.exists(real_json):
        size = os.path.getsize(real_json)
        check("research/strategytree/tree.json <= 1.5 MB", size <= MAX_JSON_BYTES, f"{size / 1e6:.2f} MB")
        page = report.PAGE_JSON
        check("the page's tree.json is the same file", os.path.exists(page) and open(page, "rb").read() ==
              open(real_json, "rb").read())


CORE_CHECK = """
import * as C from '%s';
const doc = JSON.parse(process.argv[1]);
const m = C.readDoc(doc);
const out = {featured: m.featured.length, trees: 0, inRange: true, parentsFirst: true, best: true};
for (const id of m.featured) {
  const L = C.layoutTree(m.trees[id]);
  out.trees++;
  const seen = new Set();
  for (const n of L.nodes) {
    out.inRange &&= n.u >= -1 && n.u <= 1 && n.r >= 0 && n.r <= 1;
    out.parentsFirst &&= n.parent < 0 || seen.has(n.parent);
    seen.add(n.id);
  }
  out.best &&= L.bestPath.length >= 1 && L.bestPath[0].id === L.root.id;
}
out.fmt = [C.usd(12.3), C.usd(-4.1), C.usd(null), C.money(-1234.4)];
console.log(JSON.stringify(out));
"""


def test_page_core(doc: dict):
    """The page's core.js on the built JSON: every featured tree lays out inside the fan, parents before children, the
    best path starts at the root, and the money formats."""
    import shutil
    import subprocess
    if not shutil.which("node"):
        check("page core.js (node not installed: skipped)", True)
        return
    core = os.path.join(ROOT, "tools", "web_public", "tree", "core.js")
    script = CORE_CHECK % ("file://" + core)
    res = subprocess.run(["node", "--input-type=module", "-e", script, json.dumps(doc)], capture_output=True, text=True,
                         timeout=60)
    try:
        out = json.loads(res.stdout.strip().splitlines()[-1])
    except (IndexError, ValueError):
        check("page core.js runs", False, res.stderr[-300:])
        return
    check("page core.js: every featured tree laid out in the fan, parents first, best path from the root",
          out["trees"] == out["featured"] >= 1 and out["inRange"] and out["parentsFirst"] and out["best"], out)
    check("page core.js: money formats", out["fmt"] == ["+$12.30", "\u2212$4.10", "\u2014", "\u2212$1,234"], out["fmt"])


def test_demo_fixture():
    """The page's demo.json: synthetic, marked demo, the same schema as the real file, and current with demo.py."""
    from tools.strategytree import demo
    doc = demo.demo_doc()
    keys = {"v", "meta", "features", "conds", "node_cols", "status_names", "roots", "trees", "top", "honesty"}
    on_disk = json.load(open(demo.DEMO_JSON, encoding="utf-8")) if os.path.exists(demo.DEMO_JSON) else {}
    check("demo fixture: marked demo, real schema, demo.json on disk = demo.py output",
          doc["meta"]["demo"] and keys <= set(doc) and on_disk == json.loads(json.dumps(doc)),
          "rerun python -X utf8 -m tools.strategytree.demo" if on_disk != json.loads(json.dumps(doc)) else "")


def test_paper_only():
    src = "".join(open(p, encoding="utf-8").read() for p in glob.glob(os.path.join(ROOT, "tools", "strategytree", "*.py")))
    check("tools/strategytree never names live_model*.json or imports engine trading code",
          "live_model" not in src and "engine.live" not in src and "ninjatrader" not in src.lower())


def main():
    test_bound_brute_force()
    test_search_is_exact()
    test_search_deterministic()
    test_root_rules()
    test_no_lookahead()
    test_build_and_json()
    test_demo_fixture()
    test_paper_only()
    print(f"strategytree: {sum(R)}/{len(R)} {'ALL PASS' if all(R) else 'FAIL'}")
    return 0 if all(R) else 1


if __name__ == "__main__":
    sys.exit(main())
